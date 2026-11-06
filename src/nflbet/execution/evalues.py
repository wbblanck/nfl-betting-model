"""Anytime-valid e-process for a tracker's bets (docs/m20_evalues_preregistration.md). Descriptive readout only."""
from __future__ import annotations

import numpy as np

LAMBDAS = (0.025, 0.05, 0.1, 0.2)
ALPHA = 0.05


def eprocess(units, lambdas=LAMBDAS) -> np.ndarray:
    """E_t after each bet: mean over lambda of prod(1 + lambda * u_i). units: profit per unit staked (>= -1)."""
    u = np.asarray(units, float)
    if (u < -1).any():
        raise ValueError("a bet cannot lose more than its stake")
    if not len(u):
        return np.array([])
    paths = np.cumprod(1.0 + np.outer(np.asarray(lambdas, float), u), axis=1)
    return paths.mean(axis=0)


def summary(units, k: int = 1) -> dict:
    e = eprocess(units)
    thr = k / ALPHA
    return {"bets": int(len(e)), "units": float(np.sum(units)) if len(e) else 0.0,
            "e": float(e[-1]) if len(e) else 1.0, "e_max": float(e.max()) if len(e) else 1.0,
            "threshold": thr, "crossed": bool(len(e) and e.max() >= thr)}
