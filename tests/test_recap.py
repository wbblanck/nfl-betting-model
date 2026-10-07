"""Known-answer checks for the weekly recap split (src/nflbet/recap.py)."""
import polars as pl

from nflbet import recap as R


def test_shapley_two_and_three_factors():
    p = R.shapley({"A": 2.0, "S": 3.0}, {"A": 4.0, "S": 5.0})        # worked by hand: A first/second -> 6, 10; S -> 8, 4
    assert abs(p["A"] - 8.0) < 1e-12 and abs(p["S"] - 6.0) < 1e-12
    assert R.shapley({"A": 2.0, "S": 3.0}, {"A": 4.0, "S": 3.0}) == {"A": 6.0, "S": 0.0}   # only A moved: all of it is A
    base, act = {"A": 10.0, "S": 0.2, "R": 0.6}, {"A": 12.0, "S": 0.25, "R": 0.5}
    q = R.shapley(base, act)
    assert abs(sum(q.values()) - (12 * 0.25 * 0.5 - 10 * 0.2 * 0.6)) < 1e-12              # pieces add up exactly


def test_pick_parts_receptions():
    rows = pl.DataFrame({"team_att": [30, 30], "team_car": [25, 25], "targets": [6, 4], "rec": [4, 2], "carries": [0, 0], "att": [0, 0], "cmp": [0, 0]})
    act = {"team_att": 40.0, "team_car": 20.0, "targets": 8.0, "rec": 3.0, "carries": 0.0, "att": 0.0, "cmp": 0.0}
    p = R.pick_parts("rec", rows, {}, {"catch": 0.65, "comp": 0.65}, act)
    assert abs(p["base"]["A"] - 30) < 1e-12 and abs(p["base"]["S"] - 10 / 60) < 1e-12
    assert abs(p["base"]["R"] - (6 + 20 * 0.65) / (10 + 20)) < 1e-12                         # catch rate shrunk toward the league rate
    assert abs(p["check"] - 3.0) < 1e-12                                                       # actual factors multiply back to the stat
    assert abs(sum(p["parts"].values()) - (3.0 - p["expected"])) < 1e-12
    fav = R.in_favor(p["parts"], "under")
    assert all(abs(fav[k] + p["parts"][k]) < 1e-12 for k in fav)                               # an under flips the sign
    assert R.pick_parts("rec", rows.head(0), {}, {"catch": 0.65, "comp": 0.65}, act) is None   # no prior games: no split


def test_zero_target_week_has_no_efficiency_part():
    rows = pl.DataFrame({"team_att": [30], "team_car": [25], "targets": [5], "rec": [3], "carries": [0], "att": [0], "cmp": [0]})
    act = {"team_att": 30.0, "team_car": 25.0, "targets": 0.0, "rec": 0.0, "carries": 0.0, "att": 0.0, "cmp": 0.0}
    p = R.pick_parts("rec", rows, {}, {"catch": 0.65, "comp": 0.65}, act)
    assert p["actual_stat"] == 0.0 and abs(p["check"]) < 1e-12 and abs(p["parts"]["R"]) < 1e-12   # all of the drop is role
