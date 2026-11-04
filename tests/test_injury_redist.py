"""Known answers for nflbet.props.injury_redist (docs/injury_redist_preregistration.md)."""
import numpy as np
import polars as pl

from nflbet.props import injury_redist as I


def _st(rows):
    d = pl.DataFrame(rows, schema=["player_id", "team", "season", "week", "pos", "rec"], orient="row")
    return d.with_columns((pl.col("season") * 100 + pl.col("week")).alias("t"), pl.col("rec").cast(pl.Float64))


def test_hand_case():
    # three WRs at constant usage 6, 4, 2 in weeks 1-3; week 4 the "4" is listed Out
    rows = [(p, "AAA", 2020, w, "WR", u) for w in (1, 2, 3) for p, u in (("a", 6), ("b", 4), ("c", 2))]
    rows += [("a", "AAA", 2020, 4, "WR", 9), ("c", "AAA", 2020, 4, "WR", 3)]
    su = I.usage_post(_st(rows), ["rec"])
    inj = pl.DataFrame({"player_id": ["b"], "team": ["AAA"], "season": [2020], "week": [4], "report_status": ["Out"]})
    sh = I.shares(I.recent(su, ["rec"]), inj, ["rec"]).filter(pl.col("week") == 4)
    assert sh.filter(pl.col("player_id") == "b")["active"].to_list() == [False]
    q = dict(zip(sh["player_id"], sh["q"]))
    assert abs(q["a"] - 0.5) < 1e-9 and abs(q["c"] - 0.5) < 1e-9
    proj = pl.DataFrame({"player_id": ["a", "c"], "season": [2020, 2020], "week": [4, 4], "team": ["AAA", "AAA"],
                         "market": ["rec", "rec"], "proj": [6.0, 2.0]})
    x = I.attach(proj, sh)
    adj = x.with_columns(I.adjusted(x, {"rec": 1.0}).alias("adj"))["adj"].to_list()
    assert adj == [9.0, 3.0]


def test_point_in_time():
    # usage of an absent player comes only from earlier games: his week-4 row (a huge value) must not enter week 4
    rows = [("a", "AAA", 2020, w, "WR", 5) for w in (1, 2, 3)] + [("b", "AAA", 2020, w, "WR", 5) for w in (1, 2, 3)]
    rows += [("b", "AAA", 2020, 4, "WR", 500), ("a", "AAA", 2020, 4, "WR", 5)]
    su = I.usage_post(_st(rows), ["rec"])
    inj = pl.DataFrame({"player_id": ["b"], "team": ["AAA"], "season": [2020], "week": [4], "report_status": ["Doubtful"]})
    sh = I.shares(I.recent(su, ["rec"]), inj, ["rec"]).filter(pl.col("week") == 4, pl.col("player_id") == "a")
    assert abs(sh["q"][0] - 1.0) < 1e-9          # 5 / 5, not 500 / 5 (and capped at 1 anyway)
    rec = I.recent(su, ["rec"]).filter(pl.col("week") == 4)
    assert rec["pw"].max() == 3


def test_questionable_and_other_team_ignored():
    rows = [(p, "AAA", 2020, w, "WR", 4) for w in (1, 2) for p in ("a", "b")]
    su = I.usage_post(_st(rows + [("a", "AAA", 2020, 3, "WR", 4)]), ["rec"])
    inj = pl.DataFrame({"player_id": ["b", "b"], "team": ["AAA", "BBB"], "season": [2020, 2020], "week": [3, 3],
                        "report_status": ["Questionable", "Out"]})
    sh = I.shares(I.recent(su, ["rec"]), inj, ["rec"]).filter(pl.col("week") == 3)
    assert sh["q"].max() == 0.0


def _synthetic(planted: bool, n=6000, seed=3):
    rng = np.random.default_rng(seed)
    proj = rng.uniform(2, 8, n)
    q = np.where(rng.random(n) < 0.3, rng.uniform(0.1, 0.8, n), 0.0)
    mean = proj * (1 + q) if planted else proj
    actual = rng.poisson(mean).astype(float)
    return pl.DataFrame({"market": ["rec"] * n, "proj": proj, "q": q, "actual": actual})


def test_planted_signal_found():
    assert I.fit_alpha(_synthetic(True))["rec"] in (0.75, 1.0, 1.25)


def test_noise_not_found():
    assert I.fit_alpha(_synthetic(False))["rec"] in (0.0, 0.25)
