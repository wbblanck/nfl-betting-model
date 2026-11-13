"""Engine A version 0.1 on the tune seasons: fit on 2018-2021, simulate every offense-game of 2022-2023, and compare
with the frozen baselines on the Test S sample. This is tuning (allowed on 2022-2023), not Test S: no 2024-2025
outcome and no price is read. Writes docs/engine/engine_a_tune.md and data/backtests/engine_a_v01.json."""
import json
import sys

import numpy as np
import polars as pl

from nflbet.config import ROOT
from nflbet.engine import accounting, baselines as BL, scoring as S
from nflbet.engine.data import nflverse as N, player_week as PW
from nflbet.engine.features import facts as F
from nflbet.engine.replication import efficiency as E, model as M

FIT, TUNE, SIMS = (2018, 2019, 2020, 2021), (2022, 2023), 2000
KMAX = {"pass_att": 90, "pass_yds": 700, "rush_att": 60, "rush_yds": 350, "rec": 30, "rec_yds": 350}
OUT_MD, OUT_JSON = ROOT / "docs" / "engine" / "engine_a_tune.md", ROOT / "data" / "backtests" / "engine_a_v01.json"
OUTCOMES = ["attempts", "completions", "passing_yards", "carries", "rushing_yards", "targets", "receptions", "receiving_yards"]


def load(seasons):
    feats = pl.read_parquet(N.DIR / "features" / "player_game.parquet").filter(pl.col("season").is_in(seasons))
    stats = N.read("player_stats", seasons)
    pw, _ = PW.build(stats, N.read("snap_counts", seasons), N.read("players"))
    pbp = N.read("pbp", seasons)
    teams = F.team_game(stats, pbp, F.games(N.read("schedules")))
    df = feats.join(pw.select("player_id", "game_id", *OUTCOMES), on=["player_id", "game_id"], how="left")
    assert df.filter(pl.col("played"))[OUTCOMES[0]].null_count() == 0          # everyone who played has an outcome row
    return df.with_columns([pl.col(c).fill_null(0) for c in OUTCOMES]), teams, pbp   # active, did not play: zeros


def pools(pbp: pl.DataFrame) -> dict:
    """Yards per completion by receiver position and per carry by rusher position, regular season, no two-point tries."""
    posmap = N.read("players").select(pl.col("gsis_id"), pl.col("position"))
    reg = pbp.filter((pl.col("season_type") == "REG") & (pl.col("two_point_attempt") == 0))
    out = {}
    for kind, flag, who, yards in (("rec", "complete_pass", "receiver_player_id", "receiving_yards"), ("rush", "rush_attempt", "rusher_player_id", "rushing_yards")):
        d = (reg.filter((pl.col(flag) == 1) & pl.col(yards).is_not_null())
             .join(posmap, left_on=who, right_on="gsis_id", how="left")
             .with_columns(pl.when(pl.col("position").is_in(["QB", "RB", "WR", "TE"])).then(pl.col("position")).otherwise(pl.lit("OTH")).alias("pos")))
        out[kind] = {p: d.filter(pl.col("pos") == p)[yards].to_numpy().astype(float) for p in E.POSITIONS}
        for p in E.POSITIONS:                                   # a position with almost no plays borrows everyone's
            if len(out[kind][p]) < 200:
                out[kind][p] = d[yards].to_numpy().astype(float)
    return out


def main() -> int:
    df, teams, pbp = load([*FIT, *TUNE])
    assert df["season"].max() <= max(TUNE)
    pl_fit = pools(pbp.filter(pl.col("season").is_in(FIT)))
    P = M.fit(df.filter(pl.col("season").is_in(FIT)), teams.filter(pl.col("season").is_in(FIT)), pl_fit)
    tab = M.tables(pl_fit, seed=0)
    tune = df.filter(pl.col("season").is_in(TUNE)).sort("game_id", "team", "player_id")
    runs = {c: np.zeros((tune.height, SIMS), dtype=np.int32) for c in OUTCOMES}
    broke, n_games, at = {}, 0, 0
    for (gid, team), rows in tune.group_by(["game_id", "team"], maintain_order=True):
        seed = int.from_bytes(f"{gid}|{team}".encode(), "little") % (2 ** 32)
        box, s = M.simulate(P, tab, rows, SIMS, np.random.default_rng([0, seed]))
        for k, v in accounting.violations(box).items():
            broke[k] = broke.get(k, 0) + v
        for c in OUTCOMES:
            runs[c][at:at + rows.height] = s[c]
        at, n_games = at + rows.height, n_games + 1
    base = json.loads((ROOT / "data" / "backtests" / "engine_baselines.json").read_text())
    res = {"version": M.VERSION, "fit_seasons": FIT, "tune_seasons": TUNE, "sims": SIMS, "team_games": n_games,
           "accounting_violations": broke, "params": {k: v for k, v in P.items() if k not in ("env", "qb")},
           "qb": {"starters": len(P["qb"]["starter_share"]), "starter_threw_all": float(np.mean(np.array(P["qb"]["starter_share"]) >= 0.999)),
                  "starter_mean_share": float(np.mean(P["qb"]["starter_share"])), "new_starters": len(P["qb"]["new_share"])},
           "env": {k: v for k, v in P["env"].items() if k != "resid"}, "markets": {}}
    L = [f"# Engine A {M.VERSION} on the tune seasons", "",
         "Written by `scripts/engine_a_tune.py`. Fitted on 2018-2021; every offense-game of 2022-2023 simulated",
         f"{SIMS:,} times ({n_games:,} offense-games). This is tuning, not Test S: no 2024-2025 outcome and no price was read.", "",
         f"Accounting: {'every simulated box score reconciles' if not broke else 'VIOLATIONS ' + json.dumps(broke)} "
         f"({n_games * SIMS:,} box scores checked).", "",
         "CRPS is in the stat's own units, lower is better. 'Engine minus baseline' below 0 means the engine is better;",
         "the interval is a week-clustered bootstrap.", "",
         "| Market | Rows | Baseline | Baseline CRPS | Engine CRPS | Engine minus baseline (95% interval) | Engine central 50% covers | 80% | 90% |",
         "|---|---|---|---|---|---|---|---|---|"]
    for market, (ycol, _, _) in BL.MARKETS.items():
        m = BL.eligible(tune, market).to_numpy() & tune["played"].to_numpy()      # Test S sample: eligible and played
        rows, y = tune.filter(pl.Series(m)), tune[ycol].to_numpy()[m]
        b = base["markets"][market]
        chosen = b["chosen"]
        bc = S.crps(S.nb_cdf(BL.means(rows, market, b["constants"])[chosen], b["baselines"][chosen]["size"], KMAX[market]), y)
        x = runs[ycol][m]
        ec = S.crps_samples(x, y)
        d, lo, hi = S.paired_bootstrap(ec - bc, (rows["season"] * 100 + rows["week"]).to_numpy())
        cov = {lv: S.coverage_samples(x, y, lv) for lv in (0.5, 0.8, 0.9)}
        res["markets"][market] = {"n": int(m.sum()), "baseline": chosen, "baseline_crps": float(bc.mean()), "engine_crps": float(ec.mean()),
                                  "diff": [d, lo, hi], "coverage": {str(k): v for k, v in cov.items()},
                                  "mean_bias": float(x.mean() - y.mean())}
        L.append(f"| {market} | {int(m.sum()):,} | {chosen} | {bc.mean():.3f} | {ec.mean():.3f} | {d:+.3f} ({lo:+.3f} to {hi:+.3f}) | "
                 f"{cov[0.5]:.1%} | {cov[0.8]:.1%} | {cov[0.9]:.1%} |")
    o, e = P["opp"], P["eff"]
    L += ["", "## Fitted on 2018-2021", "",
          "| Split | Window | Prior weight m | Concentration kappa | Share to non-skill players |", "|---|---|---|---|---|"]
    L += [f"| {k} | {v['window']} | {v['m']:g} | {v['kappa']:.0f} | {v['other']:.2%} |" for k, v in o.items()]
    L += ["", f"- Catch-rate prior strength: {e['c']['catch']:g} targets. Yards-per-catch factor: {e['c']['rec']:g} catches. Yards-per-carry factor: {e['c']['rush']:g} carries.",
          f"- Team-wide yardage shock (standard deviation of the multiplier): receiving {e['shock']['rec']:.3f}, rushing {e['shock']['rush']:.3f}.",
          f"- Expected starting quarterbacks in the fit seasons: {res['qb']['starters']:,}; they threw every one of their team's passes in "
          f"{res['qb']['starter_threw_all']:.1%} of games and {res['qb']['starter_mean_share']:.1%} of the passes on average.",
          f"- Chance an active skill player takes a snap, fit seasons: {P['play']['all']:.1%} overall ("
          + ", ".join(f"{k} {x:.1%}" for k, x in sorted(P["play"]["pos"].items())) + ").",
          f"- Targets per pass attempt {P['env']['target_rate']:.3f}; sacks per attempt {P['sack_rate']:.3f}; scrambles as a share of quarterback carries {P['scramble_share']:.2f}.",
          "", "Mean of the runs minus mean of the outcomes, by market: "
          + ", ".join(f"{k} {v['mean_bias']:+.2f}" for k, v in res["markets"].items()) + "."]
    L += ["", "## Reading (limits of this comparison)", "",
          "- These are the tune seasons, where the engine's design was chosen, so the gaps flatter it. Only Test S on",
          "  2024-2025, run once on a frozen version, counts.",
          "- In the passing markets much of the gap is shape, not a better average: the baseline is one negative binomial,",
          "  which is too wide for a starter's attempts (docs/engine/baselines.md), while the engine separates the usual",
          "  full game from the occasional short one.",
          "- What the engine is told: each team's game-day active list (published about 90 minutes before kickoff) and",
          "  earlier games. It is not told who went on to play. Each player's forecast comes from the runs in which he",
          "  plays, because a prop on a player who does not play is void; his teammates' participation stays uncertain.",
          "  So these are forecasts as of the active list; a forecast made earlier in the week would also need",
          "  availability drawn from the injury report, which is not built.",
          "- Two earlier runs of this comparison were wrong in opposite directions and are not reported: one told the",
          "  engine who actually played (hindsight, flattering it), the other made it forecast for players regardless of",
          "  whether they played (scoring it on outcomes that are void).",
          "- The expected starting quarterback is the recent starter if there is one, otherwise the depth chart's number",
          "  one, otherwise the active quarterback with the most recent volume. On 2018-2021 that names the actual leader",
          "  in attempts in 92.8% of team-games. A change announced during the week and not yet on the chart is missed.",
          "- The weekly depth charts through 2024 carry no timestamp and are taken as that week's pregame chart; from",
          "  2025 they are dated and only a chart from before game day is used.",
          "- Not in this version: play-by-play game script, the two teams drawn jointly, availability draws,",
          "  opponent-specific efficiency, touchdowns, interceptions."]
    OUT_JSON.write_text(json.dumps(res, indent=1) + "\n")
    OUT_MD.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 1 if broke else 0


if __name__ == "__main__":
    sys.exit(main())
