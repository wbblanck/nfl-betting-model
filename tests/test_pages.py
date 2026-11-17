import datetime as dt
from pathlib import Path

import polars as pl

from nflbet import dashboard as D


def test_snapshot_time():
    assert D.snapshot_time(Path("20261117T0322Z_w10.json.gz")) == dt.datetime(2026, 11, 17, 3, 22, tzinfo=dt.timezone.utc)
    assert D.snapshot_time(Path("odd.json.gz")) is None
    assert D.snapshot_time(None) is None


def test_live_line_only_with_live_prices():
    assert D.live_line({}, 0.5) == ""
    r = {"live_at": "2026-11-16T19:58:00Z", "live_best_venue": "Novig", "live_best_cost": 0.54,
         "live_venues": '{"Novig": [0.54, 353.0], "DraftKings (ParlayAPI)": [0.563, null]}',
         "live_venues_opp": '{"Novig": [0.49, 300.0], "DraftKings (ParlayAPI)": [0.47, null]}'}
    h = D.live_line(r, 0.53)
    assert "Live now" in h and "Novig -117" in h and "DraftKings" in h
    empty = D.live_line({"live_at": "2026-11-16T19:58:00Z", "live_venues": "{}"}, 0.5)
    assert "No venue quotes" in empty


def test_pages_banner():
    assert D.pages_banner(None) == ""
    now = dt.datetime(2026, 11, 16, 20, 0, tzinfo=dt.timezone.utc)
    b = D.pages_banner({"refreshed": now, "snap_at": None, "n": 3, "actions": D.ACTIONS})
    assert "3 open props-mix picks" in b and "Refresh now" in b and "no DraftKings/FanDuel pull saved" in b


def test_live_quotes_without_quotes(tmp_path):
    """No venue quotes: a pick is priced with no best venue, and no open picks gives no rows (no fetch, no snapshot)."""
    now = dt.datetime(2026, 11, 16, 20, 0, tzinfo=dt.timezone.utc)
    pk = pl.DataFrame({"week": ["10"], "an_game_id": ["g1"], "start_time": ["2026-11-17T01:15:00Z"], "home": ["LAC"],
                       "away": ["BAL"], "player": ["Kimani Vidal"], "player_id": ["p1"], "team": ["LAC"],
                       "market": ["rush_att"], "line": [6.5], "side": ["under"], "odds": [-129.0]})
    rows = D.Bp.best_rows(pk, {}, None, {}, {}, {}, "2026-11-16T20:00:00Z", {}, {})
    assert rows.height == 1 and rows["best_venue"][0] is None
    data = {"mix_props": pl.DataFrame(), "mix_runs": pl.DataFrame(), "mix_rec": pl.DataFrame(), "mix_best": None, "live": tmp_path}
    got, snap = D.live_quotes(data, now, quotes={"pmq": {}, "pm_size": {}, "nv_idx": {}, "nv_books": {}, "ksq": {}}, snap=None)
    assert got.height == 0 and snap is None


def test_page_is_a_document():
    h = D.page("<title>x</title><p>y</p>")
    assert h.startswith("<!doctype html>") and 'name="viewport"' in h and h.endswith("</body></html>")
