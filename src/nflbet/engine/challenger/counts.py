"""Engine B counts (MODEL_SPECIFICATION 3.1).

Negative binomial regression with a log link for a player's volume (pass attempts, carries, targets):
    log mean = X beta,  log size = gamma[position] + delta * instability,
fitted by maximum likelihood with a small ridge penalty on beta (not on the intercept). Player and team effects
enter through the player's and team's own trailing rates; there is no separate random-effect term in this version.

Receptions given targets: beta-binomial with the player's catch rate shrunk toward his position's rate,
    p_i = (catches_i + m * pos_rate) / (targets_i + m),  rec | targets ~ BetaBinomial(targets, p_i kappa, (1 - p_i) kappa),
with m and kappa fitted by likelihood on the fit seasons.
"""
from __future__ import annotations

import numpy as np
from scipy import optimize, special, stats

POSITIONS = ("QB", "RB", "WR", "TE")


def nb_loglik(y: np.ndarray, mu: np.ndarray, r: np.ndarray) -> np.ndarray:
    return (special.gammaln(y + r) - special.gammaln(r) - special.gammaln(y + 1)
            + r * np.log(r / (r + mu)) + y * np.log(mu / (r + mu)))


def fit_nb(X: np.ndarray, y: np.ndarray, pos: np.ndarray, inst: np.ndarray, ridge: float = 1.0) -> dict:
    """X standardized, without an intercept column (one is added). Returns beta (intercept first), gamma per
    position and delta."""
    n, k = X.shape
    Z = np.column_stack([np.ones(n), X])
    P = np.array([[p == q for q in POSITIONS] for p in pos], float)
    y = np.clip(np.asarray(y, float), 0, None)
    b0 = np.zeros(k + 1)
    b0[0] = np.log(max(y.mean(), 0.1))
    theta0 = np.concatenate([b0, np.full(len(POSITIONS), np.log(5.0)), [0.0]])

    def nll(theta):
        beta, gam, dlt = theta[:k + 1], theta[k + 1:k + 1 + len(POSITIONS)], theta[-1]
        eta = np.clip(Z @ beta, -10, 8)
        mu = np.exp(eta)
        lr = np.clip(P @ gam + dlt * inst, -5, 8)
        r = np.exp(lr)
        ll = nb_loglik(y, mu, r)
        g_eta = (y - mu) * r / (mu + r)
        g_r = (special.digamma(y + r) - special.digamma(r) + np.log(r / (r + mu)) + 1 - (y + r) / (r + mu)) * r
        grad = np.concatenate([Z.T @ g_eta, P.T @ g_r, [inst @ g_r]])
        pen = 0.5 * ridge * (beta[1:] ** 2).sum()
        grad[1:k + 1] -= ridge * beta[1:]
        return -(ll.sum() - pen) / n, -grad / n

    res = optimize.minimize(nll, theta0, jac=True, method="L-BFGS-B", options={"maxiter": 2000})
    th = res.x
    return {"beta": th[:k + 1].tolist(), "gamma": dict(zip(POSITIONS, th[k + 1:k + 1 + len(POSITIONS)].tolist())),
            "delta": float(th[-1]), "converged": bool(res.success), "n": int(n)}


def nb_params(fit: dict, X: np.ndarray, pos: np.ndarray, inst: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(mean, size) per row."""
    beta = np.asarray(fit["beta"])
    mu = np.exp(np.clip(beta[0] + X @ beta[1:], -10, 8))
    lr = np.array([fit["gamma"].get(p, fit["gamma"]["WR"]) for p in pos]) + fit["delta"] * inst
    return mu, np.exp(np.clip(lr, -5, 8))


def nb_draw(rng: np.random.Generator, mu: np.ndarray, r: np.ndarray, sims: int) -> np.ndarray:
    """[rows, sims] negative binomial draws (gamma-Poisson)."""
    lam = rng.gamma(r[:, None], (mu / r)[:, None], size=(len(mu), sims))
    return rng.poisson(lam).astype(np.int32)


def catch_prior(rec: np.ndarray, tgt: np.ndarray, pos: np.ndarray) -> dict:
    """Position catch rates from fit-season totals."""
    return {p: float(rec[pos == p].sum() / max(tgt[pos == p].sum(), 1)) for p in POSITIONS}


def catch_rate(hist_rec: np.ndarray, hist_tgt: np.ndarray, pos: np.ndarray, prior: dict, m: float) -> np.ndarray:
    base = np.array([prior.get(p, prior["WR"]) for p in pos])
    return (hist_rec + m * base) / (hist_tgt + m)


def fit_catch(y_rec: np.ndarray, y_tgt: np.ndarray, hist_rec: np.ndarray, hist_tgt: np.ndarray, pos: np.ndarray,
              prior: dict) -> dict:
    """Grid search over (m, kappa) for the beta-binomial likelihood of this game's catches given its targets."""
    keep = y_tgt > 0
    best = None
    for m in (10, 20, 40, 80, 160):
        p = np.clip(catch_rate(hist_rec[keep], hist_tgt[keep], pos[keep], prior, m), 0.02, 0.98)
        for kappa in (5, 10, 20, 40, 80, 160, 400):
            ll = stats.betabinom.logpmf(y_rec[keep], y_tgt[keep], p * kappa, (1 - p) * kappa).sum()
            if best is None or ll > best[0]:
                best = (ll, m, kappa)
    return {"m": float(best[1]), "kappa": float(best[2]), "prior": prior}


def catch_draw(rng: np.random.Generator, tgt: np.ndarray, p: np.ndarray, kappa: float) -> np.ndarray:
    """Receptions [rows, sims] given simulated targets [rows, sims] and catch rates p [rows]."""
    p = np.clip(p, 0.02, 0.98)[:, None]
    q = rng.beta(p * kappa, (1 - p) * kappa, size=tgt.shape)
    return rng.binomial(tgt, q).astype(np.int32)


def fit_logit(X: np.ndarray, z: np.ndarray, ridge: float = 1.0) -> list[float]:
    """Ridge logistic regression of a 0/1 outcome on standardized X (intercept added, not penalized)."""
    n, k = X.shape
    Z = np.column_stack([np.ones(n), X])
    z = np.asarray(z, float)
    b0 = np.zeros(k + 1)
    b0[0] = np.log(max(z.mean(), 1e-4) / max(1 - z.mean(), 1e-4))

    def nll(b):
        eta = np.clip(Z @ b, -30, 30)
        ll = z * eta - np.logaddexp(0, eta)
        g = Z.T @ (z - special.expit(eta))
        g[1:] -= ridge * b[1:]
        return -(ll.sum() - 0.5 * ridge * (b[1:] ** 2).sum()) / n, -g / n

    return optimize.minimize(nll, b0, jac=True, method="L-BFGS-B", options={"maxiter": 2000}).x.tolist()


def logit_prob(beta: list[float], X: np.ndarray) -> np.ndarray:
    b = np.asarray(beta)
    return special.expit(np.clip(b[0] + X @ b[1:], -30, 30))


def hurdle_draw(rng: np.random.Generator, p0: np.ndarray, mu: np.ndarray, r: np.ndarray, sims: int) -> np.ndarray:
    """Zero with probability p0, otherwise a zero-truncated negative binomial draw (zeros redrawn)."""
    x = nb_draw(rng, mu, r, sims)
    for _ in range(50):
        z = x == 0
        if not z.any():
            break
        rows = np.nonzero(z.any(axis=1))[0]
        redraw = nb_draw(rng, mu[rows], r[rows], sims)
        sub = x[rows]
        sub[z[rows]] = redraw[z[rows]]
        x[rows] = sub
    x[x == 0] = 1                                      # a mean near zero that never drew a positive value
    return np.where(rng.random(x.shape) < p0[:, None], 0, x).astype(np.int32)
