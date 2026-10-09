"""Known-answer checks for the OpenMarkets record (src/nflbet/openmarkets.py)."""
import polars as pl

from nflbet import openmarkets as Om
from nflbet import parlay as Pa


def _pos(side, line, quotes, mk="player_receptions", name="Aaron Jones Sr."):
    return {"contest_title": "NFL: Minnesota Vikings vs New Orleans Saints", "market_key": mk, "side_key": side,
            "variable": str(line), "title": f"{name} {side} +{line} receptions",
            "partner_liquidities": [{"partner_name": v, "price": p, "available": a, "actionable": True} for v, p, a in quotes]}


ROWS = [_pos("over", 3.5, [("Kalshi", 0.40, 1581), ("ProphetX", 0.4167, 10)]),
        _pos("under", 3.5, [("Kalshi", 0.63, 44.82), ("ProphetX", 0.6183, 7.5)]),
        _pos("over", 4.5, [("Kalshi", 0.24, 2170)]),                        # one-sided: dropped
        _pos("under", 3.5, [("Polymarket", 0.6, 100)]),                      # venue without props: ignored
        dict(_pos("over", 3.5, [("Kalshi", 0.5, 1)]), contest_title="2026 NFL Win Totals")]   # not a game: dropped


def test_american():
    assert round(Om.american(0.63)) == -170 and round(Om.american(0.40)) == 150 and Om.american(0.5) == -100


def test_parse_two_sided_only():
    d = Om.parse(ROWS)
    assert sorted(d["venue"].to_list()) == ["kalshi", "prophetx"]
    k = d.filter(pl.col("venue") == "kalshi").row(0, named=True)
    assert (k["game"], k["nkey"], k["market"], k["line"], k["p_under"], k["avail_under"]) == ("MIN|NO", "aaron jones", "rec", 3.5, 0.63, 44.82)


def test_compare_and_attach():
    om = Om.parse(ROWS)
    dk = Pa.parse([{"bookmaker": "draftkings", "market_key": "player_receptions", "home_team": "New Orleans Saints",
                    "away_team": "Minnesota Vikings", "period": "FULL", "player": "Aaron Jones", "line": 3.5,
                    "over_price": 142, "under_price": -168, "last_update": "x"}])
    c = {r["venue"]: r for r in Om.compare(om, dk)}
    # DK no-vig P(over): .4132/(.4132+.6269) = .3973; Kalshi .40/1.03 = .3883 -> 0.90 points
    assert c["kalshi"]["n_both"] == 1 and abs(c["kalshi"]["mean_gap_pts"] - 0.90) < 0.02
    assert c["bettoredge"]["n_both"] == 0 and c["bettoredge"]["mean_gap_pts"] is None
    picks = pl.DataFrame({"home": ["NO"], "away": ["MIN"], "player": ["Aaron Jones"], "market": ["rec"], "side": ["under"], "line": [3.5]})
    r = Om.attach(picks, om).row(0, named=True)
    assert round(r["om_kalshi_odds"]) == -170 and r["om_kalshi_avail"] == 44.82 and r["om_bettoredge_odds"] is None
