"""Known answers for nflbet.props.signals (docs/five_signals_preregistration.md)."""
import numpy as np
import polars as pl

from nflbet.props import signals as S


def _sched(rows):
    return pl.DataFrame(rows, schema=["season", "week", "gameday", "home_team", "away_team", "home_qb_id", "away_qb_id",
                                      "roof", "wind", "game_type"], orient="row")


def test_qb_change_and_wind():
    rows = [(2020, w, f"2020-09-{10 + w}", "AAA", "BBB", qa, "b1", roof, wd, "REG")
            for w, qa, roof, wd in ((1, "a1", "outdoors", 5), (2, "a1", "dome", 30), (3, "a1", "outdoors", 18),
                                    (4, "a2", "open", None), (5, "a2", "outdoors", 12))]
    q = S.qb_change(_sched(rows)).filter(pl.col("team") == "AAA").sort("week")["x"].to_list()
    assert q == [0, 0, 0, 1, 1]          # week 5: previous 3 = a1, a1, a2 -> a1 established
    w = S.wind(_sched(rows)).filter(pl.col("team") == "AAA").sort("week")["x"].to_list()
    assert w == [0.0, 0.0, 8.0, 0.0, 2.0]


def test_snap_trend_uses_earlier_rows_only():
    pct = [0.5, 0.5, 0.5, 0.5, 0.9, 0.1]
    s = pl.DataFrame({"player_id": ["p"] * 6, "season": [2020] * 6, "week": list(range(1, 7)), "offense_pct": pct})
    x = S.snap_trend(s).sort("week")["x"].to_list()
    assert x[:4] == [None, None, None, None]
    assert abs(x[4] - 0.0) < 1e-9                       # week 5: last 0.5 minus mean(0.5,0.5,0.5)
    assert abs(x[5] - 0.4) < 1e-9                       # week 6: last 0.9 minus mean(0.5 x4); week 6's 0.1 unused


def test_ngs_prior_and_center():
    n = pl.DataFrame({"player_id": ["p", "p", "q", "p"], "season": [2020] * 4, "week": [0, 1, 1, 2],
                      "sep": [9.0, 3.0, 1.0, 5.0]})
    st = S.ngs_prior(n, "sep")
    rows = pl.DataFrame({"player_id": ["p", "p", "p"], "season": [2020] * 3, "week": [1, 2, 3]})
    x = S.attach_ngs(rows, st, n, "sep", center=False).sort("week")["x"].to_list()
    assert x == [None, 3.0, 4.0]                        # week 0 (season total) ignored; own week never used
    xc = S.attach_ngs(rows, st, n, "sep", center=True).sort("week")["x"].to_list()
    assert xc[1] == 3.0 - 2.0 and xc[2] == 4.0 - 3.0    # league means of weeks < w: (3+1)/2, (3+1+5)/3


def _syn(planted, seed=5, n=8000):
    rng = np.random.default_rng(seed)
    proj = rng.uniform(2, 8, n)
    x = rng.normal(0, 1, n)
    mean = proj * np.exp(0.3 * x) if planted else proj
    return pl.DataFrame({"market": ["rec"] * n, "proj": proj, "x": x, "actual": rng.poisson(mean).astype(float)})


def test_planted_found_noise_not():
    assert S.fit_k(_syn(True), S.GRIDS["qb"])["rec"] in (0.25, 0.3, 0.35)
    assert abs(S.fit_k(_syn(False), S.GRIDS["qb"])["rec"]) <= 0.05
