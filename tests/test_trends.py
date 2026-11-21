import datetime as dt

import polars as pl

from nflbet.ui import trends as T


def rec(rows):
    return pl.DataFrame(rows, schema={"week": pl.Utf8, "result": pl.Utf8, "units": pl.Utf8, "units_best": pl.Utf8})


def test_mix_weekly_hand_case():
    r = rec([("9", "W", "0.5", "0.6"), ("9", "L", "-1", "-1"), ("10", "W", "0.5", ""), ("10", "pending", "", ""), ("10", "void", "0", "")])
    m = T.mix_weekly(r)
    assert m["W"] == {9: 1, 10: 1} and m["L"] == {9: 1, 10: 0}
    assert m["dk"] == {9: -0.5, 10: 0.0}
    assert m["best"] == {9: -0.4, 10: 0.1}


def test_engine_and_empty_inputs():
    assert T.engine_weekly(None)["dk"] == {}
    e = T.engine_weekly({"by_week": {"11": {"n": 5, "dk": 0.69, "A": 0.7, "B": 0.68}}})
    assert e["A"] == {11: 0.7} and e["n"] == {11: 5}
    assert T.clv_weekly(None) == {} and T.venue_share_weekly(None) == {}


def test_freshness_flags_old_and_missing():
    now = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc)
    runs = pl.DataFrame({"run_utc": ["2026-11-20T23:00:00Z"]})
    f = {x["name"]: x for x in T.freshness({"mix_runs": runs}, now)}
    assert f["Props mix run"]["stale"] is False and f["Pinnacle snapshot"]["stale"] is True
