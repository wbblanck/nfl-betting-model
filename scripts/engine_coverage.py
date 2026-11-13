"""Engine phase 1 gate: what the warehouse holds and how well it joins. Counts and keys only; no outcome is modelled.
Writes docs/engine/coverage.md from data/cache/engine/ (run scripts/engine_ingest.py first)."""
import collections
import json

import polars as pl

from nflbet.config import ROOT
from nflbet.engine.data import nflverse as N, player_week as PW

OUT = ROOT / "docs" / "engine" / "coverage.md"


def main() -> None:
    man = json.loads(N.MANIFEST.read_text())
    by = collections.defaultdict(dict)
    for k, v in man.items():
        t, s = k.split("/")
        by[t][s] = v
    L = ["# Warehouse coverage (engine phase 1)", "",
         "Written by `scripts/engine_coverage.py` from the local warehouse (`data/cache/engine/`, not in git; rebuilt by",
         "`scripts/engine_ingest.py`). Counts and join keys only.", "", "## Sources", "",
         "| Table | Seasons held | Rows | Not published |", "|---|---|---|---|"]
    for t in sorted(by):
        ok = sorted(s for s, v in by[t].items() if v["status"] == "ok")
        bad = sorted(s for s, v in by[t].items() if v["status"] != "ok")
        span = "all" if ok == ["all"] else f"{ok[0]}-{ok[-1]} ({len(ok)})"
        L.append(f"| {t} | {span} | {sum(by[t][s]['rows'] for s in ok):,} | {', '.join(bad) or '-'} |")
    players = N.read("players")
    sched = N.read("schedules")
    L += ["", "## Player-week table (QB, RB, WR, TE; regular season)", "",
          "Stat rows plus a zero row for anyone with offensive snaps and no stat row. Snap counts start in 2013, so",
          "2010-2012 have stat rows only.", "",
          "| Season | Stat rows | Duplicate keys | Zero rows added | Snap rows | Snap rows with no player ID match | Stat rows with no snap row | Stat rows on that week's roster | Team agrees with roster | Games vs schedule |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    empty_snaps = pl.DataFrame(schema={"game_id": pl.Utf8, "season": pl.Int64, "game_type": pl.Utf8, "week": pl.Int64, "pfr_player_id": pl.Utf8,
                                       "position": pl.Utf8, "team": pl.Utf8, "opponent": pl.Utf8, "offense_snaps": pl.Float64, "offense_pct": pl.Float64})
    for season in N.SEASONS:
        stats = N.read("player_stats", [season])
        has_snaps = N.path("snap_counts", season).exists()
        snaps = N.read("snap_counts", [season]) if has_snaps else empty_snaps
        try:
            pw, rep = PW.build(stats, snaps, players)
            dups = 0
        except ValueError as e:
            L.append(f"| {season} | build refused: {e} | | | | | | | | |")
            continue
        ros = N.read("rosters_weekly", [season]).filter(pl.col("gsis_id").is_not_null()).select(
            pl.col("gsis_id").alias("player_id"), pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64), PW.team_code("team").alias("roster_team")).unique(subset=PW.KEY)
        st = pw.filter(pl.col("stat_row")).join(ros, on=PW.KEY, how="left")
        on = st.filter(pl.col("roster_team").is_not_null())
        agree = on.filter(pl.col("roster_team") == pl.col("team")).height
        games = pw["game_id"].n_unique()
        want = sched.filter(pl.col("season") == season, pl.col("game_type") == "REG").height
        L.append(f"| {season} | {rep['stat_rows']:,} | {dups} | {rep['zero_rows_added']:,} | {rep['snap_rows']:,} | "
                 f"{rep['snap_rows_unmapped']:,} | {rep['stat_rows_without_snaps']:,} | {on.height / st.height:.1%} | "
                 f"{agree / max(on.height, 1):.1%} | {games} / {want} |")
    L += ["", "## Injury report timestamps", "", "| Season | Rows | With `date_modified` | With a game status |", "|---|---|---|---|"]
    for season in N.SEASONS:
        inj = N.read("injuries", [season])
        share = lambda c: f"{inj[c].is_not_null().mean():.1%}" if c in inj.columns else "column absent"   # noqa: E731
        L.append(f"| {season} | {inj.height:,} | {share('date_modified')} | {share('report_status')} |")
    L += ["", "## Participation joined to play-by-play", "", "| Season | Participation plays | Found in play-by-play | Pass plays with a route recorded |", "|---|---|---|---|"]
    for season in N.SEASONS:
        if not N.path("participation", season).exists():
            continue
        part = N.read("participation", [season])
        pbp = N.read("pbp", [season]).select(pl.col("game_id").alias("nflverse_game_id"), pl.col("play_id").cast(pl.Int64), "pass")
        j = part.with_columns(pl.col("play_id").cast(pl.Int64)).join(pbp, on=["nflverse_game_id", "play_id"], how="left")
        passes = j.filter(pl.col("pass") == 1)
        route = passes.filter(pl.col("route").is_not_null() & (pl.col("route") != "")).height / max(passes.height, 1) if "route" in j.columns else float("nan")
        L.append(f"| {season} | {part.height:,} | {j['pass'].is_not_null().mean():.1%} | {route:.1%} |")
    L += ["", "## What this means for the build", "",
          "- Snap counts start in 2013 and participation and Next Gen Stats in 2016, so snap-based role features exist",
          "  for every fit, tune and test season (2018 on) but not for all of the 2010-2017 history window.",
          "- Routes run per player are not in the free nflverse feeds: the participation `route` column is one value per",
          "  pass play, and the nflverse Next Gen Stats files have no routes column. Route participation is derived from",
          "  who was on the field on dropbacks, which overstates it for tight ends and running backs who stay in to block.",
          "- Sumer Sports publishes routes run per player, but its terms of service (read 2026-11-13) forbid automated",
          "  collection and use of its content to develop or train machine-learning models, so it is not used.",
          "- Franchise codes differ between tables in older seasons (for example OAK and LV); `player_week.TEAM_ALIASES`",
          "  maps them, and the roster agreement above is measured after mapping.",
          "- Injury rows carry `date_modified` through 2024 but the 2025 file has no such column, and only about half the",
          "  rows from 2016 on carry a game status. Historical availability inputs are weaker than live ones.",
          "- A few stat rows each season have no snap row and a few snap rows have no player ID match; they are counted",
          "  above and never matched by guessing."]
    OUT.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
