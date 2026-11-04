"""Hand cases for scripts/dkfd_rules.py (docs/dkfd_rules_preregistration.md)."""
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dkfd_rules as D  # noqa: E402


def _pairs():
    return pl.DataFrame({
        "game": ["A|B"] * 4, "nkey": ["p1", "p2", "p3", "p4"], "market": ["rec_yds"] * 4, "week": [9] * 4,
        "dk_line": [55.5, 40.5, 30.5, 60.5], "dk_over": [-100.0] * 4, "dk_under": [-125.0, -110.0, -130.0, -125.0],
        "fd_line": [52.5, 42.5, 30.5, 30.5], "fd_over": [-110.0] * 4, "fd_under": [-110.0, -135.0, -110.0, -110.0]})


def test_d2_takes_higher_line_book_price():
    x = D.rule_d2(_pairs()).sort("nkey")
    # p1: DK higher, -125 qualifies; p2: FD higher, -135 qualifies; p3 same line; p4 gap 98% > 30%
    assert x["nkey"].to_list() == ["p1", "p2"]
    assert x["line"].to_list() == [55.5, 42.5] and x["odds"].to_list() == [-125.0, -135.0]


def test_d1_needs_dk_high_and_projection_gap():
    proj = pl.DataFrame({"week": [9, 9], "nkey": ["p1", "p2"], "market": ["rec_yds"] * 2, "team": ["A", "B"],
                         "proj": [49.0, 30.0]})
    x = D.rule_d1(_pairs(), proj)
    # p1: DK high, (55.5-49)/55.5 = 11.7% >= 10%; p2: FD high -> excluded
    assert x["nkey"].to_list() == ["p1"] and x["odds"].to_list() == [-125.0]
    proj2 = proj.with_columns(pl.Series("proj", [51.0, 30.0]))      # 8.1% gap -> no bet
    assert D.rule_d1(_pairs(), proj2).height == 0


def test_screen_drops_junk():
    q = pl.DataFrame({"over": [220.0, -115.0, -150.0], "under": [-300.0, -115.0, -150.0]})
    assert D.screen(q)["over"].to_list() == [-115.0]               # +220/-300: P(over) 0.30; -150/-150: hold 20%
