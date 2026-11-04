"""Signals A-D (docs/five_signals_preregistration.md): train 2019-2021, confirm 2022-2023.
Writes docs/signals_report.md and data/backtests/signals.json."""
from __future__ import annotations

import json

import numpy as np
import polars as pl

from nflbet import config
from nflbet.props import player_proj as M
from nflbet.props import signals as S

TRAIN, CONFIRM = [2019, 2020, 2021], [2022, 2023]
FLOOR = {"rec": 2, "rec_yds": 20, "rush_att": 6, "rush_yds": 25, "pass_yds": 150}
POS = {"rec": ["RB", "WR", "TE"], "rec_yds": ["RB", "WR", "TE"], "rush_att": ["RB"], "rush_yds": ["RB"], "pass_yds": ["QB"]}
TESTS = [("A_qb_change", "qb", ["rec", "rec_yds", "pass_yds"]), ("B_snap_trend", "snap", ["rec", "rec_yds", "rush_att", "rush_yds"]),
         ("C_ngs", "ngs", ["rush_yds", "rec_yds"]), ("D_wind", "wind", ["pass_yds", "rec_yds"])]
N_TESTS = sum(len(m) for _, _, m in TESTS)
LEVEL = 0.05 / N_TESTS / 2
SEASONS = TRAIN + CONFIRM


def boot(diff, cl, n=4000, seed=7):
    ids = np.unique(cl)
    idx = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    bs = [diff[np.concatenate([idx[j] for j in rng.integers(0, len(ids), len(ids))])].mean() for _ in range(n)]
    return float(diff.mean()), [float(np.quantile(bs, LEVEL)), float(np.quantile(bs, 1 - LEVEL))]


def base() -> pl.DataFrame:
    seasons = [TRAIN[0] - 1, *SEASONS]
    L = M.long(M.features(M.stats(seasons), M.implied_points(seasons))).filter(pl.col("market").is_in(list(FLOOR)))
    params = M.fit(L.filter(pl.col("season").is_in(TRAIN)))
    x = M.project(L.filter(pl.col("season").is_in(SEASONS)), params)
    return pl.concat([x.filter(pl.col("market") == m, pl.col("pos").is_in(POS[m]), pl.col("usage") >= FLOOR[m])
                      for m in FLOOR])


def signal_frames(rows: pl.DataFrame) -> tuple[dict, dict]:
    import nflreadpy as nfl

    meta = {}
    sched = nfl.load_schedules(seasons=SEASONS)
    sched = sched.with_columns(pl.col("home_team").replace({"OAK": "LV"}), pl.col("away_team").replace({"OAK": "LV"}))
    qb, wd = S.qb_change(sched), S.wind(sched)
    k = ["team", "season", "week"]
    a = rows.join(qb.rename({"x": "xq"}), on=k, how="left")
    # pass_yds: only the starter's own row carries x; other QBs 0
    a = a.with_columns(pl.when((pl.col("market") == "pass_yds") & (pl.col("player_id") != pl.col("qb"))).then(0)
                       .otherwise(pl.col("xq")).fill_null(0).cast(pl.Float64).alias("x")).drop("xq", "qb")
    d = rows.join(wd, on=k, how="left").with_columns(pl.col("x").fill_null(0.0))
    sn = nfl.load_snap_counts(seasons=[TRAIN[0] - 1, *SEASONS]).filter(pl.col("game_type") == "REG")
    ids = nfl.load_players().select(pl.col("pfr_id"), pl.col("gsis_id")).drop_nulls().unique(subset="pfr_id")
    sn = sn.join(ids, left_on="pfr_player_id", right_on="pfr_id", how="left")
    meta["snap_rows"], meta["snap_rows_matched"] = sn.height, int(sn["gsis_id"].is_not_null().sum())
    sn = sn.filter(pl.col("gsis_id").is_not_null()).select(pl.col("gsis_id").alias("player_id"), "season", "week",
                                                          pl.col("offense_pct").cast(pl.Float64))
    sn = sn.filter(pl.col("offense_pct") > 0).unique(subset=["player_id", "season", "week"])
    b = rows.join(S.snap_trend(sn), on=["player_id", "season", "week"], how="left")
    parts = []
    for m, typ, col, center in (("rush_yds", "rushing", "rush_yards_over_expected_per_att", False),
                                ("rec_yds", "receiving", "avg_separation", True)):
        ng = nfl.load_nextgen_stats(seasons=[TRAIN[0] - 1, *SEASONS], stat_type=typ) \
            .filter(pl.col("season_type") == "REG").select(pl.col("player_gsis_id").alias("player_id"), "season", "week", col)
        r = rows.filter(pl.col("market") == m)
        parts.append(S.attach_ngs(r, S.ngs_prior(ng, col), ng, col, center))
    c = pl.concat(parts, how="diagonal_relaxed")
    return {"qb": a, "snap": b, "ngs": c, "wind": d}, meta


def main() -> None:
    rows = base()
    frames, meta = signal_frames(rows)
    res = {}
    for name, key, markets in TESTS:
        f = frames[key].filter(pl.col("market").is_in(markets), pl.col("x").is_not_null())
        k = S.fit_k(f.filter(pl.col("season").is_in(TRAIN)), S.GRIDS[key])
        c = f.filter(pl.col("season").is_in(CONFIRM))
        for m in markets:
            z = c.filter(pl.col("market") == m)
            if key in ("qb", "wind"):
                z = z.filter(pl.col("x") > 0)
            p, y = z["proj"].to_numpy(), z["actual"].to_numpy()
            adj = p * np.exp(k[m] * z["x"].to_numpy())
            dlt, ci = boot(np.abs(adj - y) - np.abs(p - y), (z["season"] * 100 + z["week"]).to_numpy())
            res[f"{name}:{m}"] = {"k": k[m], "n": z.height, "bias_current": float(np.mean(y - p)),
                                  "mae_current": float(np.mean(np.abs(p - y))), "mae_adjusted": float(np.mean(np.abs(adj - y))),
                                  "diff": dlt, "ci": ci, "passes": bool(k[m] != 0 and ci[1] < 0)}
    (config.ROOT / "data" / "backtests" / "signals.json").write_text(json.dumps({"meta": meta, "results": res}, indent=1))
    L = ["# Signals A-D: confirm 2022-2023", "", "Pre-registration: docs/five_signals_preregistration.md. Train 2019-2021. "
         f"Interval: week-clustered, two-sided 0.05/{N_TESTS}.", "",
         f"- Snap-count rows {meta['snap_rows']:,}, matched to a gsis id {meta['snap_rows_matched']:,}.", "",
         "| Signal: market | k (train) | Rows tested | Current: mean (actual − proj) | MAE current | MAE adjusted | Diff (interval) | Verdict |",
         "|---|---|---|---|---|---|---|---|"]
    for t, r in res.items():
        L.append(f"| {t} | {r['k']:+g} | {r['n']:,} | {r['bias_current']:+.2f} | {r['mae_current']:.2f} | {r['mae_adjusted']:.2f} | "
                 f"{r['diff']:+.3f} ({r['ci'][0]:+.3f} to {r['ci'][1]:+.3f}) | **{'PASS' if r['passes'] else 'FAIL'}** |")
    (config.ROOT / "docs" / "signals_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
