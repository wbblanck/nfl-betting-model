"""How Polymarket US lists player props across sports (read-only, no key).

For each sport in /v1/sports: search its upcoming game events ('X vs. Y' titles), fetch up to N_GAMES of them by slug
(/v1/events/slug/{slug}; the search omits player props), and record per sport: event slug and title formats, the
sportsMarketType values with sample questions, whether sides carry `quote`, whether markets carry
bestBidQuote / bestAskQuote, and the feeCoefficient values. Writes docs/evidence/polymarket_sports_probe/<stamp>/.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PM = "https://gateway.polymarket.us"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
N_GAMES = 3


def get(path: str):
    time.sleep(0.3)
    try:
        with urllib.request.urlopen(urllib.request.Request(PM + path, headers={"User-Agent": UA}), timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - recorded
        return -1, repr(e)[:300]


def sport_names(body) -> list[str]:
    items = body.get("sports", body) if isinstance(body, dict) else body
    names = []
    for s in items if isinstance(items, list) else []:
        if isinstance(s, dict):
            names.append(s.get("name") or s.get("title") or s.get("slug") or s.get("label"))
        else:
            names.append(str(s))
    return [n for n in names if n]


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    out: dict = {"run_utc": now.isoformat()}
    st, body = get("/v1/sports")
    out["sports_status"], out["sports_raw"] = st, body if st == 200 else str(body)[:300]
    sports = sport_names(body) if st == 200 else []
    for extra in ("NFL", "NBA", "WNBA", "MLB", "NHL", "college football", "college basketball", "soccer", "tennis", "golf", "UFC"):
        if extra.lower() not in {s.lower() for s in sports}:
            sports.append(extra)
    out["queried"] = sports
    out["by_sport"] = {}
    for sp in sports:
        st, body = get(f"/v1/search?query={urllib.parse.quote(sp)}&limit=20")
        evs = body.get("events", []) if isinstance(body, dict) else []
        games = []
        for e in evs:
            try:
                t = dt.datetime.fromisoformat((e.get("startTime") or e.get("startDate") or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if " vs" in (e.get("title") or "") and t >= now - dt.timedelta(hours=4) and e.get("slug"):
                games.append(e)
        rec = {"search_status": st, "search_events": len(evs), "games_found": len(games), "games": []}
        types, fees = collections.Counter(), collections.Counter()
        samples: dict = {}
        n_mk = n_quote = n_ba = 0
        for e in games[:N_GAMES]:
            st2, body2 = get(f"/v1/events/slug/{urllib.parse.quote(e['slug'])}")
            ev = body2.get("event", body2) if st2 == 200 and isinstance(body2, dict) else {}
            mk = ev.get("markets") or []
            rec["games"].append({"slug": e["slug"], "title": e.get("title"), "start": e.get("startTime") or e.get("startDate"),
                                 "series": ev.get("seriesSlug"), "status": st2, "n_markets": len(mk)})
            for m in mk:
                t = m.get("sportsMarketType") or m.get("marketType") or "?"
                types[t] += 1
                fees[str(m.get("feeCoefficient"))] += 1
                samples.setdefault(t, [])
                if len(samples[t]) < 3:
                    samples[t].append(m.get("question"))
                n_mk += 1
                sides = m.get("marketSides") or []
                n_quote += bool(sides) and all((s.get("quote") or {}).get("value") not in (None, "") for s in sides)
                n_ba += m.get("bestAskQuote") is not None and m.get("bestBidQuote") is not None
        rec.update({"markets": n_mk, "both_sides_quoted": n_quote, "with_best_bid_ask": n_ba, "fee_coefficients": dict(fees),
                    "market_types": dict(types.most_common()), "samples": samples})
        out["by_sport"][sp] = rec
        print(f"{sp:20s} search {st} events {len(evs):2d} games {len(games):2d} | markets {n_mk:5d} quoted {n_quote:5d} bid/ask {n_ba:5d} "
              f"| fees {dict(fees)} | types {len(types)}")
        for t, n in types.most_common(12):
            print(f"      {t:45s} {n:5d}  e.g. {samples[t][0]!r}")
    p = Path(f"docs/evidence/polymarket_sports_probe/{now.strftime('%Y%m%dT%H%M%SZ')}")
    p.mkdir(parents=True, exist_ok=True)
    (p / "probe.json").write_text(json.dumps(out, indent=1))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
