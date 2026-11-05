"""Known answers for the EndzoneAPI spot-check feed's game draw."""
import importlib.util

from nflbet import config

_spec = importlib.util.spec_from_file_location("ezf", config.ROOT / "scripts" / "fetch" / "endzone_props.py")
F = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F)


def test_pick_is_fixed_by_season_and_week_not_order():
    ids = [f"2026_09_T{i:02d}_H{i:02d}" for i in range(14)]
    a = F.pick(ids, 2026, 9, 4)
    assert a == F.pick(list(reversed(ids)), 2026, 9, 4) and len(a) == 4 and set(a) <= set(ids)
    assert a != F.pick(ids, 2026, 10, 4) or a != F.pick(ids, 2025, 9, 4)
    assert F.pick(ids[:2], 2026, 9, 4) == sorted(ids[:2])


def test_latest_completed_week():
    s = [{"week": 8, "result": 3}, {"week": 8, "result": -7}, {"week": 9, "result": 1}, {"week": 9, "result": None}]
    assert F.latest_completed_week(s) == 8
    assert F.latest_completed_week([{"week": 1, "result": None}]) is None
