"""Known-answer checks for the live ATS tracker (src/nflbet/ats/live.py)."""
import polars as pl

from nflbet.ats import rating as A
from nflbet.ats import live as AL


def _sb():
    def side(bid, side, value, odds):
        return {"book_id": bid, "side": side, "value": value, "odds": odds, "period": "event"}
    return {"games": [{"home_team_id": 1, "away_team_id": 2, "start_time": "2026-10-11T17:00:00.000Z",
                       "teams": [{"id": 1, "abbr": "PIT"}, {"id": 2, "abbr": "IND"}],
                       "markets": {"15": {"event": {"spread": [side(15, "home", -2.5, -110), side(15, "away", 2.5, -110)]}},
                                   "30": {"event": {"spread": [side(30, "home", 6.5, -110), side(30, "away", -6.5, -110)]}},
                                   "68": {"event": {"spread": [side(68, "home", -2.5, -115), side(68, "away", 2.5, -105)]}},
                                   "69": {"event": {"spread": [side(69, "home", -3.0, -105), side(69, "away", 3.0, -115)]}}}}]}


def test_parse_an_signs_and_books():
    d = AL.parse_an(_sb())
    assert sorted(d["book"].to_list()) == ["DraftKings", "FanDuel", "consensus"]          # book 30 ("Open") ignored
    dk = d.filter(pl.col("book") == "DraftKings").row(0, named=True)
    assert (dk["home_line"], dk["home_odds"], dk["away_odds"], dk["game"]) == (2.5, -115, -105, "IND|PIT")


def test_evaluate_home_side_key_number():
    books = AL.parse_an(_sb())
    fair = pl.DataFrame({"game_id": ["g"], "game": ["IND|PIT"], "home": ["PIT"], "away": ["IND"], "neutral": [False], "fair": [4.0]})
    r = AL.evaluate(fair, books, None).row(0, named=True)
    # home side (fair 4.0 > consensus 2.5); best home number = smallest line = 2.5 at DraftKings (-115)
    assert (r["side"], r["best_book"], r["best_line"], r["best_odds"]) == ("PIT", "DraftKings", 2.5, -115)
    assert r["gap"] == 1.5 and r["key"] is True and r["beats_ref"] is True and r["label"] == "Bet Now"
    assert r["exp_clv"] == round(0.235 * 1.5, 2)
    q = AL.evaluate(fair, books, None, {"PIT": "PIT QB X: Questionable"}).row(0, named=True)
    assert q["label"] == "Wait"


def test_evaluate_away_side_and_reference():
    books = AL.parse_an(_sb())
    fair = pl.DataFrame({"game_id": ["g"], "game": ["IND|PIT"], "home": ["PIT"], "away": ["IND"], "neutral": [False], "fair": [0.5]})
    ex = pl.DataFrame({"game": ["IND|PIT"], "venue": ["Kalshi"], "home_line": [3.5], "p_home": [0.5], "p_away": [0.5]})
    r = AL.evaluate(fair, books, ex).row(0, named=True)
    # away side; best away number = largest home line = 3.0 at FanDuel; gap 2.5; +3 vs fair +0.5 crosses 3? no (3 not > 3)
    assert (r["side"], r["best_book"], r["best_line"], r["gap"]) == ("IND", "FanDuel", 3.0, 2.5)
    assert r["key"] is False and r["beats_ref"] is False and r["label"] == "Monitor"   # exchange has +3.5 for IND


def test_crosses_key_moved():
    assert A.crosses_key(2.5, 3.5, True) and A.crosses_key(3.5, 2.5, False) and not A.crosses_key(4.5, 5.5, True)
