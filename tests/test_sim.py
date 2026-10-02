"""Known-answer checks for nflbet.sim."""
import numpy as np
import polars as pl

from nflbet import sim as S


def _pg(n=10, tgt=8.0, rec=6.0, yds=60.0, last_yds=60.0):
    rows = []
    for w in range(1, n + 1):
        rows.append({"player_id": "p", "season": 2024, "week": w, "team": "GB", "pos": "WR", "targets": tgt,
                     "receptions": rec, "receiving_yards": yds if w < n else last_yds, "carries": 0.0,
                     "rushing_yards": 0.0, "attempts": 0.0, "completions": 0.0, "passing_yards": 0.0,
                     "team_att": 35.0, "team_car": 25.0, "team_tgt": 34.0, "t": 202400 + w})
    return pl.DataFrame(rows)


def test_current_game_never_enters_its_own_rates():
    pm = S.position_means(_pg())
    a = S.rates(_pg(last_yds=60.0), pm).filter(pl.col("week") == 10)
    b = S.rates(_pg(last_yds=500.0), pm).filter(pl.col("week") == 10)
    assert a["ypr"].item() == b["ypr"].item() and a["tgt_share"].item() == b["tgt_share"].item()


def test_simulated_means_match_rates():
    r = {"pos": "WR", "implied": 24.0, "team_spread": 0.0, "tgt_share": 0.25, "car_share": 0.0, "att_share": 0.0,
         "catch": 0.6, "ypr": 12.0, "ypc": 4.0, "cmp": 0.65, "ypcmp": 11.0}
    vol = {"team_att": {"coef": [40.0, 0.0, 0.0], "sd": 1e-9}, "team_car": {"coef": [25.0, 0.0, 0.0], "sd": 1e-9}}
    pools = {("rec", "WR"): np.array([5.0, 10.0, 21.0]), ("rush", "WR"): np.array([3.0]), "cmp": np.array([11.0])}
    out = S.simulate_row(r, vol, pools, np.random.default_rng(1), n=40000)
    assert abs(out["rec"].mean() - 40 * 0.25 * 0.6) < 0.1                     # 6 receptions
    assert abs(out["rec_yds"].mean() - 40 * 0.25 * 0.6 * 12.0) < 1.5           # 72 yards
    assert out["rush_att"].max() == 0 and "pass_yds" not in out
    again = S.simulate_row(r, vol, pools, np.random.default_rng(1), n=40000)
    assert np.array_equal(out["rec_yds"], again["rec_yds"])                    # same seed, same draws
