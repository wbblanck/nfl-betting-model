"""Novig public catalog probe (read-only, no key): what NFL markets exist and how props are described.

For each host (production, then Paper if production refuses): the canonical type lists, this week's NFL events and
markets (counted by marketType, with sample description / outcome names / strike / fee), and the order book of one
sample market per type. Writes docs/evidence/novig_probe/<stamp>/probe.json and prints a summary.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOSTS = {"production": "https://api.novig.com", "paper": "https://api.paper.novig.com"}
UA = "nfl-betting-model/1.0 (read-only research probe)"


def get(host: str, path: str, **q):
    url = host + path + (("?" + urllib.parse.urlencode(q)) if q else "")
    time.sleep(0.4)
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < 3:
                time.sleep(5 * 2 ** i)
                continue
            return e.code, e.read()[:400].decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - recorded
            return -1, repr(e)[:300]
    return 429, "throttled"


def probe(host: str, now: dt.datetime) -> dict:
    out: dict = {"host": host, "types": {}}
    for t in ("sports", "leagues", "markets", "event-statuses"):
        st, body = get(host, f"/v3/public/types/{t}")
        out["types"][t] = {"status": st, "body": body}
    if out["types"]["leagues"]["status"] != 200:
        return out
    leagues = out["types"]["leagues"]["body"]
    nfl = "NFL" if "NFL" in leagues else next((x for x in leagues if "NFL" in str(x).upper()), None)
    out["nfl_league"] = nfl
    lo, hi = int((now - dt.timedelta(hours=6)).timestamp() * 1000), int((now + dt.timedelta(days=8)).timestamp() * 1000)
    st, ev = get(host, "/v3/public/catalog/events", league=nfl, startsAfter=lo, startsBefore=hi, limit=200)
    out["events"] = {"status": st, "items": ev.get("items", []) if isinstance(ev, dict) else ev}
    markets, after, pages = [], None, 0
    while pages < 6:
        q = {"league": nfl, "startsAfter": lo, "startsBefore": hi, "limit": 5000}
        if after:
            q["after"] = after
        st, body = get(host, "/v3/public/catalog/markets", **q)
        pages += 1
        if st != 200 or not isinstance(body, dict):
            out["markets_error"] = {"status": st, "body": body}
            break
        markets += body.get("items", [])
        after = body.get("next")
        if not after:
            break
    by_type = collections.defaultdict(list)
    for m in markets:
        by_type[m.get("marketType")].append(m)
    out["n_markets"] = len(markets)
    out["by_type"] = {}
    for t, ms in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        ex = ms[0]
        out["by_type"][t] = {"n": len(ms), "n_with_strike": sum(1 for m in ms if m.get("strike") not in (None, "")),
                             "fee": ex.get("fee"), "voids": ex.get("voids"),
                             "examples": [{"marketId": m.get("marketId"), "eventId": m.get("eventId"), "description": m.get("description"),
                                           "strike": m.get("strike"), "status": m.get("status"),
                                           "outcomes": [o.get("name") for o in m.get("outcomes", [])]} for m in ms[:4]]}
        st, book = get(host, f"/v3/public/catalog/markets/{ex['marketId']}/book", depth=3)
        names = {o.get("outcomeId"): o.get("name") for o in ex.get("outcomes", [])}
        if st == 200 and isinstance(book, dict):
            out["by_type"][t]["book"] = {names.get(k, k): v for k, v in (book.get("orders") or {}).items()}
        else:
            out["by_type"][t]["book"] = {"status": st, "body": book}
    return out


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    res = {"run_utc": now.isoformat(), "hosts": {}}
    for name, host in HOSTS.items():
        r = probe(host, now)
        res["hosts"][name] = r
        print(f"== {name} {host}: types/leagues status {r['types']['leagues']['status']}, NFL league {r.get('nfl_league')}, "
              f"events {len((r.get('events') or {}).get('items') or [])}, markets {r.get('n_markets')}")
        if r["types"]["markets"]["status"] == 200:
            print("   market types:", r["types"]["markets"]["body"])
        for t, v in (r.get("by_type") or {}).items():
            e = v["examples"][0]
            print(f"   {t:<28} n={v['n']:<5} strike={v['n_with_strike']:<5} fee={v['fee']} | {e['description']!r} {e['outcomes']} strike={e['strike']}")
        if "markets_error" in r:
            print("   markets error:", r["markets_error"])
        if r["types"]["leagues"]["status"] == 200 and r.get("n_markets"):
            break                                   # production answered with data; Paper not needed
    p = Path(f"docs/evidence/novig_probe/{now.strftime('%Y%m%dT%H%M%SZ')}")
    p.mkdir(parents=True, exist_ok=True)
    (p / "probe.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
