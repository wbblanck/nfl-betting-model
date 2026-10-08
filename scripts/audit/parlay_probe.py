"""Does ParlayAPI carry NFL player props with two-sided prices, and for which markets and books? (evidence only)

Two requests: the sports list (to find the NFL key), then one props call for it with no market filter (3 credits
on the free tier). The API key is read from PARLAY_API_KEY and never written: URLs are saved with it redacted.

Writes docs/evidence/parlay/<UTC stamp>/summary.json and props.jsonl.gz (rows as returned).
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = "https://parlay-api.com/v1"


def get(path: str, **params):
    key = os.environ["PARLAY_API_KEY"]
    url = f"{ROOT}{path}?" + urllib.parse.urlencode({"apiKey": key, **params})
    shown = url.replace(key, "REDACTED")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nfl-betting-model/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            hdr = {k: v for k, v in r.headers.items() if any(s in k.lower() for s in ("remain", "used", "credit", "limit", "cost"))}
            return shown, r.status, hdr, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return shown, e.code, {}, e.read()[:500].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - record and continue
        return shown, str(e)[:120], {}, None


def main() -> None:
    if not os.environ.get("PARLAY_API_KEY"):
        raise SystemExit("PARLAY_API_KEY not set")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/parlay") / stamp
    out.mkdir(parents=True, exist_ok=True)
    summary = {"stamp": stamp}

    try:
        with urllib.request.urlopen(urllib.request.Request("https://parlay-api.com/openapi.json",
                                    headers={"User-Agent": "nfl-betting-model/1.0"}), timeout=60) as r:
            (out / "openapi.json").write_bytes(r.read())
    except Exception as e:  # noqa: BLE001
        summary["openapi_error"] = str(e)[:120]

    url, st, hdr, body = get("/sports")
    keys = [s.get("key") for s in body if isinstance(s, dict)] if isinstance(body, list) else []
    summary["sports"] = {"url": url, "status": st, "headers": hdr, "keys": keys,
                         "body_head": body if not isinstance(body, list) else None}
    print("sports", st, hdr, keys, flush=True)
    nfl = next((k for k in keys if k and "nfl" in k.lower() and "preseason" not in k.lower()), "americanfootball_nfl")

    url, st, hdr, mk = get(f"/sports/{nfl}/props/markets")
    summary["markets_endpoint"] = {"url": url, "status": st, "headers": hdr, "body": mk}
    params = {"limit": 10000, "oddsFormat": "american"}
    if os.environ.get("PARLAY_BOOKS"):
        params["bookmakers"] = os.environ["PARLAY_BOOKS"]
    if os.environ.get("PARLAY_MARKETS"):
        params["markets"] = os.environ["PARLAY_MARKETS"]
    summary["params"] = params
    url, st, hdr, rows = get(f"/sports/{nfl}/props", **params)
    s = {"sport_key": nfl, "url": url, "status": st, "headers": hdr}
    if isinstance(rows, list):
        s["n_rows"] = len(rows)
        s["fields"] = sorted({k for r in rows[:2000] if isinstance(r, dict) for k in r})
        s["markets"] = collections.Counter(r.get("market") for r in rows).most_common()
        s["books"] = collections.Counter(r.get("bookmaker") for r in rows).most_common()
        two = [r for r in rows if r.get("over_price") not in (None, "") and r.get("under_price") not in (None, "")]
        s["two_sided"] = len(two)
        s["two_sided_by_book"] = collections.Counter(r.get("bookmaker") for r in two).most_common()
        s["games"] = collections.Counter(f"{r.get('away_team')} @ {r.get('home_team')} {r.get('commence_time')}"
                                         for r in rows).most_common()
        s["age_seconds"] = sorted(r.get("age_seconds") for r in rows if isinstance(r.get("age_seconds"), (int, float)))[::max(1, len(rows) // 20)]
        s["samples"] = rows[:5]
        with gzip.open(out / "props.jsonl.gz", "wt") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    else:
        s["body_head"] = rows
    summary["props"] = s
    print("props", nfl, st, hdr, s.get("n_rows"), s.get("two_sided"), flush=True)
    print("markets", s.get("markets"), flush=True)
    print("books", s.get("books"), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
