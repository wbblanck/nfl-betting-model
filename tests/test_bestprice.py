"""Known-answer checks for the best-price record (src/nflbet/bestprice.py) and the venue pricing (src/nflbet/venues.py)."""
import json

import polars as pl

from nflbet import bestprice as Bp
from nflbet import venues as V

PICK = {"run_utc": "2026-10-18T15:50:00Z", "season": 2026, "week": 6, "an_game_id": "300001", "start_time": "2026-10-18T17:00:00.000Z",
        "home": "NO", "away": "MIN", "player": "Aaron Jones Sr.", "player_id": "00-0033293", "market": "rec", "line": 3.5,
        "side": "under", "odds": -150.0, "om_kalshi_odds": -140.0, "om_prophetx_odds": None, "om_bettoredge_odds": None}


def _an(rows):
    cols = ["an_game_id", "player", "market", "book_id", "book", "line", "over_odds", "under_odds"]
    return pl.DataFrame([dict(zip(cols, r)) for r in rows], schema={c: pl.Utf8 for c in cols})


AN = _an([("300001", "Aaron Jones", "rec", "68", "DK NJ", "3.5", "120", "-150"),
          ("300001", "Aaron Jones", "rec", "69", "FanDuel NJ", "3.5", "105", "-130"),
          ("300001", "Aaron Jones", "rec", "75", "BetMGM NJ", "2.5", "-200", "160"),       # other line: not comparable
          ("300001", "Aaron Jones", "rec", "15", "Consensus", "3.5", "110", "-140"),       # not a book
          ("300001", "Aaron Jones", "rec", "71", "BetRivers NJ", "3.5", "", "-125")])      # one-sided: dropped

NV_MARKET = {"marketId": "m1", "eventId": "e1", "marketType": "RECEPTIONS", "description": "Aaron Jones Sr. 3.5 RECEPTIONS",
             "strike": "3.5", "status": "OPEN", "fee": {"coefficient": "0.03", "charged": "WHEN_LIVE"},
             "outcomes": [{"outcomeId": "o", "name": "Over 3.5"}, {"outcomeId": "u", "name": "Under 3.5"}]}
NV_EVENTS = {"e1": {"eventId": "e1", "description": "Minnesota Vikings @ New Orleans Saints", "status": "OPEN_PREGAME"}}
NV_BOOK = {"orders": {"o": [{"price": "0.47", "qty": 20000}, {"price": "0.47", "qty": 5000}], "u": [{"price": "0.40", "qty": 900}]}}


def _rows(pmq=None, nv_events=NV_EVENTS, books=None):
    nv_idx = V.nv_index([NV_MARKET], nv_events)
    return Bp.best_rows(pl.DataFrame([PICK]), Bp.an_quotes(AN), None, pmq or {}, nv_idx, {"m1": NV_BOOK} if books is None else books,
                        PICK["run_utc"]).row(0, named=True)


def test_novig_taker_side_and_size():
    # every Novig order buys: Under costs 1 - best Over price (0.47); 25,000 contracts at 1 cent = $250 of payout
    assert V.nv_taker(NV_BOOK, NV_MARKET) == {"under": (0.53, 250.0), "over": (0.6, 9.0)}


def test_best_is_cheapest_all_in_at_the_same_line():
    pmq = {("MIN|NO", "aaron jones", "rec", 3.5): {"over": 0.46, "under": 0.55, "fee": 0.0695}}
    r = _rows(pmq)
    v = json.loads(r["venues"])
    # DK -150 = .6; FanDuel -130 = .5652; Polymarket .55 + .0695 * .55 * .45 = .5672; Novig .53, no pregame fee
    assert set(v) == {"DraftKings", "FanDuel", "Polymarket US", "Novig"}            # BetMGM other line, Consensus, one-sided out
    assert abs(v["Polymarket US"][0] - 0.567201) < 1e-5 and abs(v["FanDuel"][0] - 0.565217) < 1e-5
    assert (r["best_venue"], r["best_cost"], r["best_size"], r["n_venues"]) == ("Novig", 0.53, 250.0, 4)
    assert r["dk_cost"] == 0.6 and r["edge_cents"] == 7.0 and r["best_odds"] == -113
    assert json.loads(r["prefee"]) == {"Kalshi": -140}                               # listed, never eligible for best


def test_novig_fee_applies_in_game():
    live = {"e1": {**NV_EVENTS["e1"], "status": "OPEN_INGAME"}}
    r = _rows(nv_events=live)
    assert abs(json.loads(r["venues"])["Novig"][0] - (0.53 + 0.03 * 0.53 * 0.47)) < 1e-5


def test_no_comparable_venue_still_records_the_pick():
    r = Bp.best_rows(pl.DataFrame([{**PICK, "line": 9.5}]), Bp.an_quotes(AN), None, {}, {}, {}, PICK["run_utc"]).row(0, named=True)
    assert r["best_venue"] is None and r["n_venues"] == 0 and r["dk_odds"] == -150.0


def test_polymarket_quotes_and_team_mapping():
    mk = [{"event": "DEN Broncos vs. LA Chargers", "question": "Will Ladd McConkey record 5+ receptions?", "feeCoefficient": 0.0695,
           "slug": "astatc-nfl-lac-den-x-rec-ladmcc-gte5",
           "marketSides": [{"description": "Yes", "quote": {"value": "0.44"}}, {"description": "No", "quote": {"value": "0.60"}}]},
          {"event": "DEN Broncos vs. LA Chargers", "question": "Will Ladd McConkey record 50+ receiving yards?",
           "marketSides": [{"description": "Yes", "quote": {"value": "0.5"}}, {"description": "No"}]}]      # unquoted side: dropped
    assert V.pm_quotes(mk) == {("DEN|LAC", "ladd mcconkey", "rec", 4.5):
                               {"over": 0.44, "under": 0.60, "fee": 0.0695, "slug": "astatc-nfl-lac-den-x-rec-ladmcc-gte5"}}


def test_dashboard_line_joins_on_the_pick_and_run():
    from nflbet import dashboard as D
    pmq = {("MIN|NO", "aaron jones", "rec", 3.5): {"over": 0.46, "under": 0.55, "fee": 0.0695}}
    best = Bp.best_rows(pl.DataFrame([PICK]), Bp.an_quotes(AN), None, pmq, V.nv_index([NV_MARKET], NV_EVENTS), {"m1": NV_BOOK}, PICK["run_utc"])
    best = best.select([pl.col(c).cast(pl.Utf8) for c in best.columns])               # as read back from the CSV
    r = D.with_best([{**PICK, "line": 3.5}], best)[0]
    html = D.best_price(r)
    assert "Best price at this line: Novig -113, $250 available (+7.0¢ per $1 vs DraftKings; 4 venues, after fees)" in html
    other_run = D.with_best([{**PICK, "run_utc": "2026-10-18T12:00:00Z"}], best)[0]
    assert D.best_price(other_run) == ""                                               # a different run's price is never shown


def test_thin_novig_price_is_listed_but_not_best():
    thin = {"orders": {"o": [{"price": "0.60", "qty": 300}], "u": [{"price": "0.40", "qty": 900}]}}     # Under 0.40, $3 behind it
    r = _rows(books={"m1": thin})
    v = json.loads(r["venues"])
    assert v["Novig"] == [0.4, 3.0] and r["best_venue"] == "FanDuel" and r["check"] == ""


def test_large_edge_is_flagged():
    big = {"orders": {"o": [{"price": "0.70", "qty": 5000}], "u": [{"price": "0.40", "qty": 900}]}}    # Under 0.30, $50: 30c better
    r = _rows(books={"m1": big})
    assert r["best_venue"] == "Novig" and r["edge_cents"] == 30.0 and r["check"].startswith("edge over 10 cents")


def test_polymarket_size_from_unsorted_book(monkeypatch):
    # Yes (over) takes the lowest offer, No (under) sells into the highest bid; equal-price levels add up
    book = {"marketData": {"bids": [{"px": {"value": "0.43"}, "qty": "10"}, {"px": {"value": "0.44"}, "qty": "25"}, {"px": {"value": "0.44"}, "qty": "5"}],
                           "offers": [{"px": {"value": "0.50"}, "qty": "7"}, {"px": {"value": "0.48"}, "qty": "120"}]}}
    monkeypatch.setattr(V, "pm_get", lambda path: book)
    assert V.pm_sizes("s") == {"over": 120.0, "under": 30.0}
    monkeypatch.setattr(V, "pm_get", lambda path: {"marketData": {"bids": [], "offers": []}})
    assert V.pm_sizes("s") == {}


def test_thin_polymarket_price_is_listed_but_not_best():
    pmq = {("MIN|NO", "aaron jones", "rec", 3.5): {"over": 0.46, "under": 0.45, "fee": 0.0695, "slug": "pm1"}}   # .45 + fee = .4637
    thin = Bp.best_rows(pl.DataFrame([PICK]), Bp.an_quotes(AN), None, pmq, V.nv_index([NV_MARKET], NV_EVENTS), {"m1": NV_BOOK},
                        PICK["run_utc"], {"pm1": {"under": 4.0}}).row(0, named=True)
    assert json.loads(thin["venues"])["Polymarket US"][1] == 4.0 and thin["best_venue"] == "Novig"
    deep = Bp.best_rows(pl.DataFrame([PICK]), Bp.an_quotes(AN), None, pmq, V.nv_index([NV_MARKET], NV_EVENTS), {"m1": NV_BOOK},
                        PICK["run_utc"], {"pm1": {"under": 500.0}}).row(0, named=True)
    assert deep["best_venue"] == "Polymarket US" and deep["best_size"] == 500.0


KS_MKT = {"ticker": "KXNFLREC-26OCT18MINNO-NOAJONES33-4", "_series": "KXNFLREC", "_fee_type": "quadratic", "_mult": 1,
          "yes_sub_title": "Aaron Jones Sr.: 4+", "yes_ask_dollars": "0.4600", "yes_ask_size_fp": "300.00",
          "yes_bid_dollars": "0.4900", "yes_bid_size_fp": "75.50"}


def test_kalshi_game_from_event_ticker():
    assert V.ks_game("KXNFLREC-26OCT18HOUJAC-HOUX1-5") == "HOU|JAX"            # JAC -> JAX
    assert V.ks_game("KXNFLREC-26OCT18ARILAR-X") == "ARI|LA"                   # LAR -> LA
    assert V.ks_game("KXNFLREC-26OCT18LACKC-X") == "KC|LAC" and V.ks_game("KXNFLREC-26OCT18NONYG-X") == "NO|NYG"
    assert V.ks_game("KXNFLREC-26OCT18XXXYYY-X") is None and V.ks_game("KXNFLREC") is None


def test_kalshi_quotes_sides_and_sizes():
    # over = YES at the ask (300 contracts); under = NO at 1 - YES bid = .51, with the YES bid's 75.5 contracts behind it
    q = V.ks_quotes([KS_MKT, {**KS_MKT, "_series": "KXNFLTD"}, {**KS_MKT, "yes_sub_title": "Aaron Jones Sr.: Yes"}])
    assert q == {("MIN|NO", "aaron jones", "rec", 3.5): {"over": (0.46, 300.0), "under": (0.51, 75.5), "mult": 1.0,
                                                          "ticker": KS_MKT["ticker"]}}
    one = V.ks_quotes([{**KS_MKT, "yes_bid_dollars": "0.0000"}])                  # no bid: no under
    assert one[("MIN|NO", "aaron jones", "rec", 3.5)]["under"] is None
    assert V.ks_quotes([{**KS_MKT, "_fee_type": "flat"}])[("MIN|NO", "aaron jones", "rec", 3.5)]["mult"] is None


def test_kalshi_all_in_cost_and_floor():
    ksq = V.ks_quotes([KS_MKT])
    r = Bp.best_rows(pl.DataFrame([{**PICK, "side": "over"}]), Bp.an_quotes(AN), None, {}, {}, {}, PICK["run_utc"], None, ksq).row(0, named=True)
    # over: .46 + .07 x .46 x .54 = .477388 with $300 behind it; FanDuel +105 = .4878, DK +120 = .4545 (pick's own price -150 aside)
    v = json.loads(r["venues"])
    assert abs(v["Kalshi"][0] - 0.477388) < 1e-5 and v["Kalshi"][1] == 300.0
    thin = V.ks_quotes([{**KS_MKT, "yes_bid_size_fp": "4.00"}])
    u = Bp.best_rows(pl.DataFrame([PICK]), Bp.an_quotes(AN), None, {}, {}, {}, PICK["run_utc"], None, thin).row(0, named=True)
    assert json.loads(u["venues"])["Kalshi"][1] == 4.0 and u["best_venue"] == "FanDuel"   # .51 + fee = .5275 but $4: not best
    deep = Bp.best_rows(pl.DataFrame([PICK]), Bp.an_quotes(AN), None, {}, {}, {}, PICK["run_utc"], None, ksq).row(0, named=True)
    assert deep["best_venue"] == "Kalshi" and abs(deep["best_cost"] - 0.52749) < 1e-5 and deep["best_size"] == 75.5
    unknown = V.ks_quotes([{**KS_MKT, "_fee_type": "flat"}])
    x = Bp.best_rows(pl.DataFrame([PICK]), Bp.an_quotes(AN), None, {}, {}, {}, PICK["run_utc"], None, unknown).row(0, named=True)
    assert "Kalshi" not in json.loads(x["venues"])                                 # fee unknown: not priced at all


def test_kalshi_markets_pages_and_series_fees(monkeypatch):
    calls = []

    def fake(path, **q):
        calls.append((path, q.get("cursor")))
        if path.startswith("/series/"):
            return {"series": {"fee_type": "quadratic", "fee_multiplier": 0.5}}
        if q["series_ticker"] == "KXNFLREC" and not q.get("cursor"):
            return {"markets": [{"ticker": "a"}], "cursor": "c2"}
        if q["series_ticker"] == "KXNFLREC":
            return {"markets": [{"ticker": "b"}], "cursor": ""}
        return {"markets": [], "cursor": ""}
    monkeypatch.setattr(V, "ks_get", fake)
    m = V.ks_markets()
    assert [x["ticker"] for x in m] == ["a", "b"] and m[0]["_mult"] == 0.5 and m[0]["_series"] == "KXNFLREC"
    assert ("/markets", "c2") in calls
