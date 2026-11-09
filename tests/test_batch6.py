"""Known-answer checks for batch 6 (docs/batch6_preregistration.md, checks 1-4)."""
import numpy as np
from scipy.stats import norm

from nflbet.ats import batch5 as B5
from nflbet.ats import batch6 as B6

ONES = np.ones(B5.KMAX + 1)


def cboot(d, cl, rng, n=400):
    ids = np.unique(cl)
    grp = [np.where(cl == c)[0] for c in ids]
    return np.array([d[np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])].mean() for _ in range(n)])


def test_hand_case():
    w = ONES.copy()
    w[3] = 2.0
    pm = B5.k1_dist([3.0], 13.0, w)[0]
    raw = norm.pdf((B5.M - 3.0) / 13.0) * np.where(np.abs(B5.M) == 3, 2.0, 1.0)
    raw /= raw.sum()
    assert np.allclose(pm, raw)
    p = B6.outcome_probs(pm[None, :], [3.0])[0]
    assert abs(p[1] - raw[B5.M == 3].sum()) < 1e-12
    assert abs(p.sum() - 1) < 1e-12
    p35 = B6.outcome_probs(pm[None, :], [3.5])[0]
    assert abs(p35[0] - raw[B5.M > 3.5].sum()) < 1e-12
    assert B6.outcome([4, 3, 2], [3, 3, 3]).tolist() == [0, 1, 2]


def test_half_point_and_reduction():
    pm = B5.k1_dist([2.5, -6.5], 13.0, ONES)
    assert np.allclose(B6.outcome_probs(pm, [2.5, -6.5])[:, 1], 0)
    d = B6.d_off_market(np.array([3.0, -7.0]), np.array([2.5, -6.0]), np.array([10, -6]),
                        {"sigma": 13.0, "w": ONES}, 13.0)
    assert np.allclose(d, 0)


# realistic centers: whole numbers half the time, extra mass on 3 and 7 (as closing spreads are)
CENTERS = np.concatenate([np.arange(-14, 14.5, 0.5), np.repeat([-7.0, -3.0, 3.0, 7.0], 8)])


def planted(rng, n, w, sigma=13.2):
    c = rng.choice(CENTERS, n)
    pm = B5.k1_dist(c, sigma, w)
    m = np.array([rng.choice(B5.M, p=row) for row in pm])
    return c, m


def test_planted_signal_found():
    rng = np.random.default_rng(11)
    w = ONES.copy()
    w[3], w[7] = 2.5, 1.8
    cf, mf = planted(rng, 1300, w)
    f = B6.fit(cf, mf)
    assert abs(f["k2"]["w"][3] / 2.5 - 1) < 0.25 and f["k2"]["w"][5] == 1.0
    hits1 = hits2 = 0
    for _ in range(20):
        c, m = planted(rng, 2700, w)
        line = c + rng.choice([-1.0, -0.5, 0.5, 1.0], len(c))
        wk = rng.integers(0, 150, len(c))
        d1 = B6.d_off_market(c, line, m, f["k2"], f["sigma_n"])
        hits1 += B6.lower(cboot(d1, wk, rng), 0.025) > 0
        whole = c == np.round(c)
        d2 = B6.d_push(c[whole], m[whole], f["k2"], f["sigma_n"])
        hits2 += B6.lower(cboot(d2, wk[whole], rng), 0.025) > 0
    assert hits1 >= 10 and hits2 >= 6, (hits1, hits2)  # power check: about 65% and 50% expected


def test_null_rarely_passes():
    rng = np.random.default_rng(12)
    cf, mf = planted(rng, 1300, ONES)
    f = B6.fit(cf, mf)
    hits = 0
    for _ in range(60):
        c, m = planted(rng, 1350, ONES)
        whole = c == np.round(c)
        wk = rng.integers(0, 75, len(c))
        d2 = B6.d_push(c[whole], m[whole], f["k2"], f["sigma_n"])
        hits += B6.lower(cboot(d2, wk[whole], rng), 0.025) > 0
    assert hits <= 6, hits
