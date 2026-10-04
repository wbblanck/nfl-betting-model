"""S1 live tracker dashboard (docs/s1_live_rules.md): one HTML page built only from the committed tracker files.

Inputs (data/live/): s1_record_2026.csv (official picks with results), s1_picks_2026.csv (every run's picks),
s1_runs_2026.csv (every run's games), injuries/ and depth/ (one archived ESPN response per run).
Every figure is recomputed here from those files; nothing is carried over by hand except the 2025 reference line
and the pass rule, which are quoted from docs/simulator_confirm.md.
"""
from __future__ import annotations

import datetime as dt
import html
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

from nflbet import config, live as Lv

ET = ZoneInfo("America/New_York")
SEASON = 2026
OUT = config.ROOT / "docs" / "s1_dashboard.html"
REPO = "https://github.com/wbblanck/nfl-betting-model/blob/main/"
REF = {"w": 38, "l": 23, "roi": 0.052, "lo": -0.163, "hi": 0.269}      # 2025, docs/simulator_confirm.md
PASS_N, PASS_WEEKS = 30, 10                                            # 2026 decision rule, same file
MARKET = {"rec": "Receptions", "rec_yds": "Receiving yds", "rush_att": "Rush attempts", "rush_yds": "Rush yds",
          "rush_rec_yds": "Rush + rec yds", "pass_att": "Pass attempts", "pass_cmp": "Completions",
          "pass_yds": "Passing yds", "pass_rush_yds": "Pass + rush yds"}
EMPTY_TEXT = ["start_time", "home", "away", "an_game_id", "player", "team", "market", "side", "result", "actual",
              "inj_self", "inj_teammates", "inj_against", "depth_note", "depth_against"]
RESULT_ICON = {"W": "✓", "L": "✕", "P": "–", "void": "∅", "pending": "…"}


# ------------------------------------------------------------------------------------------------ loading

def _read(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema_length=0) if path.exists() and path.stat().st_size else pl.DataFrame()


def load(live: Path | None = None) -> dict:
    live = live or Lv.LIVE
    rec = _read(live / f"s1_record_{SEASON}.csv")
    picks = _read(live / f"s1_picks_{SEASON}.csv")
    runs = _read(live / f"s1_runs_{SEASON}.csv")
    if not rec.height:
        rec = pl.DataFrame(schema={**{c: pl.Utf8 for c in EMPTY_TEXT}, "week": pl.Int64, "line": pl.Float64, "odds": pl.Float64,
                                   "p_sim": pl.Float64, "p_over_dk": pl.Float64, "proj": pl.Float64, "units": pl.Float64})
    else:
        rec = rec.with_columns(pl.col("week").cast(pl.Int64), pl.col("line").cast(pl.Float64), pl.col("odds").cast(pl.Float64),
                               pl.col("p_sim").cast(pl.Float64), pl.col("p_over_dk").cast(pl.Float64),
                               pl.col("proj").cast(pl.Float64), pl.col("units").cast(pl.Float64))
    return {"rec": rec, "picks": picks, "runs": runs, "live": live}


# ------------------------------------------------------------------------------------------------ numbers

def break_even(odds: float) -> float:
    return -odds / (-odds + 100) if odds < 0 else 100 / (odds + 100)


def with_probs(rec: pl.DataFrame) -> pl.DataFrame:
    """break-even (price incl. vig), market (DraftKings de-vigged) and model win probability for the side taken.
    p_sim and p_over_dk are P(over); a push has probability zero on the half-point lines S1 prices."""
    under = pl.col("side") == "under"
    return rec.with_columns(
        pl.col("odds").map_elements(break_even, return_dtype=pl.Float64).alias("be"),
        pl.when(under).then(1 - pl.col("p_over_dk")).otherwise(pl.col("p_over_dk")).alias("p_mkt"),
        pl.when(under).then(1 - pl.col("p_sim")).otherwise(pl.col("p_sim")).alias("p_model"))


def summarize(d: pl.DataFrame) -> dict:
    """W-L-P, void, pending, win %, units, ROI and mean break-even of the graded picks."""
    if not d.height:
        return {"W": 0, "L": 0, "P": 0, "void": 0, "pending": 0, "n": 0, "win": None, "units": 0.0, "roi": None, "be": None}
    c = {k: int((d["result"] == k).sum()) for k in ("W", "L", "P", "void", "pending")}
    n = c["W"] + c["L"]
    units = float(d["units"].sum())
    graded = d.filter(pl.col("result").is_in(["W", "L"]))
    return {**c, "n": n, "win": c["W"] / n if n else None, "units": units, "roi": units / n if n else None,
            "be": float(graded["be"].mean()) if n else None}


def week_ci(d: pl.DataFrame, reps: int = 4000, seed: int = 7) -> tuple[float, float] | None:
    """Week-clustered bootstrap 95% interval for ROI (resample weeks), shown only as an interim description."""
    import random

    g = d.filter(pl.col("result").is_in(["W", "L"]))
    if g.select(pl.col("week").n_unique()).item() < 3:
        return None
    by = {w: (float(x["units"].sum()), x.height) for (w,), x in g.group_by("week")}
    weeks = list(by)
    rng = random.Random(seed)
    out = []
    for _ in range(reps):
        s = [by[rng.choice(weeks)] for _ in weeks]
        n = sum(x[1] for x in s)
        out.append(sum(x[0] for x in s) / n)
    out.sort()
    return out[int(0.025 * reps)], out[int(0.975 * reps) - 1]


def to_et(ts: str) -> dt.datetime:
    return Lv.parse_ts(ts).astimezone(ET)


def fmt_dt(ts: str) -> str:
    t = to_et(ts)
    return f"{t:%a} {t.hour % 12 or 12}:{t:%M} {'AM' if t.hour < 12 else 'PM'}"


def fmt_pct(x, digits=0, sign=False) -> str:
    return "–" if x is None else f"{x * 100:{'+' if sign else ''}.{digits}f}%"


def fmt_units(x: float) -> str:
    return f"{x:+.2f}"


# ------------------------------------------------------------------------------------------------ changes between runs

def changes(picks: pl.DataFrame, runs: pl.DataFrame, week: int, now: dt.datetime) -> list[dict]:
    """For each pick that appeared in any run of `week`: runs it was in, first and latest price, and whether the
    game's deciding run (last run before kickoff, else the latest) kept it."""
    if not picks.height or not runs.height:
        return []
    p = picks.filter(pl.col("week") == str(week))
    r = runs.filter(pl.col("week") == str(week))
    out = []
    for (gid,), g in r.group_by("an_game_id"):
        start = g["start_time"][0]
        run_times = sorted(g["run_utc"].to_list())
        before = [t for t in run_times if Lv.parse_ts(t) < Lv.parse_ts(start)]
        decide = before[-1] if before else run_times[-1]
        gp = p.filter(pl.col("an_game_id") == gid)
        for key, x in gp.group_by(["player_id", "market", "side"], maintain_order=True):
            x = x.sort("run_utc")
            kept = decide in x["run_utc"].to_list()
            seen = [t for t in x["run_utc"].to_list() if t in before or not before]
            last = x.filter(pl.col("run_utc") == (decide if kept else x["run_utc"][-1]))
            out.append({"game": f"{g['away'][0]}@{g['home'][0]}", "start": start, "player": x["player"][0],
                        "market": key[1], "side": key[2], "line_first": float(x["line"][0]), "line_last": float(last["line"][0]),
                        "odds_first": float(x["odds"][0]), "odds_last": float(last["odds"][0]),
                        "n_seen": len(set(seen)), "n_runs": len(before) or len(run_times), "kept": kept})
    return sorted(out, key=lambda c: (c["start"], c["player"]))


def run_log(picks: pl.DataFrame, runs: pl.DataFrame, live: Path) -> list[dict]:
    """One row per run: when, games scored, props scored, picks, minutes to the next kickoff, and whether the
    ESPN injury and depth-chart responses were archived for it (flags exist from 2026-10-03)."""
    if not runs.height:
        return []
    out = []
    for (t,), g in runs.group_by("run_utc"):
        when = Lv.parse_ts(t)
        stamp = when.strftime("%Y%m%dT%H%MZ")
        wk = g["week"][0]
        ahead = [Lv.parse_ts(s) for s in g["start_time"].to_list() if Lv.parse_ts(s) > when]
        out.append({"run": t, "games": g.height, "props": int(g["props_scored"].cast(pl.Int64).sum()),
                    "picks": int(picks.filter(pl.col("run_utc") == t).height) if picks.height else 0,
                    "lead": (min(ahead) - when).total_seconds() / 60 if ahead else None,
                    "inj": (live / "injuries" / f"{stamp}_w{wk}.json.gz").exists(),
                    "depth": (live / "depth" / f"{stamp}_w{wk}.json.gz").exists(),
                    "flags_era": when >= dt.datetime(2026, 10, 3, tzinfo=dt.timezone.utc)})
    return sorted(out, key=lambda r: r["run"], reverse=True)


# ------------------------------------------------------------------------------------------------ html pieces

def esc(x) -> str:
    return html.escape(str(x), quote=True)


def chip(kind: str, text: str, title: str = "") -> str:
    return f'<span class="chip {kind}"' + (f' title="{esc(title)}"' if title else "") + f">{esc(text)}</span>"


def pick_row(r: dict, locked: bool) -> str:
    flags = []
    if r.get("inj_against") == "true":
        flags.append(chip("flag", "Injury news against"))
    if r.get("depth_against") == "true":
        flags.append(chip("flag", "Depth chart against"))
    detail = "; ".join(x for x in (f"{r['player']}: {r['inj_self']}" if r.get("inj_self") and r["inj_self"] != "fetch failed" else "",
                                    r.get("inj_teammates") or "", r.get("depth_note") or "") if x)
    if r.get("inj_self") == "fetch failed" or r.get("depth_note") == "fetch failed":
        flags.append(chip("warn", "Flag fetch failed"))
    against = "1" if r.get("inj_against") == "true" or r.get("depth_against") == "true" else "0"
    res = r["result"]
    rc = {"W": "win", "L": "loss"}.get(res, "idle")
    return (
        f'<li class="pick" data-against="{against}">'
        f'<div class="who"><span class="name">{esc(r["player"])}</span><span class="team">{esc(r["team"])}</span></div>'
        f'<div class="bet"><span class="side {esc(r["side"])}">{esc(r["side"])}</span> '
        f'<span class="line">{r["line"]:g}</span> <span class="mkt">{esc(MARKET.get(r["market"], r["market"]))}</span></div>'
        f'<div class="price">{r["odds"]:+.0f}</div>'
        f'<div class="probs" title="Break-even for this price, DraftKings de-vigged, model">'
        f'<span>{fmt_pct(r["be"])}</span><span>{fmt_pct(r["p_mkt"])}</span><span>{fmt_pct(r["p_model"])}</span></div>'
        f'<div class="res">{chip(rc, (RESULT_ICON.get(res, res) + " " + res) if res != "pending" else ("Locked" if locked else "Open"), "")}'
        + (f'<span class="actual">actual {float(r["actual"]):g}</span>' if r.get("actual") not in (None, "") else "")
        + "</div>"
        + (f'<div class="news">{"".join(flags)}<span class="detail">{esc(detail)}</span></div>' if flags or detail else "")
        + "</li>")


def game_block(g: dict, rows: list[dict], now: dt.datetime) -> str:
    start = Lv.parse_ts(g["start_time"])
    locked = start <= now
    graded = [r for r in rows if r["result"] in ("W", "L", "P", "void")]
    state = ("final" if rows and len(graded) == len(rows) else "locked") if locked else "open"
    label = {"open": "Open", "locked": "Kicked off", "final": "Final"}[state]
    if locked and not rows:
        label = "Kicked off, no picks"
    body = "".join(pick_row(r, locked) for r in rows) if rows else '<li class="none">No pick met all four signals at the deciding run.</li>'
    return (f'<section class="game {state}"><header><h3>{esc(g["away"])} <span class="at">at</span> {esc(g["home"])}</h3>'
            f'<span class="ko">{fmt_dt(g["start_time"])} ET</span>{chip("state " + state, label, "Open games can still change their picks until kickoff" if state == "open" else "")}</header>'
            f'<ul class="picks">{body}</ul></section>')


def scale(vals: list[float], lo: float, hi: float, a: float, b: float):
    return lambda v: a + (v - lo) / (hi - lo) * (b - a)


def chart_edge(rows: list[dict]) -> str:
    """Dumbbell per pick: break-even for the price (hollow) to the model's win probability (filled), market tick."""
    if not rows:
        return '<p class="empty">No picks to plot yet.</p>'
    rows = sorted(rows, key=lambda r: r["p_model"] - r["be"], reverse=True)
    lo, hi = 0.30, 1.0
    left, right, top, rh = 132, 20, 26, 22
    w, h = 520, top + rh * len(rows) + 30
    x = scale([], lo, hi, left, w - right)
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Model win probability against break-even, one row per pick">']
    for t in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        out.append(f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 8}" y2="{h - 26}"/>'
                   f'<text class="tick" x="{x(t):.1f}" y="{h - 8}" text-anchor="middle">{t * 100:.0f}%</text>')
    for i, r in enumerate(rows):
        y = top + rh * i + rh / 2
        name = f'{r["player"].split()[-1][:10]} {r["side"][0].upper()}{r["line"]:g} {MARKET.get(r["market"], r["market"]).split()[0][:4]}'
        out.append(f'<text class="rowl" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{esc(name)}</text>'
                   f'<line class="gap" x1="{x(r["be"]):.1f}" x2="{x(r["p_model"]):.1f}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<circle class="be" cx="{x(r["be"]):.1f}" cy="{y:.1f}" r="4.5"/>'
                   f'<rect class="mk" x="{x(r["p_mkt"]) - 1.5:.1f}" y="{y - 6:.1f}" width="3" height="12" rx="1"/>'
                   f'<circle class="md" cx="{x(r["p_model"]):.1f}" cy="{y:.1f}" r="4.5"/>')
    out.append("</svg>")
    return "".join(out)


def chart_units(d: pl.DataFrame) -> str:
    """Cumulative units over graded picks in kickoff order."""
    g = d.filter(pl.col("result").is_in(["W", "L"])).sort("start_time", "player")
    if not g.height:
        return ('<p class="empty">Nothing is graded yet. The first results appear after the early games on '
                'Sunday; the cumulative line starts then.</p>')
    cum, s = [], 0.0
    for u in g["units"].to_list():
        s += u
        cum.append(s)
    w, h, l, r_, t, b = 520, 220, 44, 20, 16, 30
    lo, hi = min(0.0, min(cum)) - 0.5, max(0.0, max(cum)) + 0.5
    xs = scale([], 0, max(len(cum) - 1, 1), l, w - r_)
    ys = scale([], lo, hi, h - b, t)
    pts = " ".join(f"{xs(i):.1f},{ys(v):.1f}" for i, v in enumerate(cum))
    step = max(1, math.ceil((hi - lo) / 5))
    ticks = [v for v in range(math.floor(lo), math.ceil(hi) + 1) if v % step == 0]
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Cumulative units after each graded pick">']
    for v in ticks:
        out.append(f'<line class="{"zero" if v == 0 else "grid"}" x1="{l}" x2="{w - r_}" y1="{ys(v):.1f}" y2="{ys(v):.1f}"/>'
                   f'<text class="tick" x="{l - 6}" y="{ys(v) + 4:.1f}" text-anchor="end">{v:+d}</text>')
    out.append(f'<polygon class="area" points="{xs(0):.1f},{ys(0):.1f} {pts} {xs(len(cum) - 1):.1f},{ys(0):.1f}"/>'
               f'<polyline class="ln" points="{pts}"/>'
               f'<circle class="end" cx="{xs(len(cum) - 1):.1f}" cy="{ys(cum[-1]):.1f}" r="4.5"/>'
               f'<text class="endl" x="{xs(len(cum) - 1) - 8:.1f}" y="{ys(cum[-1]) - 9:.1f}" text-anchor="end">{cum[-1]:+.2f} units</text>'
               f'<text class="tick" x="{w - r_}" y="{h - 8}" text-anchor="end">graded picks, in kickoff order</text></svg>')
    return "".join(out)


def table(head: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def breakdown(d: pl.DataFrame, by: str | None, groups: list[tuple[str, pl.DataFrame]]) -> str:
    rows = []
    for name, x in groups:
        s = summarize(x)
        rows.append([esc(name), f'{s["W"]}-{s["L"]}-{s["P"]}', str(s["pending"]), fmt_pct(s["win"]), fmt_pct(s["be"]),
                     fmt_units(s["units"]) if s["n"] else "–", fmt_pct(s["roi"], 1, True)])
    return table(["", "W-L-P", "Open", "Win", "BE", "Units", "ROI"], rows, "num")


# ------------------------------------------------------------------------------------------------ page

CSS = """
:root{
  /* Layout: a scoreboard header, then the current week game by game, then the evidence tables. Numbers set in a
     plex mono, labels in barlow condensed (stadium-board lettering), body in barlow. */
  --bg:#eaeef2;--surface:#fafbfc;--raised:#ffffff;--ink:#121c26;--ink2:#46535f;--muted:#6f7c88;--line:#d6dde4;
  --accent:#1d5f9e;--accent-soft:#dbe8f5;--good:#0b6b0b;--good-bg:#d9f0d6;--bad:#b02a2a;--bad-bg:#f8dcdc;
  --warn-bg:#fde7b0;--warn-ink:#4d3500;--idle-bg:#e6ebf0;--shadow:0 1px 0 rgba(18,28,38,.06);
  --display:'Barlow Condensed','Arial Narrow',sans-serif;--body:'Barlow',system-ui,sans-serif;--mono:'IBM Plex Mono',ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0e1318;--surface:#161c23;--raised:#1b222a;--ink:#e9eef3;--ink2:#b3beca;--muted:#8793a0;--line:#27313b;
  --accent:#5aa4ec;--accent-soft:#1c3550;--good:#5fd35f;--good-bg:#17341a;--bad:#ff8a8a;--bad-bg:#3d1c1c;
  --warn-bg:#4a3a10;--warn-ink:#ffdf91;--idle-bg:#222b34;--shadow:none;color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0e1318;--surface:#161c23;--raised:#1b222a;--ink:#e9eef3;--ink2:#b3beca;--muted:#8793a0;--line:#27313b;
  --accent:#5aa4ec;--accent-soft:#1c3550;--good:#5fd35f;--good-bg:#17341a;--bad:#ff8a8a;--bad-bg:#3d1c1c;
  --warn-bg:#4a3a10;--warn-ink:#ffdf91;--idle-bg:#222b34;--shadow:none;color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:15px/1.45 var(--body);margin:0;padding-inline:16px;padding-block:20px 48px}
.wrap{max-width:1040px;margin:0 auto;display:flex;flex-direction:column;gap:22px}
h1,h2,h3{font-family:var(--display);margin:0;font-weight:600;letter-spacing:.01em;text-wrap:balance}
h1{font-size:34px;line-height:1.05}h2{font-size:22px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink2)}
h3{font-size:21px}
a{color:var(--accent)}
.top{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:8px 20px}
.sub{color:var(--ink2);margin:4px 0 0}.stamp{font:12px var(--mono);color:var(--muted);text-align:right}
.notice{background:var(--warn-bg);color:var(--warn-ink);padding:10px 14px;border-radius:6px;font-size:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:10px 14px;box-shadow:var(--shadow);min-width:0}
.tile .k{font:600 13px var(--display);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.tile .v{font:600 34px/1.1 var(--display);font-variant-numeric:tabular-nums}
.tile .s{font:12px var(--mono);color:var(--ink2)}
.bar{height:6px;background:var(--idle-bg);border-radius:3px;overflow:hidden;margin-top:6px}
.bar i{display:block;height:100%;background:var(--accent)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px;min-width:0}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,470px),1fr));gap:14px}
.cols.charts{grid-template-columns:repeat(auto-fit,minmax(min(100%,560px),1fr))}
.card h2{margin-bottom:8px}.note{color:var(--muted);font-size:13px;margin:6px 0 0}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12.5px;color:var(--ink2);margin-bottom:6px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:-1px}
.legend .k1{border:2px solid var(--ink2)}.legend .k2{background:var(--accent)}.legend .k3{width:3px;border-radius:1px;height:12px;background:var(--muted)}
.chart{width:100%;height:auto;display:block}
.chart .grid{stroke:var(--line);stroke-width:1}.chart .zero{stroke:var(--muted);stroke-width:1.2}
.chart .tick,.chart .rowl{fill:var(--muted);font:11.5px var(--mono)}.chart .rowl{fill:var(--ink2)}
.chart .gap{stroke:var(--accent);stroke-width:2;opacity:.45}.chart .be{fill:var(--surface);stroke:var(--ink2);stroke-width:2}
.chart .md{fill:var(--accent)}.chart .mk{fill:var(--muted)}
.chart .ln{fill:none;stroke:var(--accent);stroke-width:2;stroke-linejoin:round}.chart .area{fill:var(--accent);opacity:.12}
.chart .end{fill:var(--accent);stroke:var(--surface);stroke-width:2}.chart .endl{fill:var(--ink);font:600 12px var(--mono)}
.empty{color:var(--muted);margin:8px 0}
.weekhead{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between}
.filters{display:flex;gap:6px}
.filters button{font:600 13px var(--display);letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);
  background:var(--surface);color:var(--ink2);padding:5px 12px;border-radius:5px;cursor:pointer}
.filters button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.filters button:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.games{display:flex;flex-direction:column;gap:12px}
.game{background:var(--surface);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.game>header{display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;padding:10px 14px;background:var(--raised);border-bottom:1px solid var(--line)}
.game .at{color:var(--muted);font-size:15px;font-weight:500}.ko{font:12px var(--mono);color:var(--ink2);margin-left:auto}
.picks{list-style:none;margin:0;padding:0}
.pick{display:grid;grid-template-columns:minmax(150px,1.3fr) minmax(190px,1.4fr) 56px 150px 96px;gap:4px 14px;align-items:center;
  padding:9px 14px;border-top:1px solid var(--line)}
.pick:first-child{border-top:0}
.pick .name{font-weight:600}.pick .team{color:var(--muted);font:12px var(--mono);margin-left:8px}
.side{font:600 13px var(--display);letter-spacing:.06em;text-transform:uppercase;padding:1px 7px;border-radius:3px;border:1px solid var(--line)}
.side.over{color:var(--accent);border-color:var(--accent)}.side.under{color:var(--ink2)}
.line{font:500 15px var(--mono)}.mkt{color:var(--ink2)}
.price{font:500 14px var(--mono);text-align:right}
.probs{display:grid;grid-template-columns:repeat(3,1fr);font:12.5px var(--mono);color:var(--ink2);text-align:right}
.probs span:last-child{color:var(--accent);font-weight:500}
.res{display:flex;flex-direction:column;align-items:flex-end;gap:2px}.actual{font:11px var(--mono);color:var(--muted)}
.news{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:4px 8px;align-items:baseline}
.detail{color:var(--ink2);font-size:13px}
.none{padding:12px 14px;color:var(--muted)}
.game.quiet .nopick{list-style:none;margin:0;padding:8px 14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:2px 18px}
.nopick li{display:flex;justify-content:space-between;gap:8px;color:var(--ink2);font-size:14px}.game.quiet .note{padding:0 14px 10px;margin:0}
.game.quiet h3{color:var(--ink2)}
.chip{display:inline-block;font:600 12px var(--display);letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:3px;white-space:nowrap}
.chip.win{background:var(--good-bg);color:var(--good)}.chip.loss{background:var(--bad-bg);color:var(--bad)}
.chip.idle{background:var(--idle-bg);color:var(--ink2)}.chip.flag,.chip.warn{background:var(--warn-bg);color:var(--warn-ink)}
.chip.state{background:var(--idle-bg);color:var(--ink2)}.chip.state.open{background:var(--accent-soft);color:var(--accent)}
.colhead{display:grid;grid-template-columns:minmax(150px,1.3fr) minmax(190px,1.4fr) 56px 150px 96px;gap:14px;padding:0 14px;
  font:600 12px var(--display);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.colhead .p{display:grid;grid-template-columns:repeat(3,1fr);text-align:right}.colhead .r{text-align:right}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th{font:600 12px var(--display);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}
table.num td:not(:first-child),table.num th:not(:first-child){text-align:right;font-family:var(--mono);font-size:13px}
table td.up{color:var(--ink2)}
details.old{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:10px 14px}
summary{cursor:pointer;font:600 18px var(--display);letter-spacing:.04em}
.foot{color:var(--muted);font-size:13px;display:flex;flex-direction:column;gap:6px}
.foot ul{margin:0;padding-left:18px}
@media (max-width:760px){
  .colhead{display:none}
  .pick{grid-template-columns:1fr auto;grid-template-areas:"who price" "bet res" "probs probs"}
  .pick .who{grid-area:who}.pick .bet{grid-area:bet}.pick .price{grid-area:price}.pick .probs{grid-area:probs;text-align:left}
  .pick .res{grid-area:res;align-items:flex-end}.probs{max-width:280px}
  .probs span:nth-child(1)::before{content:"BE ";color:var(--muted)}.probs span:nth-child(2)::before{content:"Mkt ";color:var(--muted)}
  .probs span:nth-child(3)::before{content:"Model ";color:var(--muted)}.probs{text-align:left}
  .ko{margin-left:0}.stamp{text-align:left}
}
@media (prefers-reduced-motion:no-preference){.bar i{transition:width .4s}}
"""

JS = """
(function(){
  var bs=document.querySelectorAll('.filters button');
  function apply(mode){
    document.querySelectorAll('.pick').forEach(function(p){
      var a=p.getAttribute('data-against')==='1';
      p.hidden=(mode==='flagged'&&!a)||(mode==='clear'&&a);
    });
    document.querySelectorAll('.game:not(.quiet)').forEach(function(g){
      g.hidden=!g.querySelector('.pick:not([hidden])');
    });
    var q=document.querySelector('.game.quiet');if(q)q.hidden=mode==='flagged';
    bs.forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-mode')===mode?'true':'false')});
    try{localStorage.setItem('s1-filter',mode)}catch(e){}
  }
  bs.forEach(function(b){b.addEventListener('click',function(){apply(b.getAttribute('data-mode'))})});
  var m='all';try{m=localStorage.getItem('s1-filter')||'all'}catch(e){}
  apply(m);
})();
"""


def tile(k: str, v: str, s: str = "", bar: float | None = None) -> str:
    b = f'<div class="bar"><i style="width:{min(max(bar, 0), 1) * 100:.0f}%"></i></div>' if bar is not None else ""
    return f'<div class="tile"><div class="k">{esc(k)}</div><div class="v">{v}</div><div class="s">{esc(s)}</div>{b}</div>'


def build(data: dict, now: dt.datetime | None = None) -> str:
    now = now or Lv.now_utc()
    rec, picks, runs, live = data["rec"], data["picks"], data["runs"], data["live"]
    rec = with_probs(rec)
    tot = summarize(rec)
    n_all = rec.height
    weeks_graded = rec.filter(pl.col("result").is_in(["W", "L"])).select(pl.col("week").n_unique()).item() if n_all else 0
    ci = week_ci(rec) if n_all else None
    cur_week = int(runs["week"].cast(pl.Int64).max()) if runs.height else None
    last_run = runs["run_utc"].max() if runs.height else None

    # ---- header / tiles
    be_txt = f'break-even {fmt_pct(tot["be"])}' if tot["be"] is not None else "no graded picks yet"
    tiles = "".join([
        tile("Record", f'{tot["W"]}-{tot["L"]}' + (f'-{tot["P"]}' if tot["P"] else ""),
             f'{tot["pending"]} open · {tot["void"]} void'),
        tile("Win rate", fmt_pct(tot["win"]), be_txt),
        tile("Units", fmt_units(tot["units"]) if tot["n"] else "–", "1 unit per pick at DraftKings price"),
        tile("ROI", fmt_pct(tot["roi"], 1, True),
             (f'interim 95% {fmt_pct(ci[0], 0, True)} to {fmt_pct(ci[1], 0, True)}' if ci else "interval after 3 graded weeks")),
        tile("Bets graded", f'{tot["n"]} <span style="font-size:18px;color:var(--muted)">of {PASS_N}</span>',
             "needed for the season test", tot["n"] / PASS_N),
        tile("Weeks with a result", f'{weeks_graded} <span style="font-size:18px;color:var(--muted)">of {PASS_WEEKS}</span>',
             "needed for the season test", weeks_graded / PASS_WEEKS),
    ])

    # ---- current week
    cur = rec.filter(pl.col("week") == cur_week) if n_all and cur_week is not None else rec
    games = []
    if runs.height and cur_week is not None:
        gr = runs.filter(pl.col("week") == str(cur_week)).sort("run_utc", descending=True).unique("an_game_id", keep="first") \
            .sort("start_time")
        games = gr.to_dicts()
    blocks, quiet = [], []
    for g in games:
        rows = cur.filter(pl.col("an_game_id") == g["an_game_id"]).sort("player").to_dicts() if cur.height else []
        if rows:
            blocks.append(game_block(g, rows, now))
        else:
            quiet.append(g)
    if quiet:
        blocks.append('<section class="game quiet"><header><h3>No picks</h3></header><ul class="nopick">' + "".join(
            f'<li><span>{esc(g["away"])} at {esc(g["home"])}</span><span class="ko">{fmt_dt(g["start_time"])} ET</span></li>' for g in quiet) +
            '</ul><p class="note">None of these games had a prop where all four signals agreed at the latest run.</p></section>')
    n_open = sum(1 for g in games if Lv.parse_ts(g["start_time"]) > now)
    n_flag = sum(1 for r in cur.to_dicts() if r.get("inj_against") == "true" or r.get("depth_against") == "true") if cur.height else 0
    colhead = ('<div class="colhead"><span>Player</span><span>Bet</span><span class="r">Price</span>'
               '<span class="p"><span title="Break-even for the price">BE</span><span title="DraftKings, de-vigged">Mkt</span><span title="Simulator">Model</span></span><span class="r">Result</span></div>')
    week_html = (
        f'<section><div class="weekhead"><h2>Week {cur_week}: {cur.height} picks in {len(games) - len(quiet)} of {len(games)} games</h2>'
        f'<div class="filters" role="group" aria-label="Filter picks">'
        f'<button type="button" data-mode="all" aria-pressed="true">All</button>'
        f'<button type="button" data-mode="flagged" aria-pressed="false">News against ({n_flag})</button>'
        f'<button type="button" data-mode="clear" aria-pressed="false">No news against</button></div></div>'
        f'<p class="note">{n_open} games have not kicked off; their picks are the latest run and can change. Break-even is the '
        f'price including vig. Market is DraftKings de-vigged. Model is the simulator, which backtests show is overconfident at the extremes.</p>'
        f'{colhead}<div class="games">{"".join(blocks)}</div></section>') if cur_week is not None else '<p class="empty">No runs yet.</p>'

    # ---- charts
    edge_rows = [r for r in cur.to_dicts() if r["result"] == "pending"] if cur.height else []
    charts = (
        '<div class="cols charts"><div class="card"><h2>Season units</h2>' + chart_units(rec) +
        f'<p class="note">2025 reference for the same rule: {REF["w"]}-{REF["l"]}, ROI {fmt_pct(REF["roi"], 1, True)}, 95% interval '
        f'{fmt_pct(REF["lo"], 1, True)} to {fmt_pct(REF["hi"], 1, True)} (61 bets). Interim 2026 numbers are descriptive.</p></div>'
        '<div class="card"><h2>Open picks: model against price</h2>'
        '<div class="legend"><span><i class="k1"></i>Break-even for the price</span><span><i class="k3"></i>Market (de-vigged)</span>'
        '<span><i class="k2"></i>Model</span></div>' + chart_edge(edge_rows) +
        '<p class="note">The filled dot should sit right of the hollow one for the pick to have value by the model\'s own numbers. '
        'Backtests found the model\'s extreme probabilities land near 50%, so long gaps are weaker than they look.</p></div></div>')

    # ---- breakdowns
    if n_all:
        wk = [(f"Week {w}", x) for (w,), x in sorted(rec.group_by("week"), key=lambda kv: kv[0][0])]
        mk = [(MARKET.get(m, m), x) for (m,), x in sorted(rec.group_by("market"), key=lambda kv: kv[0][0])]
        sd = [(s.capitalize(), x) for (s,), x in sorted(rec.group_by("side"), key=lambda kv: kv[0][0])]
        fl = [("Injury news against", rec.filter(pl.col("inj_against") == "true")),
              ("Depth chart against", rec.filter(pl.col("depth_against") == "true")),
              ("No news against", rec.filter(pl.col("inj_against") != "true", pl.col("depth_against") != "true")),
              ("Flags not recorded (before 2026-10-03)", rec.filter(pl.col("inj_against").is_null()))]
        fl = [(n, x) for n, x in fl if x.height]
        breakdowns = (
            '<div class="cols"><div class="card"><h2>By week</h2>' + breakdown(rec, None, wk) + '</div>'
            '<div class="card"><h2>By news flag</h2>' + breakdown(rec, None, fl) +
            '<p class="note">Flags are descriptive. S1 still records flagged picks; dropping them would be a new rule that needs its own pre-registration.</p></div>'
            '<div class="card"><h2>By prop</h2>' + breakdown(rec, None, mk) + '</div>'
            '<div class="card"><h2>Over and under</h2>' + breakdown(rec, None, sd) + '</div></div>'
            f'<p class="note">Fewer than {PASS_N} graded bets in any row is too few to read. Pushes and voids (player did not play) take no units.</p>')
    else:
        breakdowns = ""

    # ---- changes between runs and run log
    ch = changes(picks, runs, cur_week, now) if cur_week is not None else []
    if ch:
        rows = []
        for c in ch:
            price = f'{c["odds_first"]:+.0f}' if c["odds_first"] == c["odds_last"] else f'{c["odds_first"]:+.0f} → {c["odds_last"]:+.0f}'
            line = f'{c["line_first"]:g}' if c["line_first"] == c["line_last"] else f'{c["line_first"]} → {c["line_last"]}'
            rows.append([esc(c["game"]), esc(c["player"]), f'{esc(c["side"])} {line} {esc(MARKET.get(c["market"], c["market"]))}', price,
                         f'{c["n_seen"]} of {c["n_runs"]}', "kept" if c["kept"] else '<span style="color:var(--bad)">dropped</span>'])
        stab = table(["Game", "Player", "Bet", "Price first → now", "Runs it was in", "Deciding run"], rows)
        kept = sum(1 for c in ch if c["kept"])
        stab_html = (f'<div class="card"><h2>Pick stability</h2><p class="note" style="margin-top:0">{len(ch)} different picks appeared this week; '
                     f'{kept} are in the deciding run and {len(ch) - kept} were dropped as lines, prices or injury news moved. '
                     f'Deciding run is the last run before kickoff.</p>{stab}</div>')
    else:
        stab_html = ""
    rl = run_log(picks, runs, live)
    if rl:
        rows = []
        for r in rl[:14]:
            def ok(b):
                return "n/a" if not r["flags_era"] else ("✓" if b else '<span style="color:var(--bad)">missing</span>')
            rows.append([esc(fmt_dt(r["run"])), str(r["games"]), str(r["props"]), str(r["picks"]),
                         "–" if r["lead"] is None else f'{r["lead"] / 60:.1f} h' if r["lead"] >= 90 else f'{r["lead"]:.0f} min',
                         ok(r["inj"]), ok(r["depth"])])
        runs_html = ('<div class="card"><h2>Run log</h2>' + table(["Run (ET)", "Games", "Props scored", "Picks", "To next kickoff", "Injuries saved", "Depth saved"], rows, "num") +
                     '<p class="note">A run late in the day has fewer games left to score. The injury and depth responses are saved with every run.</p></div>')
    else:
        runs_html = ""

    # ---- earlier weeks
    old = []
    if n_all:
        for (w,), x in sorted(rec.group_by("week"), key=lambda kv: -kv[0][0]):
            if w == cur_week:
                continue
            s = summarize(x)
            rows = "".join(pick_row(r, True) for r in x.sort("start_time", "player").to_dicts())
            old.append(f'<details class="old"><summary>Week {w}: {s["W"]}-{s["L"]}-{s["P"]}, {fmt_units(s["units"])} units</summary>'
                       f'<ul class="picks">{rows}</ul></details>')

    stamp = f'Built {fmt_dt(now.strftime("%Y-%m-%dT%H:%M:%SZ"))} ET' + (f' · last run {fmt_dt(last_run)} ET' if last_run else "")
    foot = (
        '<div class="foot"><ul>'
        f'<li>Rule S1: DraftKings props where the disagree, projection, simulator and price signals all point the same way. Locked before the season; '
        f'<a href="{REPO}docs/s1_live_rules.md">tracker rules</a> · <a href="{REPO}docs/simulator_confirm.md">season test</a>.</li>'
        f'<li>Season test: pass only if at least {PASS_N} bets in at least {PASS_WEEKS} weeks and the week-clustered ROI interval has its lower end above 0. This page does not decide that.</li>'
        '<li>The official pick for a game is the last run before kickoff. Nothing is edited after kickoff. A player who does not play is void.</li>'
        '<li>Results come from nflverse player stats and snap counts, which can lag a game by hours. Injury news is ESPN at the time of each run, saved in <code>data/live/injuries</code>.</li>'
        '</ul></div>')

    return (
        '<title>S1 Live Tracker</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&amp;family=Barlow+Condensed:wght@500;600&amp;family=IBM+Plex+Mono:wght@400;500;600&amp;display=swap">'
        f'<style>{CSS}</style>'
        '<div class="wrap">'
        f'<div class="top"><div><h1>S1 Live Tracker</h1><p class="sub">2026 NFL player props, rule S1 (all four signals agree)</p></div>'
        f'<div class="stamp">{esc(stamp)}</div></div>'
        '<div class="notice">Unvalidated rule. These are tracker records of what S1 selected, not recommendations. In 2025 it went '
        f'{REF["w"]}-{REF["l"]} on 61 bets with a 95% interval of {fmt_pct(REF["lo"], 0, True)} to {fmt_pct(REF["hi"], 0, True)} ROI.</div>'
        f'<div class="tiles">{tiles}</div>'
        f'{week_html}{charts}{breakdowns}{stab_html}{runs_html}'
        + ("<section><h2>Earlier weeks</h2><div class=\"games\">" + "".join(old) + "</div></section>" if old else "")
        + f'{foot}</div><script>{JS}</script>')


def write(now: dt.datetime | None = None, out: Path | None = None) -> Path:
    out = out or OUT
    out.write_text(build(load(), now))
    return out
