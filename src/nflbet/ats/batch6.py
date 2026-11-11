"""Batch 6 (docs/batch6_preregistration.md): key-number margins centered on the market line, priced against a line
away from the market (P1) and a push at the market's whole number (P2)."""
from __future__ import annotations

import numpy as np

from . import batch5 as B5

M = B5.M  # margins -60..60


def outcome_probs(pm, line):
    """(G, 3) P(home covers, push, away covers) at home line `line` (positive = home favored)."""
    line = np.asarray(line, float)[:, None]
    hc = (pm * (M[None, :] > line)).sum(1)
    pu = (pm * (M[None, :] == line)).sum(1)
    return np.stack([hc, pu, 1.0 - hc - pu], 1)


def outcome(margin, line):
    """0 home covers, 1 push, 2 away covers."""
    margin, line = np.asarray(margin, float), np.asarray(line, float)
    return np.where(margin > line, 0, np.where(margin == line, 1, 2))


def d_off_market(c, line, margin, k2, sig_n):
    """P1: log P_K2(outcome at line) - log P_N(outcome at line), centers at the close c."""
    o = outcome(margin, line)
    idx = np.arange(len(o))
    pk = outcome_probs(B5.k1_dist(c, k2["sigma"], k2["w"]), line)[idx, o]
    pn = outcome_probs(B5.k1_dist(c, sig_n, np.ones(B5.KMAX + 1)), line)[idx, o]
    return np.log(np.maximum(pk, 1e-300)) - np.log(np.maximum(pn, 1e-300))


def d_push(c, margin, k2, sig_n):
    """P2: push or not at the whole-number close c."""
    c = np.asarray(c, float)
    push = np.asarray(margin, float) == c
    pk = outcome_probs(B5.k1_dist(c, k2["sigma"], k2["w"]), c)[:, 1]
    pn = outcome_probs(B5.k1_dist(c, sig_n, np.ones(B5.KMAX + 1)), c)[:, 1]
    lk = np.where(push, np.log(np.maximum(pk, 1e-300)), np.log(np.maximum(1 - pk, 1e-300)))
    ln = np.where(push, np.log(np.maximum(pn, 1e-300)), np.log(np.maximum(1 - pn, 1e-300)))
    return lk - ln


KEYS = (3, 6, 7, 10, 14)


def fit(c, margin, keys=KEYS):
    """N: sigma by maximum likelihood with all weights 1. K2: w_k for k in `keys` = actual share of |margin| = k over
    the share N gives (all other weights stay 1), then sigma refit once with the weights fixed."""
    c, margin = np.asarray(c, float), np.asarray(margin, float)
    ones = np.ones(B5.KMAX + 1)
    sig_n = B5.E._golden(lambda s: -B5._lp(B5.k1_dist(c, s, ones), margin).sum(), 5.0, 25.0)
    base = B5.k1_dist(c, sig_n, ones)
    a = np.abs(margin)
    w = ones.copy()
    for k in keys:
        w[k] = max(np.mean(a == k), 1e-4) / max(base[:, np.abs(M) == k].sum(1).mean(), 1e-9)
    sig = B5.E._golden(lambda s: -B5._lp(B5.k1_dist(c, s, w), margin).sum(), 5.0, 25.0)
    return {"sigma_n": float(sig_n), "k2": {"sigma": float(sig), "w": w.tolist()}}


def lower(draws, level):
    return float(np.quantile(draws, level))
