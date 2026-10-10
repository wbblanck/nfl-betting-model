"""Polymarket US gateway (https://gateway.polymarket.us): public, read-only probe (evidence only).

Saves the API description if the gateway serves one, then tries the likely public market and event listing paths and
records status, headers and the first fields of each response. No orders, no account calls. A key, if set in
POLYMARKET_US_API_KEY, is sent only as a request header and never written to disk.
Writes docs/evidence/polymarket_us/<stamp>/summary.json and the first 30 KB of each response.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://gateway.polymarket.us"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
PATHS = ["/", "/openapi.json", "/swagger.json", "/docs", "/api-docs", "/v1", "/v1/sports", "/v1/leagues", "/v1/markets?limit=3",
         "/v1/events?limit=3", "/v1/markets/search?query=NFL", "/v1/sports/nfl", "/v1/nfl/markets?limit=3", "/v1/series",
         "/v1/tags", "/v1/markets/active?limit=3", "/v1/public/markets?limit=3", "/markets?limit=3", "/events?limit=3"]


def get(url: str):
    time.sleep(0.8)
    headers = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.8"}
    key = os.environ.get("POLYMARKET_US_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as r:
            return r.status, dict(r.headers.items()), r.read(60_000_000)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers.items()) if e.headers else {}, e.read(20_000)
    except Exception as e:  # noqa: BLE001
        return str(e)[:150], {}, b""


def shape(body: bytes):
    try:
        j = json.loads(body)
    except ValueError:
        return {"text_head": body[:300].decode("utf-8", "replace")}
    if isinstance(j, dict):
        return {"keys": sorted(j.keys())[:30], "sample": json.dumps(j)[:800]}
    if isinstance(j, list):
        return {"n": len(j), "first": json.dumps(j[0])[:800] if j else None}
    return {"value": str(j)[:300]}


ALL_NFL: list = []


def nfl_markets(out, s):
    """Page through /v1/markets, keep NFL markets with a game start in the next 8 days, count their types."""
    import collections
    now = dt.datetime.now(dt.timezone.utc)
    kept, offset, seen = [], 0, 0
    while offset < 60000:
        st, hdr, body = get(f"{BASE}/v1/markets?limit=500&offset={offset}")
        s.setdefault("pages", []).append({"offset": offset, "status": st, "bytes": len(body)})
        if st != 200:
            s["markets_paging_error"] = {"offset": offset, "status": st}
            break
        try:
            page = json.loads(body).get("markets", [])
        except ValueError as e:
            s["markets_paging_error"] = {"offset": offset, "parse": str(e)[:120], "bytes": len(body)}
            break
        if not page:
            break
        seen += len(page)
        for m in page:
            blob = json.dumps(m).lower()
            if '"nfl"' in blob or " nfl" in blob or "-nfl-" in (m.get("slug") or ""):
                ALL_NFL.append(m)
                try:
                    t = dt.datetime.fromisoformat((m.get("gameStartTime") or m.get("startDate") or "").replace("Z", "+00:00"))
                except ValueError:
                    t = None
                if t and now - dt.timedelta(hours=4) <= t <= now + dt.timedelta(days=8):
                    kept.append(m)
        offset += len(page)
    s["markets_scanned"] = seen
    import collections as _c
    nfl_any = _c.Counter()
    nfl_sample = []
    now2 = now
    for m in ALL_NFL:
        t = (m.get("gameStartTime") or m.get("startDate") or "")[:7]
        nfl_any[t] += 1
        if t.startswith("2026-1") and len(nfl_sample) < 40:
            nfl_sample.append({k: m.get(k) for k in ("slug", "question", "marketType", "sportsMarketType", "gameStartTime", "active", "closed")})
    s["nfl_markets_any_date_by_month"] = sorted(nfl_any.items())
    s["nfl_2026_10_sample"] = nfl_sample
    s["nfl_this_week_markets"] = len(kept)
    s["types"] = collections.Counter(m.get("sportsMarketType") or m.get("marketType") for m in kept).most_common()
    s["examples"] = [{k: m.get(k) for k in ("id", "slug", "question", "marketType", "sportsMarketType", "gameStartTime", "active", "closed")}
                     | {"sides": [{"d": x.get("description"), "price": x.get("price"), "long": x.get("long"),
                                   "line": x.get("line"), "team": (x.get("team") or {}).get("abbreviation")}
                                  for x in (m.get("marketSides") or [])][:4]} for m in kept[:12]]
    (out / "nfl_this_week_markets.json").write_text(json.dumps(kept, indent=1)[:3_000_000])


def nfl_events(out, s):
    """Page through /v1/events and keep NFL events whose start is in the next 8 days, with their market questions."""
    import collections
    now = dt.datetime.now(dt.timezone.utc)
    kept, offset, seen, nfl_all = [], 0, 0, collections.Counter()
    while offset < 40000:
        st, hdr, body = get(f"{BASE}/v1/events?limit=500&offset={offset}")
        if st != 200:
            s["events_paging_error"] = {"offset": offset, "status": st}
            break
        try:
            page = json.loads(body).get("events", [])
        except ValueError as e:
            s["events_paging_error"] = {"offset": offset, "parse": str(e)[:120]}
            break
        if not page:
            break
        seen += len(page)
        for e in page:
            blob = json.dumps(e).lower()
            if '"nfl"' in blob or " nfl" in blob or "-nfl-" in (e.get("slug") or ""):
                st_ = (e.get("startDate") or e.get("gameStartTime") or "")[:7]
                nfl_all[st_] += 1
                try:
                    t = dt.datetime.fromisoformat((e.get("startDate") or e.get("gameStartTime") or "").replace("Z", "+00:00"))
                except ValueError:
                    t = None
                if t and now - dt.timedelta(hours=4) <= t <= now + dt.timedelta(days=8):
                    kept.append({"title": e.get("title"), "slug": e.get("slug"), "start": e.get("startDate"),
                                 "markets": [m.get("question") for m in (e.get("markets") or [])][:40]})
        offset += len(page)
    s["events_scanned"] = seen
    s["nfl_events_by_month"] = sorted(nfl_all.items())
    s["nfl_events_this_week"] = kept[:60]
    (out / "nfl_events_this_week.json").write_text(json.dumps(kept, indent=1)[:3_000_000])


def series_and_search(out, s):
    """The docs list Series (e.g. 'NFL 2025-26 Season'), Sports (schedules) and Search. Save the NFL series, then search
    for this week's games and props and record what each returns."""
    st, hdr, body = get(f"{BASE}/v1/series?limit=500")
    try:
        ser = json.loads(body).get("series", [])
    except ValueError:
        ser = []
    nfl = [x for x in ser if "nfl" in json.dumps(x).lower()]
    s["nfl_series"] = [{k: x.get(k) for k in ("id", "slug", "title", "ticker", "startDate", "endDate", "active", "closed", "recurrence")} for x in nfl][:40]
    s["nfl_series_status"] = st
    for q in ("Bears Packers", "Eagles Jaguars", "Josh Downs receptions", "Jalen Hurts passing yards", "NFL Week 5"):
        st2, _, b2 = get(f"{BASE}/v1/search?query={urllib.parse.quote(q)}&limit=20")
        try:
            j = json.loads(b2)
            keys = sorted(j.keys())
            evs = j.get("events") or j.get("results") or []
            s[f"search_{q}"] = {"status": st2, "keys": keys, "n": len(evs),
                                "titles": [e.get("title") for e in evs[:10]]}
        except ValueError:
            s[f"search_{q}"] = {"status": st2, "text": b2[:200].decode("utf-8", "replace")}
    for sid in [x.get("id") for x in nfl if x.get("id")][:3]:
        st3, _, b3 = get(f"{BASE}/v1/events?limit=100&seriesId={sid}")
        try:
            evs = json.loads(b3).get("events", [])
            s[f"series_{sid}_events"] = {"status": st3, "n": len(evs),
                                         "titles": [(e.get("title"), e.get("startDate")) for e in evs[:15]]}
        except ValueError:
            s[f"series_{sid}_events"] = {"status": st3}


def main():
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/polymarket_us") / stamp
    out.mkdir(parents=True, exist_ok=True)
    s = {"stamp": stamp, "key_sent": bool(os.environ.get("POLYMARKET_US_API_KEY")), "results": []}
    for p in PATHS:
        st, hdr, body = get(BASE + p)
        rec = {"path": p, "status": st, "content_type": hdr.get("Content-Type", hdr.get("content-type")), "bytes": len(body),
               "www_auth": hdr.get("WWW-Authenticate", hdr.get("www-authenticate")), **shape(body)}
        s["results"].append(rec)
        name = p.strip("/").replace("/", "_").replace("?", "_").replace("=", "_").replace("&", "_") or "root"
        (out / f"{name[:80]}.txt").write_bytes(body[:30000])   # full bodies are parsed in memory above
        print(p, st, len(body), rec.get("keys", rec.get("first", rec.get("text_head", "")))[:200] if rec.get("keys") or rec.get("first") else rec.get("text_head", "")[:120], flush=True)
    nfl_markets(out, s)
    nfl_events(out, s)
    series_and_search(out, s)
    (out / "summary.json").write_text(json.dumps(s, indent=1, default=str))


if __name__ == "__main__":
    main()
