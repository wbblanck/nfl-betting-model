"""Known-answer checks for nflbet.sim."""
import numpy as np
import polars as pl

from nflbet import sim as S


def _pg(n=10, tgt=8.0, rec=6.0, yds=60.0, last_yds=60.0):
    rows = []
    for w in range(1, n + 1):
        rows.append({"player_id": "p", "season": 2024, "week": w, "team": "GB", "opp": "CHI", "pos": "WR", "targets": tgt,
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


def test_center_matches_market_and_recovers_shape():
    from nflbet import ladder as L
    rng = np.random.default_rng(3)
    true = rng.gamma(4.0, 15.0, 200000)                      # "real" yards distribution, mean 60
    sim = rng.gamma(4.0, 15.0, 200000) * 0.8                 # simulator with the right shape, mean 20% too low
    p_mkt = float(np.mean(true > 54.5))
    c = L.center(sim, 54.5, p_mkt)
    assert abs(np.mean(c > 54.5) - p_mkt) < 0.002            # matches the book's main line
    for n in (40, 60, 80, 100):                              # and the ladder then matches the true tail
        assert abs(np.mean(c >= n) - np.mean(true >= n)) < 0.01


def _defense_pg(yds_allowed_last=60.0, ypr_allowed=20.0):
    """WRs facing defense CHI gain ypr_allowed per catch for 9 weeks; league (vs DET) gains 10."""
    rows = []
    for w in range(1, 11):
        for opp, ypr in (("CHI", ypr_allowed), ("DET", 10.0)):
            yds = 6 * ypr if not (opp == "CHI" and w == 10) else yds_allowed_last
            rows.append({"player_id": f"p{opp}", "season": 2024, "week": w, "team": "GB", "opp": opp, "pos": "WR",
                         "targets": 8.0, "receptions": 6.0, "receiving_yards": yds, "carries": 0.0, "rushing_yards": 0.0,
                         "attempts": 0.0, "completions": 0.0, "passing_yards": 0.0, "team_att": 35.0, "team_car": 25.0,
                         "team_tgt": 34.0, "t": 202400 + w})
    return pl.DataFrame(rows)


def test_defense_factor_uses_only_earlier_games_and_finds_a_soft_defense():
    pg = _defense_pg()
    pm = S.position_means(pg)
    a = S.defense_factors(pg, pm, pg).filter(pl.col("opp") == "CHI", pl.col("t") == 202410)
    b = S.defense_factors(_defense_pg(yds_allowed_last=900.0), pm, _defense_pg(yds_allowed_last=900.0)) \
        .filter(pl.col("opp") == "CHI", pl.col("t") == 202410)
    assert a["d_ypr"].item() > 1.1          # CHI allowed 20 per catch vs a league 15; shrunk over 54 catches ~1.16
    fit = _defense_pg()
    assert S.defense_factors(fit, pm, fit).filter(pl.col("opp") == "DET", pl.col("t") == 202410)["d_ypr"].item() < 1.0
    # the current game's stats never move its own factor (fit-season averages held fixed)
    assert abs(S.defense_factors(_defense_pg(yds_allowed_last=900.0), pm, pg).filter(
        pl.col("opp") == "CHI", pl.col("t") == 202410)["d_ypr"].item() - a["d_ypr"].item()) < 1e-12
