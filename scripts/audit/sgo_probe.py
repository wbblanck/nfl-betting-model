"""SportsGameOdds probe (evidence only): what Will's key can see, and what one NFL event costs.

Not analysed for any question; a schema/coverage check. Calls (about 8 requests, a handful of objects):
  1. /account/usage before and after (plan limits, objects used);
  2. one upcoming NFL event (books and prop markets the key sees, any `notice` about filtered data);
  3. one finalized NFL event from last week, 2025, 2024 and 2022 with includeOpenCloseOdds=true
     (is history reachable on this plan, and do per-book open/close fields come back?).
Also saves the public docs (llms-full.txt and the /events parameter list from openapi.json).
The workflow passes candidate secret names as K_<name>; the first one set is used. Its value is never written.
Writes docs/evidence/sgo_probe/<UTC stamp>/.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.sportsgameodds.com/v2/"
ROOT = Path(__file__).resolve().parents[2]
UA = "nfl-betting-model/1.0 (read-only research)"
# The repo and its Actions logs are public: no account email may be written or printed.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def find_key() -> tuple[str, str]:
    set_ = [(k[2:], v) for k, v in sorted(os.environ.items()) if k.startswith("K_") and v]
    print("candidate secrets set:", [n for n, _ in set_], flush=True)
    if not set_:
        sys.exit("none of the candidate SportsGameOdds secret names is set")
    return set_[0]


def get(url: str, key: str | None = None, raw: bool = False):
    h = {"user-agent": UA, "accept": "application/json"}
    if key:
        h["x-api-key"] = key
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read()
            hdr = {k.lower(): v for k, v in r.headers.items() if "limit" in k.lower() or "remaining" in k.lower()}
            return r.status, hdr, body if raw else json.loads(body)
    except urllib.error.HTTPError as e:
        return e.code, {}, e.read().decode(errors="replace")[:3000]


def redact(obj):
    if isinstance(obj, dict):
        return {k: ("<redacted>" if k in ("keyID", "customerID", "apiKey", "email") else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str) and EMAIL.search(obj):
        return EMAIL.sub("<redacted-email>", obj)
    return obj


def summarize_event(ev: dict) -> dict:
    odds = ev.get("odds") or {}
    books = collections.Counter()
    field_by_book = collections.Counter()
    stat_kinds = collections.Counter()
    prop = 0
    with_close = 0
    for oid, o in odds.items():
        ent = o.get("statEntityID", "")
        if ent not in ("home", "away", "all"):
            prop += 1
            stat_kinds[o.get("statID")] += 1
        for b, bo in (o.get("byBookmaker") or {}).items():
            books[b] += 1
            for f in bo:
                field_by_book[f] += 1
            if "closeOdds" in bo:
                with_close += 1
    return {"eventID": ev.get("eventID"), "startsAt": (ev.get("status") or {}).get("startsAt"),
            "teams": [((ev.get("teams") or {}).get(s) or {}).get("teamID") for s in ("away", "home")],
            "finalized": (ev.get("status") or {}).get("finalized"), "n_oddIDs": len(odds),
            "n_player_prop_oddIDs": prop, "prop_stats": dict(stat_kinds.most_common(40)),
            "bookmakers": dict(books.most_common()), "byBookmaker_fields": dict(field_by_book),
            "book_quotes_with_closeOdds": with_close,
            "sample_prop": next(({k: v for k, v in odds.items() if k == oid} for oid, o in odds.items()
                                 if o.get("statEntityID") not in ("home", "away", "all")), None)}


def main() -> None:
    name, key = find_key()
    print("using secret:", name, flush=True)
    out = ROOT / "docs" / "evidence" / "sgo_probe" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    log: dict = {"secret_name": name}

    # public docs (no key)
    s, _, body = get("https://sportsgameodds.com/docs/llms-full.txt", raw=True)
    if s == 200:
        (out / "llms-full.txt").write_bytes(body)
    s, _, body = get("https://sportsgameodds.com/openapi.json", raw=True)
    if s == 200:
        spec = json.loads(body)
        ev = (spec.get("paths") or {}).get("/events/") or (spec.get("paths") or {}).get("/events") or {}
        (out / "openapi_events_get.json").write_text(json.dumps(ev.get("get", ev), indent=1)[:400_000])
        (out / "openapi_paths.txt").write_text("\n".join(sorted(spec.get("paths", {}))))
    log["docs_saved"] = sorted(p.name for p in out.iterdir())

    calls = [("usage_before", "account/usage", {})]
    base = {"leagueID": "NFL", "limit": 1}
    calls.append(("upcoming", "events", {**base, "oddsAvailable": "true", "includeOpenCloseOdds": "true"}))
    for tag, a, b in [("last_week", "2026-11-13", "2026-11-18"), ("y2025", "2025-11-06", "2025-11-11"),
                      ("y2024", "2024-11-07", "2024-11-12"), ("y2022", "2022-11-10", "2022-11-15")]:
        calls.append((f"final_{tag}", "events", {**base, "finalized": "true", "startsAfter": a,
                                                  "startsBefore": b, "includeOpenCloseOdds": "true"}))
    calls.append(("usage_after", "account/usage", {}))

    for tag, path, params in calls:
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        status, hdr, body = get(url, key)
        body = redact(body)
        (out / f"{tag}.json").write_text(json.dumps({"status": status, "params": params, "headers": hdr,
                                                     "body": body}, indent=1)[:5_000_000])
        entry: dict = {"status": status, "params": params, "headers": hdr}
        if isinstance(body, dict):
            entry["notice"] = body.get("notice")
            data = body.get("data")
            if path == "events" and isinstance(data, list):
                entry["n_events"] = len(data)
                entry["events"] = [summarize_event(e) for e in data]
            elif path == "account/usage":
                entry["usage"] = data
            if not body.get("success", True):
                entry["error"] = body
        else:
            entry["error"] = body
        log[tag] = entry
        print(tag, status, entry.get("notice"), flush=True)
        time.sleep(7)  # free plan: 10 requests a minute
    (out / "summary.json").write_text(json.dumps(log, indent=1, default=str))
    print(json.dumps(log, indent=1, default=str)[:30000])


if __name__ == "__main__":
    main()
