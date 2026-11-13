"""Pressure vs QB props (docs/pressure_preregistration.md).

    python scripts/pressure_eval.py --power   # step 1: power analysis on 2018 only (burn-in season)
    python scripts/pressure_eval.py           # step 2: train 2019-2021, confirm 2022-2023, run once

Writes data/backtests/pressure_power.json or data/backtests/pressure.json and docs/pressure_report.md."""
from __future__ import annotations

import json
import sys
from statistics import NormalDist

import numpy as np
import polars as pl

from nflbet import config
from nflbet.props import player_proj as M
from nflbet.props import pressure as P
from nflbet.props.core import STAT

BURN, TRAIN, CONFIRM = 2018, [2019, 2020, 2021], [2022, 2023]
MARKETS = ["pass_yds", "pass_int", "sacks"]
STAT_X = {"pass_yds": STAT["pass_yds"], "pass_int": STAT["pass_int"], "pass_att": STAT["pass_att"], **P.EXTRA_STAT}
ATT_FLOOR = 20.0
ALPHA = 0.05


def load(seasons: list[int]) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    import nflreadpy as nfl

    st = M.stats(seasons, STAT_X)
    raw = nfl.load_player_stats(seasons=seasons).filter(pl.col("season_type") == "REG") \
        .select("season", "week", "team", "opponent_team", "attempts", "sacks_suffered")
    pfr = nfl.load_pfr_advstats(seasons=seasons, stat_type="pass")
    return st, raw, pfr


def rows(seasons: list[int]) -> tuple[pl.DataFrame, pl.DataFrame, dict]:
    """QB rows (all MARKETS) with usage, factors, D, Q, actual; starters only (pass_att usage >= ATT_FLOOR)."""
    st, raw, pfr = load(seasons)
    L = M.long(M.features(st, M.implied_points(seasons), STAT_X), STAT_X).filter(pl.col("pos") == "QB")
    starters = L.filter(pl.col("market") == "pass_att", pl.col("usage") >= ATT_FLOOR).select("player_id", "season", "week")
    L = L.filter(pl.col("market").is_in(MARKETS)).join(starters, on=["player_id", "season", "week"])
    tg = P.team_games(pfr, raw)
    fac = P.factors(tg)
    meta = {"team_games": tg.height, "team_games_missing_pfr": tg.filter(pl.col("pressures").is_null()).height,
            "league_rate": {str(k): v for k, v in P.league_rates(tg).items()}}
    return P.attach(L, fac), tg, meta


def power() -> None:
    x, tg, meta = rows([BURN])
    params = M.fit(x)
    x = M.project(x, params).filter(pl.col("week") >= 5)
    z = NormalDist().inv_cdf(1 - ALPHA / len(MARKETS) / 2)
    n_cl_burn = x["week"].n_unique()
    n_cl_conf = 36                                   # 2022 and 2023: 18 regular-season weeks each
    out = {"meta": meta, "z": z, "clusters_2018": n_cl_burn, "clusters_confirm": n_cl_conf, "markets": {}}
    rng = np.random.default_rng(7)
    for m in MARKETS:
        r = x.filter(pl.col("market") == m)
        proj, D, y = (r[k].to_numpy().astype(float) for k in ("proj", "D", "actual"))
        res, cl = y - proj, r["week"].to_numpy()
        per = {"n_rows_2018_wk5plus": r.height, "sd_logD": float(np.std(np.log(D))),
               "sd_residual": float(np.std(res)), "by_c": {}}
        for c in (-1.5, -1.0, -0.75, -0.5, -0.25, 0.25, 0.5, 0.75, 1.0, 1.5):
            pw, mu, eff = [], [], []
            for _ in range(20):
                truth = proj * D ** c
                ys = truth + rng.permutation(res)
                diff = (ys - truth) ** 2 - (ys - proj) ** 2
                se = float(np.std(P.cluster_boot(diff, cl, n=1000, seed=int(rng.integers(1e9)))))
                se_conf = se * np.sqrt(n_cl_burn / n_cl_conf)
                pw.append(NormalDist().cdf(abs(diff.mean()) / se_conf - z))
                mu.append(diff.mean()); eff.append(np.mean(np.abs(truth - proj)))
            per["by_c"][str(c)] = {"power": float(np.mean(pw)), "mean_diff": float(np.mean(mu)),
                                   "mean_abs_shift": float(np.mean(eff))}
        out["markets"][m] = per
    (config.ROOT / "data" / "backtests" / "pressure_power.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main() -> None:
    x, tg, meta = rows([BURN, *TRAIN, *CONFIRM])
    params = M.fit(x.filter(pl.col("season").is_in(TRAIN)))
    x = M.project(x.filter(pl.col("season").is_in(TRAIN + CONFIRM)), params)
    cd = P.fit_cd(x.filter(pl.col("season").is_in(TRAIN)))
    c = x.filter(pl.col("season").is_in(CONFIRM)).with_columns(P.adjusted(cd).alias("adj"))
    res, pv = {}, {}
    for m in MARKETS:
        z = c.filter(pl.col("market") == m)
        a, p, j = (z[k].to_numpy().astype(float) for k in ("actual", "proj", "adj"))
        cl = (z["season"] * 100 + z["week"]).to_numpy()
        diff = (j - a) ** 2 - (p - a) ** 2
        bs = P.cluster_boot(diff, cl)
        pv[m] = P.boot_p(bs)
        by_season = {str(s): float(diff[z["season"].to_numpy() == s].mean()) for s in CONFIRM}
        res[m] = {"c": cd[m][0], "d": cd[m][1], "n": z.height, "mse_current": float(np.mean((p - a) ** 2)),
                  "mse_adjusted": float(np.mean((j - a) ** 2)), "diff": float(diff.mean()),
                  "ci95": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))], "p": pv[m],
                  "mae_current": float(np.mean(np.abs(p - a))), "mae_adjusted": float(np.mean(np.abs(j - a))),
                  "bias_current": float(np.mean(a - p)), "sd_logD": float(np.std(np.log(z["D"].to_numpy()))),
                  "sd_logQ": float(np.std(np.log(z["Q"].to_numpy()))), "diff_by_season": by_season}
    rej = P.holm(pv, ALPHA)
    for m in MARKETS:
        r = res[m]
        r["holm_reject"] = rej[m]
        r["passes"] = bool((r["c"], r["d"]) != (0.0, 0.0) and r["diff"] < 0 and rej[m])
    out = {"meta": meta, "params": params, "cd": cd, "confirm": res}
    (config.ROOT / "data" / "backtests" / "pressure.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["# Pressure vs QB props: confirm 2022-2023", "",
         "Pre-registration: docs/pressure_preregistration.md. (a, b) and (c, d) fitted on 2019-2021. Metric: squared "
         "error of adjusted minus current projection (negative = pressure helps); week-clustered bootstrap, Holm over "
         "3 markets at 0.05.", "",
         f"- Team-games {meta['team_games']:,}; without a PFR passing row {meta['team_games_missing_pfr']:,}.", "",
         "| Market | c (defense) | d (own line) | Rows | MSE current | MSE adjusted | Diff (95% interval) | p | Holm | "
         "Verdict | MAE current / adjusted | Current mean (actual − proj) |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, r in res.items():
        L.append(f"| {m} | {r['c']:+.2f} | {r['d']:+.2f} | {r['n']:,} | {r['mse_current']:.3f} | {r['mse_adjusted']:.3f} | "
                 f"{r['diff']:+.4f} ({r['ci95'][0]:+.4f} to {r['ci95'][1]:+.4f}) | {r['p']:.4f} | "
                 f"{'reject' if r['holm_reject'] else 'keep'} | **{'PASS' if r['passes'] else 'FAIL'}** | "
                 f"{r['mae_current']:.3f} / {r['mae_adjusted']:.3f} | {r['bias_current']:+.3f} |")
    (config.ROOT / "docs" / "pressure_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    power() if "--power" in sys.argv else main()
