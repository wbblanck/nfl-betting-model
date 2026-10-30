"""Known-answer checks for the your-venues records (docs/your_venues_rules.md)."""
import math

import polars as pl
import pytest

from nflbet.ats import your_venues as AY
from nflbet.props import your_venues as SY
from nflbet.sources import openmarkets as Om
from nflbet.sources import parlay as Pa


# ------------------------------------------------------------------------------------------------ pick'em pricing
def test_pickem_costs():
    pp = {"bookmaker": "prizepicks", "odds_type": "standard"}
    assert Pa.pickem_cost(pp, "over") == pytest.approx(1 / math.sqrt(3))        # 0.5774: needs 57.7% per pick
    assert Pa.pickem_cost(dict(pp, odds_type="goblin"), "over") is None
    ud = {"bookmaker": "underdog",
          "selection_by_side": {"over": {"payout_multiplier": 1.04}, "under": {"payout_multiplier": 0.95}},
          "product_quotes": {"over": {"products": {"fantasy": {"decimal": 1.94}}},
                             "under": {"products": {"fantasy": {"decimal": 1.50}}}}}      # 1.50 is far from sqrt(3.5)*0.95
    assert Pa.pickem_cost(ud, "over") == pytest.approx(1 / (math.sqrt(3.5) * 1.04))
    assert Pa.pickem_cost(ud, "under") is None
    sl = {"bookmaker": "sleeper", "over_price": -128, "under_price": 110}
    assert Pa.pickem_cost(sl, "over") == pytest.approx(128 / 228) and Pa.pickem_cost(sl, "under") == pytest.approx(100 / 210)


def test_parse_pickem_maps_markets_and_skips_half_games():
    base = {"home_team": "New England Patriots", "away_team": "New York Jets", "player": "Rhamondre Stevenson",
            "line": 3.5, "last_update": "t", "bookmaker": "sleeper", "over_price": -120, "under_price": -110}
    rows = [dict(base, market_key="player_receptions", period="FULL"),
            dict(base, market_key="player_receptions", period="1H"),
            dict(base, market_key="player_receptions_combo", period="FULL")]
    d = Pa.parse_pickem(rows)
    assert d.height == 2 and set(d["side"]) == {"over", "under"} and set(d["market"]) == {"rec"}
    assert set(d["game"]) == {"NE|NYJ"} and d["venue"][0] == "Sleeper"


# ------------------------------------------------------------------------------------------------ exchange spreads
def _om(side, var, ven, price, avail=100, title="NFL: New York Jets vs New England Patriots"):
    return {"contest_title": title, "market_key": "spread", "side_key": side, "variable": var,
            "partner_liquidities": [{"partner_name": ven, "actionable": True, "price": price, "available": avail}]}


def test_spread_quotes_two_sided_and_venue_filter():
    rows = [_om("home", "-3.5", "Kalshi", 0.52), _om("away", "3.5", "Kalshi", 0.50),          # NE -3.5: home_line 3.5
            _om("home", "-6.5", "Kalshi", 0.30),                                               # one-sided: dropped
            _om("home", "-3.5", "Polymarket", 0.51), _om("away", "3.5", "Polymarket", 0.51)]   # international: dropped
    q = Om.spread_quotes(rows)
    assert set(q["venue"]) == {"Kalshi"} and set(q["home_line"]) == {3.5} and q.height == 2


def test_exchange_quotes_add_fees():
    q = pl.DataFrame({"game": ["G", "G"], "venue": ["Kalshi", "PolymarketUS"], "home_line": [3.5, 3.5],
                      "side": ["home", "home"], "price": [0.5, 0.5], "avail": [100.0, 100.0]})
    c = AY.exchange_quotes(q)
    assert c.filter(pl.col("venue") == "Kalshi")["cost"][0] == pytest.approx(0.5 + 0.07 * 0.25)
    assert c.filter(pl.col("venue") == "Polymarket US")["cost"][0] == pytest.approx(0.5 + 0.0695 * 0.25)


# ------------------------------------------------------------------------------------------------ ATS on your venues
def _quotes(rows):
    return pl.DataFrame(rows, schema=AY.QUOTE_SCHEMA)


EV = pl.DataFrame({"game_id": ["2026_08_NYJ_NE"], "game": ["NE|NYJ"], "start_time": ["2026-11-01T17:00:00Z"], "home": ["NE"],
                   "away": ["NYJ"], "fair": [4.0], "consensus": [2.5], "exchange": [None], "side": ["NE"],
                   "side_is_home": [True], "qb_note": [""]}, schema_overrides={"exchange": pl.Float64})
FAIR = pl.DataFrame({"game_id": ["2026_08_NYJ_NE"], "fair": [4.0]})


def test_ats_your_venues_hand_case():
    q = _quotes([{"game": "NE|NYJ", "venue": "Kalshi", "home_line": 2.5, "side": "home", "cost": 0.52, "size": 100.0},
                 {"game": "NE|NYJ", "venue": "Polymarket US", "home_line": 1.5, "side": "home", "cost": 0.60, "size": 100.0},  # over the -120 cap
                 {"game": "NE|NYJ", "venue": "Novig", "home_line": 2.0, "side": "home", "cost": 0.51, "size": 5.0},            # under $10
                 {"game": "NE|NYJ", "venue": "Kalshi", "home_line": 2.5, "side": "away", "cost": 0.50, "size": 100.0}])       # other side
    r = AY.evaluate(FAIR, EV, q).row(0, named=True)
    # NE gives 2.5 where the rating says 4: edge 1.5, across 3, as good as the consensus reference -> Bet Now
    assert r["yv_venue"] == "Kalshi" and r["yv_line"] == 2.5 and r["gap"] == 1.5 and r["key"] is True
    assert r["beats_ref"] is True and r["label"] == "Bet Now" and r["n_quotes"] == 1


def test_ats_your_venues_tie_goes_to_lower_cost_and_no_line():
    q = _quotes([{"game": "NE|NYJ", "venue": "Kalshi", "home_line": 2.5, "side": "home", "cost": 0.53, "size": None},
                 {"game": "NE|NYJ", "venue": "Hard Rock", "home_line": 2.5, "side": "home", "cost": 0.5238, "size": None}])
    assert AY.evaluate(FAIR, EV, q)["yv_venue"][0] == "Hard Rock"
    none = AY.evaluate(FAIR, EV, _quotes([]))
    assert none["label"][0] == AY.NO_LINE and none["yv_line"][0] is None


def test_ats_your_venues_grade():
    off = pl.DataFrame({"game_id": ["g1", "g2", "g3"], "yv_line": ["2.5", "2.5", ""], "yv_cost": ["0.52", "0.52", ""],
                        "side_is_home": ["true", "false", "true"]})
    sched = pl.DataFrame({"game_id": ["g1", "g2", "g3"], "result": [3, 3, 3], "spread_line": [3.5, 3.5, 3.5]})
    g = AY.grade_rows(off, sched)
    assert g["result_ats"].to_list() == ["W", "L", "no line"]
    assert g["units"][0] == pytest.approx(1 / 0.52 - 1) and g["units"][1] == -1.0
    assert g["clv"][0] == pytest.approx(1.0) and g["clv"][1] == pytest.approx(-1.0)


# ------------------------------------------------------------------------------------------------ S1 on your venues
PICK = {"week": "8", "an_game_id": "1", "start_time": "t", "home": "NE", "away": "NYJ", "player": "Rhamondre Stevenson",
        "player_id": "00-1", "market": "rec", "side": "under", "line": "3.5", "odds": "-177"}


def test_s1_quotes_respect_line_direction():
    key = ("NE|NYJ", "rhamondre stevenson", "rec")
    pmq = {(*key, 3.5): {"under": 0.55, "over": 0.47, "fee": 0.0695, "slug": "a"},
           (*key, 2.5): {"under": 0.40, "over": 0.62, "fee": 0.0695, "slug": "b"}}   # under 2.5 is worse than under 3.5
    q = SY.exchange_quotes(PICK, pmq, {"a": {"under": 50.0}}, {}, {}, {})
    assert [x["line"] for x in q] == [3.5] and q[0]["cost"] == pytest.approx(0.55 + 0.0695 * 0.55 * 0.45)
    pk = pl.DataFrame([{"venue": "Underdog", "game": "NE|NYJ", "nkey": "rhamondre stevenson", "player": "x", "market": "rec",
                        "line": 4.5, "side": "under", "cost": 0.53, "last_update": ""}], schema=Pa.PICKEM_SCHEMA)
    assert SY.pickem_quotes(PICK, pk)[0]["line"] == 4.5                         # under 4.5 beats under 3.5


def test_s1_best_and_rows():
    qs = [{"venue": "Kalshi", "line": 3.5, "cost": 0.50, "size": 5.0},          # too thin
          {"venue": "Underdog", "line": 3.5, "cost": 0.53, "size": None},
          {"venue": "Sleeper", "line": 4.5, "cost": 0.53, "size": None}]        # same cost, better line for an under
    b = SY.best(qs, "under")
    assert b["venue"] == "Sleeper"
    r = SY.rows(pl.DataFrame([PICK]), [qs], "run").row(0, named=True)
    assert r["yv_venue"] == "Sleeper" and r["yv_line"] == 4.5 and r["label"] == "priced"
    assert SY.rows(pl.DataFrame([PICK]), [[]], "run")["label"][0] == SY.NO_LINE


def test_s1_grade_at_venue_line():
    yv = pl.DataFrame({"run_utc": ["r"] * 3, "an_game_id": ["1", "2", "3"], "player_id": ["p"] * 3, "market": ["rec"] * 3,
                       "side": ["under"] * 3, "yv_line": ["4.5", "4.5", ""], "yv_cost": ["0.53", "0.53", ""]})
    rec = pl.DataFrame({"run_utc": ["r"] * 3, "an_game_id": ["1", "2", "3"], "player_id": ["p"] * 3, "market": ["rec"] * 3,
                        "side": ["under"] * 3, "result": ["L", "void", "W"], "actual": ["4", None, "2"]})
    g = SY.grade(yv, rec)
    # DK's under 3.5 lost with 4 catches; Sleeper's under 4.5 wins
    assert g["result"].to_list() == ["W", "void", "no line"] and g["units"][0] == pytest.approx(1 / 0.53 - 1)


def test_novig_spread_quotes_hand_case():
    from nflbet.sources import venues as V
    ev = {"e1": {"eventId": "e1", "description": "Tennessee Titans @ Cincinnati Bengals", "status": "OPEN_PREGAME"}}
    mk = [{"marketId": "m1", "eventId": "e1", "marketType": "SPREAD", "status": "OPEN", "fee": {"charged": "WHEN_LIVE", "coefficient": "0.06"},
           "outcomes": [{"name": "CIN -18.5", "bid": {"price": "0.275", "qty": 100000}},
                        {"name": "TEN +18.5", "bid": {"price": "0.68", "qty": 125000}}]}]
    q = {x["side"]: x for x in V.nv_spread_quotes(mk, ev)}
    # CIN (home) -18.5 = home_line 18.5, bought against TEN's 0.68 bid: cost 0.32, $1,250 of payout behind it
    assert q["home"]["home_line"] == 18.5 and q["home"]["cost"] == pytest.approx(0.32) and q["home"]["size"] == 1250
    assert q["away"]["home_line"] == 18.5 and q["away"]["cost"] == pytest.approx(0.725) and q["away"]["size"] == 1000
