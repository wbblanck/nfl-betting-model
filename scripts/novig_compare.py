"""Novig vs DraftKings and FanDuel on this week's NFL player props (docs/novig_compare.md). Descriptive, one snapshot.

Both sources are pulled in the same run: DK/FD two-sided prices from ParlayAPI (PARLAY_API_KEY), Novig from its public
catalog (no key). A Novig prop is matched to a book line on game, player, stat and the exact line.

Novig prices (docs.novig.com, saved in docs/evidence/novig_docs/): every order buys one outcome, and "a bid resting at
0.665 on one outcome is liquidity for the other outcome" at 0.335. So the taker's cost to buy Over = 1 - best resting
Under price, and the size available = that order level's contracts (one contract pays 1 cent). Taker fee =
coefficient x P x (1 - P) per $1 of payout, charged only while the game is live on WHEN_LIVE markets, so a pregame
taker pays none. Cost is compared per $1 of payout: book cost = implied probability of its American price.
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import polars as pl

sys.path.insert(0, "src")
from nflbet import parlay as Pa, props as P  # noqa: E402

HOST = "https://api.novig.com"
UA = "nfl-betting-model/1.0 (read-only research)"
MAP = {"RECEPTIONS": "rec", "RECEIVING_YARDS": "rec_yds", "RUSHING_YARDS": "rush_yds", "RUSHING_ATTEMPTS": "rush_att",
       "PASSING_YARDS": "pass_yds", "PASSING_COMPLETIONS": "pass_cmp", "PASSING_ATTEMPTS": "pass_att",
       "RUSHING_AND_RECEIVING_YARDS": "rush_rec_yds", "PASSING_AND_RUSHING_YARDS": "pass_rush_yds"}
DESC = re.compile(r"^(.+?) (\d+(?:\.\d+)?) ([A-Z_]+)$")       # 'Keenan Allen 6.5 RECEPTIONS'


def imp(a: float) -> float:
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def nv_get(path: str, **q):
    url = HOST + path + (("?" + urllib.parse.urlencode(q)) if q else "")
    for i in range(4):
        try:
            time.sleep(0.15)
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=60) as r:
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


def fetch_novig(now: dt.datetime) -> tuple[list[dict], dict[str, dict]]:
    """This week's NFL prop markets of the mapped types, and events by ID."""
    lo, hi = int((now - dt.timedelta(hours=6)).timestamp() * 1000), int((now + dt.timedelta(days=8)).timestamp() * 1000)
    events = {e["eventId"]: e for e in nv_get("/v3/public/catalog/events", league="NFL", startsAfter=lo, startsBefore=hi, limit=500).get("items", [])}
    markets, after = [], None
    for _ in range(10):
        q = {"league": "NFL", "marketType": ",".join(MAP), "startsAfter": lo, "startsBefore": hi, "limit": 5000}
        if after:
            q["after"] = after
        body = nv_get("/v3/public/catalog/markets", **q)
        markets += body.get("items", [])
        after = body.get("next")
        if not after:
            break
    return markets, events


def index_novig(markets: list[dict], events: dict[str, dict]) -> dict[tuple, dict]:
    """(game, nkey, market, line) -> Novig market. Unparseable descriptions are skipped."""
    idx = {}
    for m in markets:
        mk = MAP.get(m.get("marketType"))
        d = DESC.match(m.get("description") or "")
        ev = events.get(m.get("eventId"))
        if not (mk and d and ev) or m.get("status") != "OPEN":
            continue
        g = nv_game(ev.get("description") or "")
        line = float(m["strike"]) if m.get("strike") not in (None, "") else float(d.group(2))
        if g:
            idx[(g, P.norm_name(d.group(1)), mk, line)] = {**m, "_event": ev}
    return idx


def taker_side(book: dict, m: dict) -> dict:
    """Cost to buy Over / Under (1 - best resting price on the other outcome) and its payout size in $."""
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


def fee(m: dict, p: float) -> float:
    f = m.get("fee") or {}
    live = (m.get("_event") or {}).get("status") == "OPEN_INGAME"
    if f.get("charged") == "ALWAYS" or (f.get("charged") == "WHEN_LIVE" and live):
        return float(f.get("coefficient") or 0) * p * (1 - p)
    return 0.0


def compare(book: pl.DataFrame, idx: dict[tuple, dict], books: dict[str, dict]) -> pl.DataFrame:
    rows = []
    for r in book.iter_rows(named=True):
        m = idx.get((r["game"], r["nkey"], r["market"], float(r["line"])))
        if not m or m["marketId"] not in books:
            continue
        ts = taker_side(books[m["marketId"]], m)
        both = "over" in ts and "under" in ts
        for side, odds in (("over", r["over"]), ("under", r["under"])):
            if side not in ts or odds is None:
                continue
            c, size = ts[side]
            bc = imp(odds)
            rows.append({"book": r["book"], "player": r["nkey"], "market": r["market"], "line": float(r["line"]), "side": side,
                         "nv_cost": c, "nv_size": size, "book_odds": odds, "book_cost": bc, "gross_diff": bc - c,
                         "net_diff": bc - (c + fee(m, c)), "book_hold": imp(r["over"]) + imp(r["under"]) - 1,
                         "nv_spread": (ts["over"][0] + ts["under"][0] - 1) if both else None})
    schema = {"book": pl.Utf8, "player": pl.Utf8, "market": pl.Utf8, "line": pl.Float64, "side": pl.Utf8, "nv_cost": pl.Float64,
              "nv_size": pl.Float64, "book_odds": pl.Float64, "book_cost": pl.Float64, "gross_diff": pl.Float64,
              "net_diff": pl.Float64, "book_hold": pl.Float64, "nv_spread": pl.Float64}
    return pl.DataFrame(rows, schema=schema)


def report(d: pl.DataFrame, n: dict, run_utc: str) -> tuple[list[str], dict]:
    L = ["# Novig vs DraftKings and FanDuel, NFL player props", "",
         f"Run {run_utc}: live ParlayAPI and Novig's public catalog pulled together. Positive diff = Novig is cheaper "
         "for the buyer, per $1 of payout.", "",
         f"Novig prop markets of the compared stats: {n['nv_markets']}; parsed: {n['nv_indexed']}. Book lines (DK+FD): "
         f"{n['book_lines']}; with a Novig market at the same line: {n['matched_lines']}; Novig books fetched: {n['books']}.", ""]
    summ = {"run_utc": run_utc, **n, "side_quotes": d.height,
            "player_lines": d.select(pl.struct("player", "market", "line")).n_unique() if d.height else 0, "books_cmp": {}}
    for bk in ("dk", "fd"):
        x = d.filter(pl.col("book") == bk)
        if not x.height:
            continue
        b = {"sides": x.height, "gross_cheaper": float((x["gross_diff"] > 0).mean()), "gross_mean_cents": float(x["gross_diff"].mean() * 100),
             "net_cheaper": float((x["net_diff"] > 0).mean()), "net_mean_cents": float(x["net_diff"].mean() * 100),
             "book_hold_median": float(x.unique(subset=["player", "market", "line"])["book_hold"].median())}
        summ["books_cmp"][bk.upper()] = b
        L.append(f"- vs {bk.upper()}: {b['sides']} sides; Novig cheaper {b['gross_cheaper']:.0%} of sides, mean {b['gross_mean_cents']:+.2f} "
                 f"cents; after Novig's fee {b['net_cheaper']:.0%}, mean {b['net_mean_cents']:+.2f} cents. {bk.upper()} hold median "
                 f"{b['book_hold_median'] * 100:.1f}%.")
    if d.height:
        sp = d.unique(subset=["player", "market", "line"])["nv_spread"].drop_nulls()
        summ["nv_spread_median"] = float(sp.median()) if sp.len() else None
        summ["nv_two_sided_lines"] = int(sp.len())
        summ["nv_size_median"] = float(d.unique(subset=["player", "market", "line", "side"])["nv_size"].median())
        L.append(f"- Novig two-sided on {sp.len()} of {summ['player_lines']} compared lines; buy-both overround median "
                 + (f"{sp.median() * 100:.1f}%." if sp.len() else "n/a."))
        L.append(f"- Size at Novig's best price: median ${summ['nv_size_median']:,.0f} of payout.")
    L += ["", "Novig taker cost = 1 - best resting price on the other outcome (every Novig order buys). Novig's taker fee is "
          "charged only while a game is live on these markets, so pregame it is zero; the after-fee column applies it only "
          "where it is charged. Novig settles a voided prop at fair market value (`FMV`), books usually void it. One snapshot, "
          "unvalidated.", ""]
    return L, summ


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    run_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    book = Pa.parse(Pa.fetch()[0]).filter(pl.col("book").is_in(["dk", "fd"]))
    markets, events = fetch_novig(now)
    idx = index_novig(markets, events)
    keys = {(r["game"], r["nkey"], r["market"], float(r["line"])) for r in book.iter_rows(named=True)}
    want = {idx[k]["marketId"]: idx[k] for k in keys if k in idx}
    books = {}
    for mid in want:
        try:
            books[mid] = nv_get(f"/v3/public/catalog/markets/{mid}/book", depth=1)
        except urllib.error.HTTPError as e:
            print(f"book {mid}: HTTP {e.code}")
    d = compare(book, idx, books)
    n = {"nv_markets": len(markets), "nv_indexed": len(idx), "book_lines": len(keys), "matched_lines": len(want), "books": len(books)}
    L, summ = report(d, n, run_utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    ev = Path(f"docs/evidence/novig_compare/{stamp}")
    ev.mkdir(parents=True, exist_ok=True)
    with gzip.open(ev / "novig.json.gz", "wt") as fh:
        json.dump({"markets": markets, "events": events, "books": books}, fh)
    d.write_csv(ev / "sides.csv")
    Path("docs/novig_compare.md").write_text("\n".join(L) + "\n")
    Path("docs/novig_compare.json").write_text(json.dumps(summ, indent=1) + "\n")
    print("\n".join(L))
    types = collections.Counter(m.get("marketType") for m in markets)
    print("Novig market types fetched:", dict(types))


if __name__ == "__main__":
    main()
