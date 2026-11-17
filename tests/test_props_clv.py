"""Props CLV record (docs/props_clv_rules.md): known answers before use."""
import gzip
import json
import math
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from scipy.stats import norm

from nflbet.props import clv as C

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "docs/evidence/pinnradar/20261117T035156Z/board.json.gz"


def test_fair_over_hand_cases():
    assert C.fair_over(1.877, 1.877)[0] == pytest.approx(0.5)
    assert C.fair_over(1.877, 1.877)[1] == pytest.approx(2 / 1.877 - 1)
    q, h = C.fair_over(1.709, 2.07)
    assert q == pytest.approx((1 / 1.709) / (1 / 1.709 + 1 / 2.07))
    assert C.fair_over(1.5, 1.5) is None            # hold 33%: junk
    assert C.fair_over(None, 1.9) is None


def test_same_line_unchanged_and_direction():
    assert C.p_over_at(50.5, 0.57, 50.5, "rec_yds", 4.0) == 0.57
    up = C.p_over_at(50.5, 0.5, 55.5, "rec_yds", 4.0)
    down = C.p_over_at(50.5, 0.5, 45.5, "rec_yds", 4.0)
    assert up < 0.5 < down
    sd = 4.0 * math.sqrt(53.0)
    assert up == pytest.approx(norm.cdf((50.5 - 55.5) / sd))


def test_planted_sigma_recovered_and_noise_not_fit():
    rng = np.random.default_rng(7)
    s_true, rows = 3.0, []
    for _ in range(400):
        mu = rng.uniform(20, 90)
        la = round(mu + rng.normal(0, 4)) + 0.5
        lb = la + rng.choice([-3.0, -2.0, -1.0, 1.0, 2.0, 3.0])
        qa = 1 - norm.cdf((la - mu) / (s_true * math.sqrt(la)))
        qb = 1 - norm.cdf((lb - mu) / (s_true * math.sqrt((la + lb) / 2)))
        rows.append({"market": "rec_yds", "line_a": la, "q_a": qa, "line_b": lb, "q_b": qb})
    pairs = pl.DataFrame(rows)
    s = C.fit_s(pairs, "rec_yds")
    assert s == pytest.approx(s_true, abs=0.15)
    mm, mb, n = C.mae(pairs, "rec_yds", s)
    assert n == 400 and mm < mb / 5
    # noise: q_b unrelated to the line gap -> the model must not beat ignoring the gap by much
    noise = pairs.with_columns(pl.Series("q_b", rng.uniform(0.35, 0.65, 400)), pl.Series("q_a", rng.uniform(0.35, 0.65, 400)))
    s2 = C.fit_s(noise, "rec_yds")
    mm2, mb2, _ = C.mae(noise, "rec_yds", s2)
    assert mm2 > 0.9 * mb2


@pytest.mark.skipif(not PROBE.exists(), reason="probe evidence not present")
def test_parse_probe_board():
    d = C.parse_pinnacle(json.load(gzip.open(PROBE, "rt")))
    assert d.height == 24
    r = d.filter((pl.col("player") == "C.J. Stroud") & (pl.col("market") == "pass_yds")).row(0, named=True)
    assert (r["game"], r["line"], r["over_dec"], r["under_dec"], r["max_risk"]) == ("HOU|IND", 263.5, 1.877, 1.877, 250.0)
    assert set(d["market"]) <= set(C.UNITS.values())


def test_last_close_window_and_pick_clv_hand_case():
    rows = pl.DataFrame([
        {"source": "pinnacle", "game": "HOU|IND", "nkey": "nico collins", "market": "rec_yds", "snap_utc": "2026-11-20T00:55:00Z",
         "lead_min": 20.0, "line": 70.5, "fair_over": 0.50},
        {"source": "pinnacle", "game": "HOU|IND", "nkey": "nico collins", "market": "rec_yds", "snap_utc": "2026-11-20T01:09:00Z",
         "lead_min": 6.0, "line": 70.5, "fair_over": 0.55},
        {"source": "dk", "game": "HOU|IND", "nkey": "nico collins", "market": "rec_yds", "snap_utc": "2026-11-19T23:00:00Z",
         "lead_min": 135.0, "line": 68.5, "fair_over": 0.5},           # too early: not a close
    ])
    last = C.last_close(rows)
    assert last.height == 1 and last.row(0, named=True)["fair_over"] == 0.55
    picks = pl.DataFrame([{"game": "HOU|IND", "nkey": "nico collins", "market": "rec_yds", "side": "over", "line": "70.5",
                           "odds": "-110", "p_over_dk": "0.5", "best_cost": "0.5", "player": "Nico Collins"}])
    out = C.pick_clv(picks, last, {})
    r = out.filter(pl.col("source") == "pinnacle").row(0, named=True)
    assert r["clv_ev"] == pytest.approx(0.55 * (1 + 100 / 110) - 1)
    assert r["clv_ev_best"] == pytest.approx(0.55 / 0.5 - 1)
    assert r["novig_move"] == pytest.approx(0.05) and r["line_move"] == 0.0
    # under on a moved line with no conversion: line move reported, no CLV
    p2 = picks.with_columns(pl.lit("under").alias("side"), pl.lit("72.5").alias("line"))
    r2 = C.pick_clv(p2, last, {}).row(0, named=True)
    assert r2["line_move"] == 2.0 and r2["clv_ev"] is None
    r3 = C.pick_clv(p2, last, {"rec_yds": 4.0}).row(0, named=True)
    assert r3["converted"] is True and r3["p_close"] == pytest.approx(1 - C.p_over_at(70.5, 0.55, 72.5, "rec_yds", 4.0))


def test_dashboard_pinnacle_and_clv_chips():
    from nflbet import dashboard as D

    cur = pl.DataFrame([{"run_utc": "r1", "an_game_id": "g1", "player_id": "p1", "market": "rec", "side": "under",
                         "line": 4.5, "home": "HOU", "away": "IND", "player": "Nico Collins"}])
    pinn = pl.DataFrame([{"game": "HOU|IND", "nkey": "nico collins", "market": "rec", "line": "4.5", "fair_over": "0.4",
                          "snap_utc": "2026-11-20T00:00:00Z", "max_risk": "250"},
                         {"game": "HOU|IND", "nkey": "nico collins", "market": "rec", "line": "5.5", "fair_over": "0.3",
                          "snap_utc": "2026-11-19T00:00:00Z", "max_risk": "250"}])
    clv = pl.DataFrame([{"run_utc": "r1", "an_game_id": "g1", "player_id": "p1", "market": "rec", "side": "under",
                         "source": "pinnacle", "clv_ev": "0.031", "line_move": "0.0", "close_line": "4.5"},
                        {"run_utc": "r1", "an_game_id": "g1", "player_id": "p1", "market": "rec", "side": "under",
                         "source": "dk", "clv_ev": "", "line_move": "-1.0", "close_line": "5.5"}])
    r = D.with_pinnacle(cur, pinn, clv).to_dicts()[0]
    assert r["pinn_line"] == 4.5 and r["pinn_over"] == 0.4          # latest snapshot wins
    html = D.pinn_chips(r)
    assert "Pinnacle 60%" in html and "CLV Pin +3.1%" in html and "DK close -1 pts" in html
    assert "+3.1%" in D.clv_stat(clv)
    assert "–" in D.clv_stat(None)
