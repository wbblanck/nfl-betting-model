"""Known answers for nflbet.props.pressure (docs/pressure_preregistration.md)."""
import numpy as np
import polars as pl

from nflbet.props import pressure as P


def _tg(rows):
    """rows: (team, opponent, season, week, pressures, dropbacks)."""
    d = pl.DataFrame(rows, schema=["team", "opponent", "season", "week", "pressures", "dropbacks"], orient="row")
    return d.with_columns(pl.col("pressures").cast(pl.Float64), pl.col("dropbacks").cast(pl.Float64),
                          (pl.col("season") * 100 + pl.col("week")).alias("t")).sort("t")


def _league(rows, rate):
    # a filler season (2019) whose pooled rate is `rate`, so 2020 factors use it
    return rows + [("ZZZ", "YYY", 2019, 1, rate * 100, 100.0), ("YYY", "ZZZ", 2019, 1, rate * 100, 100.0)]


def test_hand_case():
    # AAA's offense: week 1 10 pressures on 40 dropbacks. League rate 0.2. Week 2: rate 0.25, ratio 1.25, n = 1,
    # factor (1 x 1.25 + 4) / 5 = 1.05. Defense BBB generated those 10 on 40, so BBB's D for week 2 is also 1.05.
    rows = _league([("AAA", "BBB", 2020, 1, 10, 40), ("BBB", "AAA", 2020, 1, 8, 40),
                    ("AAA", "CCC", 2020, 2, 99, 40), ("CCC", "AAA", 2020, 2, 99, 40),
                    ("DDD", "BBB", 2020, 2, 99, 40), ("BBB", "DDD", 2020, 2, 99, 40)], 0.2)
    f = P.factors(_tg(rows)).filter(pl.col("season") == 2020, pl.col("week") == 2)
    aaa = f.filter(pl.col("team") == "AAA")
    assert abs(aaa["Q"][0] - 1.05) < 1e-9 and aaa["n_q"][0] == 1
    # AAA faces CCC (no history): D = 1. DDD faces BBB, which generated 10 on 40 in week 1.
    assert aaa["D"][0] == 1.0
    ddd = f.filter(pl.col("team") == "DDD")
    assert abs(ddd["D"][0] - 1.05) < 1e-9 and ddd["Q"][0] == 1.0
    # BBB's own offense allowed 8 on 40 = 0.2 = league: Q = 1
    assert abs(f.filter(pl.col("team") == "BBB")["Q"][0] - 1.0) < 1e-9


def test_point_in_time():
    # a game's own pressures never enter its factors
    base = [("AAA", "BBB", 2020, 1, 10, 40), ("BBB", "AAA", 2020, 1, 10, 40),
            ("AAA", "BBB", 2020, 2, 10, 40), ("BBB", "AAA", 2020, 2, 10, 40)]
    hot = base[:2] + [("AAA", "BBB", 2020, 2, 40, 40), ("BBB", "AAA", 2020, 2, 40, 40)]
    a = P.factors(_tg(_league(base, 0.25))).filter(pl.col("week") == 2, pl.col("season") == 2020).sort("team")
    b = P.factors(_tg(_league(hot, 0.25))).filter(pl.col("week") == 2, pl.col("season") == 2020).sort("team")
    assert a["Q"].to_list() == b["Q"].to_list() and a["D"].to_list() == b["D"].to_list()


def test_missing_pfr_game_skipped():
    # week 1 has no PFR row (null pressures and dropbacks): week 2's factor rests on nothing -> 1, n = 0
    rows = _league([("AAA", "BBB", 2020, 1, None, None), ("BBB", "AAA", 2020, 1, None, None),
                    ("AAA", "BBB", 2020, 2, 30, 40), ("BBB", "AAA", 2020, 2, 30, 40)], 0.2)
    f = P.factors(_tg(rows)).filter(pl.col("season") == 2020, pl.col("week") == 2)
    assert f["Q"].to_list() == [1.0, 1.0] and f["n_q"].to_list() == [0, 0]


def test_team_games_oak_and_missing():
    pfr = pl.DataFrame({"season": [2019, 2019], "week": [1, 1], "game_type": ["REG", "REG"], "team": ["OAK", "DEN"],
                        "times_pressured": [7.0, None]})
    st = pl.DataFrame({"season": [2019] * 3, "week": [1] * 3, "team": ["LV", "LV", "DEN"],
                       "opponent_team": ["DEN", "DEN", "LV"], "attempts": [30, 1, 35], "sacks_suffered": [2, 0, 1]})
    g = P.team_games(pfr, st).sort("team")
    assert g["team"].to_list() == ["DEN", "LV"]
    assert g["pressures"].to_list() == [None, 7.0] and g["dropbacks"].to_list() == [None, 33.0]


def test_holm():
    assert P.holm({"a": 0.01, "b": 0.02, "c": 0.04}) == {"a": True, "b": True, "c": True}
    assert P.holm({"a": 0.01, "b": 0.03, "c": 0.04}) == {"a": True, "b": False, "c": False}
    assert P.holm({"a": 0.03, "b": 0.001, "c": 0.9}) == {"a": False, "b": True, "c": False}


def test_boot_p():
    assert P.boot_p(np.array([-1.0] * 4000)) == 1 / 4000
    assert abs(P.boot_p(np.array([-1.0] * 3000 + [1.0] * 1000)) - 0.5) < 1e-12


def _synthetic(c_true, n=8000, seed=5):
    rng = np.random.default_rng(seed)
    proj = rng.uniform(180, 300, n)
    D = np.exp(rng.normal(0, 0.12, n)).clip(0.5, 2)
    Q = np.exp(rng.normal(0, 0.12, n)).clip(0.5, 2)
    actual = proj * D ** c_true + rng.normal(0, 70, n)
    return pl.DataFrame({"market": ["pass_yds"] * n, "proj": proj, "D": D, "Q": Q, "actual": actual})


def test_planted_signal_found():
    c, d = P.fit_cd(_synthetic(-1.0))["pass_yds"]
    assert -1.25 <= c <= -0.75 and abs(d) <= 0.5


def test_noise_not_found():
    c, d = P.fit_cd(_synthetic(0.0, seed=11))["pass_yds"]
    assert abs(c) <= 0.5 and abs(d) <= 0.5


def test_adjusted_expression():
    x = pl.DataFrame({"market": ["pass_yds", "sacks"], "proj": [200.0, 2.0], "D": [1.1, 1.2], "Q": [0.9, 1.0]})
    out = x.with_columns(P.adjusted({"pass_yds": (-1.0, 0.5), "sacks": (1.0, 0.0)}).alias("adj"))["adj"].to_list()
    assert abs(out[0] - 200 / 1.1 * 0.9 ** 0.5) < 1e-9 and abs(out[1] - 2.4) < 1e-9
