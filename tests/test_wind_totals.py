"""Known answers for the wind-totals test (docs/wind_totals_preregistration.md)."""
import datetime as dt
import importlib.util
import random

from nflbet import config
from nflbet.sources import weather

_spec = importlib.util.spec_from_file_location("wte", config.ROOT / "scripts" / "wind_totals_eval.py")
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)


def test_kickoff_daylight_and_standard_time():
    # 13:00 EDT (October) = 17:00 UTC; 13:00 EST (December) = 18:00 UTC; 20:20 EST -> 01:20 UTC next day.
    assert weather.kickoff_utc("2014-10-26", "13:00") == dt.datetime(2014, 10, 26, 17, 0, tzinfo=dt.timezone.utc)
    assert weather.kickoff_utc("2014-12-14", "13:00") == dt.datetime(2014, 12, 14, 18, 0, tzinfo=dt.timezone.utc)
    assert weather.kickoff_utc("2014-12-14", "20:20") == dt.datetime(2014, 12, 15, 1, 20, tzinfo=dt.timezone.utc)


def test_window_mean_uses_kickoff_hour_and_next_three():
    k = dt.datetime(2014, 12, 15, 1, 20, tzinfo=dt.timezone.utc)
    hourly = {"2014-12-15T00:00": 99, "2014-12-15T01:00": 8, "2014-12-15T02:00": 10, "2014-12-15T03:00": 12,
              "2014-12-15T04:00": 14, "2014-12-15T05:00": 99}
    assert weather.window_mean(hourly, k) == 11.0
    del hourly["2014-12-15T03:00"]
    assert weather.window_mean(hourly, k) is None


def test_bucket_edges_and_sides():
    assert E.bucket(7.99) == "calm <8"
    assert E.bucket(8.0) == "moderate 8-15"
    assert E.bucket(14.99) == "moderate 8-15"
    assert E.bucket(15.0) == "strong 15+"
    assert E.side(40, 42.5) == "under" and E.side(45, 42.5) == "over" and E.side(42, 42) == "push"


def test_binomial_tail_hand_cases():
    assert abs(E.binom_sf(1, 1, 0.3) - 0.3) < 1e-12
    assert abs(E.binom_sf(2, 2, 0.5) - 0.25) < 1e-12
    assert abs(E.binom_sf(1, 2, 0.5) - 0.75) < 1e-12
    assert E.binom_sf(0, 10, 0.5) == 1.0


def test_planted_signal_passes_and_noise_fails():
    rng = random.Random(7)
    n = 600
    planted = sum(rng.random() < 0.60 for _ in range(n))
    assert E.verdict(planted, n)[0] == "PASS"
    fails = sum(E.verdict(sum(rng.random() < 0.50 for _ in range(n)), n)[0] == "FAIL" for _ in range(50))
    assert fails >= 49
    assert E.verdict(80, 100)[0] == "UNDERPOWERED"


def test_pearson_hand_case():
    assert abs(E.pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-12
    assert abs(E.pearson([1, 2, 3], [3, 2, 1]) + 1.0) < 1e-12
