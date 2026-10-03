"""Known-answer checks for the S1 tracker's injury flag."""
import glob
import gzip
import json

import polars as pl

from nflbet import injuries as Inj


def test_parse_runner_snapshot():
    path = sorted(glob.glob("docs/evidence/espn_injuries/*/site_injuries.json.gz"))[0]
    inj = Inj.parse(json.load(gzip.open(path, "rt"))["body"])
    hall = inj.filter(pl.col("espn_id") == "4427366")          # Breece Hall (nflverse players: gsis 00-0038120)
    assert hall["status"].to_list() == ["Out"] and hall["name"].to_list() == ["Breece Hall"]
    assert inj.height > 500 and set(inj["status"].unique().to_list()) >= {"Active", "Out", "Questionable"}


def test_flag_known_answer():
    picks = pl.DataFrame({"player_id": ["a", "b", "c", "d", "e"], "team": ["NYJ", "NYJ", "GB", "GB", "SF"],
                          "side": ["under", "under", "under", "over", "under"]})
    ids = pl.DataFrame({"espn_id": ["1", "2", "3", "4", "5", "6", "7"], "player_id": ["a", "h", "q", "w", "d", "x", "old"]})
    inj = pl.DataFrame({"espn_id": ["2", "3", "4", "5", "6", "7"], "name": ["H", "Q", "W", "D", "X", "Old"],
                        "espn_pos": ["RB", "WR", "QB", "TE", "WR", "WR"],
                        "status": ["Out", "Questionable", "Out", "Questionable", "Active", "Injured Reserve"],
                        "date": [None] * 6})
    recent = pl.DataFrame({"player_id": ["a", "h", "b", "c", "q", "w", "d", "e", "x"],
                           "team": ["NYJ", "NYJ", "NYJ", "GB", "GB", "GB", "GB", "SF", "SF"],
                           "position": ["RB", "RB", "WR", "WR", "WR", "QB", "TE", "WR", "WR"]})   # "old" not recent
    f = Inj.flag(picks, inj, ids, recent)
    got = {r["player_id"]: (r["inj_self"], r["inj_teammates"], r["inj_against"]) for r in f.iter_rows(named=True)}
    assert got["a"] == ("", "RB H: Out", True)                 # under, RB teammate out -> against
    assert got["b"] == ("", "", False)                         # WR: the out RB is another position group
    assert got["c"] == ("", "WR Q: Questionable; TE D: Questionable", False)   # questionable is shown, not "against"
    assert got["d"] == ("Questionable", "WR Q: Questionable", True)            # over, player himself listed
    assert got["e"] == ("", "", False)                         # Active teammate and a non-recent IR player ignored
