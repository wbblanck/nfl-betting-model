"""Check the direct Kalshi read (src/nflbet/sources/venues.py ks_markets / ks_quotes) before it counts in the best-price record.

1. Parsing: how many open markets of the S1 prop series parse to (game, player, market, line); the line must equal the
   market's floor_strike; unparsed examples are saved.
2. Matching, against OpenMarkets as an answer key: OpenMarkets names the Kalshi ticker (`buy_id`) of every Kalshi
   quote it carries. For each such quote, the direct read must find the same (game, player, market, line) with that
   ticker; its price must equal the direct ask on that side and its size the direct size (both read within ~2 min).
3. How often Kalshi would be cheapest: Kalshi's all-in cost (ask + M x 0.07 x p(1-p)) against DraftKings and FanDuel
   at the same line and side, from the latest committed ParlayAPI snapshot (data/live/parlay/; its time is reported:
   the gap means this is indicative only), counting only sides with at least $10 behind the Kalshi price.
Writes docs/evidence/kalshi_direct_check/<stamp>/check.json and kalshi_quotes.json.gz.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")
from nflbet.sources import openmarkets as Om  # noqa: E402
from nflbet.sources import parlay as Pa  # noqa: E402
from nflbet.sources import venues as V  # noqa: E402
from nflbet.props.bestprice import MIN_SIZE, imp  # noqa: E402
from nflbet.props.core import norm_name  # noqa: E402


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"docs/evidence/kalshi_direct_check/{stamp}")
    out.mkdir(parents=True, exist_ok=True)
    res: dict = {"stamp": stamp}

    mk = V.ks_markets()
    ksq = V.ks_quotes(mk)
    res["kalshi_read_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_ticker = {q["ticker"]: k for k, q in ksq.items()}
    unparsed = [m for m in mk if m.get("ticker") not in by_ticker]
    strike_bad = [m["ticker"] for m in mk if m.get("ticker") in by_ticker and m.get("floor_strike") is not None
                  and abs(float(m["floor_strike"]) - by_ticker[m["ticker"]][3]) > 1e-9]
    res["parse"] = {"open_markets": len(mk), "parsed": len(ksq), "unparsed": len(unparsed),
                    "duplicate_keys": len(mk) - len(unparsed) - len(ksq),
                    "by_series": {s: sum(1 for m in mk if m["_series"] == s) for s in V.KS_SERIES},
                    "fee": sorted({f"{m['_fee_type']}|{m['_mult']}" for m in mk}),
                    "floor_strike_mismatch": len(strike_bad), "floor_strike_examples": strike_bad[:5],
                    "unparsed_examples": [{k: m.get(k) for k in ("ticker", "yes_sub_title", "title", "status")} for m in unparsed[:15]]}

    # 2. OpenMarkets as an answer key
    rows = Om.fetch(now=now, days=8, spreads=False)
    res["openmarkets_read_utc"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    n = {"quotes": 0, "om_key_unparsed": 0, "key_found": 0, "ticker_same": 0, "ticker_other": 0, "ticker_not_in_direct": 0,
         "price_same": 0, "size_same": 0, "compared": 0}
    misses, diffs = [], []
    for r in rows:
        g, mkey = Om._teams(r.get("contest_title")), Om.MARKETS.get(r.get("market_key"))
        name = re.split(r"\s+(?:over|under)\s+", r.get("title") or "")[0].strip()
        for v in r.get("partner_liquidities") or []:
            if v.get("partner_name") != "Kalshi" or not v.get("buy_id") or r.get("side_key") not in ("over", "under"):
                continue
            n["quotes"] += 1
            if not (g and mkey and r.get("variable") not in (None, "")):
                n["om_key_unparsed"] += 1
                continue
            key = (g, norm_name(name), mkey, float(r["variable"]))
            q = ksq.get(key)
            if q is None:
                n["ticker_not_in_direct" if v["buy_id"] not in by_ticker else "ticker_other"] += 1
                if len(misses) < 15:
                    misses.append({"om_key": list(key), "om_ticker": v["buy_id"], "direct_key_for_ticker": list(by_ticker.get(v["buy_id"], ()))})
                continue
            n["key_found"] += 1
            if q["ticker"] != v["buy_id"]:
                n["ticker_other"] += 1
                if len(misses) < 15:
                    misses.append({"om_key": list(key), "om_ticker": v["buy_id"], "direct_ticker": q["ticker"]})
                continue
            n["ticker_same"] += 1
            side = q[r["side_key"]]
            if side is None or v.get("price") is None:
                continue
            n["compared"] += 1
            ps, ss = abs(side[0] - float(v["price"])) < 1e-9, abs((side[1] or 0) - float(v.get("available") or 0)) < 0.01
            n["price_same"] += ps
            n["size_same"] += ss
            if not (ps and ss) and len(diffs) < 15:
                diffs.append({"ticker": q["ticker"], "side": r["side_key"], "direct": side, "om": [v.get("price"), v.get("available")]})
    res["vs_openmarkets"] = {**n, "misses": misses, "price_or_size_diffs": diffs}

    # 3. How often Kalshi would be cheapest vs DK / FD (latest committed ParlayAPI snapshot)
    snaps = sorted(Path(os.environ.get("PARLAY_DIR", "data/live/parlay")).glob("*.json.gz"))
    if snaps:
        book = Pa.parse(json.load(gzip.open(snaps[-1], "rt")))
        idx = {(r["book"], r["game"], r["nkey"], r["market"], r["line"]): r for r in book.iter_rows(named=True)}
        cmp = {"snapshot": snaps[-1].name, "sides": 0, "kalshi_cheapest": 0, "cents": []}
        for (g, nk, mkey, line), q in ksq.items():
            if q["mult"] is None:
                continue
            for side in ("over", "under"):
                s = q[side]
                if not s or (s[1] or 0) < MIN_SIZE:
                    continue
                books = [imp(b[side]) for b in (idx.get((bk, g, nk, mkey, line)) for bk in ("dk", "fd")) if b and b[side] is not None]
                if not books:
                    continue
                cost = s[0] + V.ks_fee(s[0], q["mult"])
                cmp["sides"] += 1
                cmp["cents"].append(round((min(books) - cost) * 100, 2))
                cmp["kalshi_cheapest"] += cost < min(books)
        c = sorted(cmp.pop("cents"))
        cmp["edge_cents_vs_best_book"] = {"median": c[len(c) // 2] if c else None, "p10": c[len(c) // 10] if c else None,
                                          "p90": c[9 * len(c) // 10] if c else None,
                                          "over_10c": sum(1 for x in c if x > 10)}
        res["vs_books"] = cmp
    with gzip.open(out / "kalshi_quotes.json.gz", "wt") as fh:
        json.dump([[list(k), q] for k, q in ksq.items()], fh)
    (out / "check.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != "vs_openmarkets"}, indent=1, default=str)[:4000])
    print(json.dumps({k: v for k, v in res["vs_openmarkets"].items() if not isinstance(v, list)}, indent=1))


if __name__ == "__main__":
    main()
