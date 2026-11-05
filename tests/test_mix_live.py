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
