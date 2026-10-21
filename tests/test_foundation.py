"""Shared foundation: odds and fee arithmetic on hand-computed cases, the HTTP client's retry policy, and the layer rules
(quant and execution import no project code; sources import no research code; props and ats never import each other)."""
import ast
import io
import math
import urllib.error
from pathlib import Path

import numpy as np
import pytest

from nflbet.execution import records
from nflbet.quant import fees, odds
from nflbet.sources import http, ids

PKG = Path(__file__).resolve().parents[1] / "src" / "nflbet"


def test_implied_hand_cases():
    assert odds.implied(-110) == pytest.approx(110 / 210)
    assert odds.implied(150) == pytest.approx(0.4)
    assert odds.implied(100) == pytest.approx(0.5)
    assert odds.implied(-200) == pytest.approx(2 / 3)


def test_no_vig_over():
    assert odds.no_vig_over(-110, -110) == pytest.approx(0.5)
    # -150 / +130: 0.6 and 100/230; P(over) = 0.6 / (0.6 + 0.43478...)
    assert odds.no_vig_over(-150, 130) == pytest.approx(0.6 / (0.6 + 100 / 230))


def test_american_round_trips():
    for a in (-300, -150, -110, 100, 120, 250):
        assert odds.american_from_prob(odds.implied(a)) == pytest.approx(a if a != 100 else -100)
    assert odds.american_to_decimal(150) == pytest.approx(2.5)
    assert odds.american_to_decimal(-200) == pytest.approx(1.5)
    assert odds.decimal_to_american(2.5) == 150
    assert odds.decimal_to_american(1.5) == -200
    assert odds.decimal_to_american(2.0) == 100
    assert odds.decimal_to_american(1.0) is None


def test_profit_win_loss_push():
    p = odds.profit(np.array([-110.0, 150.0, -110.0]), np.array([1.0, 0.0, math.nan]))
    assert p == pytest.approx([100 / 110, -1.0, 0.0])


def test_taker_fee_matches_venue_formulas():
    from nflbet.sources import venues as V
    assert fees.taker_fee(0.07, 0.5) == pytest.approx(0.0175)
    assert V.pm_fee(0.4) == 0.0695 * 0.4 * 0.6
    assert V.ks_fee(0.4, 1) == 1 * 0.07 * 0.4 * 0.6
    assert V.nv_fee({"fee": {"charged": "ALWAYS", "coefficient": 0.05}}, 0.3) == 0.05 * 0.3 * 0.7
    assert V.nv_fee({"fee": {"charged": "WHEN_LIVE", "coefficient": 0.05}, "_event": {"status": "OPEN"}}, 0.3) == 0.0


def test_ids_keys():
    assert ids.norm_name("D.J. Moore Jr.") == "dj moore"
    assert ids.last_name("Garrett Wilson") == "wilson g"
    assert ids.game_key("NYJ", "BUF") == ids.game_key("BUF", "NYJ") == "BUF|NYJ"
    assert ids.TEAMS["Los Angeles Rams"] == "LA" and ids.TEAM_FIX["JAC"] == "JAX"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_get_json_retries_429_then_succeeds(monkeypatch):
    calls, sleeps = [], []
    def fake_open(req, timeout):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, None)
        return _Resp(b'{"ok": 1}')
    monkeypatch.setattr(http.urllib.request, "urlopen", fake_open)
    monkeypatch.setattr(http.time, "sleep", sleeps.append)
    assert http.get_json("https://x.test/a", {}, pace=0.25, retries_429=3, backoff=2) == {"ok": 1}
    assert len(calls) == 3
    assert sleeps == [0.25, 2, 0.25, 4, 0.25]          # pace before each try, backoff 2 x 2^i after each 429


def test_get_json_raises_other_errors_and_exhausted_429(monkeypatch):
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    def boom(code):
        def f(req, timeout):
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, None)
        return f
    monkeypatch.setattr(http.urllib.request, "urlopen", boom(500))
    with pytest.raises(urllib.error.HTTPError):
        http.get_json("https://x.test/a", {}, retries_429=3)
    monkeypatch.setattr(http.urllib.request, "urlopen", boom(429))
    with pytest.raises(urllib.error.HTTPError):
        http.get_json("https://x.test/a", {}, retries_429=1)


def test_before_kickoff_is_strict():
    import polars as pl
    runs = pl.DataFrame({"run_utc": ["2026-10-18T16:59:59Z", "2026-10-18T17:00:00Z"],
                         "start_time": ["2026-10-18T17:00:00Z", "2026-10-18T17:00:00Z"]})
    assert records.before_kickoff(runs)["run_utc"].to_list() == ["2026-10-18T16:59:59Z"]


# --------------------------------------------------------------------------------------------- layer rules
ALLOWED = {
    "quant": {"quant"},
    "execution": {"quant", "execution", "config"},
    "sources": {"quant", "sources", "config"},
    "props": {"quant", "execution", "sources", "props", "config"},
    "ats": {"quant", "execution", "sources", "ats", "config"},
}


def _nflbet_imports(path: Path) -> set[str]:
    """Top-level nflbet subpackage or module names imported anywhere in the file, including inside functions."""
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "nflbet":
            parts = node.module.split(".")
            out |= {parts[1]} if len(parts) > 1 else {a.name for a in node.names}
        elif isinstance(node, ast.Import):
            out |= {a.name.split(".")[1] for a in node.names if a.name.startswith("nflbet.")}
    return out


@pytest.mark.parametrize("layer", sorted(ALLOWED))
def test_layer_imports(layer):
    for f in sorted((PKG / layer).glob("*.py")):
        extra = _nflbet_imports(f) - ALLOWED[layer]
        assert not extra, f"{layer}/{f.name} imports {sorted(extra)}"


def test_no_modules_left_at_top_level():
    top = {f.stem for f in PKG.glob("*.py")}
    assert top == {"__init__", "config", "dashboard"}
