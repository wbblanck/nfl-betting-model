"""Best available price for each official S1 pick, at the pick's exact line and side (record only).

A separate record: S1 is still graded at the DraftKings price it recorded (docs/s1_live_rules.md), so this file never
changes a pick or its result. For every pick at each run it lists what one dollar of payout costs at each venue,
all-in, and names the cheapest:

- Action Network books at this run (DraftKings, FanDuel, BetMGM, BetRivers, Caesars): implied probability of the
  American price on the pick's side, only where the book's line equals the pick's line. Vig is already in the price.
- ParlayAPI's DraftKings and FanDuel at the same line (src/nflbet/sources/parlay.py).
- Polymarket US: the side's quoted buy price plus the taker fee 0.0695 x p x (1 - p) (src/nflbet/sources/venues.py).
- Novig: 1 - best resting price on the other outcome, plus its taker fee where charged (none pregame on NFL game
  markets), with the dollars of payout available at that price.
- Kalshi, read directly (src/nflbet/sources/venues.py): the side's ask plus the taker fee M x 0.07 x p x (1 - p), M from the
  series, with the contracts at the ask as the size.

The OpenMarkets prices (Kalshi, ProphetX, BettorEdge) stay in `prefee`, listed but not eligible for "best": they reach
us without fees. OpenMarkets' Kalshi price is a cross-check on the direct read. A Novig, Polymarket US or Kalshi price
with less than MIN_SIZE dollars of payout behind it is listed but not eligible either: one stray resting order can make
a side look cheap with a dollar behind it. Polymarket's size comes from its order book; if the
book cannot be read, the price stays eligible without a size. An edge over CHECK_CENTS is flagged for a look.

Written to data/live/s1_bestprice_2026.csv by scripts/live_s1.py; one row per pick per run.
"""
from __future__ import annotations

import datetime as dt
import json

import polars as pl

from nflbet.sources import venues as V
from nflbet.quant.odds import american_from_prob as american, implied as imp
from nflbet.sources.ids import NON_BOOKS, TEAM_FIX, game_key, norm_name

AN_NAME = {"DK NJ": "DraftKings", "FanDuel NJ": "FanDuel", "BetMGM NJ": "BetMGM", "BetRivers NJ": "BetRivers",
           "Caesars NV": "Caesars"}
PREFEE = {"om_kalshi_odds": "Kalshi", "om_prophetx_odds": "ProphetX", "om_bettoredge_odds": "BettorEdge"}
MIN_SIZE = 10.0                 # $ of payout at an exchange's best price (Novig, Polymarket US, Kalshi) for it to count as "best"
CHECK_CENTS = 10.0              # an edge over DK larger than this is flagged: usually a stale or stray quote
COLS = ["run_utc", "week", "an_game_id", "start_time", "home", "away", "player", "player_id", "market", "line", "side",
        "dk_odds", "dk_cost", "best_venue", "best_cost", "best_odds", "best_size", "edge_cents", "n_venues", "venues",
        "prefee", "check"]


def an_quotes(an: pl.DataFrame) -> dict[tuple, dict[str, tuple[float, float]]]:
    """(an_game_id, nkey, market, line) -> {book: (over_odds, under_odds)} for two-sided quotes of real books."""
    out: dict = {}
    d = an.filter(~pl.col("book_id").is_in(list(NON_BOOKS)), pl.col("over_odds").fill_null("") != "",
                  pl.col("under_odds").fill_null("") != "")
    for r in d.iter_rows(named=True):
        book = AN_NAME.get(r["book"], r["book"])
        out.setdefault((str(r["an_game_id"]), norm_name(r["player"]), r["market"], float(r["line"])), {})[book] = (
            float(r["over_odds"]), float(r["under_odds"]))
    return out


def venue_costs(p: dict, anq: dict, pa_idx: dict, pmq: dict, nv_idx: dict, nv_books: dict,
                pm_size: dict | None = None, ksq: dict | None = None) -> dict[str, tuple[float, float | None]]:
    """{venue: (all-in cost per $1 of payout, $ available or None)} at the pick's line and side."""
    side, line = p["side"], float(p["line"])
    nk = norm_name(p["player"])
    g = game_key(TEAM_FIX.get(p["home"], p["home"]), TEAM_FIX.get(p["away"], p["away"]))
    out: dict = {}
    for book, (o, u) in anq.get((str(p["an_game_id"]), nk, p["market"], line), {}).items():
        out[book] = (imp(u if side == "under" else o), None)
    for b, name in (("dk", "DraftKings (ParlayAPI)"), ("fd", "FanDuel (ParlayAPI)")):
        r = pa_idx.get((b, g, nk, p["market"]))
        if r and float(r["line"]) == line and r[side] is not None:
            out[name] = (imp(r[side]), None)
    q = pmq.get((g, nk, p["market"], line))
    if q:
        c = q[side]
        out["Polymarket US"] = (c + V.pm_fee(c, q["fee"]), (pm_size or {}).get(q.get("slug"), {}).get(side))
    m = nv_idx.get((g, nk, p["market"], line))
    if m and m["marketId"] in nv_books:
        t = V.nv_taker(nv_books[m["marketId"]], m).get(side)
        if t:
            out["Novig"] = (t[0] + V.nv_fee(m, t[0]), t[1])
    k = (ksq or {}).get((g, nk, p["market"], line))
    if k and k[side] and k["mult"] is not None:          # unknown fee type: not priced, so never "best"
        c, size = k[side]
        out["Kalshi"] = (c + V.ks_fee(c, k["mult"]), size or 0.0)
    return out


def best_rows(picks: pl.DataFrame, anq: dict, pa: pl.DataFrame | None, pmq: dict, nv_idx: dict, nv_books: dict,
              run_utc: str, pm_size: dict | None = None, ksq: dict | None = None) -> pl.DataFrame:
    pa_idx = {(r["book"], r["game"], r["nkey"], r["market"]): r for r in pa.iter_rows(named=True)} if pa is not None else {}
    rows = []
    for p in picks.iter_rows(named=True):
        vc = venue_costs(p, anq, pa_idx, pmq, nv_idx, nv_books, pm_size, ksq)
        dk_cost = imp(float(p["odds"]))
        elig = {k: v for k, v in vc.items() if v[1] is None or v[1] >= MIN_SIZE}
        best = min(elig.items(), key=lambda kv: kv[1][0]) if elig else None
        pre = {name: p.get(col) for col, name in PREFEE.items() if p.get(col) is not None}
        rows.append({"run_utc": run_utc, "week": p.get("week"), "an_game_id": p["an_game_id"], "start_time": p["start_time"],
                     "home": p["home"], "away": p["away"], "player": p["player"], "player_id": p.get("player_id"),
                     "market": p["market"], "line": float(p["line"]), "side": p["side"], "dk_odds": float(p["odds"]),
                     "dk_cost": round(dk_cost, 5),
                     "best_venue": best[0] if best else None, "best_cost": round(best[1][0], 5) if best else None,
                     "best_odds": round(american(best[1][0])) if best else None, "best_size": best[1][1] if best else None,
                     "edge_cents": round((dk_cost - best[1][0]) * 100, 2) if best else None, "n_venues": len(vc),
                     "venues": json.dumps({k: [round(c, 5), s] for k, (c, s) in sorted(vc.items(), key=lambda kv: kv[1][0])}),
                     "prefee": json.dumps({k: round(float(v)) for k, v in pre.items()}),
                     "check": "edge over 10 cents: check the quote" if best and (dk_cost - best[1][0]) * 100 > CHECK_CENTS else ""})
    return pl.DataFrame(rows, schema={c: (pl.Float64 if c in ("line", "dk_odds", "dk_cost", "best_cost", "best_odds", "best_size", "edge_cents")
                                          else pl.Int64 if c == "n_venues" else pl.Utf8) for c in COLS})


def fetch_quotes(picks: pl.DataFrame, week: int, when: dt.datetime) -> dict:
    """Fetch Polymarket US, Novig and Kalshi once for this run's picks: {pmq, pm_size, nv_idx, nv_books, ksq}.
    Order books (Novig) and sizes (Polymarket US) are read for every line of each picked player's market, so the
    your-venues record (src/nflbet/props/your_venues.py) can price alternate lines; this record reads only the
    pick's own line. One venue down never stops the others."""
    keys = {(game_key(TEAM_FIX.get(p["home"], p["home"]), TEAM_FIX.get(p["away"], p["away"])), norm_name(p["player"]), p["market"])
            for p in picks.iter_rows(named=True)}
    pm_size: dict = {}
    try:
        pmq = V.pm_quotes(V.pm_markets(week, when, verbose=False))
        for (g, nk, mk, _ln), q in pmq.items():                        # size only for the picks' markets: a few calls
            if (g, nk, mk) in keys and q.get("slug") and q["slug"] not in pm_size:
                try:
                    pm_size[q["slug"]] = V.pm_sizes(q["slug"])
                except Exception as e:  # noqa: BLE001 - the price stays, without a size
                    print(f"best price: Polymarket book for {q['slug']} unavailable: {type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"best price: Polymarket US unavailable: {type(e).__name__}: {e}")
        pmq = {}
    nv_idx, nv_books = {}, {}
    try:
        markets, events = V.nv_markets(when)
        nv_idx = V.nv_index(markets, events)
        for (g, nk, mk, _ln), m in nv_idx.items():
            if (g, nk, mk) in keys and m["marketId"] not in nv_books:
                nv_books[m["marketId"]] = V.nv_book(m["marketId"])
    except Exception as e:  # noqa: BLE001
        print(f"best price: Novig unavailable: {type(e).__name__}: {e}")
    try:
        ksq = V.ks_quotes(V.ks_markets())
    except Exception as e:  # noqa: BLE001
        print(f"best price: Kalshi unavailable: {type(e).__name__}: {e}")
        ksq = {}
    return {"pmq": pmq, "pm_size": pm_size, "nv_idx": nv_idx, "nv_books": nv_books, "ksq": ksq}


def record(picks: pl.DataFrame, an_path, pa: pl.DataFrame | None, week: int, when: dt.datetime,
           quotes: dict | None = None) -> pl.DataFrame | None:
    """Price every pick at its line (quotes from fetch_quotes, fetched here if not given); the caller appends the rows."""
    if picks is None or not picks.height:
        return None
    anq = an_quotes(pl.read_csv(an_path, infer_schema_length=0)) if an_path is not None else {}
    q = quotes if quotes is not None else fetch_quotes(picks, week, when)
    return best_rows(picks, anq, pa, q["pmq"], q["nv_idx"], q["nv_books"], when.strftime("%Y-%m-%dT%H:%M:%SZ"), q["pm_size"], q["ksq"])
