"""Engine A layer 3: what players do with the ball.

Catches: each player's catch rate is drawn from a Beta posterior (position prior + his own targets and catches this
season and last), then receptions ~ Binomial(targets, rate), so receptions never exceed targets.
Yards: the yards on n catches (or n carries) are a draw from the empirical distribution of sums of n plays at the
player's position in the fit seasons, times a player factor shrunk toward 1, times a game-wide shock shared by the
team's receivers (or runners) in that run. Quarterback yards are the sum of his receivers' yards.
"""
from __future__ import annotations

import numpy as np

POSITIONS = ("QB", "RB", "WR", "TE", "OTH")
C_GRID = (5.0, 10.0, 20.0, 40.0, 80.0, 160.0)
NMAX = {"rec": 25, "rush": 50}
TABLE_DRAWS = 2000


def sum_table(pool: np.ndarray, nmax: int, rng: np.random.Generator, draws: int = TABLE_DRAWS) -> np.ndarray:
    """[nmax + 1, draws]: row n holds `draws` sums of n plays drawn from the pool (row 0 is zeros)."""
    picks = pool[rng.integers(0, len(pool), size=(nmax, draws))]
    return np.vstack([np.zeros((1, draws)), np.cumsum(picks, axis=0)])


def factor(yards: np.ndarray, n: np.ndarray, mu: np.ndarray, c: float) -> np.ndarray:
    """Player yards-per-play factor shrunk toward 1: (his yards + c x mu) / ((his plays + c) x mu)."""
    return np.clip((yards + c * mu) / ((n + c) * mu), 0.4, 2.5)


def fit_factor_strength(yards_hist, n_hist, mu, n_now, yards_now) -> float:
    """c that minimizes squared error of yards_now against n_now x mu x factor (plays in the game taken as given)."""
    err = [float(((yards_now - n_now * mu * factor(yards_hist, n_hist, mu, c)) ** 2).mean()) for c in C_GRID]
    return C_GRID[int(np.argmin(err))]


def fit_catch_strength(rec_hist, tgt_hist, rate, tgt_now, rec_now) -> float:
    """Prior strength c maximizing the beta-binomial likelihood of catches given targets in the game."""
    from scipy.special import betaln
    best = None
    for c in C_GRID:
        a, b = c * rate + rec_hist, c * (1 - rate) + np.maximum(tgt_hist - rec_hist, 0)
        ll = float((betaln(a + rec_now, b + tgt_now - rec_now) - betaln(a, b)).sum())
        if best is None or ll > best[0]:
            best = (ll, c)
    return best[1]


def shock_sd(actual: np.ndarray, expected: np.ndarray, sampling_var: np.ndarray) -> float:
    """Spread of the team-wide yardage multiplier: variance of actual / expected across team-games beyond what
    play-to-play sampling alone would give. 0 when sampling explains it all."""
    ok = expected > 0
    r = actual[ok] / expected[ok]
    extra = float(r.var() - (sampling_var[ok] / expected[ok] ** 2).mean())
    return float(np.sqrt(max(extra, 0.0)))
