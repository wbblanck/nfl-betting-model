"""Model accuracy without lines (docs/accuracy_preregistration.md): projection and simulator vs a recent average on
2021-2023 (pooled) and 2025 (reference). Writes docs/accuracy_eval.md and data/backtests/accuracy_eval.json."""
from __future__ import annotations

import json

import numpy as np
import polars as pl

from nflbet import config, player_proj as M, props_projection as R
from nflbet.sim import Simulator

MARKETS = ["rec", "rec_yds", "rush_att", "rush_yds", "rush_rec_yds", "pass_att", "pass_cmp", "pass_yds", "pass_rush_yds"]
FLOOR = {"rec": 2, "rec_yds": 20, "rush_att": 6, "rush_yds": 25, "rush_rec_yds": 30, "pass_att": 20, "pass_cmp": 12,
         "pass_yds": 150, "pass_rush_yds": 160}
PASS = {"pass_att", "pass_cmp", "pass_yds", "pass_rush_yds"}
LEVEL = 0.05 / 9 / 2


def history(seasons: list[int]) -> pl.DataFrame:
    """Per player-game-market: baseline (prev-5 mean), prev-10 values (for the frequency), across seasons."""
    st = M.stats(sorted(set(seasons) | {s - 1 for s in seasons}))
    parts = []
    for m in MARKETS:
        x = st.select("player_id", "season", "week", "t", pl.col(m).cast(pl.Float64).alias("v")).sort("player_id", "t")
        x = x.with_columns(pl.col("v").shift(1).rolling_mean(5, min_samples=5).over("player_id").alias("base"),
                           pl.concat_list([pl.col("v").shift(i).over("player_id") for i in range(1, 11)]).alias("prev"))
        parts.append(x.with_columns(pl.lit(m).alias("market")))
    return pl.concat(parts).filter(pl.col("season").is_in(seasons))


def ll(p, y):
    p = np.clip(p, 0.02, 0.98)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def boot(diff: np.ndarray, cl: np.ndarray, n=4000, seed=7):
    ids = np.unique(cl)
    idx = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    bs = [diff[np.concatenate([idx[j] for j in rng.integers(0, len(ids), len(ids))])].mean() for _ in range(n)]
    return float(diff.mean()), [float(np.quantile(bs, LEVEL)), float(np.quantile(bs, 1 - LEVEL))]


def slope(p, y):
    """Logistic calibration slope by Newton's method on logit(p)."""
    z = np.log(np.clip(p, .01, .99) / (1 - np.clip(p, .01, .99)))
    X = np.c_[np.ones_like(z), z]
    b = np.zeros(2)
    for _ in range(25):
        q = 1 / (1 + np.exp(-X @ b))
        H = X.T @ (X * (q * (1 - q))[:, None]) + 1e-9 * np.eye(2)
        b += np.linalg.solve(H, X.T @ (y - q))
    return float(b[1])


def frame(seasons: list[int]) -> pl.DataFrame:
    proj = pl.concat([R.projections(s).select("player_id", "season", "week", "market", "pos", "proj", "actual") for s in seasons])
    h = history(seasons)
    d = proj.join(h.select("player_id", "season", "week", "market", "base", "prev"), on=["player_id", "season", "week", "market"])
    d = d.filter(pl.col("base").is_not_null(), pl.col("market").is_in(MARKETS))
    d = d.filter(pl.col("base") >= pl.col("market").replace_strict(FLOOR, return_dtype=pl.Float64),
                 ~pl.col("market").is_in(list(PASS)) | (pl.col("pos") == "QB"))
    sim = Simulator(fit_season=2024, seasons=sorted(set(seasons) | {s - 1 for s in seasons} | {2023, 2024}))
    rows = []
    for s in seasons:
        x = d.filter(pl.col("season") == s)
        out = sim.run(s, keep=set(zip(x["player_id"].to_list(), x["week"].to_list())))
        for r in x.iter_rows(named=True):
            smp = out.get((r["player_id"], r["week"]), {}).get(r["market"])
            if smp is None:
                continue
            line = np.floor(r["base"]) + 0.5
            prev = [v for v in (r["prev"] or []) if v is not None]
            rows.append({"season": s, "week": r["week"], "market": r["market"], "actual": r["actual"], "proj": r["proj"],
                         "base": r["base"], "line": line, "p_sim": float(np.mean(smp > line)),
                         "p_base": (sum(v > line for v in prev) + 1) / (len(prev) + 2),
                         "in50": float(np.quantile(smp, .25) <= r["actual"] <= np.quantile(smp, .75)),
                         "in80": float(np.quantile(smp, .10) <= r["actual"] <= np.quantile(smp, .90))})
    return pl.DataFrame(rows)


def evaluate(x: pl.DataFrame) -> dict:
    res = {}
    for m in MARKETS + ["all"]:
        z = x if m == "all" else x.filter(pl.col("market") == m)
        if not z.height:
            continue
        cl = (z["season"] * 100 + z["week"]).to_numpy()
        a = z["actual"].to_numpy()
        ea, eb = np.abs(z["proj"].to_numpy() - a), np.abs(z["base"].to_numpy() - a)
        y = (a > z["line"].to_numpy()).astype(float)
        ls, lb = ll(z["p_sim"].to_numpy(), y), ll(z["p_base"].to_numpy(), y)
        dA, ciA = boot(ea - eb, cl)
        dB, ciB = boot(ls - lb, cl)
        res[m] = {"n": z.height, "mae_proj": float(ea.mean()), "mae_base": float(eb.mean()), "mae_diff": dA, "mae_ci": ciA,
                  "proj_better": ciA[1] < 0, "ll_sim": float(ls.mean()), "ll_base": float(lb.mean()), "ll_diff": dB, "ll_ci": ciB,
                  "sim_better": ciB[1] < 0, "over_rate": float(y.mean()), "slope": slope(z["p_sim"].to_numpy(), y),
                  "in50": float(z["in50"].mean()), "in80": float(z["in80"].mean())}
        if m == "all":
            q = np.quantile(z["p_sim"].to_numpy(), np.linspace(0, 1, 11))
            res[m]["deciles"] = [(float(lo), float(hi), int(k.height), float(k["p_sim"].mean()), float((k["actual"] > k["line"]).mean()))
                                 for lo, hi in zip(q[:-1], q[1:])
                                 if (k := z.filter(pl.col("p_sim").is_between(lo, hi, closed="left" if hi < q[-1] else "both"))).height]
    return res


def main() -> None:
    out = {"2021-2023": evaluate(frame([2021, 2022, 2023])), "2025": evaluate(frame([2025]))}
    (config.ROOT / "data" / "backtests" / "accuracy_eval.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["# Model accuracy without lines", "", "Pre-registration: docs/accuracy_preregistration.md. Intervals: week-clustered, "
         "two-sided 0.05/9 (Bonferroni over 9 markets).", ""]
    for k, res in out.items():
        L += [f"## {k}", "", "| Market | n | MAE projection | MAE recent avg | Diff (interval) | Projection better | "
              "Log loss sim | Log loss recent freq | Diff (interval) | Sim better | Calib. slope | In 50% / 80% |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for m, r in res.items():
            L.append(f"| {m} | {r['n']} | {r['mae_proj']:.2f} | {r['mae_base']:.2f} | {r['mae_diff']:+.2f} ({r['mae_ci'][0]:+.2f} to {r['mae_ci'][1]:+.2f}) | "
                     f"{'yes' if r['proj_better'] else 'no'} | {r['ll_sim']:.4f} | {r['ll_base']:.4f} | {r['ll_diff']:+.4f} "
                     f"({r['ll_ci'][0]:+.4f} to {r['ll_ci'][1]:+.4f}) | {'yes' if r['sim_better'] else 'no'} | {r['slope']:.2f} | "
                     f"{r['in50']:.2f} / {r['in80']:.2f} |")
        L += ["", "Simulator calibration, all markets (decile of P(over pseudo-line): n, mean P, actual over rate):", ""]
        L += [f"- [{lo:.2f}, {hi:.2f}] n {n}: P {p:.3f}, over {o:.3f}" for lo, hi, n, p, o in res["all"]["deciles"]] + [""]
    (config.ROOT / "docs" / "accuracy_eval.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
