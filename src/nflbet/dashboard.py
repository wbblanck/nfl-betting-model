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
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

from nflbet import config, explain as Ex, live as Lv

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
    return {"rec": rec, "picks": picks, "runs": runs, "live": live, "pcmp": _read(live / f"parlay_compare_{SEASON}.csv"),
            "pa_rec": _read(live / f"s1pa_record_{SEASON}.csv"),
            "ocmp": _read(live / f"openmarkets_compare_{SEASON}.csv"),
            "ats_runs": _read(live / f"ats_runs_{SEASON}.csv"), "ats_rec": _read(live / f"ats_record_{SEASON}.csv")}


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


COVERAGE_GLOB = "coverage_fantasypoints_2026_w1-*.csv"
TEAM_FIX = {"JAC": "JAX", "LAR": "LA", "WSH": "WAS"}


def coverage_for_pick(r: dict, ext: Path | None = None) -> str:
    """Opponent defense's coverage mix from the newest hand-transcribed table that ends BEFORE the pick's week (so the
    game itself is not in it). Context only: it is not an input to rule S1. Empty when no such table exists."""
    ext = ext or config.ROOT / "data" / "external"
    try:
        wk = int(r["week"])
    except (KeyError, TypeError, ValueError):
        return ""
    best = None
    for f in ext.glob(COVERAGE_GLOB):
        m = re.search(r"w1-(\d+)\.csv$", f.name)
        if m and int(m.group(1)) < wk and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), f)
    if best is None:
        return ""
    team = TEAM_FIX.get(r.get("team"), r.get("team"))
    home, away = TEAM_FIX.get(r.get("home"), r.get("home")), TEAM_FIX.get(r.get("away"), r.get("away"))
    opp = away if team == home else home
    d = pl.read_csv(best[1]).filter(pl.col("team") == opp, pl.col("table") == "all_plays")
    if not d.height:
        return ""
    x = d.row(0, named=True)
    return f"{opp} defense, weeks 1-{best[0]}: man {x['man_total']:.0f}% of plays, Cover 3 {x['cov3']:.0f}%, EPA per DB {x['epa_per_db']:+.2f}"


def chip(kind: str, text: str, title: str = "") -> str:
    return f'<span class="chip {kind}"' + (f' title="{esc(title)}"' if title else "") + f">{esc(text)}</span>"


def pick_row(r: dict, locked: bool, tag: str = "") -> str:
    flags = [chip("tag", tag)] if tag else []
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
        f'<div class="bet"><span class="side-pill {esc(r["side"])}">{esc(r["side"])}</span> '
        f'<span class="line">{r["line"]:g}</span> <span class="mkt">{esc(MARKET.get(r["market"], r["market"]))}</span></div>'
        f'<div class="price">{r["odds"]:+.0f}</div>'
        f'<div class="probs" title="Break-even for this price, DraftKings de-vigged, model">'
        f'<span>{fmt_pct(r["be"])}</span><span>{fmt_pct(r["p_mkt"])}</span><span>{fmt_pct(r["p_model"])}</span></div>'
        f'<div class="res">{chip(rc, (RESULT_ICON.get(res, res) + " " + res) if res != "pending" else ("Locked" if locked else "Open"), "")}'
        + (f'<span class="actual">actual {float(r["actual"]):g}</span>' if r.get("actual") not in (None, "") else "")
        + "</div>"
        + (f'<div class="news">{"".join(flags)}<span class="detail">{esc(detail)}</span></div>' if flags or detail else "")
        + (f'<div class="news"><span class="detail">{esc(cov)}</span></div>' if (cov := coverage_for_pick(r)) else "")
        + second_source(r)
        + (('<details class="why"><summary>Why this pick</summary><ul>' + "".join(f"<li>{esc(x)}</li>" for x in r["_why"]) + '</ul></details>')
           if r.get("_why") else "")
        + "</li>")


def second_source(r: dict) -> str:
    """ParlayAPI's DK / FanDuel line and price on the pick's side at the same run (from 2026-10-08)."""
    parts, differs = [], False
    for b, lab in (("dk", "DK"), ("fd", "FanDuel")):
        ln, od = r.get(f"pa_{b}_line"), r.get(f"pa_{b}_odds")
        if ln in (None, "") or od in (None, ""):
            continue
        parts.append(f"{lab} {float(ln):g} {float(od):+.0f}")
        differs |= b == "dk" and float(ln) != float(r["line"])
    om = []
    for v, lab in (("kalshi", "Kalshi"), ("prophetx", "ProphetX"), ("bettoredge", "BettorEdge")):
        o, a = r.get(f"om_{v}_odds"), r.get(f"om_{v}_avail")
        if o not in (None, ""):
            om.append(f"{lab} {float(o):+.0f}" + (f" (${float(a):,.0f})" if a not in (None, "") else ""))
    html_ = ""
    if parts:
        html_ += ('<div class="news">' + (chip("warn", "ParlayAPI DK line differs") if differs else "")
                  + f'<span class="detail">ParlayAPI at this run: {esc(", ".join(parts))}</span></div>')
    if om:
        html_ += f'<div class="news"><span class="detail">Prediction markets at this line: {esc(", ".join(om))}</span></div>'
    return html_


def openmarkets_card(oc: pl.DataFrame) -> str:
    """Latest run's comparison of the prediction-market venues with DraftKings at DraftKings' line."""
    if not oc.height:
        return ""
    last = oc["run_utc"].max()
    x = oc.filter(pl.col("run_utc") == last)
    rows = [[esc({"kalshi": "Kalshi", "prophetx": "ProphetX", "bettoredge": "BettorEdge"}.get(r["venue"], r["venue"])),
             f'{r["n_both"]} of {r["n_dk"]}',
             f'{float(r["mean_gap_pts"]):.1f} pts' if r["mean_gap_pts"] not in (None, "") else "–",
             f'${float(r["median_avail"]):,.0f}' if r["median_avail"] not in (None, "") else "–"] for r in x.to_dicts()]
    return ('<div class="card"><h3>Prediction markets vs DraftKings</h3>' +
            table(["Venue", "DK props quoted at DK's line", "Mean no-vig gap", "Median $ available"], rows, "num") +
            f'<p class="note">Run {esc(fmt_dt(last))} ET, from OpenMarkets (read-only). A record next to Action Network and ParlayAPI; '
            'S1 does not use these prices. The gap is the mean absolute difference in no-vig P(over) at the same line.</p></div>')


def parlay_card(pc: pl.DataFrame) -> str:
    """Latest run's comparison of ParlayAPI with Action Network, per book."""
    if not pc.height:
        return ""
    last = pc["run_utc"].max()
    x = pc.filter(pl.col("run_utc") == last)
    name = {"dk": "DraftKings", "fd": "FanDuel"}
    rows = [[name.get(r["book"], r["book"]), r["n_parlay"], r["n_an"], r["n_both"],
             f'{int(r["same_line"]) / int(r["n_both"]):.0%}' if r["n_both"] not in (None, "", "0") else "–",
             f'{float(r["mean_p_gap_pts"]):.1f} pts' if r["mean_p_gap_pts"] not in (None, "") else "–"] for r in x.to_dicts()]
    left = x["credits_left"].drop_nulls()
    return ('<div class="card"><h2>Second price source</h2>' +
            table(["Book", "ParlayAPI props", "Action Network props", "In both", "Same line", "P(over) gap at same line"], rows, "num") +
            f'<p class="note">Run {esc(fmt_dt(last))} ET. ParlayAPI (DraftKings, FanDuel) is a record next to Action Network; S1 still picks from '
            'Action Network, whose book set the rule was locked on. The gap is the mean absolute difference in de-vigged P(over) where both list the same line.'
            + (f' ParlayAPI requests left this month: {esc(left[-1])}.' if left.len() else "") + '</p></div>')


_FTN: dict = {}


def ftn_context(week: int) -> dict | None:
    """Season-to-date FTN team stats before `week` (cached per build); None when unavailable offline."""
    if "tg" not in _FTN:
        try:
            from nflbet import teamstats as T
            _FTN["tg"] = T.ftn([SEASON])
        except Exception:  # noqa: BLE001
            _FTN["tg"] = None
    if _FTN["tg"] is None or not _FTN["tg"].height:
        return None
    from nflbet import teamstats as T
    s = T.season_to_date(_FTN["tg"], SEASON, week)
    if not s.height:
        return None
    lg = {c: float(s[c].mean()) for c in s.columns if c.startswith(("def_", "off_"))}
    return {"week": week, "teams": {r["team"]: r for r in s.iter_rows(named=True)}, "league": lg}


def with_why(rows: list[dict], live: Path, source: str, stats: pl.DataFrame | None) -> list[dict]:
    """Attach the plain-language reasons (src/nflbet/explain.py) to each pick row."""
    out = []
    for r in rows:
        try:
            games = Ex.recent_games(stats, r["player_id"], r["market"], int(r["week"])) if stats is not None else []
            team, home, away = r.get("team"), r.get("home"), r.get("away")
            fix = {"JAC": "JAX", "LAR": "LA", "WSH": "WAS"}
            opp = fix.get(away, away) if fix.get(team, team) == fix.get(home, home) else fix.get(home, home)
            ctx = ftn_context(int(r["week"])) if stats is not None else None
            r = dict(r, _why=Ex.reasons(r, Ex.book_lines(live, r, source), games, Ex.opponent_context(r, opp, ctx)))
        except Exception:  # noqa: BLE001 - a missing reason never breaks the page
            pass
        out.append(r)
    return out


def load_stats() -> pl.DataFrame | None:
    try:
        from nflbet import props as P
        return P.load_stats(SEASON)
    except Exception:  # noqa: BLE001 - offline build: picks show without recent games
        return None


def hcp(team: str, home_line, side_is_home: bool) -> str:
    """'PIT -2.5' from a home margin line (positive = home favored), seen from the side's team."""
    if home_line in (None, ""):
        return "–"
    v = -float(home_line) if side_is_home else float(home_line)
    return f"{team} {'PK' if v == 0 else f'{v:+g}'}"


LABEL_CHIP = {"Bet Now": "win", "Wait": "flag", "Monitor": "state open", "No Value": "idle"}


def ats_section(runs: pl.DataFrame, rec: pl.DataFrame, now: dt.datetime) -> str:
    """Live ATS tab (docs/ats_live_rules.md)."""
    head = ('<section class="block"><div class="sechead"><div><p class="eyebrow">NFL against the spread · unvalidated tracker</p>'
            '<h2>Line value and expected CLV</h2></div></div>'
            '<p class="lede">Each run compares the rating\'s fair line with every book\'s spread and the exchanges\' price. The rating does not beat '
            'closing spreads (2022-2025 backtest), but its side gained about half a point of closing-line value from opening lines (2008-2024). '
            'Labels follow the pre-registered rules; they are tracker records, not recommendations.</p>')
    if not runs.height:
        return head + '<p class="empty">No ATS runs yet. The first scheduled S1 run records this week\'s games.</p></section>'
    wk = int(runs["week"].cast(pl.Int64).max())
    cur = runs.filter(pl.col("week").cast(pl.Int64) == wk)
    latest = cur.sort("run_utc", descending=True).unique("game_id", keep="first").sort("start_time")
    rows = []
    for r in latest.to_dicts():
        h = r["side_is_home"] in (True, "true")
        locked = Lv.parse_ts(r["start_time"]) <= now
        rows.append([esc(fmt_dt(r["start_time"])), f'{esc(r["away"])} at {esc(r["home"])}',
                     esc(hcp(r["home"], r["fair"], True)),
                     esc(hcp(r["home"], r["consensus"], True)), esc(hcp(r["home"], r["exchange"], True)) if r.get("exchange") not in (None, "") else "–",
                     f'<b>{esc(hcp(r["side"], r["best_line"], h))}</b> <span class="muted">{esc(r["best_book"])} {float(r["best_odds"]):+.0f}</span>',
                     f'{float(r["gap"]):+.1f}', f'{float(r["exp_clv"]):+.2f}', "3/7" if r["key"] in (True, "true") else "",
                     chip(LABEL_CHIP.get(r["label"], "idle"), ("Kicked off · " if locked else "") + r["label"], r.get("qb_note") or "")])
    table_html = table(["Kickoff (ET)", "Game", "Fair (home)", "Consensus", "Exchanges", "Rating's side at best number", "Gap", "Exp. CLV", "Key", "Label"], rows)
    last = latest["run_utc"].max()
    graded = rec.filter(pl.col("result_ats").is_in(["W", "L", "P"])) if rec.height else rec
    def summ(x):
        if not x.height:
            return "none graded yet"
        w, l, pu = (int((x["result_ats"] == k).sum()) for k in ("W", "L", "P"))
        u = float(x["units"].cast(pl.Float64).sum())
        c = x["clv"].cast(pl.Float64).drop_nulls()
        return f"{w}-{l}" + (f"-{pu}" if pu else "") + f", {u:+.2f} units, mean CLV {float(c.mean()):+.2f} pts" if c.len() else f"{w}-{l}, {u:+.2f} units"
    rec_html = ""
    if graded.height:
        lines = []
        for lab in ("Bet Now", "Wait", "Monitor", "No Value"):
            x = graded.filter(pl.col("label") == lab)
            if x.height:
                lines.append(f'<li><b>{esc(lab)}</b>: {esc(summ(x))}</li>')
        rec_html = '<div class="card"><h3>Season record by label</h3><ul>' + "".join(lines) + '</ul><p class="note">CLV against the nflverse closing spread. No Value rows are graded for reference only.</p></div>'
    return (head + f'<p class="note">Week {wk}, latest run {esc(fmt_dt(last))} ET. Lines are each team\'s handicap; "Fair (home)" is the rating\'s line for the home team.</p>'
            + f'<div class="card">{table_html}</div>' + rec_html
            + '<p class="note">Rules: docs/ats_live_rules.md. Expected CLV = 0.235 × gap, the share of the gap bet365 openers moved by the close in 2022-2024.</p></section>')


def pa_section(pa: pl.DataFrame, rec: pl.DataFrame, now: dt.datetime, live: Path | None = None,
               stats: pl.DataFrame | None = None) -> str:
    """S1 on ParlayAPI: the same rule on ParlayAPI's DK and FanDuel lines (books-disagree = DK vs FanDuel only).
    A separate record from the official one; never pooled."""
    if not pa.height:
        return ""
    pa = prep(pa)
    wk = int(pa["week"].max())
    official = {(r["player_id"], r["market"], r["side"]) for r in rec.to_dicts()} if rec.height else set()
    cur = pa.filter(pl.col("week") == wk).sort("start_time", "player")
    blocks = []
    for _, x in sorted(cur.group_by("away", "home"), key=lambda kv: kv[1]["start_time"].min()):
        rows = with_why(x.sort("player").to_dicts(), live, "parlay", stats) if live is not None else x.sort("player").to_dicts()
        g = {"start_time": rows[0]["start_time"], "home": rows[0]["home"], "away": rows[0]["away"]}
        locked = Lv.parse_ts(g["start_time"]) <= now
        body = "".join(pick_row(r, locked, "Also official S1" if (r["player_id"], r["market"], r["side"]) in official else "")
                       for r in rows)
        blocks.append(game_block(g, rows, now, body))
    return ('<section class="block" id="parlay"><div class="sechead"><div><p class="eyebrow">Separate record · not pooled</p>'
            f'<h2>Week {wk}, S1 on ParlayAPI lines: {cur.height} picks</h2></div></div>'
            '<p class="lede">Same rule and model, scored on ParlayAPI\'s DraftKings and FanDuel lines, so it runs as soon as DraftKings posts. '
            'The books-disagree vote here compares DraftKings with FanDuel only, so this record is kept apart from official S1. Unvalidated, like S1.</p>'
            + (COLHEAD + f'<div class="games">{"".join(blocks)}</div>' if blocks else f'<p class="empty">No week {wk} props met all four signals.</p>')
            + '</section>')


COLHEAD = ('<div class="colhead" aria-hidden="true"><span>Player</span><span>Bet</span><span class="r">Price</span>'
           '<span class="p"><span title="Break-even for the price">BE</span><span title="DraftKings, de-vigged">Mkt</span>'
           '<span title="Simulator">Model</span></span><span class="r">Result</span></div>')


def prep(d: pl.DataFrame) -> pl.DataFrame:
    """Typed columns plus break-even / market / model probabilities for the side taken."""
    return with_probs(d.with_columns(pl.col("week").cast(pl.Int64), pl.col("line").cast(pl.Float64), pl.col("odds").cast(pl.Float64),
                                     pl.col("p_sim").cast(pl.Float64), pl.col("p_over_dk").cast(pl.Float64),
                                     pl.col("units").cast(pl.Float64)))


def game_block(g: dict, rows: list[dict], now: dt.datetime, body: str | None = None) -> str:
    start = Lv.parse_ts(g["start_time"])
    locked = start <= now
    graded = [r for r in rows if r["result"] in ("W", "L", "P", "void")]
    state = ("final" if rows and len(graded) == len(rows) else "locked") if locked else "open"
    label = {"open": "Open", "locked": "Kicked off", "final": "Final"}[state]
    if locked and not rows:
        label = "Kicked off, no picks"
    if body is None:
        body = "".join(pick_row(r, locked) for r in rows) if rows else '<li class="none">No pick met all four signals at the deciding run.</li>'
    return (f'<section class="game {state}"><header><h3>{esc(g["away"])} <span class="at">at</span> {esc(g["home"])}</h3>'
            f'<span class="ko">{fmt_dt(g["start_time"])} ET</span>{chip("state " + state, label, "Open games can still change their picks until kickoff" if state == "open" else "")}</header>'
            f'<ul class="picks">{body}</ul></section>')


def scale(vals: list[float], lo: float, hi: float, a: float, b: float):
    return lambda v: a + (v - lo) / (hi - lo) * (b - a)


def tipattr(text: str) -> str:
    return f' data-tip="{esc(text)}" tabindex="0"'


def chart_edge(rows: list[dict]) -> str:
    """Dumbbell per open pick: break-even for the price (hollow ring) to the model's win probability (filled dot), with
    DraftKings' de-vigged market as a tick. Rows from both records, tagged."""
    if not rows:
        return '<p class="empty">No open picks right now. Picks appear here after the next run and stay until kickoff.</p>'
    rows = sorted(rows, key=lambda r: r["p_model"] - r["be"], reverse=True)
    lo, hi = 0.30, 1.0
    left, right, top, rh = 250, 24, 14, 34
    w, h = 820, top + rh * len(rows) + 30
    x = scale([], lo, hi, left, w - right)
    out = [f'<svg class="chart edge" viewBox="0 0 {w} {h}" role="img" aria-label="Model win probability against break-even, one row per open pick">']
    for t in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        out.append(f'<line class="{"mid" if t == 0.5 else "grid"}" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 4}" y2="{h - 26}"/>'
                   f'<text class="tick" x="{x(t):.1f}" y="{h - 9}" text-anchor="middle">{t * 100:.0f}%</text>')
    for i, r in enumerate(rows):
        y = top + rh * i + rh / 2
        tag = r.get("_tag", "")
        name = f'{r["player"]}'
        sub = f'{r["side"]} {r["line"]:g} {MARKET.get(r["market"], r["market"])} · {r["odds"]:+.0f}{" · " + tag if tag else ""}'
        tip = (f'{r["player"]} {r["side"]} {r["line"]:g} {MARKET.get(r["market"], r["market"])} at {r["odds"]:+.0f}{" (" + tag + ")" if tag else ""}'
               f' | break-even {fmt_pct(r["be"])} · DraftKings {fmt_pct(r["p_mkt"])} · model {fmt_pct(r["p_model"])}')
        out.append(f'<g class="row"{tipattr(tip)}><rect class="hit" x="0" y="{y - rh / 2:.1f}" width="{w}" height="{rh}"/>'
                   f'<text class="rowl" x="{left - 10}" y="{y - 2:.1f}" text-anchor="end">{esc(name)}</text>'
                   f'<text class="rows" x="{left - 10}" y="{y + 12:.1f}" text-anchor="end">{esc(sub)}</text>'
                   f'<line class="gap" x1="{x(r["be"]):.1f}" x2="{x(r["p_model"]):.1f}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<rect class="mk" x="{x(r["p_mkt"]) - 1.5:.1f}" y="{y - 7:.1f}" width="3" height="14" rx="1.5"/>'
                   f'<circle class="be" cx="{x(r["be"]):.1f}" cy="{y:.1f}" r="5"/>'
                   f'<circle class="md" cx="{x(r["p_model"]):.1f}" cy="{y:.1f}" r="5"/></g>')
    out.append("</svg>")
    return "".join(out)


def chart_units(d: pl.DataFrame) -> str:
    """Cumulative units over graded picks in kickoff order, with a hover readout per pick."""
    g = d.filter(pl.col("result").is_in(["W", "L"])).sort("start_time", "player")
    if not g.height:
        return ('<p class="empty">Nothing is graded yet. The first results appear after the early games on '
                'Sunday; the cumulative line starts then.</p>')
    cum, s = [], 0.0
    for u in g["units"].to_list():
        s += u
        cum.append(s)
    w, h, l, r_, t, b = 560, 240, 40, 64, 14, 28
    lo, hi = min(0.0, min(cum)), max(0.0, max(cum))
    step = max(1, math.ceil((hi - lo) / 5))
    lo, hi = math.floor(lo / step) * step - (step if lo == math.floor(lo / step) * step and lo < 0 else 0), math.ceil(hi / step) * step
    lo, hi = min(lo, -step), max(hi, step)
    xs = scale([], 0, len(cum), l, w - r_)          # x = 0 is the start (0 units), then one step per graded pick
    ys = scale([], lo, hi, h - b, t)
    pts = [(xs(0), ys(0))] + [(xs(i + 1), ys(v)) for i, v in enumerate(cum)]
    line = " ".join(f"{a:.1f},{c:.1f}" for a, c in pts)
    out = [f'<svg class="chart units" viewBox="0 0 {w} {h}" role="img" aria-label="Cumulative units after each graded pick, ending at {cum[-1]:+.2f}">']
    for v in range(int(lo), int(hi) + 1, step):
        out.append(f'<line class="{"zero" if v == 0 else "grid"}" x1="{l}" x2="{w - r_}" y1="{ys(v):.1f}" y2="{ys(v):.1f}"/>'
                   f'<text class="tick" x="{l - 8}" y="{ys(v) + 4:.1f}" text-anchor="end">{v:+d}</text>')
    out.append(f'<polygon class="area" points="{xs(0):.1f},{ys(0):.1f} {line} {xs(len(cum)):.1f},{ys(0):.1f}"/>'
               f'<polyline class="ln" points="{line}"/>')
    rows = g.to_dicts()
    seg = (xs(1) - xs(0))
    for i, (r, v) in enumerate(zip(rows, cum)):
        cx, cy = pts[i + 1]
        tip = (f'Pick {i + 1}: {r["player"]} {r["side"]} {r["line"]:g} {MARKET.get(r["market"], r["market"])}, week {r["week"]} | '
               f'{"won" if r["result"] == "W" else "lost"} {r["units"]:+.2f} · season {v:+.2f} units')
        out.append(f'<g class="pt"{tipattr(tip)}><rect class="hit" x="{cx - seg / 2:.1f}" y="{t}" width="{seg:.1f}" height="{h - t - b}"/>'
                   f'<line class="xh" x1="{cx:.1f}" x2="{cx:.1f}" y1="{t}" y2="{h - b}"/>'
                   f'<circle class="dot {"w" if r["result"] == "W" else "l"}" cx="{cx:.1f}" cy="{cy:.1f}" r="4"/></g>')
    ex, ey = pts[-1]
    out.append(f'<circle class="end" cx="{ex:.1f}" cy="{ey:.1f}" r="5"/>'
               f'<text class="endl" x="{ex + 9:.1f}" y="{ey + 4:.1f}">{cum[-1]:+.2f}</text>'
               f'<text class="tick" x="{l}" y="{h - 8}">start</text>'
               f'<text class="tick" x="{w - r_}" y="{h - 8}" text-anchor="end">pick {len(cum)}</text></svg>')
    return "".join(out)


def chart_weeks(d: pl.DataFrame) -> str:
    """Units per week, a column per graded week from one zero baseline; value on the cap."""
    g = d.filter(pl.col("result").is_in(["W", "L"]))
    if not g.height:
        return '<p class="empty">No graded weeks yet.</p>'
    wk = sorted(((int(w), x) for (w,), x in g.group_by("week")), key=lambda kv: kv[0])
    vals = [(w, float(x["units"].sum()), summarize(x)) for w, x in wk]
    w, h, l, r_, t, b = 560, 240, 40, 12, 22, 28
    m = max(1.0, max(abs(v) for _, v, _ in vals))
    step = max(1, math.ceil(m / 3))
    top_ = math.ceil(m / step) * step
    ys = scale([], -top_, top_, h - b, t)
    n = max(len(vals), 6)                                   # fixed slot width so one week is not one fat bar
    slot = (w - l - r_) / n
    bw = min(24, slot * 0.5)
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Units won or lost in each graded week">']
    for v in range(-top_, top_ + 1, step):
        out.append(f'<line class="{"zero" if v == 0 else "grid"}" x1="{l}" x2="{w - r_}" y1="{ys(v):.1f}" y2="{ys(v):.1f}"/>'
                   f'<text class="tick" x="{l - 8}" y="{ys(v) + 4:.1f}" text-anchor="end">{v:+d}</text>')
    for i, (wn, v, s) in enumerate(vals):
        cx = l + slot * i + slot / 2
        y0, y1 = ys(0), ys(v)
        hgt = abs(y1 - y0)
        rr = min(4, hgt)
        x0 = cx - bw / 2
        if v >= 0:   # rounded at the data end (top), square at the baseline
            path = (f"M{x0:.1f},{y0:.1f} V{y1 + rr:.1f} Q{x0:.1f},{y1:.1f} {x0 + rr:.1f},{y1:.1f} H{x0 + bw - rr:.1f} "
                    f"Q{x0 + bw:.1f},{y1:.1f} {x0 + bw:.1f},{y1 + rr:.1f} V{y0:.1f} Z")
            ly = y1 - 6
        else:
            path = (f"M{x0:.1f},{y0:.1f} V{y1 - rr:.1f} Q{x0:.1f},{y1:.1f} {x0 + rr:.1f},{y1:.1f} H{x0 + bw - rr:.1f} "
                    f"Q{x0 + bw:.1f},{y1:.1f} {x0 + bw:.1f},{y1 - rr:.1f} V{y0:.1f} Z")
            ly = y1 + 14
        tip = f'Week {wn}: {s["W"]}-{s["L"]}{"-" + str(s["P"]) if s["P"] else ""} | {v:+.2f} units · ROI {fmt_pct(s["roi"], 1, True)}'
        out.append(f'<g class="col"{tipattr(tip)}><rect class="hit" x="{cx - slot / 2:.1f}" y="{t}" width="{slot:.1f}" height="{h - t - b}"/>'
                   f'<path class="{"pos" if v >= 0 else "neg"}" d="{path}"/>'
                   f'<text class="capl" x="{cx:.1f}" y="{ly:.1f}" text-anchor="middle">{v:+.2f}</text>'
                   f'<text class="tick" x="{cx:.1f}" y="{h - 8}" text-anchor="middle">Wk {wn}</text></g>')
    out.append("</svg>")
    return "".join(out)


def table(head: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def winbar(win: float | None, be: float | None) -> str:
    """Win rate as a bar on a 0-100% track with the break-even marked."""
    if win is None:
        return '<span class="muted">–</span>'
    ok = be is not None and win >= be
    return (f'<span class="wb" title="Win {fmt_pct(win)}, break-even {fmt_pct(be)}"><span class="track">'
            f'<i class="{"ok" if ok else "short"}" style="width:{win * 100:.0f}%"></i>'
            + (f'<b style="left:{be * 100:.0f}%"></b>' if be is not None else "") +
            f'</span><span class="v">{fmt_pct(win)}</span></span>')


def unitbar(u: float | None, span: float) -> str:
    """Units as a diverging bar from a center line; span = largest |units| in the table."""
    if u is None:
        return '<span class="muted">–</span>'
    wpc = min(abs(u) / span, 1) * 50 if span else 0
    side = f"left:50%;width:{wpc:.1f}%" if u >= 0 else f"left:{50 - wpc:.1f}%;width:{wpc:.1f}%"
    return (f'<span class="ub"><span class="track"><i class="{"pos" if u >= 0 else "neg"}" style="{side}"></i></span>'
            f'<span class="v">{fmt_units(u)}</span></span>')


def breakdown(d: pl.DataFrame, by: str | None, groups: list[tuple[str, pl.DataFrame]]) -> str:
    stats = [(name, summarize(x)) for name, x in groups]
    span = max([abs(s["units"]) for _, s in stats if s["n"]] + [1.0])
    rows = [[esc(name), f'{s["W"]}-{s["L"]}' + (f'-{s["P"]}' if s["P"] else "") + (f' <span class="muted">· {s["pending"]} open</span>' if s["pending"] else ""),
             winbar(s["win"], s["be"]), unitbar(s["units"] if s["n"] else None, span), fmt_pct(s["roi"], 1, True)] for name, s in stats]
    return table(["", "Record", "Win rate vs break-even", "Units", "ROI"], rows, "bd")


# ------------------------------------------------------------------------------------------------ page

CSS = """
/* Layout: a scoreboard band (season record) up top, then the current week game by game for each record, then the
   charts, then the evidence tables. Labels in Barlow Condensed (stadium-board lettering), body in Barlow, every
   number in IBM Plex Mono. One accent (field-goal-net blue); win / loss are status colors with icons. */
:root{
  --bg:#edf0f3;--surface:#fbfcfd;--raised:#ffffff;--ink:#111b25;--ink2:#46535f;--muted:#6c7884;--line:#d9dfe5;--grid:#e4e8ec;
  --accent:#2a78d6;--accent-soft:#dde9f8;--neg:#e34948;--good:#0b6b0b;--good-bg:#dcf1d9;--bad:#b42b2b;--bad-bg:#f9e0df;
  --warn-bg:#fcebbd;--warn-ink:#4d3500;--idle-bg:#e7ebef;--board:#122030;--board-ink:#f2f6fa;--board-muted:#9fb0c1;
  --shadow:0 1px 2px rgba(17,27,37,.06);
  --display:'Barlow Condensed','Arial Narrow',sans-serif;--body:'Barlow',system-ui,sans-serif;--mono:'IBM Plex Mono',ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0d1217;--surface:#151c23;--raised:#1a222b;--ink:#e8edf2;--ink2:#b2bdc8;--muted:#86929e;--line:#26303a;--grid:#212a33;
  --accent:#3987e5;--accent-soft:#1b3452;--neg:#e66767;--good:#5fd35f;--good-bg:#16331a;--bad:#ff8c8c;--bad-bg:#3c1d1d;
  --warn-bg:#47380f;--warn-ink:#ffdf91;--idle-bg:#212a33;--board:#0a1622;--board-ink:#f2f6fa;--board-muted:#8fa2b6;--shadow:none;color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0d1217;--surface:#151c23;--raised:#1a222b;--ink:#e8edf2;--ink2:#b2bdc8;--muted:#86929e;--line:#26303a;--grid:#212a33;
  --accent:#3987e5;--accent-soft:#1b3452;--neg:#e66767;--good:#5fd35f;--good-bg:#16331a;--bad:#ff8c8c;--bad-bg:#3c1d1d;
  --warn-bg:#47380f;--warn-ink:#ffdf91;--idle-bg:#212a33;--board:#0a1622;--board-ink:#f2f6fa;--board-muted:#8fa2b6;--shadow:none;color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--body);margin:0;padding-inline:16px;padding-block:22px 56px}
.wrap{max-width:1080px;margin:0 auto;display:flex;flex-direction:column;gap:28px}
h1,h2,h3{font-family:var(--display);margin:0;font-weight:600;letter-spacing:.01em;text-wrap:balance}
h1{font-size:30px;line-height:1.05}
h2{font-size:21px;letter-spacing:.02em}
h3{font-size:19px}
a{color:var(--accent)}
a:focus-visible,button:focus-visible,summary:focus-visible,[data-tip]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.eyebrow{font:600 12px var(--display);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 2px}
.lede{color:var(--ink2);font-size:14px;margin:4px 0 0;max-width:72ch}
.note{color:var(--muted);font-size:13px;margin:8px 0 0;max-width:80ch}
.muted{color:var(--muted)}
.empty{color:var(--muted);margin:6px 0;font-size:14px}
.top{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:6px 20px}
.top .sub{color:var(--ink2);margin:2px 0 0}
.stamp{font:12px var(--mono);color:var(--muted)}
.notice{border-left:3px solid var(--warn-ink);background:var(--warn-bg);color:var(--warn-ink);padding:8px 12px;border-radius:0 4px 4px 0;font-size:13.5px}

/* scoreboard */
.board{background:var(--board);color:var(--board-ink);border-radius:8px;padding:18px 20px;display:grid;
  grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:18px 28px}
.board .eyebrow{color:var(--board-muted)}
.hero{display:flex;flex-wrap:wrap;align-items:flex-end;gap:10px 28px}
.big{font:600 64px/0.95 var(--mono);letter-spacing:-.02em}
.stats{display:flex;flex-wrap:wrap;gap:8px 26px}
.stat .k{font:600 12px var(--display);letter-spacing:.1em;text-transform:uppercase;color:var(--board-muted)}
.stat .v{font:500 22px var(--mono)}
.stat .s{font:11.5px var(--mono);color:var(--board-muted)}
.meters{display:grid;grid-template-columns:1fr 1fr;gap:12px 20px;margin-top:16px}
.meter .k{display:flex;justify-content:space-between;font:600 12px var(--display);letter-spacing:.1em;text-transform:uppercase;color:var(--board-muted)}
.meter .k b{font:500 12px var(--mono);letter-spacing:0;color:var(--board-ink)}
.meter .t{height:6px;border-radius:3px;background:rgba(255,255,255,.12);margin-top:5px;overflow:hidden}
.meter .t i{display:block;height:100%;background:var(--accent);border-radius:3px}
.side{border-left:1px solid rgba(255,255,255,.14);padding-left:24px;display:flex;flex-direction:column;gap:14px}
.side .mid{font:500 30px/1.1 var(--mono)}
.side .s{font:12px var(--mono);color:var(--board-muted)}
.side a{color:#9cc5f5}

/* sections and cards */
.block{display:flex;flex-direction:column;gap:12px;min-width:0}
.sechead{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:flex-end;justify-content:space-between}
.card{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:16px 18px;min-width:0;box-shadow:var(--shadow)}
.card h2{margin-bottom:2px}
.stack{display:flex;flex-direction:column;gap:16px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:16px}
.filters{display:flex;gap:6px;flex-wrap:wrap}
.filters button{font:600 13px var(--display);letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);
  background:var(--surface);color:var(--ink2);padding:5px 12px;border-radius:5px;cursor:pointer}
.filters button:hover{border-color:var(--accent);color:var(--accent)}
.filters button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line)}
.tabs button{font:600 15px var(--display);letter-spacing:.06em;text-transform:uppercase;background:none;border:0;border-bottom:3px solid transparent;
  color:var(--muted);padding:8px 14px;cursor:pointer;margin-bottom:-1px}
.tabs button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent)}
.tabs button:hover{color:var(--ink)}
.tabpane{display:flex;flex-direction:column;gap:28px}

/* games and picks */
.games{display:flex;flex-direction:column;gap:10px}
.game{background:var(--surface);border:1px solid var(--line);border-radius:8px;overflow:hidden;box-shadow:var(--shadow)}
.game>header{display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;padding:9px 14px;background:var(--raised);border-bottom:1px solid var(--line)}
.game .at{color:var(--muted);font-size:14px;font-weight:500}
.ko{font:12px var(--mono);color:var(--ink2);margin-left:auto}
.picks{list-style:none;margin:0;padding:0}
.pick,.colhead{display:grid;grid-template-columns:minmax(150px,1.3fr) minmax(190px,1.4fr) 60px 156px 100px;gap:4px 14px;align-items:center}
.pick{padding:10px 14px;border-top:1px solid var(--line)}
.pick:first-child{border-top:0}
.pick .name{font-weight:600}.pick .team{color:var(--muted);font:12px var(--mono);margin-left:8px}
.side-pill{font:600 12.5px var(--display);letter-spacing:.07em;text-transform:uppercase;padding:1px 7px;border-radius:3px;border:1px solid var(--line);color:var(--ink2)}
.side-pill.over{color:var(--accent);border-color:var(--accent)}
.line{font:500 15px var(--mono)}.mkt{color:var(--ink2)}
.price{font:500 14px var(--mono);text-align:right}
.probs{display:grid;grid-template-columns:repeat(3,1fr);font:12.5px var(--mono);color:var(--ink2);text-align:right;font-variant-numeric:tabular-nums}
.probs span:last-child{color:var(--accent);font-weight:600}
.res{display:flex;flex-direction:column;align-items:flex-end;gap:2px}
.actual{font:11px var(--mono);color:var(--muted)}
.news{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:4px 8px;align-items:baseline}
.detail{color:var(--ink2);font-size:13px}
details.why{grid-column:1/-1;font-size:13.5px;color:var(--ink2)}
details.why summary{font:600 12.5px var(--display);letter-spacing:.07em;text-transform:uppercase;color:var(--accent);cursor:pointer;width:max-content}
details.why ul{margin:6px 0 2px;padding-left:18px;display:flex;flex-direction:column;gap:3px;max-width:90ch}
.none{padding:12px 14px;color:var(--muted)}
.colhead{padding:0 14px;font:600 12px var(--display);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.colhead .p{display:grid;grid-template-columns:repeat(3,1fr);text-align:right}.colhead .r{text-align:right}
.game.quiet .nopick{list-style:none;margin:0;padding:8px 14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:2px 18px}
.nopick li{display:flex;justify-content:space-between;gap:8px;color:var(--ink2);font-size:14px}
.game.quiet .note{padding:0 14px 10px;margin:0}.game.quiet h3{color:var(--ink2)}
.chip{display:inline-block;font:600 12px var(--display);letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:3px;white-space:nowrap}
.chip.win{background:var(--good-bg);color:var(--good)}.chip.loss{background:var(--bad-bg);color:var(--bad)}
.chip.idle,.chip.state{background:var(--idle-bg);color:var(--ink2)}.chip.flag,.chip.warn{background:var(--warn-bg);color:var(--warn-ink)}
.chip.state.open{background:var(--accent-soft);color:var(--accent)}.chip.tag{background:var(--accent-soft);color:var(--accent)}

/* charts */
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12.5px;color:var(--ink2);margin:8px 0 4px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px;vertical-align:-1px}
.legend .k1{border:2px solid var(--ink2)}.legend .k2{background:var(--accent)}.legend .k3{width:3px;border-radius:2px;height:13px;background:var(--muted)}
.legend .kp{border-radius:2px;background:var(--accent)}.legend .kn{border-radius:2px;background:var(--neg)}
.chart{width:100%;height:auto;display:block;overflow:visible}
.chart.edge{max-width:820px}
.chart .grid{stroke:var(--grid);stroke-width:1}.chart .zero{stroke:var(--muted);stroke-width:1}.chart .mid{stroke:var(--line);stroke-width:1}
.chart .tick{fill:var(--muted);font:11.5px var(--mono)}
.chart .rowl{fill:var(--ink);font:600 13px var(--body)}.chart .rows{fill:var(--muted);font:11px var(--mono)}
.chart .hit{fill:transparent}
.chart .gap{stroke:var(--accent);stroke-width:2;opacity:.4;stroke-linecap:round}
.chart .be{fill:var(--surface);stroke:var(--ink2);stroke-width:2}
.chart .md{fill:var(--accent);stroke:var(--surface);stroke-width:2}
.chart .mk{fill:var(--muted)}
.chart .ln{fill:none;stroke:var(--accent);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .area{fill:var(--accent);opacity:.1}
.chart .end{fill:var(--accent);stroke:var(--surface);stroke-width:2}
.chart .endl,.chart .capl{fill:var(--ink);font:600 12px var(--mono)}
.chart .xh{stroke:var(--ink2);stroke-width:1;opacity:0}
.chart .dot{stroke:var(--surface);stroke-width:2}.chart .dot.w{fill:var(--accent)}.chart .dot.l{fill:var(--neg)}
.chart .pos{fill:var(--accent)}.chart .neg{fill:var(--neg)}
.chart [data-tip]{outline:none;cursor:default}
.chart .pt:hover .xh,.chart .pt:focus .xh{opacity:.5}
.chart .row:hover .hit,.chart .row:focus .hit,.chart .col:hover .hit,.chart .col:focus .hit{fill:var(--accent-soft);opacity:.45}
.tip{position:fixed;z-index:10;pointer-events:none;background:var(--raised);color:var(--ink);border:1px solid var(--line);border-radius:6px;
  padding:7px 10px;font:12.5px/1.4 var(--body);box-shadow:0 4px 14px rgba(0,0,0,.18);max-width:300px}
.tip strong{display:block;font:600 13px var(--mono)}

/* tables */
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th{font:600 12px var(--display);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:middle}
tbody tr:last-child td{border-bottom:0}
table.num td{white-space:nowrap}
table.num td:not(:first-child),table.num th:not(:first-child){text-align:right;font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums}
table.bd td:not(:first-child){font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}
table.bd td:first-child{font-weight:500}
.wb,.ub{display:flex;align-items:center;gap:8px}
.wb .track,.ub .track{position:relative;width:140px;height:8px;border-radius:4px;background:var(--idle-bg);flex:none}
.wb i{position:absolute;left:0;top:0;bottom:0;border-radius:4px}
.wb i.ok{background:var(--accent)}.wb i.short{background:var(--muted)}
.wb b{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink);border-radius:1px}
.ub .track::after{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--muted)}
.ub i{position:absolute;top:0;bottom:0;border-radius:4px}.ub i.pos{background:var(--accent)}.ub i.neg{background:var(--neg)}
.wb .v,.ub .v{min-width:48px;text-align:right}
details.old{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 14px}
summary{cursor:pointer;font:600 17px var(--display);letter-spacing:.03em}
details.old .picks{margin-top:8px}
.foot{color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:14px}
.foot ul{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:4px}
@media (max-width:820px){
  .board{grid-template-columns:1fr}
  .side{border-left:0;border-top:1px solid rgba(255,255,255,.14);padding-left:0;padding-top:14px}
}
@media (max-width:760px){
  .colhead{display:none}
  .pick{grid-template-columns:1fr auto;grid-template-areas:"who price" "bet res" "probs probs"}
  .pick .who{grid-area:who}.pick .bet{grid-area:bet}.pick .price{grid-area:price}.pick .probs{grid-area:probs}
  .pick .res{grid-area:res}
  .probs{text-align:left;max-width:280px}
  .probs span:nth-child(1)::before{content:"BE ";color:var(--muted)}.probs span:nth-child(2)::before{content:"Mkt ";color:var(--muted)}
  .probs span:nth-child(3)::before{content:"Model ";color:var(--muted)}
  .ko{margin-left:0}.big{font-size:52px}
  .wb .track,.ub .track{width:70px}
}
@media (prefers-reduced-motion:no-preference){.meter .t i{transition:width .5s}}
"""

JS = """
(function(){
  var bs=document.querySelectorAll('.filters button');
  function apply(mode){
    document.querySelectorAll('#week .pick').forEach(function(p){
      var a=p.getAttribute('data-against')==='1';
      p.hidden=(mode==='flagged'&&!a)||(mode==='clear'&&a);
    });
    document.querySelectorAll('#week .game:not(.quiet)').forEach(function(g){
      g.hidden=!g.querySelector('.pick:not([hidden])');
    });
    var q=document.querySelector('#week .game.quiet');if(q)q.hidden=mode==='flagged';
    bs.forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-mode')===mode?'true':'false')});
    try{localStorage.setItem('s1-filter',mode)}catch(e){}
  }
  bs.forEach(function(b){b.addEventListener('click',function(){apply(b.getAttribute('data-mode'))})});
  var m='all';try{m=localStorage.getItem('s1-filter')||'all'}catch(e){}
  apply(m);
  // tabs (remembered per viewer; #ats deep-links)
  var tabs=document.querySelectorAll('.tabs button');
  function show(t){
    tabs.forEach(function(b){b.setAttribute('aria-selected',b.getAttribute('data-tab')===t?'true':'false')});
    document.querySelectorAll('.tabpane').forEach(function(p){p.hidden=p.id!=='tab-'+t});
    try{localStorage.setItem('tab',t)}catch(e){}
  }
  tabs.forEach(function(b){b.addEventListener('click',function(){show(b.getAttribute('data-tab'))})});
  var t0=(location.hash==='#ats')?'ats':'s1';try{if(location.hash!=='#ats'){t0=localStorage.getItem('tab')||'s1'}}catch(e){}
  show(t0);
  // one tooltip for every chart mark: "headline | detail"
  var tip=document.createElement('div');tip.className='tip';tip.hidden=true;document.body.appendChild(tip);
  function show(el,x,y){
    var t=(el.getAttribute('data-tip')||'').split(' | ');
    tip.textContent='';var s=document.createElement('strong');s.textContent=t[1]||t[0];tip.appendChild(s);
    if(t[1]){var d=document.createElement('span');d.textContent=t[0];tip.appendChild(d);}
    tip.hidden=false;
    var w=tip.offsetWidth,h=tip.offsetHeight,vw=window.innerWidth;
    tip.style.left=Math.max(8,Math.min(vw-w-8,x+14))+'px';tip.style.top=Math.max(8,y-h-12)+'px';
  }
  document.querySelectorAll('[data-tip]').forEach(function(el){
    el.addEventListener('pointermove',function(e){show(el,e.clientX,e.clientY)});
    el.addEventListener('pointerleave',function(){tip.hidden=true});
    el.addEventListener('focus',function(){var r=el.getBoundingClientRect();show(el,r.left+r.width/2,r.top)});
    el.addEventListener('blur',function(){tip.hidden=true});
  });
})();
"""


def meter(k: str, n: int, of: int) -> str:
    return (f'<div class="meter"><div class="k"><span>{esc(k)}</span><b>{n} of {of}</b></div>'
            f'<div class="t" role="progressbar" aria-valuemin="0" aria-valuemax="{of}" aria-valuenow="{n}" aria-label="{esc(k)}">'
            f'<i style="width:{min(n / of, 1) * 100:.0f}%"></i></div></div>')


def stat(k: str, v: str, s: str = "") -> str:
    return f'<div class="stat"><div class="k">{esc(k)}</div><div class="v">{v}</div>' + (f'<div class="s">{esc(s)}</div>' if s else "") + '</div>'


def build(data: dict, now: dt.datetime | None = None) -> str:
    now = now or Lv.now_utc()
    rec, picks, runs, live = data["rec"], data["picks"], data["runs"], data["live"]
    rec = with_probs(rec)
    tot = summarize(rec)
    n_all = rec.height
    weeks_graded = rec.filter(pl.col("result").is_in(["W", "L"])).select(pl.col("week").n_unique()).item() if n_all else 0
    ci = week_ci(rec) if n_all else None
    cur_week = int(runs["week"].cast(pl.Int64).max()) if runs.height else None
    pa_raw = data.get("pa_rec", pl.DataFrame())
    pa = prep(pa_raw) if pa_raw.height else pa_raw
    if pa.height:                                  # the ParlayAPI record can reach a week before Action Network posts
        cur_week = int(pa["week"].max()) if cur_week is None else max(cur_week, int(pa["week"].max()))
    last_run = runs["run_utc"].max() if runs.height else None
    stats = data["stats"] if "stats" in data else load_stats()

    # ---- scoreboard
    rec_txt = f'{tot["W"]}-{tot["L"]}' + (f'-{tot["P"]}' if tot["P"] else "")
    pat = summarize(pa) if pa.height else None
    board = (
        '<section class="board" aria-label="Season record">'
        '<div><p class="eyebrow">Official S1 · 2026 season</p>'
        f'<div class="hero"><div class="big">{rec_txt}</div><div class="stats">'
        + stat("Win rate", fmt_pct(tot["win"]), f'break-even {fmt_pct(tot["be"])}' if tot["be"] is not None else "no graded picks")
        + stat("Units", fmt_units(tot["units"]) if tot["n"] else "–", "1 unit per pick")
        + stat("ROI", fmt_pct(tot["roi"], 1, True), f'95% {fmt_pct(ci[0], 0, True)} to {fmt_pct(ci[1], 0, True)}' if ci else "interval after 3 weeks")
        + '</div></div>'
        f'<div class="meters">{meter("Bets graded", tot["n"], PASS_N)}{meter("Weeks with a result", weeks_graded, PASS_WEEKS)}</div></div>'
        '<div class="side">'
        + ('<div><p class="eyebrow">S1 on ParlayAPI lines</p>'
           f'<div class="mid">{pat["W"]}-{pat["L"]}' + (f'-{pat["P"]}' if pat["P"] else "") + '</div>'
           f'<div class="s">{fmt_units(pat["units"]) + " units · " if pat["n"] else ""}{pat["pending"]} open · <a href="#parlay">picks</a></div></div>'
           if pat else "")
        + f'<div><p class="eyebrow">2025, same rule</p><div class="mid">{REF["w"]}-{REF["l"]}</div>'
        f'<div class="s">ROI {fmt_pct(REF["roi"], 1, True)} · 95% {fmt_pct(REF["lo"], 0, True)} to {fmt_pct(REF["hi"], 0, True)}</div></div>'
        '</div></section>')

    # ---- current week, official
    cur = rec.filter(pl.col("week") == cur_week) if n_all and cur_week is not None else rec.head(0)
    games = []
    if runs.height and cur_week is not None:
        games = runs.filter(pl.col("week") == str(cur_week)).sort("run_utc", descending=True).unique("an_game_id", keep="first") \
            .sort("start_time").to_dicts()
    blocks, quiet = [], []
    for g in games:
        rows = cur.filter(pl.col("an_game_id") == g["an_game_id"]).sort("player").to_dicts() if cur.height else []
        rows = with_why(rows, live, "an", stats)
        (blocks.append(game_block(g, rows, now)) if rows else quiet.append(g))
    if quiet:
        blocks.append('<section class="game quiet"><header><h3>No picks</h3></header><ul class="nopick">' + "".join(
            f'<li><span>{esc(g["away"])} at {esc(g["home"])}</span><span class="ko">{fmt_dt(g["start_time"])} ET</span></li>' for g in quiet) +
            '</ul><p class="note">None of these games had a prop where all four signals agreed at the latest run.</p></section>')
    n_open = sum(1 for g in games if Lv.parse_ts(g["start_time"]) > now)
    n_flag = sum(1 for r in cur.to_dicts() if r.get("inj_against") == "true" or r.get("depth_against") == "true") if cur.height else 0
    if cur_week is None:
        week_html = '<p class="empty">No runs yet.</p>'
    elif not games:
        week_html = (f'<section class="block" id="week"><div class="sechead"><div><p class="eyebrow">Official S1 · Action Network lines</p>'
                     f'<h2>Week {cur_week}: waiting for Action Network</h2></div></div>'
                     '<p class="lede">Action Network has not posted this week\'s player props yet, so official S1 has nothing to score. '
                     'The ParlayAPI record below already covers this week.</p></section>')
    else:
        week_html = (
            f'<section class="block" id="week"><div class="sechead"><div><p class="eyebrow">Official S1 · Action Network lines</p>'
            f'<h2>Week {cur_week}: {cur.height} picks in {len(games) - len(quiet)} of {len(games)} games</h2></div>'
            f'<div class="filters" role="group" aria-label="Filter picks">'
            f'<button type="button" data-mode="all" aria-pressed="true">All</button>'
            f'<button type="button" data-mode="flagged" aria-pressed="false">News against ({n_flag})</button>'
            f'<button type="button" data-mode="clear" aria-pressed="false">No news against</button></div></div>'
            f'<p class="lede">{n_open} of {len(games)} games have not kicked off; their picks can change until the last run before kickoff. '
            'BE is the break-even for the price, Mkt is DraftKings de-vigged, Model is the simulator.</p>'
            f'{COLHEAD}<div class="games">{"".join(blocks)}</div></section>')

    # ---- charts
    edge_rows = [dict(r, _tag="official S1") for r in cur.to_dicts() if r["result"] == "pending" and Lv.parse_ts(r["start_time"]) > now] if cur.height else []
    if pa.height:
        edge_rows += [dict(r, _tag="ParlayAPI") for r in pa.filter(pl.col("week") == cur_week).to_dicts()
                      if r["result"] == "pending" and Lv.parse_ts(r["start_time"]) > now]
    charts = (
        '<section class="block"><div class="sechead"><div><p class="eyebrow">Official S1</p><h2>Season so far</h2></div></div>'
        '<div class="grid2"><div class="card"><h3>Cumulative units</h3><p class="note" style="margin-top:2px">One step per graded pick, in kickoff order. Hover a pick for its result.</p>'
        '<div class="legend"><span><i class="k2"></i>Won</span><span><i style="background:var(--neg)"></i>Lost</span></div>'
        + chart_units(rec) + '</div>'
        '<div class="card"><h3>Units by week</h3><p class="note" style="margin-top:2px">Each column is one graded week, at the DraftKings price recorded with the pick.</p>'
        '<div class="legend"><span><i class="kp"></i>Up</span><span><i class="kn"></i>Down</span></div>'
        + chart_weeks(rec) + '</div></div></section>'
        '<section class="card"><p class="eyebrow">Both records · open picks</p><h2>Model against price</h2>'
        '<p class="note" style="margin-top:2px">A pick has value by the model\'s own numbers when the filled dot sits right of the ring. '
        'Backtests found the model\'s extreme probabilities land near 50%, so long gaps are weaker than they look.</p>'
        '<div class="legend"><span><i class="k1"></i>Break-even for the price</span><span><i class="k3"></i>DraftKings, de-vigged</span>'
        '<span><i class="k2"></i>Model</span></div>' + chart_edge(edge_rows) + '</section>')

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
            '<section class="block"><div class="sechead"><div><p class="eyebrow">Official S1</p><h2>Record by group</h2></div></div>'
            f'<p class="lede">The black tick on each win bar is the break-even for the prices taken. Fewer than {PASS_N} graded bets in a row is too few to read; '
            'pushes and voids (player did not play) take no units.</p>'
            '<div class="stack"><div class="card"><h3>By prop</h3>' + breakdown(rec, None, mk) + '</div>'
            '<div class="card"><h3>By news flag</h3>' + breakdown(rec, None, fl) +
            '<p class="note">Flags are descriptive. S1 still records flagged picks; dropping them would be a new rule that needs its own pre-registration.</p></div>'
            '<div class="card"><h3>Over and under</h3>' + breakdown(rec, None, sd) + '</div>'
            '<div class="card"><h3>By week</h3>' + breakdown(rec, None, wk) + '</div></div></section>')
    else:
        breakdowns = ""

    # ---- changes between runs, run log, second source
    ch = changes(picks, runs, cur_week, now) if cur_week is not None else []
    if ch:
        rows = []
        for c in ch:
            price = f'{c["odds_first"]:+.0f}' if c["odds_first"] == c["odds_last"] else f'{c["odds_first"]:+.0f} → {c["odds_last"]:+.0f}'
            line = f'{c["line_first"]:g}' if c["line_first"] == c["line_last"] else f'{c["line_first"]} → {c["line_last"]}'
            rows.append([esc(c["game"]), esc(c["player"]), f'{esc(c["side"])} {line} {esc(MARKET.get(c["market"], c["market"]))}', price,
                         f'{c["n_seen"]} of {c["n_runs"]}', chip("win", "kept") if c["kept"] else chip("idle", "dropped")])
        kept = sum(1 for c in ch if c["kept"])
        stab_html = (f'<div class="card"><h3>Pick stability, week {cur_week}</h3><p class="note" style="margin-top:2px">{len(ch)} different picks appeared; '
                     f'{kept} are in the deciding run and {len(ch) - kept} dropped out as lines, prices or injury news moved.</p>'
                     + table(["Game", "Player", "Bet", "Price first → now", "Runs", "Deciding run"], rows) + '</div>')
    else:
        stab_html = ""
    rl = run_log(picks, runs, live)
    if rl:
        rows = []
        for r in rl[:12]:
            def ok(b):
                return "n/a" if not r["flags_era"] else ("✓" if b else '<span style="color:var(--bad)">missing</span>')
            rows.append([esc(fmt_dt(r["run"])), str(r["games"]), str(r["props"]), str(r["picks"]),
                         "–" if r["lead"] is None else f'{r["lead"] / 60:.1f} h' if r["lead"] >= 90 else f'{r["lead"]:.0f} min',
                         ok(r["inj"]), ok(r["depth"])])
        runs_html = ('<div class="card"><h3>Run log, official S1</h3>' + table(["Run (ET)", "Games", "Props", "Picks", "To kickoff", "Injuries", "Depth"], rows, "num") +
                     '<p class="note">A late run has fewer games left to score. The injury and depth responses are saved with every run.</p></div>')
    else:
        runs_html = ""
    pc = parlay_card(data.get("pcmp", pl.DataFrame()))
    ops = [x for x in (pc, openmarkets_card(data.get("ocmp", pl.DataFrame())), runs_html) if x]
    ops_html = (('<section class="block"><div class="sechead"><div><p class="eyebrow">Runs and sources</p><h2>How the picks were made</h2></div></div>'
                 + (stab_html if stab_html else "") + (f'<div class="stack">{"".join(ops)}</div>' if ops else "") + '</section>')
                if stab_html or ops else "")

    # ---- earlier weeks
    old = []
    if n_all:
        for (w,), x in sorted(rec.group_by("week"), key=lambda kv: -kv[0][0]):
            if w == cur_week:
                continue
            s = summarize(x)
            rows = "".join(pick_row(r, True) for r in with_why(x.sort("start_time", "player").to_dicts(), live, "an", stats))
            old.append(f'<details class="old"><summary>Week {w}: {s["W"]}-{s["L"]}' + (f'-{s["P"]}' if s["P"] else "")
                       + f', {fmt_units(s["units"])} units</summary><ul class="picks">{rows}</ul></details>')

    stamp = f'Built {fmt_dt(now.strftime("%Y-%m-%dT%H:%M:%SZ"))} ET' + (f' · last official run {fmt_dt(last_run)} ET' if last_run else "")
    foot = (
        '<footer class="foot"><ul>'
        f'<li>Rule S1: DraftKings props where the disagree, projection, simulator and price signals all point the same way. Locked before the season; '
        f'<a href="{REPO}docs/s1_live_rules.md">tracker rules</a> · <a href="{REPO}docs/simulator_confirm.md">season test</a>.</li>'
        f'<li>Season test: pass only if at least {PASS_N} bets in at least {PASS_WEEKS} weeks and the week-clustered ROI interval has its lower end above 0. This page does not decide that.</li>'
        f'<li>Weekly recaps (why each pick landed where it did): <a href="{REPO}docs/recaps/">docs/recaps</a>, written after each week is graded.</li>'
        '<li>The official pick for a game is the last run before kickoff. Nothing is edited after kickoff. A player who does not play is void.</li>'
        '<li>Results come from nflverse player stats and snap counts, which can lag a game by hours. Injury news is ESPN at the time of each run, saved in <code>data/live/injuries</code>.</li>'
        '</ul></footer>')

    return (
        '<title>S1 Live Tracker</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&amp;family=Barlow+Condensed:wght@500;600&amp;family=IBM+Plex+Mono:wght@400;500;600&amp;display=swap">'
        f'<style>{CSS}</style>'
        '<div class="wrap">'
        f'<header class="top"><div><h1>S1 Live Tracker</h1><p class="sub">2026 NFL player props · rule S1, all four signals agree</p></div>'
        f'<div class="stamp">{esc(stamp)}</div></header>'
        '<div class="notice">Unvalidated rule. These are tracker records of what S1 selected, not recommendations.</div>'
        '<nav class="tabs" role="tablist"><button type="button" role="tab" data-tab="s1" aria-selected="true">Player props (S1)</button>'
        '<button type="button" role="tab" data-tab="ats" aria-selected="false">Spreads (ATS)</button></nav>'
        f'<div class="tabpane" id="tab-ats" hidden>{ats_section(data.get("ats_runs", pl.DataFrame()), data.get("ats_rec", pl.DataFrame()), now)}</div>'
        f'<div class="tabpane" id="tab-s1">{board}{week_html}{pa_section(pa_raw, rec, now, live, stats)}{charts}{breakdowns}{ops_html}'
        + ('<section class="block"><div class="sechead"><div><p class="eyebrow">Official S1</p><h2>Earlier weeks</h2></div></div><div class="games">' + "".join(old) + "</div></section>" if old else "")
        + '</div>'
        + f'{foot}</div><script>{JS}</script>')


def write(now: dt.datetime | None = None, out: Path | None = None) -> Path:
    out = out or OUT
    out.write_text(build(load(), now))
    return out
