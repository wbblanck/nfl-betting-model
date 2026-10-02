"""Fetch ESPN BET (provider 58) player props for one regular season from ESPN's core API.

One row per prop record (ESPN files the over and the under as separate records):
  season, week, event_id, athlete_id, type_id, type_name, side, open_line, open_odds, cur_line, cur_odds,
  last_updated
`side` is over / under (records with no price are skipped: milestone and display-only lines).
`last_updated` is when ESPN last touched the record, often after the game (settlement), NOT the price time.
Join to nflverse with athlete_id = nflverse players.espn_id.

Usage: python scripts/fetch/espn_props.py --season 2025 [--weeks 1-18]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
PROVIDER = 58
FIELDS = ["season", "week", "event_id", "athlete_id", "type_id", "type_name", "side", "open_line", "open_odds",
          "cur_line", "cur_odds", "last_updated"]


def get(url: str, pause: float = 0.3, tries: int = 4):
    last = None
    for i in range(tries):
        time.sleep(pause if i == 0 else pause + 2 ** i)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = e.code
            if e.code == 404:
                return None
        except Exception as e:  # noqa: BLE001 - retried, then reported
            last = str(e)[:80]
    print(f"  [fail] {url}: {last}", file=sys.stderr)
    return None


def rows_for(item: dict, season: int, week: int, eid: str) -> dict | None:
    m = re.search(r"athletes/(\d+)", (item.get("athlete") or {}).get("$ref", ""))
    cur, opn = item.get("current") or {}, item.get("open") or {}
    side = "over" if "over" in cur or "over" in opn else ("under" if "under" in cur or "under" in opn else None)
    if not m or side is None:
        return None
    t = item.get("type") or {}
    return {"season": season, "week": week, "event_id": eid, "athlete_id": m.group(1), "type_id": t.get("id"),
            "type_name": t.get("name"), "side": side,
            "open_line": (opn.get("target") or {}).get("value"), "open_odds": (opn.get(side) or {}).get("american"),
            "cur_line": (cur.get("target") or {}).get("value"), "cur_odds": (cur.get(side) or {}).get("american"),
            "last_updated": item.get("lastUpdated")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--weeks", default="1-18")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.weeks.split("-"))
    out = Path(f"data/espn/espn_props_{a.season}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for week in range(lo, hi + 1):
            ev = get(f"{CORE}/seasons/{a.season}/types/2/weeks/{week}/events?limit=50") or {}
            ids = [re.search(r"events/(\d+)", r["$ref"]).group(1) for r in ev.get("items", [])]
            n_week = 0
            for eid in ids:
                page, pages, got = 1, 1, 0
                while page <= pages:
                    b = get(f"{CORE}/events/{eid}/competitions/{eid}/odds/{PROVIDER}/propBets?limit=1000&page={page}")
                    if not b:
                        stats["events_without_props"] += page == 1
                        break
                    pages = b.get("pageCount", 1)
                    for it in b.get("items", []):
                        r = rows_for(it, a.season, week, eid)
                        if r:
                            w.writerow(r)
                            got += 1
                        else:
                            stats["skipped_unpriced_or_no_athlete"] += 1
                    page += 1
                stats["events"] += 1
                n_week += got
            stats["rows"] += n_week
            print(f"week {week:2d}: events {len(ids):2d}, rows {n_week}", flush=True)
    print("SUMMARY", a.season, json.dumps(dict(stats), indent=1))


if __name__ == "__main__":
    main()
