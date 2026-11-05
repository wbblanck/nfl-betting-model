import datetime as dt

from nflbet.execution import wind as W

UTC = dt.timezone.utc


def test_bucket_edges():
    assert W.bucket(7.99) == "calm <8"
    assert W.bucket(8.0) == "moderate 8-15" and W.is_pick(8.0)
    assert W.bucket(14.99) == "moderate 8-15" and W.is_pick(14.99)
    assert W.bucket(15.0) == "strong 15+" and not W.is_pick(15.0)
    assert not W.is_pick(None) and W.bucket(None) == ""


def test_eligible():
    now = dt.datetime(2026, 11, 5, 4, 0, tzinfo=UTC)
    ko = dt.datetime(2026, 11, 6, 1, 15, tzinfo=UTC)
    g = {"game_type": "REG", "location": "Home", "roof": "outdoors"}
    assert W.eligible(g, now, ko, 30)
    assert not W.eligible(g, now, ko, 12)                       # beyond horizon
    assert not W.eligible(g, ko, ko, 30)                        # already started
    assert not W.eligible({**g, "roof": "dome"}, now, ko, 30)
    assert not W.eligible({**g, "roof": None}, now, ko, 30)     # retractable, unknown
    assert not W.eligible({**g, "location": "Neutral"}, now, ko, 30)
    assert not W.eligible({**g, "game_type": "WC"}, now, ko, 30)


def test_official_last_before_kickoff():
    k = "2026-11-08T18:00Z"
    rows = [{"game_id": "g", "run_utc": "2026-11-07T15:00Z", "kickoff_utc": k, "v": 1},
            {"game_id": "g", "run_utc": "2026-11-08T16:00Z", "kickoff_utc": k, "v": 2},
            {"game_id": "g", "run_utc": "2026-11-08T18:00Z", "kickoff_utc": k, "v": 3},   # at kickoff: never counts
            {"game_id": "h", "run_utc": "2026-11-08T19:00Z", "kickoff_utc": k, "v": 4}]   # only after kickoff
    off = W.official(rows)
    assert [r["v"] for r in off] == [2]


def test_grade():
    assert W.grade(40, 44.5, -110) == ("W", 100 / 110)
    assert W.grade(45, 44.5, -110) == ("L", -1.0)
    assert W.grade(44, 44, -105) == ("P", 0.0)
    assert W.grade(30, 44.5, 120) == ("W", 1.2)
    assert W.grade(30, 44.5, None) == ("W", 100 / 110)


def test_binom_matches_wind_report():
    # docs/wind_totals_report.md: 420 of 771, p = 0.1296
    assert abs(W.binom_p_greater(420, 771) - 0.1296) < 5e-4
    assert abs(W.binom_p_greater(0, 10) - 1.0) < 1e-9
