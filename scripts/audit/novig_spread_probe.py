"""What do Novig's NFL game-spread markets look like? (evidence only, keyless)

Reads this week's NFL events and SPREAD markets from Novig's public catalog, plus the order books of the first two
open markets, so the "your venues" ATS reader (docs/your_venues_rules.md) can be checked against real rows.
Writes docs/evidence/novig_spread_probe/<UTC stamp>/{events,markets,books}.json.gz and summary.json.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
from pathlib import Path

from nflbet.sources import venues as V


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/novig_spread_probe") / stamp
    out.mkdir(parents=True, exist_ok=True)
    lo, hi = int((now - dt.timedelta(hours=6)).timestamp() * 1000), int((now + dt.timedelta(days=8)).timestamp() * 1000)
    events = V.nv_get("/v3/public/catalog/events", league="NFL", startsAfter=lo, startsBefore=hi, limit=500).get("items", [])
    markets = V.nv_get("/v3/public/catalog/markets", league="NFL", marketType="SPREAD", startsAfter=lo, startsBefore=hi,
                       limit=5000).get("items", [])
    opened = [m for m in markets if m.get("status") == "OPEN"]
    books = {m["marketId"]: V.nv_book(m["marketId"]) for m in opened[:2]}
    for name, body in (("events", events), ("markets", markets), ("books", books)):
        with gzip.open(out / f"{name}.json.gz", "wt") as fh:
            json.dump(body, fh)
    summary = {"stamp": stamp, "events": len(events), "spread_markets": len(markets), "open": len(opened),
               "per_event": {}, "sample_markets": markets[:4], "sample_book": next(iter(books.values()), None)}
    for m in markets:
        summary["per_event"][m.get("eventId")] = summary["per_event"].get(m.get("eventId"), 0) + 1
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: summary[k] for k in ("events", "spread_markets", "open")}), json.dumps(markets[:2])[:1500])


if __name__ == "__main__":
    main()
