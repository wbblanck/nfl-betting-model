"""How Polymarket US lists player props across sports (read-only, no key).

For each league slug in LEAGUES: list its events with the documented GET /v2/leagues/{slug}/events, keep the soonest
N_GAMES upcoming ones, fetch each in full with GET /v1/events/slug/{slug} (the search omits player props), and record:
the event fields and title format, every sportsMarketType with counts and sample questions (player-prop types are the
ones containing 'player'), whether sides carry `quote`, whether markets carry bestBidQuote / bestAskQuote, and the
feeCoefficient values. Raw first event of each league is kept for field reference.
Writes docs/evidence/polymarket_sports_probe/<stamp>/probe.json.
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
LEAGUES = ["nfl", "cfb", "nba", "cbb", "wnba", "wcbb", "mlb", "nhl", "ahl", "khl", "epl", "ucl", "lal", "bun", "mls", "atp", "wta",
           "ufc", "pfl", "kbo", "npb", "eurolg", "nbl", "pll", "cs2", "lol"]


def get(path: str):
    time.sleep(0.15)
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(PM + path, headers={"User-Agent": UA}), timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < 3:
                time.sleep(2 ** i)
                continue
            return e.code, e.read()[:300].decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - recorded
            return -1, repr(e)[:300]
    return 429, "throttled"


def start_of(e: dict):
    for k in ("startTime", "startDate", "gameStartTime", "eventDate"):
        v = e.get(k)
        if v:
            try:
                return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            except ValueError:
                pass
    return None


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    out: dict = {"run_utc": now.isoformat(), "leagues": {}}
    for lg in LEAGUES:
        st, body = get(f"/v2/leagues/{lg}/events?limit=50")
        evs = body.get("events", []) if isinstance(body, dict) else []
        dated = sorted(((start_of(e), e) for e in evs if start_of(e) and start_of(e) >= now - dt.timedelta(hours=3)), key=lambda x: x[0])
        rec = {"status": st, "n_events": len(evs), "n_upcoming": len(dated), "event_keys": sorted(evs[0].keys()) if evs else [],
               "titles": [e.get("title") for e in evs[:8]], "games": []}
        types, fees, samples = collections.Counter(), collections.Counter(), {}
        n_mk = n_quote = n_ba = 0
        for t0, e in dated[:N_GAMES]:
            st2, body2 = get(f"/v1/events/slug/{urllib.parse.quote(e.get('slug', ''))}")
            ev = body2.get("event", body2) if st2 == 200 and isinstance(body2, dict) else {}
            mk = ev.get("markets") or []
            rec["games"].append({"slug": e.get("slug"), "title": e.get("title"), "start": t0.isoformat(), "series": ev.get("seriesSlug"),
                                 "status": st2, "n_markets": len(mk)})
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
            if mk and "raw_market_example" not in rec:
                pm = next((m for m in mk if "player" in (m.get("sportsMarketType") or "")), mk[0])
                rec["raw_market_example"] = {k: pm.get(k) for k in ("question", "slug", "sportsMarketType", "marketType", "line",
                                                                     "marketSides", "bestBidQuote", "bestAskQuote", "feeCoefficient")}
        player = {t: n for t, n in types.items() if "player" in t}
        rec.update({"markets": n_mk, "both_sides_quoted": n_quote, "with_best_bid_ask": n_ba, "fee_coefficients": dict(fees),
                    "market_types": dict(types.most_common()), "player_types": player, "samples": samples})
        out["leagues"][lg] = rec
        print(f"{lg:7s} status {st} events {len(evs):3d} upcoming {len(dated):3d} | markets {n_mk:5d} quoted {n_quote:5d} bid/ask {n_ba:5d} "
              f"| fees {dict(fees)} | player-prop types {len(player)} ({sum(player.values())} markets)")
        for g in rec["games"]:
            print(f"        {g['slug']} | {g['title']} | {g['start']} | {g['n_markets']} markets")
        for t, n in sorted(player.items(), key=lambda kv: -kv[1]):
            print(f"        {t:46s} {n:4d}  e.g. {samples[t][0]!r}")
    p = Path(f"docs/evidence/polymarket_sports_probe/{now.strftime('%Y%m%dT%H%M%SZ')}")
    p.mkdir(parents=True, exist_ok=True)
    (p / "probe.json").write_text(json.dumps(out, indent=1))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
