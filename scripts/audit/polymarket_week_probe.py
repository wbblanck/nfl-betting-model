"""Why does the Polymarket US week search miss this week's NFL games? (read-only diagnostic, no key)

Three ways to find this week's game events, each logged with what it returned and why events were dropped:
  A. the free-text search scripts/polymarket_compare.py uses (limit 20),
  B. /v1/events with candidate filter / pagination parameters (the API returns no pagination field, so each variant is
     compared with the unfiltered list to see whether the parameter is honoured),
  C. direct lookup of each scheduled game by its slug, nfl-{away}-{home}-{ET date} (seen in week 5 data; Rams = lar).
Writes docs/evidence/polymarket_week_probe/<stamp>/diag.json and prints a summary.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

PM = "https://gateway.polymarket.us"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
WEEK, SEASON = 6, 2026
REC = re.compile(r"^Will (.+?) record (\d+)\+ (.+?)\?$")
SLUG_CODE = {"LA": "lar"}                    # nflverse -> Polymarket slug code where they differ (others: lower case)
ALT_CODES = {"WAS": ["wsh"], "JAX": ["jac"], "LA": ["la"], "LV": ["lvr"]}


def get(path: str, **q) -> tuple[int, object]:
    url = PM + path + (("?" + urllib.parse.urlencode(q)) if q else "")
    time.sleep(0.3)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, (e.read()[:300].decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001 - logged
        return -1, repr(e)[:300]


def describe(e: dict, now: dt.datetime) -> dict:
    """One event: identity, start, record-market count, and the reason polymarket_compare.fetch_polymarket drops it."""
    start = (e.get("startTime") or e.get("startDate") or "")
    try:
        t = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        t = None
    mk = e.get("markets") or []
    n_rec = sum(1 for m in mk if REC.match(m.get("question") or ""))
    if " vs. " not in (e.get("title") or ""):
        why = "title has no ' vs. '"
    elif t is None:
        why = "no parseable startTime/startDate"
    elif not (now - dt.timedelta(hours=4) <= t <= now + dt.timedelta(days=8)):
        why = "start outside window"
    elif not mk:
        why = "no markets embedded in the event"
    elif not n_rec:
        why = "no 'Will X record N+' markets"
    else:
        why = "kept"
    return {"title": e.get("title"), "slug": e.get("slug"), "series": e.get("seriesSlug"), "start": start,
            "n_markets": len(mk), "n_record": n_rec, "verdict": why}


def schedule() -> list[dict]:
    import nflreadpy as nfl
    import polars as pl

    s = nfl.load_schedules(seasons=[SEASON]).filter(pl.col("game_type") == "REG", pl.col("week") == WEEK)
    out = []
    for r in s.iter_rows(named=True):
        kick = dt.datetime.fromisoformat(f"{r['gameday']}T{r['gametime']}:00").replace(tzinfo=ZoneInfo("America/New_York"))
        out.append({"game_id": r["game_id"], "away": r["away_team"], "home": r["home_team"], "et_date": r["gameday"],
                    "kick_utc": kick.astimezone(dt.timezone.utc).isoformat()})
    return out


def slug_candidates(g: dict) -> list[str]:
    def codes(t):
        return [SLUG_CODE.get(t, t.lower())] + ALT_CODES.get(t, [])
    return [f"nfl-{a}-{h}-{g['et_date']}" for a in codes(g["away"]) for h in codes(g["home"])]


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    out: dict = {"run_utc": now.isoformat(), "week": WEEK}

    # A. the current search
    out["search"] = {}
    for q in (f"NFL Week {WEEK}", f"NFL week {WEEK} props"):
        st, body = get("/v1/search", query=q, limit=20)
        evs = body.get("events", []) if isinstance(body, dict) else []
        out["search"][q] = {"status": st, "n_events": len(evs), "events": [describe(e, now) for e in evs]}

    # B. event listing with candidate parameters
    base = {"limit": 50}
    variants = {"none": {}, "offset=500": {"offset": 500}, "seriesSlug=nfl-2025": {"seriesSlug": "nfl-2025"},
                "series_slug=nfl-2025": {"series_slug": "nfl-2025"},
                "seriesSlug+active+open": {"seriesSlug": "nfl-2025", "active": "true", "closed": "false"},
                "active+open": {"active": "true", "closed": "false"}, "tag=nfl": {"tag": "nfl"},
                "tagSlug=nfl": {"tagSlug": "nfl"}, "league=nfl": {"league": "nfl"},
                "startDateMin=now": {"startDateMin": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
                "order=startTime desc": {"order": "startTime", "ascending": "false"}}
    out["list"] = {}
    for name, extra in variants.items():
        st, body = get("/v1/events", **base, **extra)
        evs = body.get("events", []) if isinstance(body, dict) else []
        d = [describe(e, now) for e in evs]
        out["list"][name] = {"status": st, "n": len(evs), "ids": [e.get("id") for e in evs[:3]] + ["..."] + [e.get("id") for e in evs[-2:]],
                             "first_slugs": [x["slug"] for x in d[:3]], "in_window_nfl": [x for x in d if x["verdict"] != "start outside window" and (x["slug"] or "").startswith("nfl-")][:20],
                             "other_keys": [k for k in body.keys() if k != "events"] if isinstance(body, dict) else body}

    # C. direct slug lookup for each scheduled game
    try:
        games = schedule()
    except Exception as e:  # noqa: BLE001
        games, out["schedule_error"] = [], repr(e)[:300]
    out["slug_lookup"] = []
    endpoints = ["/v1/events/slug/{s}", "/v1/events/{s}", "/v1/event/slug/{s}"]
    working = None
    for g in games:
        rec = {**g, "tries": []}
        for s in slug_candidates(g):
            for ep in ([working] if working else endpoints):
                st, body = get(ep.format(s=s))
                ev = (body.get("event") if isinstance(body, dict) and "event" in body else body) if st == 200 else None
                hit = isinstance(ev, dict) and ev.get("slug") == s
                rec["tries"].append({"endpoint": ep, "slug": s, "status": st, "hit": hit})
                if not hit:
                    st2, body2 = get("/v1/events", slug=s, limit=5)
                    evs = body2.get("events", []) if isinstance(body2, dict) else []
                    m = [e for e in evs if e.get("slug") == s]
                    rec["tries"].append({"endpoint": "/v1/events?slug=", "slug": s, "status": st2, "hit": bool(m), "n": len(evs)})
                    if m:
                        ev, hit = m[0], True
                if hit:
                    working = working or ep
                    rec["found"] = describe(ev, now)
                    break
            if rec.get("found"):
                break
        out["slug_lookup"].append(rec)

    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    p = Path(f"docs/evidence/polymarket_week_probe/{stamp}")
    p.mkdir(parents=True, exist_ok=True)
    (p / "diag.json").write_text(json.dumps(out, indent=1))

    # summary
    for q, r in out["search"].items():
        kept = sum(1 for e in r["events"] if e["verdict"] == "kept")
        print(f"search {q!r}: status {r['status']}, {r['n_events']} events, kept {kept}")
        for e in r["events"]:
            print(f"   {e['verdict']:<32} {e['title']!s:<60} {e['start']}")
    for name, r in out["list"].items():
        print(f"list {name:<24} status {r['status']} n={r['n']} ids={r['ids']} nfl in window={len(r['in_window_nfl'])}")
    print(f"slug lookup: {sum(1 for g in out['slug_lookup'] if g.get('found'))} of {len(out['slug_lookup'])} games found; endpoint {working}")
    for g in out["slug_lookup"]:
        f = g.get("found")
        print(f"   {g['away']}@{g['home']} {g['et_date']}: " + (f"{f['slug']} markets {f['n_markets']} record {f['n_record']} ({f['verdict']})" if f else
                                                         "not found: " + ", ".join(f"{t['endpoint']} {t['slug']} {t['status']}" for t in g["tries"][:4])))
    if "schedule_error" in out:
        print("schedule error:", out["schedule_error"])
    sys.stdout.flush()


if __name__ == "__main__":
    main()
