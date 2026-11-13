"""Record Novig's NFL books (docs/engine/NOVIG_INTEGRATION.md). Read-only; places nothing; needs no key.

Writes data/live/novig_books/<UTC stamp>/: events.json.gz, markets.json.gz (catalog rows verbatim, top of book
included), books.jsonl.gz (one full-depth book per line, with the time it was fetched) and summary.json. A run that
cannot read the catalog exits non-zero so the job goes red; a book that fails is counted and the run continues.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import json
import sys

from nflbet.config import ROOT
from nflbet.engine import novig_capture as C
from nflbet.sources.venues import nv_get

OUT = ROOT / "data" / "live" / "novig_books"


def _utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _gz(path, obj) -> None:
    with gzip.open(path, "wt") as f:
        json.dump(obj, f, separators=(",", ":"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=6.0, help="pull full depth for games starting within this many hours")
    ap.add_argument("--max-books", type=int, default=5000)   # about 50 minutes of calls; soonest games first if a window has more
    a = ap.parse_args()
    now = _utc()
    lo, hi = C.window_ms(now)
    try:
        events = nv_get("/v3/public/catalog/events", league="NFL", startsAfter=lo, startsBefore=hi, limit=500).get("items", [])
        markets, after = [], None
        for _ in range(20):
            q = {"league": "NFL", "marketType": ",".join(C.market_types()), "startsAfter": lo, "startsBefore": hi, "limit": 5000}
            if after:
                q["after"] = after
            body = nv_get("/v3/public/catalog/markets", **q)
            markets += body.get("items", [])
            after = body.get("next")
            if not after:
                break
        else:
            raise RuntimeError("catalog did not finish in 20 pages")
    except Exception as e:  # noqa: BLE001 - the run must go red, with the reason in the log
        print(f"ALARM: Novig catalog read failed: {e!r}", file=sys.stderr)
        return 1
    fetched = _utc()
    by_id = {e["eventId"]: e for e in events}
    targets = C.book_targets(markets, by_id, now, a.hours, a.max_books)
    d = OUT / now.strftime("%Y%m%dT%H%M%SZ")
    d.mkdir(parents=True, exist_ok=True)
    _gz(d / "events.json.gz", events)
    _gz(d / "markets.json.gz", markets)
    ok, errors = 0, collections.Counter()
    with gzip.open(d / "books.jsonl.gz", "wt") as f:
        for m in targets:
            try:
                book = nv_get(f"/v3/public/catalog/markets/{m['marketId']}/book", depth=C.MAX_DEPTH)
            except Exception as e:  # noqa: BLE001 - counted by kind; one bad book does not lose the snapshot
                errors[type(e).__name__ + (f" {e.code}" if hasattr(e, "code") else "")] += 1
                continue
            f.write(json.dumps({"fetched_utc": _utc().isoformat(), **book}, separators=(",", ":")) + "\n")
            ok += 1
    summary = {"run_utc": now.isoformat(), "catalog_fetched_utc": fetched.isoformat(), "finished_utc": _utc().isoformat(),
               "events": len(events), "markets": len(markets),
               "markets_by_type": dict(collections.Counter(m.get("marketType") for m in markets).most_common()),
               "book_hours": a.hours, "books_wanted": len(targets), "books_saved": ok, "book_errors": dict(errors)}
    (d / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    if not markets:
        print("ALARM: Novig catalog returned no NFL markets", file=sys.stderr)
        return 1
    if targets and ok < len(targets) / 2:
        print("ALARM: more than half of the wanted books failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
