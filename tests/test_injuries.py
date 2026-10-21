"""Known-answer checks for the S1 tracker's injury flag."""
import glob
import gzip
import json

import polars as pl

from nflbet.sources import injuries as Inj


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


def test_depth_parse_and_changes_on_runner_snapshot():
    from nflbet.sources import depth as D

    d = sorted(glob.glob("docs/evidence/espn_depth/*/"))[0]
    charts = {k: {"id": v["id"], "body": v["body"]} for k, v in json.load(gzip.open(d + "core_depthcharts.json.gz", "rt")).items()}
    dc = D.parse(charts)
    assert dc["team"].n_unique() == 32 and set(dc["pos"].unique().to_list()) == {"QB", "RB"}
    nyj = dc.filter(pl.col("team") == "NYJ", pl.col("pos") == "RB").sort("rank")["espn_id"].to_list()
    assert nyj[:2] == ["4427366", "4685247"]                   # Breece Hall still listed first, Braelon Allen second
    inj = Inj.parse(json.load(gzip.open(d + "site_injuries.json.gz", "rt"))["body"])
    players = pl.DataFrame({"espn_id": ["4427366", "4685247"], "player_id": ["hall", "allen"], "name": ["Hall", "Allen"]})
    usage = pl.DataFrame({"player_id": ["hall", "allen"], "team": ["NYJ", "NYJ"], "pos": ["RB", "RB"], "n": [51, 19]})
    # Hall is Out: the healthy chart starter is Allen, but the leader is injured -> the injury flag's case, no change
    assert D.changes(dc.filter(pl.col("team") == "NYJ"), inj, players, usage).height == 0


def test_depth_flag_known_answer():
    from nflbet.sources import depth as D

    ch = pl.DataFrame({"team": ["SEA", "GB"], "pos": ["QB", "RB"], "starter_id": ["new", "kj"], "starter_name": ["New", "KJ"],
                       "starter_n": [10, 12], "leader_id": ["old", "ml"], "leader_name": ["Old", "ML"], "leader_n": [60, 23]})
    picks = pl.DataFrame({"player_id": ["new", "new", "old", "wr", "kj", "kj", "ml"],
                          "team": ["SEA", "SEA", "SEA", "SEA", "GB", "GB", "GB"],
                          "market": ["pass_cmp", "pass_yds", "pass_att", "rec", "rush_att", "rec", "rush_yds"],
                          "side": ["under", "over", "over", "under", "under", "under", "under"]})
    f = D.flag(picks, ch)
    assert f["depth_against"].to_list() == [True, False, True, False, True, False, False]
    notes = f["depth_note"].to_list()
    assert notes[3].startswith("team QB change") and notes[5] == "" and notes[6].startswith("RB change")
