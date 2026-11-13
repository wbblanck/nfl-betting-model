"""Engine A layer 2: who gets the ball. A team's targets, carries and pass attempts are split among the active
players with a Dirichlet-multinomial: shares are uncertain (Dirichlet), then the fixed total is dealt out
(multinomial), so player counts always add up to the team's.

Expected share of player i: (his count over a window + m x prior) / (his team's count in those games + m), where
the prior is the average share of an active player at his position; a last bucket "other" (non-skill players)
gets its average share; then all are scaled to sum to 1. The window, m and the concentration kappa are chosen by
likelihood on the fit seasons. Higher kappa = shares closer to expected.
"""
from __future__ import annotations

import numpy as np
from scipy.special import gammaln

WINDOWS = ("w3", "w5", "w8", "std")
M_GRID = (2.0, 5.0, 10.0, 20.0, 40.0, 80.0)
KAPPA_GRID = tuple(float(k) for k in np.exp(np.linspace(np.log(3), np.log(600), 24)))


def expected_shares(count: np.ndarray, denom: np.ndarray, prior: np.ndarray, m: float, other: float) -> np.ndarray:
    """[..., K] player arrays -> [..., K + 1] shares summing to 1, 'other' last. Padded slots carry prior 0 and count 0."""
    raw = (count + m * prior) / (denom + m)
    raw = np.where(prior > 0, np.maximum(raw, 1e-4), 0.0)
    full = np.concatenate([raw, np.full(raw.shape[:-1] + (1,), other)], axis=-1)
    return full / full.sum(axis=-1, keepdims=True)


def dm_loglik(x: np.ndarray, mu: np.ndarray, kappa: float) -> float:
    """Dirichlet-multinomial log-likelihood (up to the multinomial constant) of counts x [G, K] given expected
    shares mu [G, K] and concentration kappa. Slots with mu = 0 must have x = 0 and contribute nothing."""
    a = kappa * mu
    live = mu > 0
    term = np.where(live, gammaln(x + np.where(live, a, 1.0)) - gammaln(np.where(live, a, 1.0)), 0.0)
    return float((gammaln(kappa) - gammaln(kappa + x.sum(axis=1)) + term.sum(axis=1)).sum())


def fit(counts: dict[str, np.ndarray], denoms: dict[str, np.ndarray], prior: np.ndarray, x: np.ndarray, other: float) -> dict:
    """counts / denoms: window -> [G, K]; prior [G, K] (0 in padded slots); x [G, K + 1] actual counts with 'other'
    last. Returns the window, m and kappa with the highest likelihood."""
    best = None
    for w in counts:
        for m in M_GRID:
            mu = expected_shares(counts[w], denoms[w], prior, m, other)
            for k in KAPPA_GRID:
                ll = dm_loglik(x, mu, k)
                if best is None or ll > best[0]:
                    best = (ll, w, m, k)
    return {"window": best[1], "m": best[2], "kappa": best[3], "other": other, "loglik": best[0]}


def allocate(rng: np.random.Generator, total: np.ndarray, mu: np.ndarray, kappa: float) -> np.ndarray:
    """total [sims] -> counts [sims, K]: shares ~ Dirichlet(kappa x mu), counts ~ Multinomial(total, shares)."""
    g = rng.gamma(np.maximum(kappa * mu, 1e-9), size=(len(total), len(mu)))
    return rng.multinomial(total, g / g.sum(axis=1, keepdims=True)).astype(np.int64)
