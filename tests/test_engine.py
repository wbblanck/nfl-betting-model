"""Engine foundation (docs/engine/TEST_PLAN.md): registry, contract matching, book pricing, accounting, ledger and
the isolation rules, each on hand cases with the wrong answer planted and found."""
import ast
import datetime as dt
import gzip
import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from nflbet import engine
from nflbet.engine import accounting, contracts, ledger, novig_capture, pricing, registry
from nflbet.props import core

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "nflbet"


# ------------------------------------------------------------------------------------------------ registry
def test_registry_loads_and_agrees_with_the_grading_map():
    R = registry.load()
    assert {"pass_yds", "rush_yds", "rec_yds", "rec", "pass_att", "rush_att", "targets"} <= set(R)
    assert set(core.STAT) <= set(R)                         # every market the repo already grades has an entry
    assert R["rec"].bounded_by == "targets" and R["pass_cmp"].bounded_by == "pass_att"
    for k in ("pass_td", "pass_int", "anytime_td", "first_td", "long_rec", "tds"):
        assert R[k].shadow
    assert R["rush_rec_yds"].components == ("rush_yds", "rec_yds")


def test_registry_novig_types_were_all_seen_in_the_saved_probe():
    probe = json.loads((ROOT / "docs/evidence/novig_probe/20261014T091702Z/probe.json").read_text())
    listed = set(probe["hosts"]["production"]["types"]["markets"]["body"])
    assert set(registry.by_novig_type()) <= listed
    assert registry.load()["targets"].novig_type is None    # Novig lists no targets market


def _doc(**over):
    m = {"positions": ["QB"], "family": "count", "distribution": "negative_binomial", "stat": ["attempts"], "shadow": False}
    return {"markets": {"x": {**m, **over}}}


@pytest.mark.parametrize("bad, msg", [
    ({"family": "vibes"}, "family"), ({"positions": ["K"]}, "positions"), ({"shadow": "no"}, "required"),
    ({"bounded_by": "nope"}, "unknown market"), ({"family": "rare_event"}, "shadow-only"), ({"typo": 1}, "unknown fields"),
])
def test_registry_rejects_bad_entries(bad, msg):
    with pytest.raises(ValueError, match=msg):
        registry.parse(_doc(**bad))


def test_registry_rejects_live_market_built_from_shadow_and_duplicate_types():
    doc = _doc(family="rare_event", shadow=True)
    doc["markets"]["y"] = {"positions": ["QB"], "family": "joint", "distribution": "d", "components": ["x"], "shadow": False}
    with pytest.raises(ValueError, match="must be shadow"):
        registry.parse(doc)
    doc = _doc(novig_type="A")
    doc["markets"]["y"] = {**doc["markets"]["x"]}
    with pytest.raises(ValueError, match="two markets"):
        registry.parse(doc)


# ------------------------------------------------------------------------------------------------ contracts
EV = {"eventId": "e1", "description": "New York Jets @ Buffalo Bills", "startsTs": 1_800_000_000_000}


def _mkt(**over):
    m = {"marketId": "m1", "eventId": "e1", "marketType": "RECEIVING_YARDS", "description": "Garrett Wilson 74.5 RECEIVING_YARDS",
         "strike": "74.5", "status": "OPEN", "voids": "FMV", "startsTs": 1_800_000_000_000,
         "outcomes": [{"outcomeId": "o", "name": "Over 74.5"}, {"outcomeId": "u", "name": "Under 74.5"}]}
    return {**m, **over}


def test_match_novig_reads_every_part_of_the_identity():
    c, why = contracts.match_novig(_mkt(), EV, registry.by_novig_type())
    assert why == "ok"
    assert (c.market, c.line, c.game, c.home, c.away) == ("rec_yds", Decimal("74.5"), "BUF|NYJ", "BUF", "NYJ")
    assert (c.over_id, c.under_id, c.period, c.voids, c.player_key) == ("o", "u", "game", "FMV", "garrett wilson")


@pytest.mark.parametrize("over, ev, why", [
    ({"marketType": "KICKING_POINTS"}, EV, "not in registry"),
    ({"strike": "75.5"}, EV, "disagree"),                                         # a different line is a different contract
    ({"description": "Garrett Wilson 74.5 RUSHING_AND_RECEIVING_YARDS"}, EV, "does not read"),   # a different stat
    ({"description": "Garrett Wilson 74.5 RECEIVING_YARDS 1H"}, EV, "does not read"),            # a partial-game prop
    ({"strike": "75", "description": "Garrett Wilson 75 RECEIVING_YARDS",
      "outcomes": [{"outcomeId": "o", "name": "Over 75"}, {"outcomeId": "u", "name": "Under 75"}]}, EV, "whole-number"),
    ({"outcomes": [{"outcomeId": "o", "name": "Over 74.5"}, {"outcomeId": "u", "name": "Under 75.5"}]}, EV, "one Over and one Under"),
    ({"outcomes": [{"outcomeId": "o", "name": "Over 74.5"}, {"outcomeId": "u", "name": "Over 74.5"}]}, EV, "one Over and one Under"),
    ({"outcomes": [{"outcomeId": "o", "name": "Yes"}, {"outcomeId": "u", "name": "No"}]}, EV, "one Over and one Under"),
    ({}, None, "event missing"), ({}, {**EV, "eventId": "other"}, "event missing"),
    ({}, {**EV, "description": "Jets vs Bills"}, "Away @ Home"), ({}, {**EV, "description": "Mars @ Buffalo Bills"}, "unknown team"),
])
def test_match_novig_refuses_anything_inexact(over, ev, why):
    c, reason = contracts.match_novig(_mkt(**over), ev, registry.by_novig_type())
    assert c is None and why in reason


def test_resolve_player_never_guesses():
    c, _ = contracts.match_novig(_mkt(), EV, registry.by_novig_type())
    ros = [{"player_id": "A", "name": "Garrett Wilson", "team": "NYJ", "position": "WR"},
           {"player_id": "B", "name": "Garrett Wilson", "team": "DAL", "position": "WR"},      # same name, not in this game
           {"player_id": "C", "name": "Josh Allen", "team": "BUF", "position": "QB"}]
    assert contracts.resolve_player(c, ros) == ("A", "name")
    assert contracts.resolve_player(c, ros + [{"player_id": "D", "name": "Garrett Wilson", "team": "BUF", "position": "CB"}]) == (None, "ambiguous (name)")
    assert contracts.resolve_player(c, ros[1:]) == (None, "not on either roster")
    ini = [{"player_id": "E", "name": "Garret Wilson", "team": "NYJ", "position": "WR"}]          # spelling differs
    assert contracts.resolve_player(c, ini) == ("E", "last+initial")
    assert contracts.resolve_player(c, ini + [{"player_id": "F", "name": "Gabe Wilson", "team": "BUF", "position": "WR"}]) == (None, "ambiguous (last+initial)")


# ------------------------------------------------------------------------------------------------ pricing
def test_mills_is_exact_and_strict():
    assert pricing.mills("0.685") == 685 and pricing.mills("0.011") == 11 and pricing.mills(0.52) == 520
    for bad in ("0.6855", "0", "1", "1.2", "-0.1"):
        with pytest.raises(ValueError):
            pricing.mills(bad)


def test_take_walks_the_other_side_cheapest_first():
    # Under rests 0.48 x 300 and 0.45 x 500 (two orders: 200 + 300). Over therefore costs 0.52 for 300, then 0.55 for 500.
    under = [{"price": "0.45", "qty": 200}, {"price": "0.48", "qty": 300}, {"price": "0.45", "qty": 300}]
    f = pricing.take(under, 300)
    assert (f.filled, f.unfilled, f.cost, f.worst) == (300, 0, Fraction(52, 100), 520)
    f = pricing.take(under, 500)
    assert f.levels == ((520, 300), (550, 200)) and f.cost == Fraction(300 * 520 + 200 * 550, 500 * 1000)   # 0.532
    f = pricing.take(under, 1000)
    assert (f.filled, f.unfilled) == (800, 200) and f.cost == Fraction(300 * 520 + 500 * 550, 800 * 1000)
    f = pricing.take(under, 500, limit_mills=520)                       # will not pay above 0.52
    assert (f.filled, f.unfilled, f.worst) == (300, 200, 520)
    f = pricing.take([], 100)
    assert (f.filled, f.unfilled, f.cost, f.worst) == (0, 100, None, None)
    with pytest.raises(ValueError):
        pricing.take(under, 0)


def test_fee_and_ev_hand_cases():
    wl = {"coefficient": "0.06", "charged": "WHEN_LIVE"}
    assert pricing.taker_fee(wl, Fraction(1, 2), live=False) == 0
    assert pricing.taker_fee(wl, Fraction(1, 2), live=True) == Fraction(15, 1000)           # 0.06 x 0.5 x 0.5
    assert pricing.taker_fee({"coefficient": "0.03", "charged": "ALWAYS"}, Fraction(3, 10), live=False) == Fraction(63, 10000)
    with pytest.raises(ValueError):
        pricing.taker_fee({"coefficient": "0.03", "charged": "SOMETIMES"}, Fraction(1, 2), live=False)
    with pytest.raises(ValueError):
        pricing.taker_fee(None, Fraction(1, 2), live=False)
    e, r = pricing.ev(0.57, Fraction(52, 100))
    assert e == pytest.approx(0.05) and r == pytest.approx(0.05 / 0.52)
    e, r = pricing.ev(0.57, Fraction(52, 100), Fraction(15, 1000))
    assert e == pytest.approx(0.035) and r == pytest.approx(0.035 / 0.535)
    assert pricing.ev(0.52, Fraction(52, 100))[0] == pytest.approx(0.0)
    with pytest.raises(ValueError):
        pricing.ev(1.2, Fraction(1, 2))


def test_mc_se_matches_the_binomial_formula():
    for n, pp in ((5_000, 0.71), (10_000, 0.50), (25_000, 0.32), (50_000, 0.22), (100_000, 0.16)):
        assert round(100 * pricing.mc_se(0.5, n), 2) == pp


# ------------------------------------------------------------------------------------------------ accounting
def _box(runs=3):
    one = {"targets": [[5, 3, 2]], "rec": [[4, 2, 1]], "rec_yds": [[50, 20, 5]], "carries": [[0, 12, 6]], "rush_yds": [[0, 40, 31]],
           "pass_att": [11], "pass_cmp": [7], "pass_yds": [75], "sacks": [2], "scrambles": [3], "dropbacks": [16], "team_carries": [18]}
    return {k: np.repeat(np.array(v, dtype=np.int64), runs, axis=0) for k, v in one.items()}


def test_clean_box_reconciles():
    assert accounting.violations(_box()) == {}


@pytest.mark.parametrize("key, idx, value, rule", [
    ("rec", (1, 0), 6, "receptions > targets (player)"),
    ("pass_cmp", (1,), 12, "completions > attempts"),
    ("pass_att", (1,), 9, "targets > pass attempts (team)"),
    ("pass_cmp", (1,), 6, "receptions != completions (team)"),
    ("pass_yds", (1,), 76, "receiving yards != passing yards (team)"),
    ("team_carries", (1,), 19, "player carries != team carries"),
    ("dropbacks", (1,), 15, "dropbacks != attempts + sacks + scrambles"),
    ("carries", (1, 0), -1, "negative count"),
    ("rush_yds", (1, 0), 4, "yards on zero carries (player)"),
])
def test_each_planted_break_is_found_in_exactly_that_run(key, idx, value, rule):
    b = _box()
    b[key][idx] = value
    v = accounting.violations(b)
    assert v.get(rule) == 1                                  # one run broken, found once (other rules may also fire)


def test_accounting_refuses_floats_and_missing_arrays():
    b = _box()
    b["rec_yds"] = b["rec_yds"].astype(float)
    with pytest.raises(TypeError):
        accounting.violations(b)
    b = _box()
    del b["sacks"]
    with pytest.raises(KeyError):
        accounting.violations(b)


# ------------------------------------------------------------------------------------------------ ledger
def test_ledger_chain_detects_edit_delete_and_reorder(tmp_path):
    p = tmp_path / "l.jsonl"
    assert ledger.verify(p) == (0, ledger.GENESIS)
    for i in range(3):
        last = ledger.append(p, {"kind": "prediction", "id": i, "p_over": "0.5700"})
    assert ledger.verify(p) == (3, last)
    lines = p.read_text().splitlines()
    for tampered in ([lines[0].replace("0.5700", "0.5900"), *lines[1:]], [lines[0], lines[2]], [lines[1], lines[0], lines[2]]):
        p.write_text("\n".join(tampered) + "\n")
        with pytest.raises(ValueError, match="chain broken"):
            ledger.verify(p)
        with pytest.raises(ValueError):
            ledger.append(p, {"kind": "prediction", "id": 9})        # a broken file cannot be extended
    with pytest.raises(TypeError):
        ledger.append(tmp_path / "f.jsonl", {"p": 0.57})


# ------------------------------------------------------------------------------------------------ Novig capture
def test_book_targets_window_order_and_cap():
    now = dt.datetime(2026, 11, 15, 16, 0, tzinfo=dt.timezone.utc)
    t = int(now.timestamp() * 1000)
    def m(i, typ="RECEPTIONS", start=t + 3_600_000, status="OPEN", bid="0.5"):
        return {"marketId": i, "eventId": "e", "marketType": typ, "status": status, "startsTs": start,
                "outcomes": [{"bid": {"price": bid, "qty": 1} if bid else None}, {}]}
    ms = [m("b"), m("a"), m("late", start=t + 5 * 3_600_000), m("started", start=t - 1), m("closed", status="CLOSED"),
          m("empty", bid=None), m("spread", typ="SPREAD"), m("soon", start=t + 60_000)]
    assert [x["marketId"] for x in novig_capture.book_targets(ms, {}, now, 4, 10)] == ["soon", "a", "b"]
    assert [x["marketId"] for x in novig_capture.book_targets(ms, {}, now, 4, 2)] == ["soon", "a"]
    assert {"SPREAD", "RECEPTIONS", "TOUCHDOWNS"} <= set(novig_capture.market_types())


def test_saved_novig_spread_snapshot_prices_with_take():
    """Real saved book: buying one outcome costs 1 - the other outcome's best resting price (nflbet.sources.venues)."""
    d = sorted((ROOT / "docs/evidence/novig_spread_probe").iterdir())[-1]
    books = json.load(gzip.open(d / "books.json.gz"))
    book = next(b for b in books.values() if all(b["orders"].values()) and len(b["orders"]) == 2)
    (ida, oa), (idb, ob) = book["orders"].items()
    f = pricing.take(ob, 1)
    assert f.cost == 1 - Fraction(pricing.mills(ob[0]["price"]), 1000)
    best_qty = sum(o["qty"] for o in ob if o["price"] == ob[0]["price"])
    assert pricing.take(ob, best_qty).levels == ((1000 - pricing.mills(ob[0]["price"]), best_qty),)


# ------------------------------------------------------------------------------------------------ isolation
def _imports(src: str) -> set[tuple[str, ...]]:
    """Every nflbet import in the source as a tuple of path parts after 'nflbet', including inside functions."""
    out = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "nflbet":
            base = tuple(node.module.split(".")[1:])
            out |= {base + (a.name,) for a in node.names}
        elif isinstance(node, ast.Import):
            out |= {tuple(a.name.split(".")[1:]) for a in node.names if a.name.startswith("nflbet.")}
    return out


def breaches(side: str, src: str) -> list[str]:
    """Imports a prediction engine ('replication' or 'challenger') may not make."""
    other = {"replication": "challenger", "challenger": "replication"}[side]
    bad = []
    for imp in _imports(src):
        if imp[:1] == ("engine",) and len(imp) > 1 and (imp[1] == other or imp[1] in engine.PRICE_LAYERS):
            bad.append(".".join(imp))
        elif imp[:1] == ("sources",) and len(imp) > 1 and imp[1] in engine.PRICE_SOURCES:
            bad.append(".".join(imp))
        elif imp[:1] in {("props",), ("ats",), ("gamesim",), ("dashboard",), ("execution",)}:
            bad.append(".".join(imp))            # research layers read lines; the engines stand on their own
    return sorted(bad)


def test_isolation_checker_finds_planted_breaches():
    assert breaches("replication", "from nflbet.engine.challenger import volume") == ["engine.challenger.volume"]
    assert breaches("challenger", "import nflbet.engine.replication.environment") == ["engine.replication.environment"]
    assert breaches("replication", "def f():\n    from nflbet.engine import pricing") == ["engine.pricing"]
    assert breaches("challenger", "from nflbet.sources.venues import nv_get") == ["sources.venues.nv_get"]
    assert breaches("challenger", "from nflbet.sources import parlay") == ["sources.parlay"]
    assert breaches("replication", "from nflbet.props import core") == ["props.core"]
    assert breaches("replication", "from nflbet.engine import registry, accounting\nfrom nflbet.sources import ids\n"
                                   "from nflbet.engine.replication import environment\nimport numpy") == []


@pytest.mark.parametrize("side", ["replication", "challenger"])
def test_prediction_engines_import_no_price_and_not_each_other(side):
    files = sorted((PKG / "engine" / side).rglob("*.py"))
    assert files
    for f in files:
        assert breaches(side, f.read_text()) == [], f.name


def test_engine_has_no_order_code_and_live_execution_is_off():
    assert engine.LIVE_EXECUTION is False
    for f in sorted((PKG / "engine").rglob("*.py")) + [ROOT / "scripts/fetch/novig_books.py"]:
        src = f.read_text()
        assert "/execution/" not in src and "orders" not in {n.attr for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Attribute)}
        assert not any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") in {"post", "put", "delete"} for n in ast.walk(ast.parse(src)))
