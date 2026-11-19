"""SportsGameOdds parser on a saved real answer (docs/evidence/sgo_probe) and on hand cases."""
import json
from pathlib import Path

import polars as pl

from nflbet.sources import sgo

EV = Path(__file__).resolve().parents[1] / "docs/evidence/sgo_probe/20261119T180127Z/final_last_week.json"


def _ev():
    return json.loads(EV.read_text())["body"]["data"][0]


def test_known_answers_from_saved_game():
    d = sgo.parse_event(_ev())
    assert set(d["game"].unique()) == {"NYG|WAS"} and d["home"][0] == "NYG" and d["away"][0] == "WAS"
    m = d.filter(pl.col("odd_id") == "receiving_receptions-DARNELL_MOONEY_1_NFL-game-ou-over",
                 pl.col("book") == "draftkings").row(0, named=True)
    assert (m["open_odds"], m["open_line"], m["close_odds"], m["close_line"]) == (-123, 1.5, 114, 1.5)
    assert (m["last_line"], m["market"], m["nkey"], m["score"]) == (2.5, "rec", "darnell mooney", 2)
    s = d.filter(pl.col("odd_id") == "points-home-game-sp-home", pl.col("book") == "draftkings").row(0, named=True)
    assert (s["open_line"], s["close_line"], s["close_odds"]) == (-1.5, -1.5, -110)
    assert d.filter(pl.col("bet_type") == "ml")["close_line"].is_null().all()


def test_full_game_only_and_unmapped_stats_kept():
    ev = {"eventID": "x", "status": {"startsAt": "2026-01-01T18:00:00.000Z"}, "info": {"seasonWeek": "Week 1"},
          "teams": {"home": {"names": {"long": "Chicago Bears"}}, "away": {"names": {"long": "Green Bay Packers"}}},
          "players": {"A_B_1_NFL": {"name": "A.J. Brown"}},
          "odds": {
              "rushing_yards-A_B_1_NFL-1h-ou-over": {"periodID": "1h", "statEntityID": "A_B_1_NFL", "betTypeID": "ou",
                                                    "statID": "rushing_yards", "sideID": "over",
                                                    "byBookmaker": {"draftkings": {"odds": "-110", "overUnder": "20.5"}}},
              "defense_sacks-A_B_1_NFL-game-ou-over": {"periodID": "game", "statEntityID": "A_B_1_NFL", "betTypeID": "ou",
                                                       "statID": "defense_sacks", "sideID": "over",
                                                       "byBookmaker": {"fanduel": {"odds": "+150", "overUnder": "0.5",
                                                                                   "closeOdds": "+140",
                                                                                   "closeOverUnder": "0.5"}}}}}
    d = sgo.parse_event(ev)
    assert d.height == 1 and d["market"][0] is None and d["close_odds"][0] == 140 and d["game"][0] == "CHI|GB"
    assert d["nkey"][0] == "aj brown"
