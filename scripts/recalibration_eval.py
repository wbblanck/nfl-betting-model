"""Projection recalibration (docs/recalibration_preregistration.md): train 2014-2016, confirm 2017-2018.
Writes docs/recalibration_report.md and data/backtests/recalibration.json."""
from __future__ import annotations

import json

import numpy as np
import polars as pl

from nflbet import config
from nflbet.props import player_proj as M

TRAIN, CONFIRM = [2014, 2015, 2016], [2017, 2018]
FLOOR = {"rec": 2, "rec_yds": 20, "rush_att": 6, "rush_yds": 25, "pass_yds": 150}
POS = {"rec": ["RB", "WR", "TE"], "rec_yds": ["RB", "WR", "TE"], "rush_att": ["RB"], "rush_yds": ["RB"], "pass_yds": ["QB"]}
GRID = np.round(np.arange(0.80, 1.1001, 0.01), 2)
LEVEL = 0.05 / len(FLOOR) / 2


def boot(diff, cl, n=4000, seed=7):
    ids = np.unique(cl)
    idx = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    bs = [diff[np.concatenate([idx[j] for j in rng.integers(0, len(ids), len(ids))])].mean() for _ in range(n)]
    return float(diff.mean()), [float(np.quantile(bs, LEVEL)), float(np.quantile(bs, 1 - LEVEL))]


def fit_c(p: np.ndarray, y: np.ndarray) -> float:
    return float(min(GRID, key=lambda c: (float(np.mean((c * p - y) ** 2)), abs(c - 1))))


def main() -> None:
    seasons = [TRAIN[0] - 1, *TRAIN, *CONFIRM]
    L = M.long(M.features(M.stats(seasons), M.implied_points(seasons))).filter(pl.col("market").is_in(list(FLOOR)))
    params = M.fit(L.filter(pl.col("season").is_in(TRAIN)))
    x = M.project(L.filter(pl.col("season").is_in(TRAIN + CONFIRM)), params)
    x = pl.concat([x.filter(pl.col("market") == m, pl.col("pos").is_in(POS[m]), pl.col("usage") >= FLOOR[m]) for m in FLOOR])
    res = {}
    for m in FLOOR:
        tr = x.filter(pl.col("market") == m, pl.col("season").is_in(TRAIN))
        c = fit_c(tr["proj"].to_numpy(), tr["actual"].to_numpy())
        z = x.filter(pl.col("market") == m, pl.col("season").is_in(CONFIRM))
        p, y = z["proj"].to_numpy(), z["actual"].to_numpy()
        cl = (z["season"] * 100 + z["week"]).to_numpy()
        d2, ci2 = boot((c * p - y) ** 2 - (p - y) ** 2, cl)
        d1, ci1 = boot(np.abs(c * p - y) - np.abs(p - y), cl)
        res[m] = {"c": c, "n": z.height, "train_bias": float(np.mean(tr["actual"].to_numpy() - tr["proj"].to_numpy())),
                  "bias_current": float(np.mean(y - p)), "bias_adjusted": float(np.mean(y - c * p)),
                  "mse_current": float(np.mean((p - y) ** 2)), "mse_diff": d2, "mse_ci": ci2,
                  "mae_current": float(np.mean(np.abs(p - y))), "mae_diff": d1, "mae_ci": ci1,
                  "passes": bool(c != 1 and ci2[1] < 0)}
    (config.ROOT / "data" / "backtests" / "recalibration.json").write_text(json.dumps({"params": params, "results": res}, indent=1))
    L = ["# Projection recalibration: confirm 2017-2018", "", "Pre-registration: docs/recalibration_preregistration.md. "
         f"Train 2014-2016. Interval: week-clustered, two-sided 0.05/{len(FLOOR)}. Criterion: squared error.", "",
         "| Market | c (train) | Train bias | Rows | Bias current → adjusted | MSE current | MSE diff (interval) | "
         "MAE current | MAE diff (interval) | Verdict |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m, r in res.items():
        L.append(f"| {m} | {r['c']:.2f} | {r['train_bias']:+.2f} | {r['n']:,} | {r['bias_current']:+.2f} → {r['bias_adjusted']:+.2f} | "
                 f"{r['mse_current']:.1f} | {r['mse_diff']:+.2f} ({r['mse_ci'][0]:+.2f} to {r['mse_ci'][1]:+.2f}) | "
                 f"{r['mae_current']:.2f} | {r['mae_diff']:+.3f} ({r['mae_ci'][0]:+.3f} to {r['mae_ci'][1]:+.3f}) | "
                 f"**{'PASS' if r['passes'] else 'FAIL'}** |")
    (config.ROOT / "docs" / "recalibration_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
