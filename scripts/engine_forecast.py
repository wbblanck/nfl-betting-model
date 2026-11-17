"""Test M forecasts (docs/engine_preregistration.md, amendment of 2026-11-17): both frozen engines' distributions for
every regular-season game of one 2026 week, built only from what was known before each kickoff. Reads no price.

  python scripts/engine_forecast.py 2026 11              forecast week 11; writes data/live/engine_forecasts/2026_w11/
  python scripts/engine_forecast.py 2026 10 --dry-run    the same machinery on a week outside the sample; writes to
                                                         the scratch folder given by ENGINE_FORECAST_DRY (default /tmp)

What is written (engine.forecast explains each input rule):
- inputs/*.parquet: the 2026 nflverse rows used (fetched now, every fact of the target week and later removed), so
  the forecast can be re-run from committed files;
- forecasts.parquet: per engine, game, player and market, the runs as a histogram (value, count);
- manifest.json: frozen-record checks for both engines, the fit/tune feature hash check, the injury snapshot and
  roster week used for each game, row counts, the code commit and the time of the run.
Refuses (exit 1) if either engine's parameters differ from its frozen record or the fit/tune features changed.
"""
import datetime as dt
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import polars as pl

import engine_feature_check as FC
import engine_test_s as SA
import engine_test_s_b as SB
from nflbet.config import ROOT
from nflbet.engine import accounting, forecast as FO
from nflbet.engine.challenger import joint as J
from nflbet.engine.data import nflverse as N, player_week as PW
from nflbet.engine.features import build as B, facts as F
from nflbet.engine.replication import model as MA
from nflbet.sources import injuries as INJ

OUT, INJURIES = ROOT / "data" / "live" / "engine_forecasts", ROOT / "data" / "live" / "injuries"
SIMS = 4000                     # as in both engines' Test S


def sha(df: pl.DataFrame) -> str:
    return hashlib.sha256(df.write_csv(float_precision=6).encode()).hexdigest()


def fetch_current(season: int, week: int, inputs: Path) -> dict:
    """The season's nflverse tables as they stand now, cut to games before the target week, saved under inputs/.
    If inputs/ already holds them (a re-run), they are read from there instead."""
    names = ("stats", "snaps", "pbp", "sched", "rosters", "depth")
    if all((inputs / f"{n}.parquet").exists() for n in names):
        return {n: pl.read_parquet(inputs / f"{n}.parquet") for n in names}
    import nflreadpy as nr
    sched = nr.load_schedules([season])
    early = sched.filter((pl.col("game_type") == "REG") & (pl.col("week") < week))["game_id"].to_list()
    d = {"stats": nr.load_player_stats([season]).filter(pl.col("season_type").eq("REG") & (pl.col("week") < week)),
         "snaps": nr.load_snap_counts([season]).filter(pl.col("game_id").is_in(early)),
         "pbp": nr.load_pbp([season]).filter(pl.col("game_id").is_in(early))
                  .select("game_id", "play_id", "posteam", "play_type", "qb_scramble", "two_point_attempt", "qb_dropback"),
         # scores of the target week and later are removed: a game's own result is not known before it
         "sched": sched.with_columns([pl.when(pl.col("week") < week).then(pl.col(c)).otherwise(None).alias(c)
                                      for c in ("home_score", "away_score", "result", "total")]),
         "rosters": nr.load_rosters_weekly([season]).filter(pl.col("week") < week)
                      .select("gsis_id", "season", "week", "team", "position", "status", "game_type"),
         "depth": nr.load_depth_charts([season]).filter(pl.col("pos_abb").is_in(FO.SKILL))}
    inputs.mkdir(parents=True, exist_ok=True)
    for n, df in d.items():
        df.write_parquet(inputs / f"{n}.parquet")
    return d


def raw_inputs(season: int, cur: dict) -> dict:
    """Warehouse seasons (2010 through last season) plus the current season's rows, in engine_feature_check's shape."""
    past = FC.load(list(range(2010, season)))
    sched_cols = past["sched"].columns
    old = N.read("schedules").filter(pl.col("season") < season)
    return {"stats": pl.concat([past["stats"], cur["stats"]], how="diagonal_relaxed"),
            "snaps": pl.concat([past["snaps"], cur["snaps"]], how="diagonal_relaxed"),
            "pbp": pl.concat([past["pbp"], cur["pbp"]], how="diagonal_relaxed"),
            "part": past["part"],                                        # nflverse publishes no 2026 participation
            "sched": pl.concat([old, cur["sched"]], how="diagonal_relaxed"),
            "sched_cols": sched_cols,
            "rosters": pl.concat([past["rosters"], cur["rosters"]], how="diagonal_relaxed"),
            "depth_weekly": past["depth_weekly"],
            "depth_dated": pl.concat([past["depth_dated"], cur["depth"]], how="diagonal_relaxed")}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) != 2:
        print(__doc__)
        return 2
    season, week = int(args[0]), int(args[1])
    out = (Path(os.environ.get("ENGINE_FORECAST_DRY", "/tmp")) / "engine_forecast_dry" if dry else OUT) / f"{season}_w{week:02d}"
    cur = fetch_current(season, week, out / "inputs")
    raw = raw_inputs(season, cur)
    players, sched = N.read("players"), raw["sched"]
    games_ = F.games(sched)
    targets = FO.target_games(games_, season, week)
    if targets.height == 0:
        print(f"no regular-season games in {season} week {week}")
        return 1

    # Injury snapshot per game: the latest saved before kickoff (within 72 hours).
    snaps = sorted(p.name for p in INJURIES.glob("*.json.gz"))
    ids = players.select(pl.col("espn_id").cast(pl.Utf8), pl.col("gsis_id").alias("player_id")).drop_nulls().unique("espn_id")
    used, absent = {}, {}
    for gid, ko in targets.select("game_id", "kickoff").unique(maintain_order=True).iter_rows():
        name = FO.snapshot_before(snaps, ko)
        used[gid] = {"kickoff_et": ko, "injury_snapshot": name}
        if name is not None:
            absent[gid] = FO.absent_ids(INJ.parse(json.load(gzip.open(INJURIES / name, "rt"))), ids)
            used[gid]["absent_listed"] = len(absent[gid])
    no_snap = [g for g, u in used.items() if u["injury_snapshot"] is None]
    targets = targets.filter(~pl.col("game_id").is_in(no_snap))           # no snapshot before kickoff: not forecast

    # Feature table with the target games as unplayed team-games and their projected active lists.
    pw, _ = PW.build(raw["stats"], raw["snaps"], players)
    tg = F.team_game(raw["stats"], raw["pbp"], games_, F.scores(sched)).with_columns(pl.lit(True).alias("played"))
    tg_all = pl.concat([tg, targets], how="diagonal_relaxed")
    act_proj = FO.projected_active(raw["rosters"].filter(pl.col("season") == season), absent, targets,
                                   FO.chart_teams(cur["depth"], targets))
    active = pl.concat([F.active(raw["rosters"], tg), act_proj], how="diagonal_relaxed")
    feats = B.build(pw, tg_all, F.on_field(raw["part"], raw["pbp"]), active, F.depth_rank(raw["depth_weekly"], raw["depth_dated"], tg_all))
    rows = feats.filter(pl.col("game_id").is_in(targets["game_id"].unique().to_list())).sort("game_id", "team", "player_id")
    assert rows.height == act_proj.height and not rows["played"].any()

    # Frozen engines: refit deterministically and compare with the frozen records.
    fa, PA, tab = SA.fingerprint()
    fb, PB = SB.fingerprint()
    froz_a, froz_b = json.loads(SA.FROZEN.read_text()), json.loads(SB.FROZEN.read_text())
    checks = {"engine_a_frozen_matches": all(froz_a[k] == fa[k] for k in fa),
              "engine_b_frozen_matches": all(froz_b[k] == fb[k] for k in fb),
              "fit_tune_features_match": B.snapshot_hash(feats.filter(pl.col("season").is_in([*SA.T.FIT, *SA.T.TUNE]))) == froz_a["features_sha256_fit_tune"]}

    hists, broke = [], {}
    for (gid,), game in rows.group_by(["game_id"], maintain_order=True):
        sides = [r for _, r in game.group_by(["team"], maintain_order=True)]
        seed = int.from_bytes(str(gid).encode(), "little") % (2 ** 32)
        for side_rows, (box, s) in zip(sides, MA.simulate_game(PA, tab, sides, SIMS, np.random.default_rng([0, seed]))):
            for k, v in accounting.violations(box).items():
                broke[k] = broke.get(k, 0) + v
            for market, col in FO.MARKETS.items():
                hists.append(FO.histogram("A", side_rows, market, s[col]))
        every = {m: np.ones(game.height, dtype=bool) for m in FO.MARKETS}
        runs, _ = J.simulate(PB, PB["rho"], game, every, SIMS, np.random.default_rng([SB.SEED, seed]))
        for market in FO.MARKETS:
            hists.append(FO.histogram("B", game, market, runs[market]))
    fc = pl.concat(hists)

    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    man = {"season": season, "week": week, "run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "commit": head, "sims": SIMS, "engines": {"A": MA.VERSION, "B": SB.M.VERSION}, **checks,
           "accounting_violations": broke, "games": used, "games_without_snapshot": no_snap,
           "player_games": rows.height, "target_rows_sha256": sha(rows),
           "inputs_sha256": {n: sha(df) for n, df in cur.items()}}
    out.mkdir(parents=True, exist_ok=True)
    fc.write_parquet(out / "forecasts.parquet")
    (out / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in man.items() if k != "games"}, indent=1))
    ok = all(checks.values()) and not broke
    if not ok:
        print("REFUSED: a frozen-record or feature check failed; this forecast does not count")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
