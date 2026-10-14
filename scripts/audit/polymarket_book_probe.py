"""Check Polymarket US's order book and BBO endpoints against the quotes we already use (read-only, no key).

For up to N_MARKETS quoted NFL player-prop markets in the soonest games (GET /v2/leagues/nfl/events, then
GET /v1/events/slug/{slug}), fetch GET /v1/markets/{slug}/book and GET /v1/markets/{slug}/bbo and record: the book's
best bid (highest) and best offer (lowest), the quantity at each, the order the levels come in, the BBO fields, and
whether best offer == bestAskQuote (the Yes quote) and best bid == bestBidQuote (1 - the No quote).
Writes docs/evidence/polymarket_book_probe/<stamp>/probe.json.
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PM = "https://gateway.polymarket.us"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
N_MARKETS = 20


def get(path: str):
    time.sleep(0.2)
    try:
        with urllib.request.urlopen(urllib.request.Request(PM + path, headers={"User-Agent": UA}), timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - recorded
        return -1, repr(e)[:300]


def px(level: dict) -> float:
    return float((level.get("px") or {}).get("value"))


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    _, body = get("/v2/leagues/nfl/events?limit=50")
    evs = [e for e in body.get("events", []) if e.get("startTime") and dt.datetime.fromisoformat(e["startTime"].replace("Z", "+00:00")) > now]
    evs.sort(key=lambda e: e["startTime"])
    picked = []
    for e in evs[:3]:
        _, b = get(f"/v1/events/slug/{urllib.parse.quote(e['slug'])}")
        for m in (b.get("event") or {}).get("markets", []):
            if "player" in (m.get("sportsMarketType") or "") and m.get("bestAskQuote") and m.get("bestBidQuote") and m.get("slug"):
                picked.append(m)
        if len(picked) >= N_MARKETS:
            break
    rows = []
    for m in picked[:N_MARKETS]:
        st_b, book = get(f"/v1/markets/{urllib.parse.quote(m['slug'])}/book")
        st_o, bbo = get(f"/v1/markets/{urllib.parse.quote(m['slug'])}/bbo")
        md = book.get("marketData", {}) if isinstance(book, dict) else {}
        bids, offers = md.get("bids") or [], md.get("offers") or []
        bb = max(bids, key=px) if bids else None
        bo = min(offers, key=px) if offers else None
        q_ask, q_bid = float(m["bestAskQuote"]["value"]), float(m["bestBidQuote"]["value"])
        rows.append({"slug": m["slug"], "question": m.get("question"), "book_status": st_b, "bbo_status": st_o,
                     "bids_px": [px(x) for x in bids[:5]], "offers_px": [px(x) for x in offers[:5]],
                     "best_bid": px(bb) if bb else None, "best_bid_qty": sum(float(x["qty"]) for x in bids if bb and px(x) == px(bb)),
                     "best_offer": px(bo) if bo else None, "best_offer_qty": sum(float(x["qty"]) for x in offers if bo and px(x) == px(bo)),
                     "event_best_ask": q_ask, "event_best_bid": q_bid,
                     "offer_matches_ask": bo is not None and abs(px(bo) - q_ask) < 1e-9,
                     "bid_matches_bid": bb is not None and abs(px(bb) - q_bid) < 1e-9,
                     "bids_first_is_best": bool(bids) and px(bids[0]) == px(bb), "offers_first_is_best": bool(offers) and px(offers[0]) == px(bo),
                     "bbo": (bbo.get("marketData") if isinstance(bbo, dict) else bbo)})
    out = {"run_utc": now.isoformat(), "n": len(rows),
           "offer_matches_ask": sum(r["offer_matches_ask"] for r in rows), "bid_matches_bid": sum(r["bid_matches_bid"] for r in rows),
           "bids_first_is_best": sum(r["bids_first_is_best"] for r in rows), "offers_first_is_best": sum(r["offers_first_is_best"] for r in rows),
           "rows": rows}
    p = Path(f"docs/evidence/polymarket_book_probe/{now.strftime('%Y%m%dT%H%M%SZ')}")
    p.mkdir(parents=True, exist_ok=True)
    (p / "probe.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "rows"})
    for r in rows[:20]:
        b = r["bbo"] if isinstance(r["bbo"], dict) else {}
        print(f"  {r['question'][:52]:52s} book {r['book_status']} bbo {r['bbo_status']} | bid {r['best_bid']} x{r['best_bid_qty']:g} "
              f"offer {r['best_offer']} x{r['best_offer_qty']:g} | event bid/ask {r['event_best_bid']}/{r['event_best_ask']} | "
              f"bbo bid {(b.get('bestBid') or {}).get('value')} ask {(b.get('bestAsk') or {}).get('value')} "
              f"long {(b.get('longQuote') or {}).get('value')} short {(b.get('shortQuote') or {}).get('value')} "
              f"bidShares {b.get('bidShares')} askShares {b.get('askShares')}")


if __name__ == "__main__":
    main()
