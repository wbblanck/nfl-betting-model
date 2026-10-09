"""Known-answer checks for the per-pick reasons (src/nflbet/explain.py)."""
import gzip
import json

import polars as pl

from nflbet import explain as Ex


def test_stamp_matches_archive_names():
    assert Ex.stamp("2026-10-08T05:42:48Z") == "20261008T0542Z"


def test_recent_games_before_week_with_opponent():
    st = pl.DataFrame({"player_id": ["a"] * 5, "week": [1, 2, 3, 4, 5], "team": ["IND"] * 5,
                       "game_id": ["2026_01_BAL_IND", "2026_02_IND_KC", "2026_03_HOU_IND", "2026_04_IND_WAS", "2026_05_IND_PIT"],
                       "rec": [2, 7, 5, 3, 9]})
    assert Ex.recent_games(st, "a", "rec", 5) == [(1, "BAL", 2.0), (2, "KC", 7.0), (3, "HOU", 5.0), (4, "WAS", 3.0)]


def test_reasons_under():
    r = {"side": "under", "line": 5.5, "odds": -151, "market": "rec", "p_mkt": 0.567, "p_model": 0.75, "proj": 3.9}
    out = Ex.reasons(r, {"DraftKings": 5.5, "FanDuel": 4.5}, [(1, "BAL", 2.0), (2, "KC", 7.0), (3, "HOU", 5.0), (4, "WAS", 3.0)])
    assert out[0].startswith("Price: DraftKings has the under at -151") and "57%" in out[0]
    assert "is the highest line on the board (FanDuel 4.5)" in out[1]
    tie = Ex.reasons(r, {"DraftKings": 5.5, "Caesars": 5.5, "FanDuel": 4.5}, [])
    assert "ties for the highest line" in tie[1] and tie[4] == "Recent games: none this season before this week."
    assert out[2] == "Projection: 3.9 receptions, 29% below the 5.5 line."      # (5.5 - 3.9) / 5.5 = 0.291
    assert out[3] == "Simulator: 75% for the under, +18 points against the market's 57%."
    assert out[4] == "Recent games: 2 vs BAL, 7 vs KC, 5 vs HOU, 3 vs WAS. Under 5.5 in 3 of 4; average 4.2 receptions."


def test_book_lines_from_parlay_archive(tmp_path):
    (tmp_path / "parlay").mkdir()
    rows = [{"bookmaker": b, "market_key": k, "home_team": "Pittsburgh Steelers", "away_team": "Indianapolis Colts",
             "period": "FULL", "player": "Josh Downs", "line": ln, "over_price": -110, "under_price": -110, "last_update": "x"}
            for b, k, ln in (("draftkings", "player_receptions", 5.5), ("fanduel", "player_receptions", 4.5))]
    with gzip.open(tmp_path / "parlay" / "20261008T0542Z_w5.json.gz", "wt") as f:
        json.dump(rows, f)
    r = {"player": "Josh Downs", "market": "rec", "run_utc": "2026-10-08T05:42:48Z", "week": "5"}
    assert Ex.book_lines(tmp_path, r, "parlay") == {"DraftKings": 5.5, "FanDuel": 4.5}
    assert Ex.book_lines(tmp_path, dict(r, run_utc="2026-10-09T00:00:00Z"), "parlay") == {}   # no archive: no claim


def test_opponent_context():
    ctx = {"week": 5, "teams": {"NO": {"def_blitz_rate": 0.31, "def_pass_rushers": 4.6, "def_box": 6.4}},
           "league": {"def_blitz_rate": 0.24, "def_pass_rushers": 4.25, "def_box": 6.1}}
    s = Ex.opponent_context({"market": "rec"}, "NO", ctx)
    assert s == "Opponent defense (NO, weeks 1-4, FTN charting): blitzes on 31% of dropbacks (league 24%), 4.6 pass rushers on average (league 4.2)."
    assert "box" in Ex.opponent_context({"market": "rush_yds"}, "NO", ctx)
    assert Ex.opponent_context({"market": "rec"}, "DAL", ctx) is None and Ex.opponent_context({"market": "rec"}, "NO", None) is None
