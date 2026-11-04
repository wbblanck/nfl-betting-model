"""Injury usage redistribution test (docs/injury_redist_preregistration.md): train 2019-2021, confirm 2022-2023.
Writes docs/injury_redist_report.md and data/backtests/injury_redist.json."""
from __future__ import annotations

import json

import numpy as np
import polars as pl

from nflbet import config
from nflbet.props import injury_redist as I
from nflbet.props import player_proj as M

TRAIN, CONFIRM = [2019, 2020, 2021], [2022, 2023]
MARKETS = list(I.POOL)
FLOOR = {"rec": 2, "rec_yds": 20, "rush_att": 6, "rush_yds": 25, "rush_rec_yds": 30}
LEVEL = 0.05 / len(MARKETS) / 2


def boot(diff: np.ndarray, cl: np.ndarray, n=4000, seed=7):
    ids = np.unique(cl)
    idx = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    bs = [diff[np.concatenate([idx[j] for j in rng.integers(0, len(ids), len(ids))])].mean() for _ in range(n)]
    return float(diff.mean()), [float(np.quantile(bs, LEVEL)), float(np.quantile(bs, 1 - LEVEL))]


def injuries(seasons: list[int]) -> pl.DataFrame:
    import nflreadpy as nfl

    j = nfl.load_injuries(seasons=seasons).filter(pl.col("game_type") == "REG")
    return j.select(pl.col("gsis_id").alias("player_id"), "team", "season", "week", "report_status")


def frame() -> tuple[pl.DataFrame, dict, dict]:
    seasons = [TRAIN[0] - 1, *TRAIN, *CONFIRM]
    st = M.stats(seasons)
    L = M.long(M.features(st, M.implied_points(seasons))).filter(pl.col("market").is_in(MARKETS))
    params = M.fit(L.filter(pl.col("season").is_in(TRAIN)))
    x = M.project(L.filter(pl.col("season").is_in(TRAIN + CONFIRM)), params)
    x = pl.concat([x.filter(pl.col("market") == m, pl.col("pos").is_in(I.POOL[m]),
                            pl.col("usage") >= FLOOR[m]) for m in MARKETS])
    su = I.usage_post(st, MARKETS)
    inj = injuries(TRAIN + CONFIRM)
    meta = {"injury_rows": inj.height, "listed_out_doubtful": inj.filter(pl.col("report_status").is_in(I.OUT_STATUS)).height,
            "listed_matched_to_stats": inj.filter(pl.col("report_status").is_in(I.OUT_STATUS))
            .join(st.select("player_id").unique(), on="player_id").height}
    sh = I.shares(I.recent(su, MARKETS), inj, MARKETS)
    x = I.attach(x, sh)
    return x, params, meta


def main() -> None:
    x, params, meta = frame()
    alpha = I.fit_alpha(x.filter(pl.col("season").is_in(TRAIN)))
    c = x.filter(pl.col("season").is_in(CONFIRM)).with_columns(I.adjusted(x, alpha).alias("adj"))
    res = {}
    for m in MARKETS:
        z = c.filter(pl.col("market") == m)
        aff = z.filter(pl.col("q") > 0)
        a, p, j = aff["actual"].to_numpy(), aff["proj"].to_numpy(), aff["adj"].to_numpy()
        d, ci = boot(np.abs(j - a) - np.abs(p - a), (aff["season"] * 100 + aff["week"]).to_numpy())
        res[m] = {"alpha": alpha[m], "n_all": z.height, "n_affected": aff.height, "mean_q": float(aff["q"].mean()),
                  "bias_current": float(np.mean(a - p)), "mae_current": float(np.mean(np.abs(p - a))),
                  "mae_adjusted": float(np.mean(np.abs(j - a))), "diff": d, "ci": ci,
                  "passes": bool(alpha[m] > 0 and ci[1] < 0),
                  "mae_all_current": float((z["proj"] - z["actual"]).abs().mean()),
                  "mae_all_adjusted": float((z["adj"] - z["actual"]).abs().mean())}
    out = {"meta": meta, "params": params, "alpha": alpha, "confirm": res}
    (config.ROOT / "data" / "backtests" / "injury_redist.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["# Injury usage redistribution: confirm 2022-2023", "",
         "Pre-registration: docs/injury_redist_preregistration.md. Train 2019-2021. Interval: week-clustered, two-sided "
         f"0.05/{len(MARKETS)}. Affected = a pool teammate was listed Out or Doubtful.", "",
         f"- Injury report rows {meta['injury_rows']:,}; listed Out/Doubtful {meta['listed_out_doubtful']:,}, of which "
         f"{meta['listed_matched_to_stats']:,} match a player in the stats.", "",
         "| Market | alpha (train) | Affected rows | Mean q | Current: mean (actual − proj) | MAE current | MAE adjusted | "
         "Diff (interval) | Verdict | All rows MAE current / adjusted |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m, r in res.items():
        L.append(f"| {m} | {r['alpha']:.2f} | {r['n_affected']:,} of {r['n_all']:,} | {r['mean_q']:.3f} | "
                 f"{r['bias_current']:+.2f} | {r['mae_current']:.2f} | {r['mae_adjusted']:.2f} | {r['diff']:+.3f} "
                 f"({r['ci'][0]:+.3f} to {r['ci'][1]:+.3f}) | **{'PASS' if r['passes'] else 'FAIL'}** | "
                 f"{r['mae_all_current']:.2f} / {r['mae_all_adjusted']:.2f} |")
    (config.ROOT / "docs" / "injury_redist_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
