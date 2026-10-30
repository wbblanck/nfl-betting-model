"""Live player-prop prices from Polymarket US and Novig, for the best-price record (src/nflbet/props/bestprice.py) and the
comparison scripts (scripts/polymarket_compare.py, scripts/novig_compare.py). Public endpoints, no keys, read-only.

Polymarket US (gateway.polymarket.us): each game is fetched by slug from /v1/events/slug/{slug}; the search returns
the games but not their player props (docs/evidence/polymarket_week_probe/). A threshold market "Will X record N+
receptions?" is the over at N - 0.5. A side's `quote` is its buy price (the Yes quote equals bestAskQuote, the No quote
1 - bestBidQuote). Taker fee per the Polymarket US fee schedule: 0.0695 x p x (1 - p) per $1 of payout
(docs/evidence/polymarket_us/fee_schedule_20261014.md).

Novig (api.novig.com, docs/evidence/novig_docs/): every order buys one outcome, and a resting order at p on one
outcome is liquidity for the other at 1 - p. So the taker's cost to buy Over = 1 - best resting Under price, with that
level's contracts (one contract pays 1 cent) as the size. Taker fee = coefficient x p x (1 - p), charged only while
the game is live on WHEN_LIVE markets (pregame: none) and always on ALWAYS markets.
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.error
import urllib.parse
import urllib.request

import polars as pl

from nflbet.quant.fees import taker_fee
from nflbet.sources.http import BROWSER_UA as UA, RESEARCH_UA, get_json
from nflbet.sources.ids import TEAMS, TEAM_FIX, game_key, norm_name

# ------------------------------------------------------------------------------------------------ Polymarket US
PM = "https://gateway.polymarket.us"
PM_FEE = 0.0695
PM_MAP = {"receptions": "rec", "receiving yards": "rec_yds", "rushing yards": "rush_yds", "rushing attempts": "rush_att",
          "passing yards": "pass_yds", "passing completions": "pass_cmp", "passing attempts": "pass_att"}
PM_PAT = re.compile(r"^Will (.+?) record (\d+)\+ (.+?)\?$")
SLUG_CODE = {"LA": "lar"}      # nflverse -> Polymarket event-slug code where they differ (others: lower case)


def pm_get(path: str):
    return get_json(f"{PM}{path}", {"User-Agent": UA})


def pm_game(title: str) -> str | None:
    """'DEN Broncos vs. LA Chargers' -> 'DEN|LAC'. Polymarket writes both Los Angeles teams as 'LA', so each team is
    matched by its nickname (last word) to parlay.TEAMS, the same abbreviations the book lines use. None if unmapped."""
    def ab(side: str) -> str | None:
        nick = side.split()[-1]
        hits = {v for k, v in TEAMS.items() if k.split()[-1] == nick}
        return hits.pop() if len(hits) == 1 else None
    if " vs. " not in title:
        return None
    a, b = (ab(s) for s in title.split(" vs. ", 1))
    return "|".join(sorted((a, b))) if a and b else None


def pm_slugs(week: int, now: dt.datetime) -> list[str]:
    """This week's game-event slugs: from the search (title 'X vs. Y', start within the window) and, as a backstop,
    built from the nflverse schedule as nfl-{away}-{home}-{ET date}. The search alone is capped at 20 events and shares
    them with season-long markets, so it can miss games."""
    slugs: list[str] = []
    for q in (f"NFL Week {week}", f"NFL week {week} props"):
        for e in pm_get(f"/v1/search?query={urllib.parse.quote(q)}&limit=20").get("events", []):
            try:
                t = dt.datetime.fromisoformat((e.get("startTime") or e.get("startDate") or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if " vs. " in (e.get("title") or "") and now - dt.timedelta(hours=4) <= t <= now + dt.timedelta(days=8):
                slugs.append(e["slug"])
    try:
        import nflreadpy as nfl
        sch = nfl.load_schedules(seasons=[now.year if now.month >= 3 else now.year - 1])
        sch = sch.filter((pl.col("game_type") == "REG") & (pl.col("week") == week))
        for r in sch.iter_rows(named=True):
            a, h = (SLUG_CODE.get(x, x.lower()) for x in (r["away_team"], r["home_team"]))
            slugs.append(f"nfl-{a}-{h}-{r['gameday']}")
    except Exception as e:  # noqa: BLE001 - the search slugs still stand
        print(f"schedule slugs unavailable: {e!r}"[:200])
    return list(dict.fromkeys(slugs))


def pm_markets(week: int, now: dt.datetime, verbose: bool = True) -> list[dict]:
    """This week's Polymarket US player-prop markets ('record N+' and first-TD), fetched game by game."""
    out = []
    for slug in pm_slugs(week, now):
        try:
            body = pm_get(f"/v1/events/slug/{slug}")
        except urllib.error.HTTPError as e:
            if verbose:
                print(f"  {slug}: HTTP {e.code}, skipped")
            continue
        e = body.get("event", body) if isinstance(body, dict) else {}
        if e.get("slug") != slug:
            if verbose:
                print(f"  {slug}: no matching event, skipped")
            continue
        kept = 0
        for m in e.get("markets") or []:
            if "record" in (m.get("question") or "") or "score the first" in (m.get("question") or ""):
                kept += 1
                out.append({"event": e["title"], "question": m.get("question"), "slug": m.get("slug"), "marketSides": m.get("marketSides") or [],
                            "feeCoefficient": m.get("feeCoefficient") or e.get("feeCoefficient"),
                            "bestBidQuote": m.get("bestBidQuote"), "bestAskQuote": m.get("bestAskQuote"),
                            "lastTradePrice": m.get("lastTradePrice"), "liquidityNum": m.get("liquidityNum"),
                            "minimumTradeQty": m.get("minimumTradeQty")})
        if verbose:
            print(f"  {slug}: {e.get('title')}, {len(e.get('markets') or [])} markets, {kept} kept")
    return out


def pm_quotes(markets: list[dict]) -> dict[tuple, dict]:
    """(game, nkey, market, line) -> {'over': cost, 'under': cost, 'fee': coefficient, 'slug': market slug} for quoted
    threshold markets."""
    out = {}
    for x in markets:
        m = PM_PAT.match(x.get("question") or "")
        if not m or m.group(3) not in PM_MAP:
            continue
        sides = {s.get("description"): s for s in x.get("marketSides") or []}

        def q(side):
            v = (sides.get(side, {}).get("quote") or {}).get("value")
            return float(v) if v not in (None, "") else None
        yes, no, g = q("Yes"), q("No"), pm_game(x.get("event") or "")
        if yes is None or no is None or g is None:
            continue
        out[(g, norm_name(m.group(1)), PM_MAP[m.group(3)], float(m.group(2)) - 0.5)] = {
            "over": yes, "under": no, "fee": float(x.get("feeCoefficient") or PM_FEE), "slug": x.get("slug")}
    return out


def pm_sizes(slug: str) -> dict[str, float]:
    """$ of payout available at the best price on each side, from GET /v1/markets/{slug}/book (one contract pays $1).
    Buying Yes (over) takes the lowest offer; buying No (under) sells into the highest bid. A side with no orders is
    absent. Levels are not assumed to be sorted (docs/evidence/polymarket_book_probe/)."""
    md = pm_get(f"/v1/markets/{urllib.parse.quote(slug)}/book").get("marketData") or {}

    def px(level: dict) -> float:
        return float((level.get("px") or {}).get("value"))
    out = {}
    offers, bids = md.get("offers") or [], md.get("bids") or []
    if offers:
        best = min(px(x) for x in offers)
        out["over"] = sum(float(x["qty"]) for x in offers if px(x) == best)
    if bids:
        best = max(px(x) for x in bids)
        out["under"] = sum(float(x["qty"]) for x in bids if px(x) == best)
    return out


def pm_fee(p: float, coef: float = PM_FEE) -> float:
    return taker_fee(coef, p)


# ------------------------------------------------------------------------------------------------ Novig
NV = "https://api.novig.com"
NV_MAP = {"RECEPTIONS": "rec", "RECEIVING_YARDS": "rec_yds", "RUSHING_YARDS": "rush_yds", "RUSHING_ATTEMPTS": "rush_att",
          "PASSING_YARDS": "pass_yds", "PASSING_COMPLETIONS": "pass_cmp", "PASSING_ATTEMPTS": "pass_att",
          "RUSHING_AND_RECEIVING_YARDS": "rush_rec_yds", "PASSING_AND_RUSHING_YARDS": "pass_rush_yds"}
NV_DESC = re.compile(r"^(.+?) (\d+(?:\.\d+)?) ([A-Z_]+)$")       # 'Keenan Allen 6.5 RECEPTIONS'


def nv_get(path: str, **q):
    url = NV + path + (("?" + urllib.parse.urlencode(q)) if q else "")
    return get_json(url, {"User-Agent": RESEARCH_UA, "Accept": "application/json"}, pace=0.15, retries_429=3, backoff=5)


def nv_game(desc: str) -> str | None:
    """'Washington Commanders @ San Francisco 49ers' -> 'SF|WAS' (parlay.TEAMS full names, the book lines' keys)."""
    parts = desc.split(" @ ")
    if len(parts) != 2:
        return None
    a, h = (TEAMS.get(x.strip()) for x in parts)
    return game_key(a, h) if a and h else None


def nv_markets(now: dt.datetime) -> tuple[list[dict], dict[str, dict]]:
    """This week's NFL prop markets of the mapped types, and events by ID."""
    lo, hi = int((now - dt.timedelta(hours=6)).timestamp() * 1000), int((now + dt.timedelta(days=8)).timestamp() * 1000)
    events = {e["eventId"]: e for e in nv_get("/v3/public/catalog/events", league="NFL", startsAfter=lo, startsBefore=hi, limit=500).get("items", [])}
    markets, after = [], None
    for _ in range(10):
        q = {"league": "NFL", "marketType": ",".join(NV_MAP), "startsAfter": lo, "startsBefore": hi, "limit": 5000}
        if after:
            q["after"] = after
        body = nv_get("/v3/public/catalog/markets", **q)
        markets += body.get("items", [])
        after = body.get("next")
        if not after:
            break
    return markets, events


def nv_spread_markets(now: dt.datetime) -> tuple[list[dict], dict[str, dict]]:
    """This week's NFL game-spread markets (every line Novig lists) and events by ID. Each market carries its two
    outcomes' best resting bids, so no order-book calls are needed (docs/evidence/novig_spread_probe)."""
    lo, hi = int((now - dt.timedelta(hours=6)).timestamp() * 1000), int((now + dt.timedelta(days=8)).timestamp() * 1000)
    events = {e["eventId"]: e for e in nv_get("/v3/public/catalog/events", league="NFL", startsAfter=lo, startsBefore=hi, limit=500).get("items", [])}
    body = nv_get("/v3/public/catalog/markets", league="NFL", marketType="SPREAD", startsAfter=lo, startsBefore=hi, limit=5000)
    return body.get("items", []), events


NV_SPREAD_OUT = re.compile(r"^([A-Z]{2,3}) ([+-]?\d+(?:\.\d+)?)$")       # 'CIN -18.5'


def nv_spread_quotes(markets: list[dict], events: dict[str, dict]) -> list[dict]:
    """Novig spread sides for the your-venues ATS record: game, venue, home_line (positive = home favored), side
    ("home" / "away"), all-in cost per $1 of payout, dollars available. Buying one outcome takes the best resting bid
    on the other: cost = 1 - that bid (+ fee where charged; none pregame), size = its contracts / 100."""
    out = []
    for m in markets:
        ev = events.get(m.get("eventId"))
        if m.get("status") != "OPEN" or not ev or " @ " not in (ev.get("description") or ""):
            continue
        away_name, home_name = (x.strip() for x in ev["description"].split(" @ "))
        h, a = TEAMS.get(home_name), TEAMS.get(away_name)
        g = nv_game(ev["description"])
        outs = m.get("outcomes") or []
        if not (h and a and g) or len(outs) != 2:
            continue
        for i, o in enumerate(outs):
            x = NV_SPREAD_OUT.match(o.get("name") or "")
            bid = (outs[1 - i].get("bid") or {})
            if not x or not bid.get("price"):
                continue
            team, hv = TEAM_FIX.get(x.group(1), x.group(1)), float(x.group(2))
            if team not in (h, a):
                continue
            c = 1 - float(bid["price"])
            if not 0 < c < 1:
                continue
            out.append({"game": g, "venue": "Novig", "home_line": -hv if team == h else hv, "side": "home" if team == h else "away",
                        "cost": c + nv_fee({**m, "_event": ev}, c), "size": float(bid.get("qty") or 0) / 100})
    return out


def nv_index(markets: list[dict], events: dict[str, dict]) -> dict[tuple, dict]:
    """(game, nkey, market, line) -> open Novig market (with its event under '_event'). Unparseable ones are skipped."""
    idx = {}
    for m in markets:
        mk = NV_MAP.get(m.get("marketType"))
        d = NV_DESC.match(m.get("description") or "")
        ev = events.get(m.get("eventId"))
        if not (mk and d and ev) or m.get("status") != "OPEN":
            continue
        g = nv_game(ev.get("description") or "")
        line = float(m["strike"]) if m.get("strike") not in (None, "") else float(d.group(2))
        if g:
            idx[(g, norm_name(d.group(1)), mk, line)] = {**m, "_event": ev}
    return idx


def nv_book(market_id: str) -> dict:
    return nv_get(f"/v3/public/catalog/markets/{market_id}/book", depth=1)


def nv_taker(book: dict, m: dict) -> dict:
    """{'over': (cost, size $), 'under': (cost, size $)}: cost = 1 - best resting price on the other outcome; size =
    contracts at that price / 100 (one contract pays 1 cent). A side is absent when the other outcome has no orders."""
    names = {o["outcomeId"]: (o.get("name") or "").split(" ")[0] for o in m.get("outcomes", [])}
    best = {}
    for oid, orders in (book.get("orders") or {}).items():
        if orders:
            best[names.get(oid)] = (float(orders[0]["price"]), sum(o["qty"] for o in orders if o["price"] == orders[0]["price"]) / 100)
    out = {}
    if "Under" in best:
        out["over"] = (round(1 - best["Under"][0], 6), best["Under"][1])
    if "Over" in best:
        out["under"] = (round(1 - best["Over"][0], 6), best["Over"][1])
    return out


def nv_fee(m: dict, p: float) -> float:
    f = m.get("fee") or {}
    live = (m.get("_event") or {}).get("status") == "OPEN_INGAME"
    if f.get("charged") == "ALWAYS" or (f.get("charged") == "WHEN_LIVE" and live):
        return taker_fee(float(f.get("coefficient") or 0), p)
    return 0.0


# Kalshi (external-api.kalshi.com, keyless reads). Checked 2026-10-15 (docs/evidence/kalshi_probe/): OpenMarkets' Kalshi
# price equalled Kalshi's ask on 60 of 60 prop sides; the S1 prop series are fee_type quadratic, multiplier 1.
# A market "Sam Darnold: 35+" (yes_sub_title) is the over at 34.5: YES costs yes_ask with yes_ask_size_fp contracts
# behind it; NO (the under) costs no_ask = 1 - yes_bid, with the YES bid's size behind it. One contract pays $1.
# Taker fee = M x 0.07 x p x (1 - p) per contract (Kalshi fee schedule; M = the series' fee_multiplier). Each fill's
# fee is rounded up to the cent; that rounding is not modelled here (as with Polymarket's).
KS = "https://external-api.kalshi.com/trade-api/v2"
KS_SERIES = {"KXNFLREC": "rec", "KXNFLRECYDS": "rec_yds", "KXNFLRSHYDS": "rush_yds", "KXNFLRSHATT": "rush_att",
             "KXNFLPASSYDS": "pass_yds", "KXNFLPASSATT": "pass_att", "KXNFLPASSCOMP": "pass_cmp"}
KS_TEAM = {"LAR": "LA", "JAC": "JAX"}        # Kalshi event-ticker code -> nflverse code where they differ
KS_FEE_TYPES = {"quadratic", "quadratic_with_maker_fees"}     # taker fee M x 0.07 x p(1-p) on both
KS_SUB = re.compile(r"^(.+?):\s*(\d+)\+$")                    # 'Sam Darnold: 35+'


def ks_get(path: str, **q):
    """Paced 0.25 s apart: without a key, back-to-back requests drew HTTP 429 after about 15 (2026-10-15)."""
    url = KS + path + (("?" + urllib.parse.urlencode(q)) if q else "")
    return get_json(url, {"User-Agent": RESEARCH_UA, "Accept": "application/json"}, pace=0.25, retries_429=3, backoff=2)


def ks_game(ticker: str) -> str | None:
    """'KXNFLREC-26OCT18HOUJAC-...' -> 'HOU|JAX'. The event code is date (7 characters), then away and home codes;
    the split must be the only one where both halves are team codes."""
    parts = ticker.split("-")
    if len(parts) < 2 or len(parts[1]) < 11:
        return None
    s, codes = parts[1][7:], set(TEAMS.values()) | set(KS_TEAM)
    splits = [(s[:i], s[i:]) for i in (2, 3) if s[:i] in codes and s[i:] in codes]
    if len(splits) != 1:
        return None
    a, b = (KS_TEAM.get(c, c) for c in splits[0])
    return game_key(a, b)


def ks_markets() -> list[dict]:
    """Open markets of the S1 prop series, each with its series' fee_type and fee_multiplier (_fee_type, _mult)."""
    out = []
    for series in KS_SERIES:
        s = ks_get(f"/series/{series}").get("series") or {}
        cursor = None
        for _ in range(20):
            q = {"series_ticker": series, "status": "open", "limit": 1000}
            if cursor:
                q["cursor"] = cursor
            r = ks_get("/markets", **q)
            for m in r.get("markets") or []:
                out.append({**m, "_series": series, "_fee_type": s.get("fee_type"), "_mult": s.get("fee_multiplier")})
            cursor = r.get("cursor")
            if not cursor or not r.get("markets"):
                break
    return out


def _f(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def ks_quotes(markets: list[dict]) -> dict[tuple, dict]:
    """(game, nkey, market, line) -> {"over": (ask, size) | None, "under": ..., "mult": M or None, "ticker"}.
    M is None when the series' fee type is not one whose formula is known here: such a price is never "best"."""
    out: dict = {}
    for m in markets:
        mk, g = KS_SERIES.get(m.get("_series")), ks_game(m.get("ticker", ""))
        x = KS_SUB.match((m.get("yes_sub_title") or "").strip())
        if not (mk and g and x):
            continue
        ya, yb = _f(m.get("yes_ask_dollars")), _f(m.get("yes_bid_dollars"))
        over = (ya, _f(m.get("yes_ask_size_fp"))) if ya and 0 < ya < 1 else None
        under = (round(1 - yb, 4), _f(m.get("yes_bid_size_fp"))) if yb and 0 < yb < 1 else None
        if not (over or under):
            continue
        mult = _f(m.get("_mult")) if m.get("_fee_type") in KS_FEE_TYPES else None
        out[(g, norm_name(x.group(1)), mk, float(x.group(2)) - 0.5)] = {"over": over, "under": under, "mult": mult,
                                                                         "ticker": m.get("ticker")}
    return out


def ks_fee(p: float, mult: float) -> float:
    """Kalshi taker fee per $1 of payout at price p (before the per-fill rounding up to the cent)."""
    return taker_fee(mult * 0.07, p)
