"""Engine B yardage (MODEL_SPECIFICATION 3.2).

Gradient-boosted quantile regression (xgboost, one model for all levels) at LEVELS, conditional on the same
features as the count model plus that model's mean. Crossing is removed by sorting each row's quantiles
(rearrangement). Between 0.05 and 0.95 the quantile function is piecewise linear. Tails, with scales fitted on the
tune seasons' exceedances:
  below 0.05: uniform on [q05 - lo * (q25 - q05), q05]   (mean shortfall below q05 = half that width)
  above 0.95: q95 + exponential with scale hi * (q95 - q75) (mean excess above q95 = that scale)
So any line can be priced from the distribution, and runs are drawn by inverting it.
"""
from __future__ import annotations

import numpy as np

LEVELS = np.array([0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
# Chosen on the tune seasons from five settings (docs/engine/engine_b_tune.md): shallow trees kept the bands honest.
PARAMS = {"max_depth": 2, "learning_rate": 0.05, "n_estimators": 300, "min_child_weight": 20, "subsample": 0.8,
          "colsample_bytree": 0.8, "reg_lambda": 1.0}


def fit(X: np.ndarray, y: np.ndarray, seed: int = 0, params: dict | None = None):
    """One booster for all LEVELS (xgboost's native API; no scikit-learn needed)."""
    import xgboost as xgb
    p = dict(params or PARAMS)
    rounds = p.pop("n_estimators")
    p.update({"objective": "reg:quantileerror", "quantile_alpha": LEVELS, "tree_method": "hist", "seed": seed, "nthread": 4})
    return xgb.train(p, xgb.DMatrix(X, label=np.asarray(y, float)), num_boost_round=rounds)


def raw(model, X: np.ndarray) -> np.ndarray:
    """[rows, len(LEVELS)] quantiles as the booster gives them (may cross)."""
    import xgboost as xgb
    return np.asarray(model.predict(xgb.DMatrix(X)), float).reshape(len(X), len(LEVELS))


def predict(model, X: np.ndarray) -> np.ndarray:
    """[rows, len(LEVELS)] quantiles after rearrangement (sorted along each row)."""
    return np.sort(raw(model, X), axis=1)


def crossings(q: np.ndarray) -> int:
    """Rows whose quantiles are not non-decreasing."""
    return int((np.diff(q, axis=1) < -1e-9).any(axis=1).sum())


def fit_tails(q: np.ndarray, y: np.ndarray) -> dict:
    """Tail scales from outcomes beyond the 0.05 and 0.95 quantiles (ratio estimators; see module doc)."""
    y = np.asarray(y, float)
    up = y > q[:, -1]
    lo = y < q[:, 0]
    w_hi = np.maximum(q[:, -1] - q[:, 4], 1.0)
    w_lo = np.maximum(q[:, 2] - q[:, 0], 1.0)
    hi = float((y[up] - q[up, -1]).sum() / w_hi[up].sum()) if up.any() else 1.0
    lo_ = float(2 * (q[lo, 0] - y[lo]).sum() / w_lo[lo].sum()) if lo.any() else 1.0
    return {"hi": hi, "lo": lo_, "n_hi": int(up.sum()), "n_lo": int(lo.sum()), "share_hi": float(up.mean()), "share_lo": float(lo.mean())}


def quantile_fn(q: np.ndarray, tails: dict, u: np.ndarray) -> np.ndarray:
    """Inverse CDF at probabilities u [rows, k] for rows of rearranged quantiles q [rows, len(LEVELS)]."""
    out = np.empty_like(u, dtype=float)
    mid = (u >= LEVELS[0]) & (u <= LEVELS[-1])
    idx = np.clip(np.searchsorted(LEVELS, u, side="right") - 1, 0, len(LEVELS) - 2)
    rows = np.broadcast_to(np.arange(len(q))[:, None], u.shape)
    a, b = LEVELS[idx], LEVELS[idx + 1]
    qa, qb = q[rows, idx], q[rows, idx + 1]
    out[mid] = (qa + (qb - qa) * (u - a) / (b - a))[mid]
    w_lo = np.maximum(q[:, 2] - q[:, 0], 1.0)[:, None] * tails["lo"]
    w_hi = np.maximum(q[:, -1] - q[:, 4], 1.0)[:, None] * tails["hi"]
    low = u < LEVELS[0]
    out[low] = np.broadcast_to(q[:, :1] - w_lo * (1 - u / LEVELS[0]), u.shape)[low]
    high = u > LEVELS[-1]
    out[high] = np.broadcast_to(q[:, -1:] - w_hi * np.log(np.clip((1 - u) / (1 - LEVELS[-1]), 1e-12, 1)), u.shape)[high]
    return out


def draw(rng: np.random.Generator, q: np.ndarray, tails: dict, sims: int) -> np.ndarray:
    """Whole-yard runs [rows, sims]."""
    u = rng.random((len(q), sims))
    return np.rint(quantile_fn(q, tails, u)).astype(np.int32)
