"""What a Novig snapshot keeps (scripts/fetch/novig_books.py does the I/O). Read-only public catalog; no key.

One snapshot = this week's NFL events, every market of the registry's types plus the game lines, each as Novig
returned it (so each outcome's best resting bid and its quantity, the fee record, void rule, volume and open
interest are kept verbatim), and the full-depth book of prop markets whose game starts soon.
"""
from __future__ import annotations

import datetime as dt

from nflbet.engine import registry

GAME_LINES = ("MONEY", "SPREAD", "TOTAL", "TEAM_TOTAL")
MAX_DEPTH = 20                # Novig's limit on `depth` (docs/evidence/novig_docs: BOOK_DEPTH_OUT_OF_RANGE)


def market_types() -> list[str]:
    return sorted(registry.by_novig_type()) + list(GAME_LINES)


def window_ms(now: dt.datetime) -> tuple[int, int]:
    """Events from 6 hours ago to 8 days ahead, as the other Novig readers use."""
    return int((now - dt.timedelta(hours=6)).timestamp() * 1000), int((now + dt.timedelta(days=8)).timestamp() * 1000)


def book_targets(markets: list[dict], events: dict[str, dict], now: dt.datetime, hours: float, cap: int) -> list[dict]:
    """Prop markets to pull full depth for: open, a registry type, at least one resting bid, game not started and
    starting within `hours`. Soonest game first, then market ID, cut at `cap` so one run stays inside the rate limit."""
    props, now_ms = registry.by_novig_type(), int(now.timestamp() * 1000)
    out = []
    for m in markets:
        ev = events.get(m.get("eventId"))
        start = (ev or {}).get("startsTs") or m.get("startsTs")
        if (m.get("marketType") in props and m.get("status") == "OPEN" and start
                and now_ms < start <= now_ms + hours * 3_600_000
                and any((o.get("bid") or {}).get("price") for o in m.get("outcomes") or [])):
            out.append((start, m["marketId"], m))
    return [m for _, _, m in sorted(out, key=lambda t: t[:2])][:cap]
