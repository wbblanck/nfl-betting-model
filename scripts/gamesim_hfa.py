"""Re-fit the simulator's home-field yard factor on 2016-2020 (docs/gamesim_preregistration.md). The first fit in
gamesim_explore.py used a straight line through 0, 0.05 and 0.1, but mean margin is not linear in the factor there,
so its check failed (K3a: 0.70 vs 1.51). This uses bisection with 200,000 simulated equal-team games per step.
Usage: python scripts/gamesim_hfa.py <cache dir>"""
from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.ats import rating as A
from nflbet.gamesim import engine as E, run as R

FIT = list(range(2016, 2021))


def main(d):
    path = config.ROOT / "data" / "backtests" / "gamesim_constants.json"
    k = json.loads(path.read_text())
    tb = E.Tables(json.loads((config.ROOT / "data" / "backtests" / "gamesim_league.json").read_text()))
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in FIT], how="diagonal_relaxed")
    kicks, xps = R.kick_pools(pbp)
    ks = kicks["y"].to_numpy().astype(float)
    xpr = float(xps["good"].mean())
    target = float(A.games(FIT).filter(~pl.col("neutral"))["result"].mean())
    N = 200000
    z = {f: np.zeros((N, 2)) for f in E.FACTORS}

    def margin(v, seed):
        h, a = E.simulate(tb, z, z, ([ks], np.zeros(N, int)), np.full(N, xpr), np.full(N, 2019), v, seed=seed)
        return float((h - a).mean())

    lo, hi, log = 0.0, 0.06, []
    for i in range(7):
        mid = (lo + hi) / 2
        m = margin(mid, 300 + i)
        log.append((round(mid, 5), round(m, 3)))
        lo, hi = (mid, hi) if m < target else (lo, mid)
    hfa = (lo + hi) / 2
    check = margin(hfa, 999)
    k["hfa_first_fit"] = k["hfa"]
    k["hfa"] = hfa
    k["hfa_refit"] = {"target": target, "steps": log, "check_mean_margin": check}
    path.write_text(json.dumps(k, indent=1))
    msg = (f"HFA refit (bisection, 200k games per step): steps {log}; yard factor {hfa:.4f}; check mean margin "
           f"{check:.3f} vs target {target:.3f}: K3a {'PASS' if abs(check - target) <= 0.5 else 'FAIL'}")
    with open(config.ROOT / "docs" / "gamesim_explore.txt", "a") as f:
        f.write(msg + "\n")
    print(msg)


if __name__ == "__main__":
    main(sys.argv[1])
