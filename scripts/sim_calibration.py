"""Simulator calibration (docs/sim_calibration_preregistration.md): fit per-market logistic recalibration on
2021-2023 pseudo-line rows, test on 2024-2025 DraftKings lines. Writes docs/sim_calibration.md and
data/backtests/sim_calibration.json (fitted constants included)."""
from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import accuracy_eval as A  # noqa: E402

from nflbet import config  # noqa: E402
from nflbet.props import core as P  # noqa: E402
from nflbet.props import confirm as C  # noqa: E402
from nflbet.props import projection as R  # noqa: E402
from nflbet.props import selective as S  # noqa: E402
from nflbet.props import screener as Sc  # noqa: E402
from nflbet.props.sim import Simulator  # noqa: E402

MARKETS = A.MARKETS


def logit(p):
    p = np.clip(p, 0.01, 0.99)
    return np.log(p / (1 - p))


def fit(p, y):
    X = np.c_[np.ones_like(p), logit(p)]
    b = np.zeros(2)
    for _ in range(50):
        q = 1 / (1 + np.exp(-X @ b))
        b += np.linalg.solve(X.T @ (X * (q * (1 - q))[:, None]) + 1e-9 * np.eye(2), X.T @ (y - q))
    return float(b[0]), float(b[1])


def apply(p, ab):
    return 1 / (1 + np.exp(-(ab[0] + ab[1] * logit(p))))


def boot(diff, cl, n=4000, seed=7):
    ids = np.unique(cl)
    idx = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    bs = [diff[np.concatenate([idx[j] for j in rng.integers(0, len(ids), len(ids))])].mean() for _ in range(n)]
    return float(diff.mean()), [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))]


def dk_rows(season: int, sim: Simulator) -> pl.DataFrame:
    g = P.graded(P.join(P.load_lines(season), P.load_stats(season), P.load_snaps(season)))
    s = C.screened(g).filter(pl.col("result") != "push", pl.col("market").is_in(MARKETS))
    dk = s.filter(pl.col("book") == "DK NJ").unique(subset=C.KEY)
    out = sim.run(season, keep=set(zip(dk["player_id"].to_list(), dk["week"].to_list())))
    p = [float(np.mean(out[(a, w)][m] > l)) if (a, w) in out and m in out[(a, w)] else None
         for a, w, m, l in zip(dk["player_id"], dk["week"], dk["market"], dk["line"])]
    return dk.with_columns(pl.Series("p_sim", p, dtype=pl.Float64)).filter(pl.col("p_sim").is_not_null()), s, out


def main() -> None:
    tr = A.frame([2021, 2022, 2023])
    y_tr = (tr["actual"] > tr["line"]).cast(pl.Float64).to_numpy()
    const = {}
    for m in MARKETS:
        k = (tr["market"] == m).to_numpy()
        const[m] = fit(tr["p_sim"].to_numpy()[k], y_tr[k])
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    res, rows, s1 = {"constants": const}, [], {}
    for season in (2024, 2025):
        dk, s, out = dk_rows(season, sim)
        pc = np.array([apply(p, const[m]) for p, m in zip(dk["p_sim"].to_numpy(), dk["market"].to_list())])
        dk = dk.with_columns(pl.Series("p_cal", pc), pl.lit(season).alias("season"))
        rows.append(dk.select("season", "week", "player_id", "market", "line", "p_over", "p_sim", "p_cal", "result"))
        # descriptive: S1 with the corrected simulator vote
        sc = Sc.score(s, R.projections(season), out)
        cal = [apply(p, const[m]) if p is not None else None for p, m in zip(sc["p_sim"].to_list(), sc["market"].to_list())]
        sc = sc.with_columns(pl.Series("p_sim", cal, dtype=pl.Float64))
        sc = sc.with_columns(pl.when(pl.col("p_over") - pl.col("p_sim") >= 0.05).then(-1)
                             .when(pl.col("p_sim") - pl.col("p_over") >= 0.05).then(1).otherwise(0).fill_null(0).alias("v_sim"))
        b = Sc.rule_s1(sc).with_columns(pl.lit(season).alias("season"))
        r = S.evaluate(Sc.bets_frame(b), level=0.025) if b.height else {"n": 0}
        s1[season] = r
    d = pl.concat(rows)
    y = (d["result"] == "over").cast(pl.Float64).to_numpy()
    lr, lc, lk = A.ll(d["p_sim"].to_numpy(), y), A.ll(d["p_cal"].to_numpy(), y), A.ll(d["p_over"].to_numpy(), y)
    cl = d["player_id"].to_numpy()
    prim, ci = boot(lc - lr, cl)
    k25 = (d["season"] == 2025).to_numpy()
    d25 = float((lc - lr)[k25].mean())
    res["primary"] = {"n": d.height, "ll_raw": float(lr.mean()), "ll_cal": float(lc.mean()), "ll_dk": float(lk.mean()),
                      "diff": prim, "ci": ci, "diff_2025": d25, "pass": bool(ci[1] < 0 and d25 < 0)}
    res["by_season"] = {int(sn): {"n": int(k.sum()), "raw": float(lr[k].mean()), "cal": float(lc[k].mean()), "dk": float(lk[k].mean())}
                        for sn in (2024, 2025) for k in [(d["season"] == sn).to_numpy()]}
    res["by_market"] = {m: {"n": int(k.sum()), "raw": float(lr[k].mean()), "cal": float(lc[k].mean()), "dk": float(lk[k].mean()),
                            "a": const[m][0], "b": const[m][1]} for m in MARKETS for k in [(d["market"] == m).to_numpy()]}
    q = np.quantile(d["p_cal"].to_numpy(), np.linspace(0, 1, 11))
    res["deciles_cal"] = [(float(lo), float(hi), int(z.height), float(z["p_cal"].mean()), float((z["result"] == "over").mean()))
                          for lo, hi in zip(q[:-1], q[1:])
                          if (z := d.filter(pl.col("p_cal").is_between(lo, hi, closed="left" if hi < q[-1] else "both"))).height]
    res["s1_with_corrected_sim"] = s1
    (config.ROOT / "data" / "backtests" / "sim_calibration.json").write_text(json.dumps(res, indent=1, default=str))
    p_ = res["primary"]
    L = ["# Simulator calibration: result", "", "Pre-registration: docs/sim_calibration_preregistration.md.", "",
         f"**Primary (2024-2025 DraftKings lines, {p_['n']} props):** log loss raw {p_['ll_raw']:.4f}, corrected {p_['ll_cal']:.4f} "
         f"(DraftKings de-vigged {p_['ll_dk']:.4f}, coin 0.6931). Difference {p_['diff']:+.4f}, 95% interval "
         f"{p_['ci'][0]:+.4f} to {p_['ci'][1]:+.4f}; 2025 alone {p_['diff_2025']:+.4f}. **{'PASS' if p_['pass'] else 'FAIL'}**.", "",
         "| Season | n | Raw | Corrected | DraftKings |", "|---|---|---|---|---|"]
    L += [f"| {k} | {v['n']} | {v['raw']:.4f} | {v['cal']:.4f} | {v['dk']:.4f} |" for k, v in res["by_season"].items()]
    L += ["", "| Market | a | b (slope) | n | Raw | Corrected | DraftKings |", "|---|---|---|---|---|---|---|"]
    L += [f"| {m} | {v['a']:+.2f} | {v['b']:.2f} | {v['n']} | {v['raw']:.4f} | {v['cal']:.4f} | {v['dk']:.4f} |" for m, v in res["by_market"].items()]
    L += ["", "Corrected calibration (decile: n, mean P, over rate):", ""]
    L += [f"- [{lo:.2f}, {hi:.2f}] n {n}: P {pp:.3f}, over {o:.3f}" for lo, hi, n, pp, o in res["deciles_cal"]]
    L += ["", "Descriptive only (seasons S1 was built on): S1 with the corrected simulator in its simulator vote:", ""]
    for sn, r in s1.items():
        L.append(f"- {sn}: " + (f"n {r['n']}, weeks {r['weeks']}, win {r['under_rate']:.1%}, ROI {r['roi']:+.1%}" if r.get("n") else "0 bets"))
    (config.ROOT / "docs" / "sim_calibration.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
