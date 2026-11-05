"""Known-answer checks for scripts/ats_hybrid.py (docs/ats_hybrid_preregistration.md)."""
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import ats_hybrid as H  # noqa: E402


def frame(o, c, f, m, odds=None):
    n = len(o)
    d = {"season": [2010] * n, "week": [2 + i % 12 for i in range(n)], "home_open": o, "home_close": c, "fair": f,
         "result": m}
    if odds is not None:
        d |= {"home_close_odds": odds, "away_close_odds": odds}
    return pl.DataFrame(d)


def test_selection_and_side():
    # moved +2 (home), rating agrees -> home bet; moved +2, rating disagrees -> no bet; moved +1 -> no bet;
    # moved -2 (away), rating agrees -> away bet
    x = frame([0.0, 0.0, 0.0, 0.0], [2.0, 2.0, 1.0, -2.0], [3.0, -1.0, 3.0, -4.0], [10.0, 10.0, 10.0, -10.0])
    b = H.bets(x)
    assert b["n"] == 2 and b["cover"] == 1.0
    assert abs(b["roi"] - 100 / 110) < 1e-9
    assert H.bets(x, rating="none")["n"] == 3


def test_push_and_price():
    x = frame([0.0, 0.0], [3.0, 3.0], [5.0, 5.0], [3.0, 0.0], odds=[150.0, 150.0])
    b = H.bets(x)
    assert b["n"] == 2 and b["cover"] == 0.0 and abs(b["roi"] - (-0.5)) < 1e-9   # one push (0), one loss (-1)


def test_strict():
    # moved +2 to close 2; fair 1.5 is above open but below close -> agree yes, strict no
    x = frame([0.0], [2.0], [1.5], [10.0])
    assert H.bets(x)["n"] == 1 and H.bets(x, rating="strict")["n"] == 0


def test_planted_signal_found_noise_not():
    rng = np.random.default_rng(0)
    n = 3000
    o = np.zeros(n)
    c = rng.choice([-3.0, -2.0, 2.0, 3.0], n)
    f = c * 2
    noise = rng.normal(0, 13, n)
    planted = H.test(frame(o, c, f, c + np.sign(c) * 4 + noise))       # moved side covers by 4 on average
    null = H.test(frame(o, c, f, c + noise + 0.25))                       # margin centered on the close
    assert planted["pass"] and planted["cover"] > 0.58
    assert not null["pass"] and abs(null["cover"] - 0.5) < 0.04
