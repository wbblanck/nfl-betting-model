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


# ------------------------------------------------------------------------------------------------ warehouse
def _pw_inputs():
    import polars as pl
    from nflbet.engine.data import player_week as PW
    z = {c: 0 for c in PW.STATS}
    def s(pid, week, team, opp, pos="WR", typ="REG", **kw):
        return {"player_id": pid, "season": 2023, "week": week, "season_type": typ, "game_id": f"2023_{week:02d}", "team": team,
                "opponent_team": opp, "position": pos, **z, **kw}
    stats = pl.DataFrame([s("A", 1, "NYJ", "BUF", receptions=5, targets=7, receiving_yards=60),
                          s("A", 2, "DAL", "NYG", receptions=2, targets=3, receiving_yards=11),      # traded after week 1
                          s("K", 1, "NYJ", "BUF", pos="K"), s("A", 19, "DAL", "GB", typ="POST")])
    def n(pfr, week, team, opp, snaps, pos="WR"):
        return {"game_id": f"2023_{week:02d}", "season": 2023, "game_type": "REG", "week": week, "pfr_player_id": pfr, "position": pos,
                "team": team, "opponent": opp, "offense_snaps": snaps, "offense_pct": 0.5}
    snaps = pl.DataFrame([n("pA", 1, "NYJ", "BUF", 40), n("pA", 2, "DAL", "NYG", 30),
                          n("pB", 1, "NYJ", "BUF", 12),          # played, no stat row -> zeros
                          n("pC", 1, "NYJ", "BUF", 0),           # dressed, no snaps -> no row
                          n("pX", 1, "NYJ", "BUF", 9),           # PFR ID unknown -> counted, left out
                          n("pD", 1, "NYJ", "BUF", 9)])          # PFR ID maps to two players -> counted, left out
    players = pl.DataFrame({"pfr_id": ["pA", "pB", "pC", "pD", "pD"], "gsis_id": ["A", "B", "C", "D1", "D2"]})
    return PW, stats, snaps, players


def test_player_week_hand_cases():
    PW, stats, snaps, players = _pw_inputs()
    out, rep = PW.build(stats, snaps, players)
    rows = {(r["player_id"], r["week"]): r for r in out.iter_rows(named=True)}
    assert set(rows) == {("A", 1), ("A", 2), ("B", 1)}                       # kicker, playoff game, zero-snap player: no row
    assert (rows[("A", 1)]["team"], rows[("A", 2)]["team"]) == ("NYJ", "DAL")   # traded player: one row a week, right team
    assert rows[("A", 1)]["receiving_yards"] == 60 and rows[("A", 1)]["offense_snaps"] == 40
    b = rows[("B", 1)]
    assert b["stat_row"] is False and b["targets"] == 0 and b["offense_snaps"] == 12 and b["team"] == "NYJ"
    assert rep == {"stat_rows": 2, "snap_rows": 5, "snap_rows_unmapped": 2, "snap_duplicate_keys": 0, "zero_rows_added": 1,
                   "stat_rows_without_snaps": 0}


def test_player_week_refuses_duplicate_stat_rows():
    import polars as pl
    PW, stats, snaps, players = _pw_inputs()
    with pytest.raises(ValueError, match="more than one stat row"):
        PW.build(pl.concat([stats, stats.head(1)]), snaps, players)


def test_team_aliases_map_old_codes_to_the_stats_code():
    import polars as pl
    from nflbet.engine.data import player_week as PW
    df = pl.DataFrame({"t": ["OAK", "SD", "SL", "BLT", "KC"]}).select(PW.team_code("t"))
    assert df["t"].to_list() == ["LV", "LAC", "LA", "BAL", "KC"]


# ------------------------------------------------------------------------------------------------ features
def _feature_inputs(seed=0, scramble_from=None):
    """Synthetic league: 4 teams, 2 seasons x 6 weeks, 3 players a team. With scramble_from, every fact of every game
    kicking off at or after it is replaced by different random numbers (the game list itself is unchanged)."""
    import polars as pl
    rng = np.random.default_rng(seed)
    teams, tg, pw, of = ["A", "B", "C", "D"], [], [], []
    for season in (2022, 2023):
        for week in range(1, 7):
            pairs = [("A", "B"), ("C", "D")] if week % 2 else [("A", "C"), ("B", "D")]
            for gi, (h, a) in enumerate(pairs):
                gid, kick = f"{season}_{week:02d}_{a}_{h}", f"{season}-09-{week:02d} {13 + 3 * gi}:00"
                r = np.random.default_rng([seed + 1000, season, week, gi]) if scramble_from and kick >= scramble_from else rng
                for t, o in ((h, a), (a, h)):
                    v = {c: int(r.integers(1, 60)) for c in ("team_att", "team_cmp", "team_pass_yds", "team_sacks", "team_carries",
                                                             "team_rush_yds", "team_targets", "team_scrambles", "team_dropbacks", "team_plays")}
                    tg.append({"game_id": gid, "team": t, "opponent": o, "season": season, "week": week, "kickoff": kick, **v})
                    for k in range(3):
                        pid = f"{t}{k}"
                        if (season, week, pid) == (2022, 3, "A1"):
                            continue                                            # a missed game: windows must skip it, not count it
                        s = {c: int(r.integers(0, 12)) for c in ("attempts", "completions", "passing_yards", "sacks_suffered", "carries",
                                                                 "rushing_yards", "targets", "receptions", "receiving_yards")}
                        pw.append({"player_id": pid, "season": season, "week": week, "game_id": gid, "team": t, "opponent": o,
                                   "position": "WR", "offense_snaps": int(r.integers(1, 70)), **s})
                        of.append({"game_id": gid, "team": t, "player_id": pid, "db_on_field": int(r.integers(0, 40)), "team_db_charted": int(r.integers(30, 45))})
    return pl.DataFrame(pw), pl.DataFrame(tg), pl.DataFrame(of)


def test_features_match_hand_sums():
    from nflbet.engine.features import build as B
    pw, tg, of = _feature_inputs()
    f = B.build(pw, tg, of)
    assert f.height == pw.height and not ({"targets", "team_att", "offense_snaps"} & set(f.columns))   # no outcome of the game itself
    def row(pid, season, week):
        return f.filter((pl.col("player_id") == pid) & (pl.col("season") == season) & (pl.col("week") == week)).row(0, named=True)
    import polars as pl
    hist = pw.filter(pl.col("player_id") == "A1").sort("season", "week")
    t = hist["targets"].to_list()                                   # A1 played 2022 wk 1,2,4,5,6 and 2023 wk 1-6
    first = row("A1", 2022, 1)
    assert (first["p_n_w3"], first["p_targets_w8"], first["p_n_std"], first["p_n_prev"], first["p_last_kickoff"]) == (0, 0, 0, 0, None)
    r = row("A1", 2022, 5)                                          # earlier games: wk 1, 2, 4
    assert (r["p_n_w3"], r["p_n_std"], r["p_targets_w3"], r["p_targets_std"]) == (3, 3, sum(t[:3]), sum(t[:3]))
    assert r["p_last_kickoff"] == "2022-09-04 13:00" or r["p_last_kickoff"].startswith("2022-09-04")
    r = row("A1", 2023, 2)                                          # earlier: five 2022 games + 2023 wk 1
    assert (r["p_n_w3"], r["p_n_w8"], r["p_n_std"], r["p_n_prev"]) == (3, 6, 1, 5)
    assert (r["p_targets_w3"], r["p_targets_w8"], r["p_targets_std"], r["p_targets_prev"]) == (sum(t[3:6]), sum(t[:6]), t[5], sum(t[:5]))
    a = tg.filter(pl.col("team") == "A").sort("kickoff")["team_att"].to_list()
    assert (r["o_n_w5"], r["o_team_att_w5"], r["o_team_att_prev"]) == (5, sum(a[2:7]), sum(a[:6]))
    opp = r["opponent"]                                             # what offenses did against A1's opponent before this game
    allowed = tg.filter(pl.col("opponent") == opp).sort("kickoff")["team_carries"].to_list()
    assert (r["d_n_w3"], r["d_team_carries_w3"]) == (3, sum(allowed[4:7]))


def test_features_ignore_everything_at_or_after_the_cutoff():
    """The leakage gate: scramble every fact from a cut-off kickoff on; rows up to and including it must not change."""
    from nflbet.engine.features import build as B
    import polars as pl
    cut = "2023-09-03 13:00"
    pw0, tg0, _ = _feature_inputs()
    act = pw0.select("player_id", "game_id", "team", "position").vstack(                 # everyone who played, plus an idle active player
        tg0.select((pl.lit("IDLE_") + pl.col("team")).alias("player_id"), "game_id", "team", pl.lit("WR").alias("position")))
    base, scr = B.build(*_feature_inputs(), act), B.build(*_feature_inputs(scramble_from=cut), act)
    keep = pl.col("kickoff") <= cut
    assert base.filter(keep).height > 0 and base.filter(keep).equals(scr.filter(keep))
    assert B.snapshot_hash(base.filter(keep)) == B.snapshot_hash(scr.filter(keep))
    assert not base.filter(~keep).equals(scr.filter(~keep))         # and the scramble really did change later rows
    assert B.snapshot_hash(base) != B.snapshot_hash(scr)


def test_leakage_gate_catches_a_planted_leak():
    """Same check on a deliberately wrong feature (a window that includes the game itself): it must fail."""
    import polars as pl
    cut = "2023-09-03 13:00"
    leaky = lambda pw: pw.sort("player_id", "season", "week").with_columns(                       # noqa: E731
        pl.col("targets").rolling_sum(3, min_samples=1).over("player_id").alias("bad")).join(
        _feature_inputs()[1].select("game_id", "team", "kickoff"), on=["game_id", "team"]).select("player_id", "game_id", "kickoff", "bad")
    a, b = leaky(_feature_inputs()[0]), leaky(_feature_inputs(scramble_from=cut)[0])
    assert not a.filter(pl.col("kickoff") <= cut).equals(b.filter(pl.col("kickoff") <= cut))


def test_team_facts_follow_the_definitions():
    import polars as pl
    from nflbet.engine.features import facts as F
    sched = pl.DataFrame({"game_id": ["g"], "season": [2023], "game_type": ["REG"], "week": [1], "gameday": ["2023-09-10"],
                          "gametime": ["13:00"], "home_team": ["OAK"], "away_team": ["KC"]})
    g = F.games(sched)
    assert g.row(0, named=True) == {"game_id": "g", "season": 2023, "week": 1, "kickoff": "2023-09-10 13:00", "home": "LV", "away": "KC"}
    z = {"completions": 0, "passing_yards": 0, "rushing_yards": 0}
    stats = pl.DataFrame([
        {"game_id": "g", "season_type": "REG", "team": "KC", "opponent_team": "OAK", "attempts": 30, "sacks_suffered": 3, "carries": 6, "targets": 0, **z},
        {"game_id": "g", "season_type": "REG", "team": "KC", "opponent_team": "OAK", "attempts": 0, "sacks_suffered": 0, "carries": 20, "targets": 9, **z},
        {"game_id": "g", "season_type": "REG", "team": "KC", "opponent_team": "OAK", "attempts": 1, "sacks_suffered": 0, "carries": 0, "targets": 19, **z}])
    def play(i, typ, scr=0, two=0, db=1):
        return {"game_id": "g", "play_id": float(i), "posteam": "KC", "play_type": typ, "qb_scramble": float(scr), "two_point_attempt": float(two), "qb_dropback": float(db)}
    pbp = pl.DataFrame([play(1, "run", scr=1), play(2, "run", scr=1), play(3, "run", scr=1, two=1), play(4, "no_play", scr=1), play(5, "pass"), play(6, "run", db=0)])
    t = F.team_game(stats, pbp, g).row(0, named=True)
    assert (t["team"], t["opponent"], t["team_att"], t["team_sacks"], t["team_carries"], t["team_targets"]) == ("KC", "LV", 31, 3, 26, 28)
    assert t["team_scrambles"] == 2                                  # the two-point scramble and the penalty no-play do not count
    assert t["team_dropbacks"] == 31 + 3 + 2 and t["team_plays"] == 36 + 26 - 2
    part = pl.DataFrame({"nflverse_game_id": ["g"] * 4, "play_id": [1.0, 5.0, 6.0, 3.0],
                         "offense_players": ["QB1;TE1;WR1", "QB1;WR1;WR1", "QB1;TE1", "QB1;TE1"]})
    o = {r["player_id"]: (r["db_on_field"], r["team_db_charted"]) for r in F.on_field(part, pbp).iter_rows(named=True)}
    assert o == {"QB1": (2, 2), "TE1": (1, 2), "WR1": (2, 2)}        # run play 6 and two-point play 3 are not dropbacks; a repeated ID counts once


# ------------------------------------------------------------------------------------------------ scoring, baselines
def test_crps_hand_cases_and_against_simulation():
    from nflbet.engine import scoring as S
    c = np.zeros((1, 11))
    c[0, 3:] = 1                                                     # all mass on 3, grid 0..10
    got = [float(S.crps(c, np.array([y]))[0]) for y in (3, 5, 0, -2, 14)]
    assert got == [0.0, 2.0, 3.0, 5.0, 11.0]                         # |y - 3|, including below 0 and beyond the grid
    rng = np.random.default_rng(0)
    m, r = 6.0, 3.0
    cdf = S.nb_cdf(np.array([m]), r, 400)
    x, x2 = rng.negative_binomial(r, r / (r + m), 200_000), rng.negative_binomial(r, r / (r + m), 200_000)
    for y in (0, 4, 15):                                             # CRPS = E|X - y| - E|X - X'| / 2
        assert float(S.crps(cdf, np.array([y]))[0]) == pytest.approx(np.abs(x - y).mean() - 0.5 * np.abs(x - x2).mean(), abs=0.03)


def test_nb_size_fit_coverage_and_bootstrap_on_planted_data():
    from nflbet.engine import scoring as S
    rng = np.random.default_rng(1)
    mean = rng.uniform(2, 12, 6000)
    y = rng.negative_binomial(4.0, 4.0 / (4.0 + mean))
    assert S.fit_nb_size(mean, y) == pytest.approx(4.0, rel=0.2)     # recovers the planted size
    right, narrow = S.nb_cdf(mean, 4.0, 200), S.nb_cdf(mean, 200.0, 200)
    assert S.coverage(right, y, 0.8) == pytest.approx(0.8, abs=0.06)  # discrete intervals over-cover a little
    assert S.coverage(narrow, y, 0.8) < 0.7                           # a too-narrow forecast is caught
    assert S.crps(right, y).mean() < S.crps(narrow, y).mean() < S.crps(S.nb_cdf(mean * 1.5, 4.0, 200), y).mean()
    week = rng.integers(0, 30, 6000)
    d, lo, hi = S.paired_bootstrap(S.crps(right, y) - S.crps(narrow, y), week, n=2000)
    assert lo < d < hi < 0                                           # the planted improvement is found
    d, lo, hi = S.paired_bootstrap(rng.normal(0, 1, 6000), week, n=2000)
    assert lo < 0 < hi                                               # and noise is not


def test_baseline_means_and_fallbacks_by_hand():
    import polars as pl
    from nflbet.engine import baselines as BL
    row = {"position": "WR", "p_n_w3": 3, "p_targets_w3": 24, "p_n_w8": 8, "p_n_std": 4, "p_n_prev": 0,
           "p_receptions_w8": 40, "p_receptions_std": 16, "p_receptions_prev": 0, "p_targets_w8": 64, "p_team_targets_w8": 256,
           "o_team_targets_w8": 280, "o_n_w8": 8}
    rookie = {**row, "p_n_w3": 0, "p_targets_w3": 0, "p_n_w8": 0, "p_n_std": 0, "p_receptions_w8": 0, "p_receptions_std": 0,
              "p_targets_w8": 0, "p_team_targets_w8": 0}
    df = pl.DataFrame([row, rookie])
    assert BL.eligible(df, "rec").to_list() == [True, False]         # 8 targets a game >= 3; no history is not eligible
    const = {"efficiency": {"WR": 0.6}, "cell_mean": {"WR|4": 5.5, "WR|0": 1.0}, "overall_mean": 3.0}
    m = BL.means(df, "rec", const)
    assert m["B3"][0] == 5.0 and m["B2"][0] == 4.0                   # 40 / 8 and 16 / 4
    assert m["B1"][0] == 5.0                                         # no last season: falls back to B3
    assert m["B4"][0] == pytest.approx((64 / 256) * (280 / 8) * 0.6)  # share x team targets per game x catch rate = 5.25
    assert m["B5"][0] == 5.5                                         # 8 a game is 2.67x the minimum: band 4
    assert [m[b][1] for b in ("B1", "B2", "B3", "B4", "B5")] == [1.0] * 5   # nothing on record: every baseline ends at B5


# ------------------------------------------------------------------------------------------------ Engine A
def test_dirichlet_multinomial_recovers_planted_concentration_and_keeps_totals():
    from nflbet.engine.replication import opportunity as O
    rng = np.random.default_rng(3)
    mu = np.array([0.4, 0.3, 0.2, 0.1])
    total = rng.integers(25, 45, 3000)
    x = O.allocate(rng, total, mu, 40.0)
    assert (x.sum(axis=1) == total).all() and (x >= 0).all()         # every run deals out exactly the team total
    assert x.mean(axis=0) / total.mean() == pytest.approx(mu, abs=0.01)
    ll = {k: O.dm_loglik(x.astype(float), np.tile(mu, (3000, 1)), k) for k in O.KAPPA_GRID}
    assert max(ll, key=ll.get) == pytest.approx(40.0, rel=0.25)      # the planted concentration is the likeliest
    wrong = np.tile(np.array([0.25, 0.25, 0.25, 0.25]), (3000, 1))
    assert max(O.dm_loglik(x.astype(float), wrong, k) for k in O.KAPPA_GRID) < max(ll.values())   # wrong shares fit worse
    s = O.expected_shares(np.array([10.0, 0.0, 0.0]), np.array([40.0, 0.0, 0.0]), np.array([0.2, 0.2, 0.0]), 10.0, 0.05)
    raw = np.array([(10 + 2) / 50, (0 + 2) / 10, 0.0, 0.05])        # history, no history (prior only), padded slot, other
    assert s == pytest.approx(raw / raw.sum()) and s[2] == 0


def test_environment_recovers_planted_coefficients():
    import polars as pl
    from nflbet.engine.replication import environment as V
    rng = np.random.default_rng(4)
    n = 4000
    cols = {}
    for pre in ("o_", "d_"):
        for w in ("w8", "std", "prev"):
            cols[f"{pre}n_{w}"] = np.full(n, 8)
            for c in ("team_att", "team_carries"):
                cols[f"{pre}{c}_{w}"] = rng.uniform(20, 45, n) * 8
    df = pl.DataFrame(cols)
    att = 5 + 0.6 * df["o_team_att_w8"].to_numpy() / 8 + 0.3 * df["d_team_att_w8"].to_numpy() / 8 + rng.normal(0, 3, n)
    car = 40 - 0.4 * df["o_team_att_w8"].to_numpy() / 8 + rng.normal(0, 3, n)
    P = V.fit(df, np.column_stack([att, car]), np.rint(att * 0.95))
    coef = np.array(P["coef"])                                       # columns: 1, att(o8, std, prev, d8), carries(o8, std, prev, d8)
    assert coef[1, 0] == pytest.approx(0.6, abs=0.03) and coef[4, 0] == pytest.approx(0.3, abs=0.03) and coef[1, 1] == pytest.approx(-0.4, abs=0.03)
    assert abs(coef[2, 0]) < 0.03 and abs(coef[5, 0]) < 0.03         # unrelated inputs get nothing
    a, c, t = V.draw(P, V.mean(P, df.head(1))[0], 5000, rng)
    assert a.min() >= V.MIN["A"] and (t <= a).all() and t.mean() / a.mean() == pytest.approx(0.95, abs=0.02)


def _engine_a_inputs(seed=5, games=220):
    """Synthetic league with planted structure: player 0 of each team truly gets 40% of targets."""
    import polars as pl
    rng = np.random.default_rng(seed)
    rows, teams = [], []
    for g in range(games):
        A, C = int(rng.integers(28, 42)), int(rng.integers(20, 34))
        T = int(rng.binomial(A, 0.94))
        tg = rng.multinomial(T, rng.dirichlet(30 * np.array([0.4, 0.25, 0.2, 0.1, 0.05])))
        ca = rng.multinomial(C, rng.dirichlet(30 * np.array([0.02, 0.02, 0.03, 0.8, 0.13])))
        teams.append({"game_id": f"g{g}", "team": "X", "team_att": A, "team_carries": C, "team_targets": T, "team_sacks": 2, "team_scrambles": 1})
        for k, pos in enumerate(["WR", "WR", "TE", "RB", "QB"]):
            rec = int(rng.binomial(tg[k], 0.65))
            r = {"game_id": f"g{g}", "team": "X", "player_id": f"p{k}", "position": pos, "p_last_kickoff": "k", "o_last_kickoff": "k", "targets": int(tg[k]), "receptions": rec,
                 "receiving_yards": int(rec * 11), "carries": int(ca[k]), "rushing_yards": int(ca[k] * 4),
                 "attempts": A if pos == "QB" else 0, "completions": 0, "passing_yards": 0}
            share = [0.4, 0.25, 0.2, 0.1, 0.05][k]
            for w, n in (("w3", 3), ("w5", 5), ("w8", 8), ("std", 6), ("prev", 16)):
                r.update({f"p_n_{w}": n, f"p_targets_{w}": round(share * 33 * n), f"p_team_targets_{w}": 35 * n,
                          f"p_offense_snaps_{w}": 50 * n,
                          f"p_carries_{w}": round([0.02, 0.02, 0.03, 0.8, 0.13][k] * 27 * n), f"p_team_carries_{w}": 27 * n,
                          f"p_attempts_{w}": 35 * n if pos == "QB" else 0, f"p_team_att_{w}": 35 * n,
                          f"p_receptions_{w}": round(share * 33 * n * 0.65), f"p_receiving_yards_{w}": round(share * 33 * n * 0.65 * 11),
                          f"p_rushing_yards_{w}": round([0.02, 0.02, 0.03, 0.8, 0.13][k] * 27 * n * 4),
                          f"o_n_{w}": n, f"o_team_att_{w}": 35 * n, f"o_team_carries_{w}": 27 * n,
                          f"d_n_{w}": n, f"d_team_att_{w}": 35 * n, f"d_team_carries_{w}": 27 * n})
            rows.append(r)
    pools = {"rec": {p: rng.gamma(2.0, 5.5, 4000).round() for p in ("QB", "RB", "WR", "TE", "OTH")},
             "rush": {p: (rng.gamma(1.5, 3.0, 4000) - 0.5).round() for p in ("QB", "RB", "WR", "TE", "OTH")}}
    return pl.DataFrame(rows), pl.DataFrame(teams), pools


def test_engine_a_fits_simulates_and_every_run_reconciles():
    import polars as pl
    from nflbet.engine.replication import model as M
    df, teams, pools = _engine_a_inputs()
    P = M.fit(df, teams, pools)
    assert P["opp"]["targets"]["prior"]["WR"] == pytest.approx(0.325, abs=0.02)      # mean of the two receivers' true shares
    assert P["opp"]["targets"]["kappa"] == pytest.approx(30, rel=0.6)                # planted concentration, roughly
    assert P["eff"]["catch_rate"]["WR"] == pytest.approx(0.65, abs=0.02)
    tab = M.tables(pools)
    rows = df.filter(pl.col("game_id") == "g0").sort("player_id")
    box, s = M.simulate(P, tab, rows, 3000, np.random.default_rng(0))
    assert accounting.violations(box) == {}                                          # all 3,000 box scores reconcile
    assert s["targets"].shape == (5, 3000)
    assert s["targets"][0].mean() / box["targets"].sum(axis=1).mean() == pytest.approx(0.4, abs=0.03)   # the planted 40% share
    assert (s["attempts"][4] == box["pass_att"]).all()               # the expected starter always threw every pass in this league
    assert M.starter_flag(rows).tolist() == [False, False, False, False, True] and set(P["qb"]["starter_share"]) == {1.0}
    P2 = {**P, "qb": {"starter_share": [0.5], "new_share": [1.0]}}  # a league where starters throw half: the rest goes to "other"
    box3, s3 = M.simulate(P2, tab, rows, 500, np.random.default_rng(1))
    assert np.abs(s3["attempts"][4] - box3["pass_att"] / 2).max() <= 0.5 and accounting.violations(box3) == {}
    assert (s["receptions"] <= s["targets"]).all() and (s["completions"][4] <= s["attempts"][4] + 1).all()
    assert P["play"]["all"] == 1.0 and (M.play_prob(P, rows) == 1.0).all()           # everyone active plays in this league
    Pq = {**P, "play": {"cell": {}, "pos": {"WR": 0.5}, "all": 1.0}}                 # now receivers play half the time
    boxq, sq = M.simulate(Pq, tab, rows, 4000, np.random.default_rng(2))
    assert accounting.violations(boxq) == {}
    assert (boxq["targets"][:, 0] == 0).mean() == pytest.approx(0.5, abs=0.05)       # in half the runs he gets nothing...
    assert (sq["targets"][0] == 0).mean() < 0.05                                     # ...but his forecast is from the runs he plays in
    assert sq["targets"][0].mean() > s["targets"][0].mean()                          # and is larger: a teammate is often missing
    box2, s2 = M.simulate(P, tab, rows, 3000, np.random.default_rng(0))
    assert all((s[k] == s2[k]).all() for k in s)                                     # same seed, same runs


def test_crps_from_runs_matches_crps_from_the_distribution():
    from nflbet.engine import scoring as S
    rng = np.random.default_rng(6)
    mean = rng.uniform(3, 10, 40)
    y = rng.negative_binomial(5.0, 5.0 / (5.0 + mean))
    runs = rng.negative_binomial(5.0, (5.0 / (5.0 + mean))[:, None], size=(40, 40_000))
    assert S.crps_samples(runs, y) == pytest.approx(S.crps(S.nb_cdf(mean, 5.0, 300), y), rel=0.03, abs=0.03)   # Monte Carlo error only
    assert S.coverage_samples(runs, y, 0.8) == pytest.approx(S.coverage(S.nb_cdf(mean, 5.0, 300), y, 0.8), abs=0.06)


def test_active_list_rows_get_features_but_add_nothing_to_history():
    import polars as pl
    from nflbet.engine.features import build as B, facts as F
    pw, tg, of = _feature_inputs()
    # A1 missed 2022 week 3 but was on the active list; a new player Z9 is active for team A all of 2023 and never plays.
    g3 = tg.filter((pl.col("team") == "A") & (pl.col("season") == 2022) & (pl.col("week") == 3))["game_id"][0]
    a23 = tg.filter((pl.col("team") == "A") & (pl.col("season") == 2023)).sort("week")["game_id"].to_list()
    act = pl.DataFrame({"player_id": ["A1"] + ["Z9"] * len(a23) + ["A0"], "game_id": [g3] + a23 + [a23[0]], "team": ["A"] * (len(a23) + 2),
                        "position": ["WR"] * (len(a23) + 2)})                      # A0 played a23[0]: his active row must not duplicate him
    base, f = B.build(pw, tg, of), B.build(pw, tg, of, act)
    assert f.height == base.height + 1 + len(a23) and f.filter(pl.col("played")).height == base.height
    k = ["player_id", "game_id"]
    assert f.filter(pl.col("played")).drop("played").sort(k).equals(base.drop("played").sort(k))   # nobody's history changed
    t = pw.filter(pl.col("player_id") == "A1").sort("season", "week")["targets"].to_list()
    r = f.filter((pl.col("player_id") == "A1") & (pl.col("game_id") == g3)).row(0, named=True)
    assert (r["played"], r["p_n_w3"], r["p_targets_w3"], r["p_n_std"]) == (False, 2, t[0] + t[1], 2)   # features as of week 3
    z = f.filter(pl.col("player_id") == "Z9").sort("kickoff")
    assert z["played"].sum() == 0 and z["p_n_w8"].sum() == 0 and z["p_targets_prev"].sum() == 0 and z["p_last_kickoff"].null_count() == len(a23)
    assert z["o_n_w3"].to_list()[-1] == 3                                          # he still carries his team's features


def test_active_list_comes_from_roster_status_only():
    import polars as pl
    from nflbet.engine.features import facts as F
    ros = pl.DataFrame({"gsis_id": ["a", "b", "c", "d", None, "a"], "season": [2023] * 6, "week": [1, 1, 1, 1, 1, 2], "team": ["OAK"] * 6,
                        "position": ["WR", "WR", "K", "QB", "RB", "WR"], "status": ["ACT", "INA", "ACT", "ACT", "ACT", "ACT"], "game_type": ["REG"] * 6})
    tg = pl.DataFrame({"game_id": ["g1"], "season": [2023], "week": [1], "team": ["LV"]})
    a = F.active(ros, tg)
    assert sorted(a["player_id"].to_list()) == ["a", "d"]            # inactive, kicker, no ID and the bye week are all left out
    assert a["game_id"].to_list() == ["g1", "g1"] and a["team"].to_list() == ["LV", "LV"]


def test_depth_rank_uses_only_charts_dated_before_game_day():
    import polars as pl
    from nflbet.engine.features import facts as F
    tg = pl.DataFrame({"game_id": ["g1", "g2", "h1"], "season": [2025, 2025, 2024], "week": [1, 2, 3], "team": ["LV", "LV", "LV"],
                       "kickoff": ["2025-09-07 13:00", "2025-09-14 13:00", "2024-09-22 13:00"]})
    def snap(dt, a, b):
        return [{"dt": dt, "team": "OAK", "gsis_id": a, "pos_abb": "QB", "pos_rank": 1}, {"dt": dt, "team": "OAK", "gsis_id": b, "pos_abb": "QB", "pos_rank": 2},
                {"dt": dt, "team": "OAK", "gsis_id": "wr", "pos_abb": "WR", "pos_rank": 1}]
    dated = pl.DataFrame(snap("2025-09-03T10:00:00Z", "old", "new") + snap("2025-09-07T09:00:00Z", "new", "old")      # game-day chart: too late for g1
                         + snap("2025-09-20T09:00:00Z", "later", "new"))                                              # after both games
    weekly = pl.DataFrame({"season": [2024, 2024, 2024], "week": [3, 3, 4], "club_code": ["OAK"] * 3, "game_type": ["REG"] * 3,
                           "position": ["QB"] * 3, "formation": ["Offense"] * 3, "gsis_id": ["w1", "w2", "w9"], "depth_team": ["1", "2", "1"]})
    d = {(r["game_id"], r["player_id"]): r["depth_rank"] for r in F.depth_rank(weekly, dated, tg).iter_rows(named=True)}
    assert d == {("g1", "old"): 1, ("g1", "new"): 2,              # the chart from four days before, not the game-day one
                 ("g2", "new"): 1, ("g2", "old"): 2,              # by week 2 the game-day chart of week 1 is known
                 ("h1", "w1"): 1, ("h1", "w2"): 2}                # weekly format: that week's chart; week 4 has no game here


def test_pick_starter_order():
    import polars as pl
    from nflbet.engine.replication import model as M
    def qb(pid, att3, team3, last, depth, w8):
        return {"player_id": pid, "position": "QB", "p_attempts_w3": att3, "p_team_att_w3": team3, "p_last_kickoff": last,
                "o_last_kickoff": "k", "depth_rank": depth, "p_attempts_w8": w8}
    wr = {**qb("wr", 0, 100, "k", 9, 0), "position": "WR"}
    recent = qb("recent", 90, 100, "k", 2, 200)                   # started the last three games; chart still lists him second
    listed = qb("listed", 0, 100, "old", 1, 250)                  # chart's number one, back from injury, did not play last game
    third = qb("third", 0, 100, "old", 9, 10)
    assert M.pick_starter(pl.DataFrame([wr, listed, recent, third])) == (2, "starter_share")    # the recent starter outranks the chart
    assert M.pick_starter(pl.DataFrame([wr, third, listed])) == (2, "starter_share")            # no recent starter: the chart decides
    assert M.pick_starter(pl.DataFrame([wr, third, qb("vol", 0, 100, "old", 9, 99)])) == (2, "new_share")   # neither: volume, new-starter pool
    assert M.pick_starter(pl.DataFrame([wr])) == (None, "new_share")
