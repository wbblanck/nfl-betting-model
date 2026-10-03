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

from nflbet import config, injuries as Inj, live as Lv, props as P

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
    when = Lv.now_utc()
    picks, log = Lv.run(SEASON, tmp, when)
    picks = with_injuries(picks, week, when)
    arch = Lv.LIVE / "lines" / f"{when.strftime('%Y%m%dT%H%MZ')}_w{week}.csv.gz"
    arch.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "rb") as f, gzip.open(arch, "wb") as g:
        shutil.copyfileobj(f, g)
    Lv.append(picks, PICKS)
    Lv.append(log, RUNS)
    print(f"week {week}: {log.height} games not yet started, {int(log['props_scored'].sum())} props scored, "
          f"{picks.height} S1 picks")
    for r in picks.sort("start_time").iter_rows(named=True):
        print(f"  {r['away']}@{r['home']}  {r['player']:24s} {r['market']:12s} {r['side']:5s} {r['line']:6} {r['odds']:+.0f}"
              f"  {'INJURY NEWS AGAINST ' if r['inj_against'] else ''}{r['inj_self'] or ''} {r['inj_teammates'] or ''}")


def with_injuries(picks: pl.DataFrame, week: int, when: dt.datetime) -> pl.DataFrame:
    """Descriptive injury flag (src/nflbet/injuries.py); the ESPN response is archived. A failed fetch leaves the
    flag empty and never stops the run."""
    try:
        body = Inj.fetch()
        arch = Lv.LIVE / "injuries" / f"{when.strftime('%Y%m%dT%H%MZ')}_w{week}.json.gz"
        arch.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(arch, "wt") as f:
            json.dump(body, f)
        return Inj.flag(picks, Inj.parse(body), Inj.espn_ids(), Inj.recent_players(SEASON, week))
    except Exception as e:  # noqa: BLE001 - the picks still count; only the flag is missing
        print(f"injury flag unavailable: {type(e).__name__}: {e}")
        return picks.with_columns(pl.lit("fetch failed").alias("inj_self"), pl.lit(None, pl.Utf8).alias("inj_teammates"),
                                  pl.lit(None, pl.Boolean).alias("inj_against"))


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
    final_games = set(g.join(final, on=["week", "home_team", "away_team"])["an_game_id"].to_list())
    st = P.load_stats(SEASON)
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
    if "inj_against" in d.columns:
        lines += ["", "Injury flag (from 2026-10-03; descriptive, S1 unchanged): ESPN statuses at the pick's run. "
                  "**Against** = an under whose teammate at the same position is Out / Doubtful / IR, or an over whose "
                  "player is himself listed."]
        for lab, x in (("Injury news against", d.filter(pl.col("inj_against") == "true")),
                       ("No injury news against", d.filter(pl.col("inj_against") == "false"))):
            r = Lv.record(x)
            lines.append(f"- {lab}: {r['W']}-{r['L']}-{r['P']}" +
                         (f", {r['units']:+.2f} units" if r["W"] + r["L"] else "") + f" (pending {r['pending']})")
    else:
        d = d.with_columns(*[pl.lit(None, pl.Utf8).alias(c) for c in Inj.FLAG_COLS])
    lines += ["", "## Picks", "", "| Week | Game | Player | Prop | Side | Line | Odds | Injury news at pick | Result |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in d.sort("week", "start_time", "player", descending=[True, False, False]).iter_rows(named=True):
        news = "; ".join(x for x in (f"self: {r['inj_self']}" if r["inj_self"] else "", r["inj_teammates"] or "") if x)
        news = ("**Against** — " if r["inj_against"] == "true" else "") + news if r["inj_against"] is not None \
            else (r["inj_self"] or "not checked")
        lines.append(f"| {r['week']} | {r['away']}@{r['home']} | {r['player']} | {r['market']} | {r['side']} | {r['line']} | "
                     f"{int(r['odds']):+d} | {news} | {r['result']} |")
    (config.ROOT / "docs" / "s1_live.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))


if __name__ == "__main__":
    {"run": do_run, "grade": do_grade}[sys.argv[1]]()
