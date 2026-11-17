"""Phase 6: executable Novig quotes from a recorded snapshot (docs/engine/NOVIG_INTEGRATION.md). Market data only.

For every prop market in a snapshot: match it to a canonical contract (engine.contracts) and a player on that week's
roster, or record why not; then, where a full-depth book was saved in time, read what each side costs at fixed sizes
(engine.pricing.take: buying Over takes the resting orders on Under) and the fee that would apply. Nothing here reads
a prediction or a probability: this produces no priced-sides list, no expected value and no decision (CLAUDE.md).
It is the execution side that Test E describes and that pricing will later stand on.

Rules, each tested in tests/test_engine.py:
- unmatched never priced: a market that fails contract matching, or whose player does not resolve to exactly one
  player on the game's two rosters, gets a reason and no quote;
- fresh only: a book is used only if it was fetched before the game started and within FRESH_MINUTES of the catalog
  read whose fee and identity it is paired with; otherwise the reason is recorded and nothing is quoted;
- re-derivable: each quote row carries the snapshot stamp, market ID, the book's seq and fetch time and a hash of the
  orders it read, and rederive() recomputes the row from the saved files and must get the same row.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path

from nflbet.engine import contracts as K, pricing, registry

FRESH_MINUTES = 60
SIZES = (1_000, 10_000)          # contracts: $10 and $100 of payout (one contract pays 1 cent)


def load(snapshot: Path) -> dict:
    """events, markets, books (marketId -> book) and summary of one saved snapshot, as recorded."""
    snapshot = Path(snapshot)
    books = {}
    with gzip.open(snapshot / "books.jsonl.gz", "rt") as f:
        for line in f:
            if line.strip():
                b = json.loads(line)
                books[b["marketId"]] = b
    return {"stamp": snapshot.name, "events": json.load(gzip.open(snapshot / "events.json.gz", "rt")),
            "markets": json.load(gzip.open(snapshot / "markets.json.gz", "rt")), "books": books,
            "summary": json.loads((snapshot / "summary.json").read_text())}


def _utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def orders_hash(orders: list[dict]) -> str:
    rows = sorted((str(o["price"]), int(o["qty"])) for o in orders)
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:16]


def fresh(book: dict | None, market: dict, catalog_utc: str) -> tuple[bool, str]:
    if book is None:
        return False, "no book saved"
    t = _utc(book["fetched_utc"])
    start = market.get("startsTs")
    if not start or t.timestamp() * 1000 >= start:
        return False, "book fetched at or after the start"
    if abs((t - _utc(catalog_utc)).total_seconds()) > FRESH_MINUTES * 60:
        return False, f"book and catalog more than {FRESH_MINUTES} minutes apart"
    if market.get("status") != "OPEN":
        return False, "market not open at the catalog read"
    return True, "ok"


def side_quote(book: dict, market: dict, c: K.Contract, side: str, size: int) -> dict:
    """What buying `size` contracts of `side` costs from this book: average price, worst level, unfilled part and the
    fee (pregame, since fresh() requires the book to predate the start)."""
    other = c.under_id if side == "Over" else c.over_id
    orders = book.get("orders", {}).get(other) or []
    fill = pricing.take(orders, size) if orders else pricing.Fill(0, size, None, None, ())
    fee = pricing.taker_fee(market.get("fee"), fill.cost, live=False) if fill.cost is not None else None
    return {"side": side, "size": size, "filled": fill.filled, "unfilled": fill.unfilled,
            "avg_cost": None if fill.cost is None else float(fill.cost), "worst_mills": fill.worst,
            "top_mills": fill.levels[0][0] if fill.levels else None,
            "fee": None if fee is None else float(fee), "all_in": None if fill.cost is None else float(fill.cost + fee),
            "orders_hash": orders_hash(orders)}


def quotes(snap: dict, rosters: dict[str, list[dict]]) -> tuple[list[dict], list[dict]]:
    """(quote rows, unmatched rows) for one snapshot. rosters: game key ('BUF|MIA') -> roster rows for that week
    ({'player_id', 'name', 'team', 'position'}). A market not of a registry type is skipped silently (game lines)."""
    by_type = registry.by_novig_type()
    events = {e["eventId"]: e for e in snap["events"]}
    catalog_utc = snap["summary"]["catalog_fetched_utc"]
    rows, unmatched = [], []
    for m in sorted(snap["markets"], key=lambda r: r["marketId"]):
        if m.get("marketType") not in by_type:
            continue
        c, why = K.match_novig(m, events.get(m.get("eventId")), by_type)
        base = {"stamp": snap["stamp"], "market_id": m["marketId"], "market_type": m.get("marketType"), "description": m.get("description")}
        if c is None:
            unmatched.append({**base, "reason": why})
            continue
        pid, how = K.resolve_player(c, rosters.get(c.game, []))
        if pid is None:
            unmatched.append({**base, "reason": f"player: {how}"})
            continue
        book = snap["books"].get(m["marketId"])
        ok, why = fresh(book, m, catalog_utc)
        if not ok:
            unmatched.append({**base, "reason": why, "matched": True})
            continue
        head = {**base, "game": c.game, "player_id": pid, "player_name": c.player_name, "resolved_by": how, "market": c.market,
                "line": str(c.line), "voids": c.voids, "starts_ms": c.starts_ms, "book_seq": book.get("seq"),
                "book_fetched_utc": book["fetched_utc"], "catalog_fetched_utc": catalog_utc,
                "minutes_before_start": round((c.starts_ms / 1000 - _utc(book["fetched_utc"]).timestamp()) / 60, 1)}
        for side in ("Over", "Under"):
            for size in SIZES:
                rows.append({**head, **side_quote(book, m, c, side, size)})
    return rows, unmatched


def rederive(row: dict, snap: dict, rosters: dict[str, list[dict]]) -> bool:
    """Recompute one quote row from the saved snapshot; True when every field comes out the same."""
    m = next((x for x in snap["markets"] if x["marketId"] == row["market_id"]), None)
    if m is None or snap["stamp"] != row["stamp"]:
        return False
    one = {**snap, "markets": [m]}
    again = [r for r in quotes(one, rosters)[0] if r["side"] == row["side"] and r["size"] == row["size"]]
    return len(again) == 1 and again[0] == row
