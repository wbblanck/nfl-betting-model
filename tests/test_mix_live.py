"""Props-mix live tracker (docs/mix_live_rules.md): hand-checked mix probabilities and the 55% pick rule."""
import math

import numpy as np
import polars as pl

from nflbet.gamesim import mix_live as M

CF = {"receiving": [0.1, 1.2, -0.05], "rushing": [-0.06, 1.1, 0.15], "passing": [0.0, 1.0, 0.0]}


def lg(p):
    return math.log(p / (1 - p))


def test_mix_matches_hand_formula():
    got = M.mix(["rec", "rush_yds", "pass_yds"], [0.55, 0.40, 0.5], [0.70, 0.20, 0.9], CF)
    want = [1 / (1 + math.exp(-(0.1 + 1.2 * lg(0.55) - 0.05 * lg(0.70)))),
            1 / (1 + math.exp(-(-0.06 + 1.1 * lg(0.40) + 0.15 * lg(0.20)))),
            0.5]
    assert np.allclose(got, want)


def test_mix_clips_like_the_fit():
    assert np.allclose(M.mix(["rec"], [0.5], [1.0], CF), M.mix(["rec"], [0.5], [0.98], CF))


def test_frozen_weights_load():
    cf = M.coefs()
    assert set(cf) == {"receiving", "rushing", "passing"} and all(len(v) == 3 for v in cf.values())


def _props(p_mix, over=-110.0, under=-110.0):
    n = len(p_mix)
    return pl.DataFrame({c: ["x"] * n for c in M.PROP_COLS if c not in ("line", "over_odds", "under_odds", "p_over_dk", "p_sim", "p_mix")}) \
        .with_columns(pl.Series("line", [4.5] * n), pl.Series("over_odds", [over] * n), pl.Series("under_odds", [under] * n),
                      pl.Series("p_over_dk", [0.5] * n), pl.Series("p_sim", [0.5] * n), pl.Series("p_mix", p_mix)).select(M.PROP_COLS)


def test_pick_rule_threshold_and_side():
    pk = M.picks_from(_props([0.56, 0.54, 0.44, 0.46, 0.55]))
    assert pk.height == 3
    assert sorted(pk["side"].to_list()) == ["over", "over", "under"]
    assert (pk["p_side"] >= 0.55).all()


def test_edge_is_mix_minus_break_even_and_sorted():
    pk = M.picks_from(_props([0.60, 0.70], over=-150.0))
    be = 150 / 250
    assert np.allclose(sorted(pk["edge"].to_list(), reverse=True), [0.70 - be, 0.60 - be])
    assert pk["edge"].to_list() == sorted(pk["edge"].to_list(), reverse=True)


def test_with_best_units_at_best_price():
    import polars as pl
    from nflbet.gamesim import mix_live as M
    k = dict(run_utc=["t", "t", "t", "t"], an_game_id=["g"] * 4, player_id=["a", "b", "c", "d"], market=["rec"] * 4,
             side=["over", "under", "over", "over"])
    rec = pl.DataFrame({**k, "odds": [-110.0, -120.0, 100.0, -110.0], "result": ["W", "L", "W", "pending"]})
    best = pl.DataFrame({**{c: v[:2] for c, v in k.items()}, "best_venue": ["Novig", "Kalshi"],
                         "best_cost": ["0.5", "0.52"], "best_odds": ["100", "-108"]})
    g = M.with_best(rec, best)
    assert g["best_venue"].to_list() == ["Novig", "Kalshi", "DraftKings", "DraftKings"]
    u = g["units_best"].to_list()
    assert abs(u[0] - 1.0) < 1e-9 and u[1] == -1.0 and abs(u[2] - 1.0) < 1e-9 and u[3] == 0.0
    assert abs(g["best_cost"][2] - 0.5) < 1e-9 and abs(g["best_cost"][3] - 110 / 210) < 1e-9
    assert M.with_best(rec, None)["best_venue"].to_list() == ["DraftKings"] * 4
