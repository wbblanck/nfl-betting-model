"""Scan the odds endpoints listed by github.com/pseudo-r/Public-ESPN-API for NFL player-prop PRICES (evidence only).

The 2026-10-08 dump (docs/evidence/espn_props/20261008T033457Z) found DraftKings (provider 100) prop LINES for every
2026 week-5 game but no over/under prices. This scans the other routes that repo documents: other provider ids
addressed directly, provider/casino lists, line-movement history, the v3 odds/bets routes, the site summary
(pickcenter) and the cdn game package. For each: HTTP status, size, item count, and whether the body holds
player-prop price fields (an item with an athlete and an over/under American price).

Writes docs/evidence/espn_scan/<UTC stamp>/summary.json plus trimmed samples.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from espn_probe import CORE, get, trim  # noqa: E402

LG = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
V3 = "https://sports.core.api.espn.com/v3"
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
CDN = "https://cdn.espn.com/core/nfl"
PROVIDERS = ["100", "41", "37", "38", "58", "68", "2000", "40", "43", "1002", "1004", "200"]


def price_props(o) -> int:
    """Count dicts that carry an athlete ref and an over/under American price anywhere beneath them."""
    n = 0
    if isinstance(o, dict):
        s = json.dumps(o)
        if "athlete" in o and re.search(r'"(over|under)"\s*:\s*\{[^{}]*"american"', s):
            return 1
        for v in o.values():
            n += price_props(v)
    elif isinstance(o, list):
        for v in o:
            n += price_props(v)
    return n


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/espn_scan") / stamp
    out.mkdir(parents=True, exist_ok=True)
    st, ev, _ = get(f"{CORE}/seasons/2026/types/2/weeks/5/events?limit=50")
    eids = [re.search(r"events/(\d+)", r["$ref"]).group(1) for r in (ev or {}).get("items", [])]
    e = eids[0]
    comp = f"{LG}/events/{e}/competitions/{e}"
    urls = {
        "providers": f"{LG}/providers?limit=200",
        "casinos": f"{LG}/casinos?limit=200",
        "odds_list": f"{comp}/odds?limit=100",
        "odds_list_prio0": f"{comp}/odds?limit=100&provider.priority=0",
        "odds_list_prio2": f"{comp}/odds?limit=100&provider.priority=2",
        "v3_odds": f"{V3}/sports/football/nfl/odds?event={e}",
        "v3_odds_plain": f"{V3}/sports/football/nfl/odds",
        "v3_predictions": f"{V3}/sports/football/nfl/predictions?event={e}",
        "v3_bets_featured": f"{V3}/bets/featured?sport=football&league=nfl",
        "v3_bets_trending": f"{V3}/bets/trending?sport=football&league=nfl",
        "v3_bets_market_props": f"{V3}/bets/markets/player-props?sport=football&league=nfl&event={e}",
        "site_summary": f"{SITE}/summary?event={e}",
        "cdn_game": f"{CDN}/game?xhr=1&gameId={e}",
    }
    for p in PROVIDERS:
        urls[f"odds_{p}"] = f"{comp}/odds/{p}"
        urls[f"props_{p}"] = f"{comp}/odds/{p}/propBets?limit=1000"
    for bt in ["0", "1", "2", "8", "11"]:
        urls[f"movement_100_bt{bt}"] = f"{comp}/odds/100/history/{bt}/movement?limit=100"
    urls["odds_100_predictors"] = f"{comp}/odds/100/predictors"
    urls["odds_100_h2h"] = f"{comp}/odds/100/head-to-heads"

    res = {}
    for name, u in urls.items():
        status, body, n = get(u)
        r = {"url": u, "status": status, "bytes": n}
        if isinstance(body, (dict, list)):
            r["count"] = body.get("count") if isinstance(body, dict) else len(body)
            r["top_keys"] = sorted(body.keys())[:40] if isinstance(body, dict) else None
            r["price_props"] = price_props(body)
            r["has_american"] = '"american"' in json.dumps(body)
            (out / f"{name}.json").write_text(json.dumps(trim(body), indent=1)[:200_000])
        res[name] = r
        print(f"{name:24s} {status} {n:8d}B count={r.get('count')} price_props={r.get('price_props')}", flush=True)
    (out / "summary.json").write_text(json.dumps({"stamp": stamp, "event": e, "events": eids, "results": res}, indent=1,
                                                 default=str))


if __name__ == "__main__":
    main()
