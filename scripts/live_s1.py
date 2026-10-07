"""S1 live tracker (docs/s1_live_rules.md).

  python scripts/live_s1.py run     # fetch this week's lines, record S1 picks for games not yet started
  python scripts/live_s1.py grade   # settle official picks, write docs/s1_live.md and the season record
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import shutil
import subprocess
import sys

import polars as pl

from nflbet import config, depth as D, injuries as Inj, live as Lv, props as P

SEASON = 2026
PICKS = Lv.LIVE / f"s1_picks_{SEASON}.csv"
RUNS = Lv.LIVE / f"s1_runs_{SEASON}.csv"


def do_run() -> None:
    week = Lv.current_week(SEASON)
    if week is None:
        print("season over"); return
    tmp = Lv.LIVE / "tmp" / "an_props_live.csv"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(config.ROOT / "scripts" / "fetch" / "an_props.py"), "--season", str(SEASON),
                    "--weeks", f"{week}-{week}", "--out", str(tmp)], check=True)
    with open(tmp) as f:
        n_rows = sum(1 for _ in f) - 1                                  # header excluded
    if n_rows <= 0:                                                      # books have not posted this week's props yet
        print(f"week {week}: Action Network has no player props posted yet; nothing to score (not an error)")
        return
    when = Lv.now_utc()
    arch = Lv.LIVE / "lines" / f"{when.strftime('%Y%m%dT%H%MZ')}_w{week}.csv.gz"   # saved first: a failed run leaves its input
    arch.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "rb") as f, gzip.open(arch, "wb") as g:
        shutil.copyfileobj(f, g)
    picks, log = Lv.run(SEASON, tmp, when)
    picks = with_news(picks, week, when)
    Lv.append(picks, PICKS)
    Lv.append(log, RUNS)
    print(f"week {week}: {log.height} games not yet started, {int(log['props_scored'].sum())} props scored, "
          f"{picks.height} S1 picks")
    for r in picks.sort("start_time").iter_rows(named=True):
        print(f"  {r['away']}@{r['home']}  {r['player']:24s} {r['market']:12s} {r['side']:5s} {r['line']:6} {r['odds']:+.0f}"
              f"  {'INJURY NEWS AGAINST ' if r['inj_against'] else ''}{r['inj_self'] or ''} {r['inj_teammates'] or ''}"
              f"  {'DEPTH CHART AGAINST ' if r['depth_against'] else ''}{r['depth_note'] or ''}")


def _archive(body, kind: str, week: int, when: dt.datetime) -> None:
    arch = Lv.LIVE / kind / f"{when.strftime('%Y%m%dT%H%MZ')}_w{week}.json.gz"
    arch.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(arch, "wt") as f:
        json.dump(body, f)


def with_news(picks: pl.DataFrame, week: int, when: dt.datetime) -> pl.DataFrame:
    """Descriptive flags (src/nflbet/injuries.py, src/nflbet/depth.py) from ESPN at run time; responses are
    archived. A failed fetch leaves that flag empty and never stops the run: the picks still count."""
    inj = None
    try:
        body = Inj.fetch()
        _archive(body, "injuries", week, when)
        inj = Inj.parse(body)
        picks = Inj.flag(picks, inj, Inj.espn_ids(), Inj.recent_players(SEASON, week))
    except Exception as e:  # noqa: BLE001
        print(f"injury flag unavailable: {type(e).__name__}: {e}")
        picks = picks.with_columns(pl.lit("fetch failed").alias("inj_self"), pl.lit(None, pl.Utf8).alias("inj_teammates"),
                                   pl.lit(None, pl.Boolean).alias("inj_against"))
    try:
        if inj is None:
            raise RuntimeError("needs the injury list")
        charts = D.fetch(SEASON)
        _archive(charts, "depth", week, when)
        ch = D.changes(D.parse(charts), inj, D.players_table(), D.recent_usage(SEASON, week))
        print("depth-chart changes:", [f"{r['team']} {r['pos']}: {r['starter_name']} over {r['leader_name']}" for r in ch.iter_rows(named=True)])
        picks = D.flag(picks, ch)
    except Exception as e:  # noqa: BLE001
        print(f"depth flag unavailable: {type(e).__name__}: {e}")
        picks = picks.with_columns(pl.lit("fetch failed").alias("depth_note"), pl.lit(None, pl.Boolean).alias("depth_against"))
    return picks


def news(r: dict) -> str:
    """One cell: injury and depth-chart news recorded at the pick's run (string fields as read back from the CSV)."""
    if r["inj_against"] is None:
        inj = f"injuries {r['inj_self'] or 'not checked'}"
    else:
        inj = "; ".join(x for x in (f"self: {r['inj_self']}" if r["inj_self"] else "", r["inj_teammates"] or "") if x)
        inj = ("**Injury against** — " + inj) if r["inj_against"] == "true" else inj
    if r["depth_against"] is None:
        dep = f"depth chart {r['depth_note'] or 'not checked'}"
    else:
        dep = ("**Depth chart against** — " + (r["depth_note"] or "")) if r["depth_against"] == "true" else (r["depth_note"] or "")
    return "; ".join(x for x in (inj, dep) if x)


def do_grade() -> None:
    import nflreadpy as nfl

    if not PICKS.exists():
        print("no picks yet"); return
    picks = pl.read_csv(PICKS, infer_schema_length=0)
    runs = pl.read_csv(RUNS, infer_schema_length=0)
    off = Lv.official(picks, runs)
    sched = nfl.load_schedules(seasons=[SEASON]).filter(pl.col("game_type") == "REG")
    fix = lambda c: pl.col(c).replace(P.TEAM_FIX)  # noqa: E731
    final = sched.filter(pl.col("result").is_not_null()).select("week", "home_team", "away_team")
    g = runs.select("an_game_id", pl.col("week").cast(pl.Int32), fix("home").alias("home_team"), fix("away").alias("away_team")).unique()
    st = P.load_stats(SEASON)
    final_games = Lv.gradable(g, final, set(zip(st["week"].cast(pl.Int32).to_list(), st["team"].to_list())))
    long = st.unpivot(index=["player_id", "week"], on=list(P.STAT), variable_name="market", value_name="actual") \
        .with_columns(pl.col("week").cast(pl.Int64), pl.col("actual").cast(pl.Float64))
    sn = P.load_snaps(SEASON)
    snap_keys = {(w, t, P.norm_name(n)) for w, t, n in zip(sn["week"], sn["team"], sn["player"])}
    played = {(r["player_id"], int(r["week"])) for r in off.iter_rows(named=True)
              if (int(r["week"]), P.TEAM_FIX.get(r["team"], r["team"]), P.norm_name(r["player"])) in snap_keys}
    d = Lv.settle(off, long, played, final_games).sort("start_time", "player")
    d.write_csv(Lv.LIVE / f"s1_record_{SEASON}.csv")
    tot = Lv.record(d)
    lines = [f"# S1 live tracker, {SEASON}", "",
             "Rule S1: bet only props where all four signals agree (docs/simulator_confirm.md). NOT validated: in 2025 it",
             "went 38-23 (+5.2%) on 61 bets, an interval of -16% to +27%. Official pick = the last run before kickoff.",
             f"Updated {Lv.now_utc().strftime('%Y-%m-%d %H:%M')} UTC.", "",
             f"**Season: {tot['W']}-{tot['L']}" + (f"-{tot['P']}" if tot["P"] else "") +
             (f", {tot['win_pct']:.1%} wins, {tot['units']:+.2f} units, ROI {tot['roi']:+.1%}" if tot["win_pct"] is not None else "") +
             f"** (pending {tot['pending']}, void {tot['void']})", "",
             "| Week | W-L-P | Win % | Units | ROI |", "|---|---|---|---|---|"]
    for (wk,), x in sorted(d.group_by(["week"]), key=lambda kv: int(kv[0][0])):
        r = Lv.record(x)
        if r["W"] + r["L"] + r["P"]:
            lines.append(f"| {wk} | {r['W']}-{r['L']}-{r['P']} | {r['win_pct']:.1%} | {r['units']:+.2f} | {r['roi']:+.1%} |"
                         if r["win_pct"] is not None else f"| {wk} | {r['W']}-{r['L']}-{r['P']} | | | |")
    for c in Inj.FLAG_COLS + D.FLAG_COLS:
        if c not in d.columns:
            d = d.with_columns(pl.lit(None, pl.Utf8).alias(c))
    lines += ["", "News flags (descriptive; S1 unchanged), from ESPN at the pick's run. **Injury against** = an under whose "
              "teammate at the same position is Out / Doubtful / IR, or an over whose player is himself listed (from "
              "2026-10-03). **Depth chart against** = the team's listed QB / RB starter differs from its recent usage "
              "leader, and the pick is an under on the new starter or an over on the old leader (from 2026-10-03)."]
    for lab, x in (("Injury against", d.filter(pl.col("inj_against") == "true")),
                   ("Depth chart against", d.filter(pl.col("depth_against") == "true")),
                   ("Neither flag against", d.filter(pl.col("inj_against") == "false", pl.col("depth_against") == "false"))):
        r = Lv.record(x)
        lines.append(f"- {lab}: {r['W']}-{r['L']}-{r['P']}" + (f", {r['units']:+.2f} units" if r["W"] + r["L"] else "")
                     + f" (pending {r['pending']})")
    lines += ["", "## Picks", "", "| Week | Game | Player | Prop | Side | Line | Odds | News at pick | Result |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in d.sort("week", "start_time", "player", descending=[True, False, False]).iter_rows(named=True):
        lines.append(f"| {r['week']} | {r['away']}@{r['home']} | {r['player']} | {r['market']} | {r['side']} | {r['line']} | "
                     f"{int(r['odds']):+d} | {news(r)} | {r['result']} |")
    (config.ROOT / "docs" / "s1_live.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))


if __name__ == "__main__":
    {"run": do_run, "grade": do_grade}[sys.argv[1]]()
