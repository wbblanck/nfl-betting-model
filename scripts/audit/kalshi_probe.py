"""Check Kalshi's own API against the Kalshi prices we already get from OpenMarkets (read-only, no Kalshi key).

Questions (from the Kalshi / Polymarket US fee guide, 2026-10-14, and the saved OpenMarkets data):
1. Which fee_type and fee_multiplier do Kalshi's NFL series carry (GET /series?category=Sports, /series/fee_changes)?
2. Is OpenMarkets' Kalshi `price` the ask on the quoted side? Over = YES, under = NO of the market in `buy_id`
   (a Kalshi market ticker). Compared with GET /markets/{ticker} (yes_ask_dollars / no_ask_dollars) and with the
   order book (bids only: YES ask = 1 - best NO bid).
3. Is OpenMarkets' `available` dollars of payout (contracts) or dollars of cost (contracts x price)?
4. Does `fee_packet.taker_price` equal price + M x 0.07 x p x (1 - p) with the series' multiplier M?
5. Rate limit without a key: 30 back-to-back requests, recording status codes and any rate headers.
OpenMarkets and Kalshi are read a minute or two apart, so a few price differences can be movement; both are saved.
Writes docs/evidence/kalshi_probe/<stamp>/probe.json and openmarkets_kalshi.jsonl.gz.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, "src")
from nflbet.sources import openmarkets as Om  # noqa: E402

HOSTS = ["https://external-api.kalshi.com/trade-api/v2", "https://api.elections.kalshi.com/trade-api/v2"]
UA = "nfl-betting-model/1.0 (read-only research)"
N_MARKETS = 30
HDRS = ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")


def get(base: str, path: str, pause: float = 0.25, **q):
    time.sleep(pause)
    url = base + path + (("?" + urllib.parse.urlencode(q)) if q else "")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}),
                                    timeout=60) as r:
            return r.status, {k: v for k, v in r.headers.items() if k.lower() in HDRS}, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {k: v for k, v in e.headers.items() if k.lower() in HDRS}, e.read()[:300].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - recorded
        return -1, {}, repr(e)[:300]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def levels(book: dict, side: str) -> list[tuple[float, float]]:
    """[(price in dollars, quantity)] for one side's bids, whatever the key spelling (yes_dollars / yes)."""
    for k in (f"{side}_dollars", side):
        v = book.get(k)
        if isinstance(v, list):
            out = []
            for lv in v:
                p, q = num(lv[0]), num(lv[1])
                if p is None or q is None:
                    continue
                out.append((p / 100 if k == side and p > 1 else p, q))
            return out
    return []


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(f"docs/evidence/kalshi_probe/{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)
    res: dict = {"stamp": stamp, "hosts": {}}

    base = None
    for h in HOSTS:
        st, hd, body = get(h, "/series", category="Sports")
        res["hosts"][h] = {"status": st, "headers": hd, "n_series": len(body.get("series") or []) if isinstance(body, dict) else body}
        if st == 200 and base is None:
            base, series = h, body.get("series") or []
    if base is None:
        (out_dir / "probe.json").write_text(json.dumps(res, indent=1))
        raise SystemExit("no Kalshi host answered")
    res["base"] = base
    nfl = [s for s in series if str(s.get("ticker", "")).startswith("KXNFL")]
    res["series_fields"] = sorted(series[0].keys()) if series else []
    res["fee_types_sports"] = {}
    for s in series:
        k = f"{s.get('fee_type')}|{s.get('fee_multiplier')}"
        res["fee_types_sports"][k] = res["fee_types_sports"].get(k, 0) + 1
    res["nfl_series"] = {s["ticker"]: {"title": s.get("title"), "fee_type": s.get("fee_type"),
                                       "fee_multiplier": s.get("fee_multiplier")} for s in nfl}
    st, hd, body = get(base, "/series/fee_changes", show_historical="true")
    res["fee_changes"] = {"status": st, "body": body if st != 200 else
                          [c for c in (body.get("series_fee_change_arr") or body.get("fee_changes") or body.get("series_fee_changes") or [])
                           if str(c.get("series_ticker", "")).startswith("KXNFL")] or str(body)[:3000]}

    # OpenMarkets' Kalshi quotes on this week's NFL player props
    rows = Om.fetch(now=now, days=8, spreads=False)
    om = []
    for r in rows:
        for v in r.get("partner_liquidities") or []:
            if v.get("partner_name") == "Kalshi" and v.get("buy_id") and r.get("side_key") in ("over", "under"):
                om.append({"title": r.get("title"), "contest": r.get("contest_title"), "market_key": r.get("market_key"),
                           "line": r.get("variable"), "side": r["side_key"], "ticker": v["buy_id"], "price": v.get("price"),
                           "available": v.get("available"), "actionable": v.get("actionable"), "fee_packet": v.get("fee_packet")})
    with gzip.open(out_dir / "openmarkets_kalshi.jsonl.gz", "wt") as fh:
        for x in om:
            fh.write(json.dumps(x) + "\n")
    res["openmarkets"] = {"read_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "kalshi_quotes": len(om),
                          "tickers": len({x["ticker"] for x in om})}

    # fee packet vs the formula with each series' multiplier
    mult = {t: num(s["fee_multiplier"]) for t, s in res["nfl_series"].items()}
    fee_chk = {"n": 0, "max_abs_err": 0.0, "no_series": 0, "multipliers_seen": {}}
    for x in om:
        p, fp = num(x["price"]), x.get("fee_packet") or {}
        m = mult.get(x["ticker"].split("-")[0])
        if p is None or num(fp.get("taker_price")) is None:
            continue
        if m is None:
            fee_chk["no_series"] += 1
            continue
        fee_chk["multipliers_seen"][str(m)] = fee_chk["multipliers_seen"].get(str(m), 0) + 1
        fee_chk["n"] += 1
        fee_chk["max_abs_err"] = max(fee_chk["max_abs_err"], abs(num(fp["taker_price"]) - (p + m * 0.07 * p * (1 - p))))
    res["fee_packet_check"] = fee_chk

    # sample markets: round-robin over series so no single stat dominates
    by_series: dict = {}
    for x in om:
        by_series.setdefault(x["ticker"].split("-")[0], {}).setdefault(x["ticker"], []).append(x)
    sample, queues = [], {k: list(v.items()) for k, v in sorted(by_series.items())}
    while len(sample) < N_MARKETS and any(queues.values()):
        for k in list(queues):
            if queues[k] and len(sample) < N_MARKETS:
                sample.append(queues[k].pop(len(queues[k]) // 2))
    checks = []
    for ticker, quotes in sample:
        s1, _, mk = get(base, f"/markets/{ticker}")
        s2, _, ob = get(base, f"/markets/{ticker}/orderbook")
        m = mk.get("market", {}) if isinstance(mk, dict) else {}
        book = (ob.get("orderbook_fp") or ob.get("orderbook") or {}) if isinstance(ob, dict) else {}
        yes, no = levels(book, "yes"), levels(book, "no")
        best = {"yes_bid": max(yes, default=None), "no_bid": max(no, default=None)}
        ask_from_book = {"over": round(1 - best["no_bid"][0], 4) if best["no_bid"] else None,
                         "under": round(1 - best["yes_bid"][0], 4) if best["yes_bid"] else None}
        qty_at_ask = {"over": sum(q for p, q in no if best["no_bid"] and p == best["no_bid"][0]),
                      "under": sum(q for p, q in yes if best["yes_bid"] and p == best["yes_bid"][0])}
        c = {"ticker": ticker, "status_market": s1, "status_book": s2, "market_status": m.get("status"),
             "title": m.get("title"), "yes_sub_title": m.get("yes_sub_title"), "floor_strike": m.get("floor_strike"),
             "market_fields": {k: m.get(k) for k in sorted(m) if any(t in k for t in ("bid", "ask", "size", "price", "fee"))},
             "book_keys": sorted(book.keys()) if isinstance(book, dict) else str(ob)[:200],
             "book_levels": {"yes": yes[:5], "no": no[:5]}, "ask_from_book": ask_from_book, "qty_at_ask": qty_at_ask,
             "openmarkets": []}
        for q in quotes:
            side, p, a = q["side"], num(q["price"]), num(q["available"])
            mk_ask = num(m.get("yes_ask_dollars" if side == "over" else "no_ask_dollars"))
            c["openmarkets"].append({"side": side, "line": q["line"], "price": p, "available": a,
                                     "market_ask": mk_ask, "book_ask": ask_from_book[side],
                                     "price_eq_market_ask": p is not None and mk_ask is not None and abs(p - mk_ask) < 1e-9,
                                     "price_eq_book_ask": p is not None and ask_from_book[side] is not None and abs(p - ask_from_book[side]) < 1e-9,
                                     "qty_at_ask": qty_at_ask[side],
                                     "available_over_qty": round(a / qty_at_ask[side], 4) if a and qty_at_ask[side] else None,
                                     "available_over_qty_x_price": round(a / (qty_at_ask[side] * p), 4) if a and p and qty_at_ask[side] else None})
        checks.append(c)
    res["markets"] = checks
    sides = [o for c in checks for o in c["openmarkets"]]
    res["summary"] = {"sides": len(sides),
                      "price_eq_market_ask": sum(o["price_eq_market_ask"] for o in sides),
                      "price_eq_book_ask": sum(o["price_eq_book_ask"] for o in sides),
                      "available_eq_qty": sum(1 for o in sides if o["available_over_qty"] and abs(o["available_over_qty"] - 1) < 0.01),
                      "available_eq_qty_x_price": sum(1 for o in sides if o["available_over_qty_x_price"]
                                                      and abs(o["available_over_qty_x_price"] - 1) < 0.01)}

    # rate limit without a key: 30 back-to-back requests
    burst = [get(base, "/markets", pause=0.0, limit=1, series_ticker="KXNFLGAME")[:2] for _ in range(30)]
    res["burst"] = {"statuses": [b[0] for b in burst], "headers_seen": [b[1] for b in burst if b[1]][:5]}

    (out_dir / "probe.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("base", "fee_types_sports", "openmarkets", "fee_packet_check", "summary")}, indent=1))
    print(json.dumps(res["nfl_series"], indent=1)[:4000])
    print("burst:", res["burst"]["statuses"])


if __name__ == "__main__":
    main()
