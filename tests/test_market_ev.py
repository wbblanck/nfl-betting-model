"""Known answers for market EV (docs/market_ev_preregistration.md): hand cases, then planted signal and noise."""
import json
import random

import polars as pl

from nflbet.props import market_ev as M
from nflbet.quant.odds import implied


def test_devig_fair_ev_hand_cases():
    assert abs(M.devig(110 / 210, 110 / 210) - 0.5) < 1e-12
    assert abs(M.devig(0.6, 0.5) - 0.6 / 1.1) < 1e-12
    assert M.fair_loo({"A": 0.5, "B": 0.52, "C": 0.54}, "A") == (0.53, 2)       # median of B, C
    assert M.fair_loo({"A": 0.5, "B": 0.52}, "A") == (None, 1)                  # one other venue: no fair
    assert abs(M.ev(0.499, implied(103)) - (0.499 * 2.03 - 1)) < 1e-12        # Prop Outliers' Hunter row: +1.3%


def test_live_fair_needs_two_other_sized_venues():
    v = json.dumps({"Novig": [0.48, 200], "DraftKings (ParlayAPI)": [0.5238, None], "FanDuel (ParlayAPI)": [0.53, None]})
    o = json.dumps({"Novig": [0.55, 200], "DraftKings (ParlayAPI)": [0.5238, None], "FanDuel (ParlayAPI)": [0.51, None]})
    fair, n = M.live_fair(v, o, "Novig")
    assert n == 2 and abs(fair - (0.5 + 0.53 / 1.04) / 2) < 1e-12           # Novig left out as the best venue
    thin = json.dumps({"Novig": [0.48, 5], "DraftKings (ParlayAPI)": [0.5238, None], "FanDuel (ParlayAPI)": [0.53, None]})
    assert M.live_fair(thin, o, "DraftKings (ParlayAPI)")[1] == 1             # $5 Novig side does not count
    assert M.live_fair(v, None, "Novig") == (None, 0)                         # old rows: no other side recorded


def test_prop_bet_picks_best_side_and_tiebreak():
    b = {"BookB": (implied(-110), implied(-110), 0.5), "BookA": (implied(-110), implied(-110), 0.5),
         "BookC": (implied(105), implied(-125), 0.5)}
    r = M.prop_bet(b)
    assert r["side"] == "over" and r["book"] == "BookC" and abs(r["ev"] - (0.5 * 2.05 - 1)) < 1e-12
    tie = M.prop_bet({k: (implied(-110), implied(-110), 0.5) for k in ("Z", "Y", "X")})
    assert tie["book"] == "X" and tie["ev"] < 0
    assert M.prop_bet({"A": (0.5, 0.5, 0.5), "B": (0.5, 0.5, 0.5)}) is None


def sim(edge: float, n_props: int = 6000, seed: int = 1, jitter: float = 0.0) -> pl.DataFrame:
    """Props with true P(over) drawn 0.42-0.58; four books at 4.5% hold around the truth, each cost moved by up to
    +-`jitter` at random (noise); book 'Soft' pays `edge` over fair on the over when edge > 0 (planted signal).
    Outcomes drawn from the truth (line 0.5, actual 0/1)."""
    rng = random.Random(seed)
    rows = []
    for i in range(n_props):
        p = rng.uniform(0.42, 0.58)
        for b in ("A", "B", "C", "Soft"):
            co = p * 1.045 * (1 + rng.uniform(-jitter, jitter))
            cu = (1 - p) * 1.045 * (1 + rng.uniform(-jitter, jitter))
            if b == "Soft" and edge > 0:
                co = p / (1 + edge)
            rows.append({"an_game_id": str(i), "an_player_id": "1", "market": "rec", "line": 0.5, "week": i % 18 + 1,
                         "book": b, "c_over": co, "c_under": cu, "p_over": co / (co + cu)})
        actual = 1.0 if rng.random() < p else 0.0
        for r in rows[-4:]:
            r["actual"] = actual
    return pl.DataFrame(rows)


def test_planted_signal_found_and_noise_not():
    c = M.units(M.select(M.bets(sim(0.05)), "M2"))
    roi, p, lo, _ = M.week_bootstrap(c, reps=2000)
    assert c.height > 5000 and roi > 0.02 and p < 0.0125 and lo > 0
    n = M.units(M.select(M.bets(sim(0.0, seed=2, jitter=0.05)), "M1"))   # books scatter, none truly off fair
    assert n.height > 100
    roi_n, p_n, _, _ = M.week_bootstrap(n, reps=2000)
    assert p_n > 0.025 and roi_n < 0.02                                       # does not pass
