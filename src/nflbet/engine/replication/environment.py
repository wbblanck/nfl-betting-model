"""Engine A layer 1: team volume. For each offense in a game, a joint draw of pass attempts and carries.

Means are a linear regression on the offense's and the opposing defense's earlier per-game volumes. The pair of
residuals (attempts, carries) is resampled together from the fit seasons, so a game that runs pass-heavy is
run-light the way real games are. Targets are a binomial share of attempts.
Version 0.1: the two teams in a game are drawn independently and volume does not respond to a simulated score.
"""
from __future__ import annotations

import numpy as np
import polars as pl

PAIRS = (("team_att", "A"), ("team_carries", "C"))
MIN = {"A": 8, "C": 5}


def _rate(df: pl.DataFrame, prefix: str, col: str, window: str) -> np.ndarray:
    n = df[f"{prefix}n_{window}"].to_numpy().astype(float)
    return np.where(n > 0, df[f"{prefix}{col}_{window}"].to_numpy() / np.maximum(n, 1), np.nan)


def design(team_rows: pl.DataFrame, league: dict) -> np.ndarray:
    """One row per offense-game. Columns: 1, then for attempts and for carries: offense last 8, offense season to
    date, offense last season, defense allowed last 8. A missing history is filled with the fit-season league mean."""
    cols = [np.ones(team_rows.height)]
    for col, _ in PAIRS:
        for prefix, window in (("o_", "w8"), ("o_", "std"), ("o_", "prev"), ("d_", "w8")):
            v = _rate(team_rows, prefix, col, window)
            cols.append(np.where(np.isnan(v), league[col], v))
    return np.column_stack(cols)


def fit(team_rows: pl.DataFrame, y: np.ndarray, targets: np.ndarray) -> dict:
    """y: [n, 2] actual (attempts, carries). Returns coefficients, the residual pairs and the target rate."""
    league = {col: float(y[:, i].mean()) for i, (col, _) in enumerate(PAIRS)}
    X = design(team_rows, league)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {"league": league, "coef": coef.tolist(), "resid": (y - X @ coef).tolist(),
            "target_rate": float(targets.sum() / y[:, 0].sum())}


def mean(params: dict, team_rows: pl.DataFrame) -> np.ndarray:
    return design(team_rows, params["league"]) @ np.array(params["coef"])


def draw(params: dict, mu: np.ndarray, sims: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """mu: (attempts, carries) mean for one offense-game. Returns integer arrays [sims]: attempts, carries, targets."""
    res = np.array(params["resid"])
    e = res[rng.integers(0, len(res), sims)]
    a = np.maximum(np.rint(mu[0] + e[:, 0]), MIN["A"]).astype(np.int64)
    c = np.maximum(np.rint(mu[1] + e[:, 1]), MIN["C"]).astype(np.int64)
    return a, c, rng.binomial(a, params["target_rate"]).astype(np.int64)
