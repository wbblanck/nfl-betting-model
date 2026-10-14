"""Live player-prop prices from Polymarket US and Novig, for the best-price record (src/nflbet/bestprice.py) and the
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
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import polars as pl

from nflbet import parlay as Pa
from nflbet.props import norm_name

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# ------------------------------------------------------------------------------------------------ Polymarket US
PM = "https://gateway.polymarket.us"
PM_FEE = 0.0695
PM_MAP = {"receptions": "rec", "receiving yards": "rec_yds", "rushing yards": "rush_yds", "rushing attempts": "rush_att",
          "passing yards": "pass_yds", "passing completions": "pass_cmp", "passing attempts": "pass_att"}
PM_PAT = re.compile(r"^Will (.+?) record (\d+)\+ (.+?)\?$")
SLUG_CODE = {"LA": "lar"}      # nflverse -> Polymarket event-slug code where they differ (others: lower case)


def pm_get(path: str):
    with urllib.request.urlopen(urllib.request.Request(f"{PM}{path}", headers={"User-Agent": UA}), timeout=60) as r:
        return json.loads(r.read())


def pm_game(title: str) -> str | None:
    """'DEN Broncos vs. LA Chargers' -> 'DEN|LAC'. Polymarket writes both Los Angeles teams as 'LA', so each team is
    matched by its nickname (last word) to parlay.TEAMS, the same abbreviations the book lines use. None if unmapped."""
    def ab(side: str) -> str | None:
        nick = side.split()[-1]
        hits = {v for k, v in Pa.TEAMS.items() if k.split()[-1] == nick}
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
                out.append({"event": e["title"], "question": m.get("question"), "marketSides": m.get("marketSides") or [],
                            "feeCoefficient": m.get("feeCoefficient") or e.get("feeCoefficient"),
                            "bestBidQuote": m.get("bestBidQuote"), "bestAskQuote": m.get("bestAskQuote"),
                            "lastTradePrice": m.get("lastTradePrice"), "liquidityNum": m.get("liquidityNum"),
                            "minimumTradeQty": m.get("minimumTradeQty")})
        if verbose:
            print(f"  {slug}: {e.get('title')}, {len(e.get('markets') or [])} markets, {kept} kept")
    return out


def pm_quotes(markets: list[dict]) -> dict[tuple, dict]:
    """(game, nkey, market, line) -> {'over': cost, 'under': cost, 'fee': coefficient} for quoted threshold markets."""
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
            "over": yes, "under": no, "fee": float(x.get("feeCoefficient") or PM_FEE)}
    return out


def pm_fee(p: float, coef: float = PM_FEE) -> float:
    return coef * p * (1 - p)


# ------------------------------------------------------------------------------------------------ Novig
NV = "https://api.novig.com"
NV_MAP = {"RECEPTIONS": "rec", "RECEIVING_YARDS": "rec_yds", "RUSHING_YARDS": "rush_yds", "RUSHING_ATTEMPTS": "rush_att",
          "PASSING_YARDS": "pass_yds", "PASSING_COMPLETIONS": "pass_cmp", "PASSING_ATTEMPTS": "pass_att",
          "RUSHING_AND_RECEIVING_YARDS": "rush_rec_yds", "PASSING_AND_RUSHING_YARDS": "pass_rush_yds"}
NV_DESC = re.compile(r"^(.+?) (\d+(?:\.\d+)?) ([A-Z_]+)$")       # 'Keenan Allen 6.5 RECEPTIONS'


def nv_get(path: str, **q):
    url = NV + path + (("?" + urllib.parse.urlencode(q)) if q else "")
    for i in range(4):
        try:
            time.sleep(0.15)
            req = urllib.request.Request(url, headers={"User-Agent": "nfl-betting-model/1.0 (read-only research)", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < 3:
                time.sleep(5 * 2 ** i)
                continue
            raise


def nv_game(desc: str) -> str | None:
    """'Washington Commanders @ San Francisco 49ers' -> 'SF|WAS' (parlay.TEAMS full names, the book lines' keys)."""
    parts = desc.split(" @ ")
    if len(parts) != 2:
        return None
    a, h = (Pa.TEAMS.get(x.strip()) for x in parts)
    return Pa.game_key(a, h) if a and h else None


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
        return float(f.get("coefficient") or 0) * p * (1 - p)
    return 0.0
