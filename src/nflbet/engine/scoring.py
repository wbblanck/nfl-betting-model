"""Scores for predictive distributions over non-negative integers (counts and whole yards).

A forecast is a matrix of cumulative probabilities F[i, k] = P(Y_i <= k) for k = 0..K. Outcomes below 0 (a
quarterback's kneel-downs) are scored as they are: every F(k) is then on the wrong side and the score says so.
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def nb_cdf(mean: np.ndarray, size: float | np.ndarray, kmax: int) -> np.ndarray:
    """Negative binomial CDF matrix [n, kmax + 1] with the given means and size r (variance = mean + mean^2 / r)."""
    mean = np.maximum(np.asarray(mean, float), 1e-6)[:, None]
    size = np.broadcast_to(np.asarray(size, float), mean.shape[:1])[:, None]
    return stats.nbinom.cdf(np.arange(kmax + 1)[None, :], size, size / (size + mean))


def crps(cdf: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Continuous ranked probability score per row: sum over k of (F(k) - 1[y <= k])^2, plus the tail beyond the
    grid for an outcome above it. Lower is better; a perfect point forecast scores 0."""
    y = np.asarray(y, float)
    k = np.arange(cdf.shape[1])[None, :]
    step = (y[:, None] <= k).astype(float)
    below = np.clip(-y, 0, None)                       # k = y..-1 for a negative outcome: F = 0, step = 1
    above = np.clip(y - cdf.shape[1], 0, None)         # k = K+1..y-1 beyond the grid: F is taken as F(K), step = 0
    return ((cdf - step) ** 2).sum(axis=1) + below + above * (cdf[:, -1] ** 2)


def quantile(cdf: np.ndarray, q: float) -> np.ndarray:
    """Smallest k with F(k) >= q, per row."""
    return (cdf < q).sum(axis=1).clip(max=cdf.shape[1] - 1)


def coverage(cdf: np.ndarray, y: np.ndarray, level: float) -> float:
    """Share of outcomes inside the central interval of the given level (both ends included)."""
    lo, hi = quantile(cdf, (1 - level) / 2), quantile(cdf, 1 - (1 - level) / 2)
    return float(((y >= lo) & (y <= hi)).mean())


def pinball(cdf: np.ndarray, y: np.ndarray, q: float) -> float:
    """Mean pinball (quantile) loss at level q."""
    d = np.asarray(y, float) - quantile(cdf, q)
    return float(np.where(d >= 0, q * d, (q - 1) * d).mean())


def fit_nb_size(mean: np.ndarray, y: np.ndarray, grid=None) -> float:
    """Size r that maximizes the negative binomial likelihood of y (clipped at 0) given the means. Grid search:
    the likelihood is smooth and one-dimensional, and a grid cannot wander off."""
    grid = np.exp(np.linspace(np.log(0.2), np.log(200), 70)) if grid is None else grid
    mean, y = np.maximum(np.asarray(mean, float), 1e-6), np.clip(np.asarray(y), 0, None)
    ll = [stats.nbinom.logpmf(y, r, r / (r + mean)).sum() for r in grid]
    return float(grid[int(np.argmax(ll))])


def paired_bootstrap(diff: np.ndarray, cluster: np.ndarray, n: int = 10_000, seed: int = 0, level: float = 0.05) -> tuple[float, float, float]:
    """Mean of diff and its (level/2, 1 - level/2) interval, resampling whole clusters (weeks) with replacement."""
    ids, inv = np.unique(cluster, return_inverse=True)
    sums, counts = np.bincount(inv, weights=diff), np.bincount(inv).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(ids), size=(n, len(ids)))
    means = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    return float(diff.mean()), float(np.quantile(means, level / 2)), float(np.quantile(means, 1 - level / 2))
