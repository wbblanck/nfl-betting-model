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
            return r.status, dict(r.headers.items()), r.read(200_000)
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
        (out / f"{name[:80]}.txt").write_bytes(body[:30000])
        print(p, st, len(body), rec.get("keys", rec.get("first", rec.get("text_head", "")))[:200] if rec.get("keys") or rec.get("first") else rec.get("text_head", "")[:120], flush=True)
    (out / "summary.json").write_text(json.dumps(s, indent=1, default=str))


if __name__ == "__main__":
    main()
