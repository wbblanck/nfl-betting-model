"""Free-tier EndzoneAPI spot-check feed: closing player props, every book, for a few random games a week.

  python scripts/fetch/endzone_props.py                       # latest completed 2026 regular-season week
  python scripts/fetch/endzone_props.py --season 2026 --week 9 --games 4

Free tier is 500 credits a month and a game costs 20 (docs/evidence/endzone_estimates), so 4 games a week. Games
are drawn with a seed fixed by season and week (random.Random("endzone-<season>-<week>")), before any line is seen,
so the sample cannot follow the lines. Writes data/live/endzone/<season>_w<week>.csv.gz; reruns skip games already
saved. Stops when fewer than 20 credits remain. Key from ENDZONEAPI_API_KEY, never written. Runs in GitHub Actions.
"""
from __future__ import annotations

import argparse
import gzip
import csv
import io
import json
import os
import random
import sys
import urllib.error
import urllib.request

from nflbet import config

BASE = "https://mcp.endzoneapi.com/v1/"
DIR = config.ROOT / "data" / "live" / "endzone"
COST = 20
FIELDS = ["game_id", "player_name", "gsis_id", "market", "bookmaker", "line", "over_odds", "under_odds",
          "captured_at", "scheduled_start", "minutes_before_scheduled_start", "source"]


def pick(game_ids: list[str], season: int, week: int, k: int) -> list[str]:
    ids = sorted(game_ids)
    return sorted(random.Random(f"endzone-{season}-{week}").sample(ids, min(k, len(ids))))


def latest_completed_week(sched: list[dict]) -> int | None:
    weeks: dict[int, list] = {}
    for g in sched:
        weeks.setdefault(int(g["week"]), []).append(g["result"])
    done = [w for w, r in weeks.items() if all(x is not None for x in r)]
    return max(done) if done else None


def call(args: dict) -> tuple[dict, dict]:
    req = urllib.request.Request(BASE + "get_player_props", data=json.dumps(args).encode(), method="POST", headers={
        "x-api-key": os.environ["ENDZONEAPI_API_KEY"], "content-type": "application/json",
        "accept": "application/json", "user-agent": "nfl-betting-model/1.0 (read-only research)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        hdr = {k.lower(): v for k, v in r.headers.items() if k.lower().startswith("x-credit")}
        return hdr, json.loads(r.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int)
    ap.add_argument("--games", type=int, default=4)
    a = ap.parse_args()
    if not os.environ.get("ENDZONEAPI_API_KEY"):
        sys.exit("ENDZONEAPI_API_KEY not set")
    import nflreadpy as nfl
    import polars as pl
    s = nfl.load_schedules(seasons=[a.season]).filter(pl.col("game_type") == "REG")
    sched = s.select("game_id", "week", "result").to_dicts()
    week = a.week or latest_completed_week(sched)
    if week is None:
        sys.exit("no completed week yet")
    ids = [g["game_id"] for g in sched if int(g["week"]) == week and g["result"] is not None]
    chosen = pick(ids, a.season, week, a.games)
    DIR.mkdir(parents=True, exist_ok=True)
    path = DIR / f"{a.season}_w{week:02d}.csv.gz"
    rows: list[dict] = []
    if path.exists():
        rows = list(csv.DictReader(io.TextIOWrapper(gzip.open(path), encoding="utf-8")))
    have = {r["game_id"] for r in rows}
    print(f"{a.season} week {week}: chosen {chosen}, already saved {sorted(have & set(chosen))}", flush=True)
    remaining = None
    for gid in chosen:
        if gid in have:
            continue
        if remaining is not None and remaining < COST:
            print(f"only {remaining} credits left; stopping", flush=True)
            break
        try:
            hdr, body = call({"game_id": gid, "snapshot_type": "closing"})
        except urllib.error.HTTPError as e:
            print(f"{gid}: HTTP {e.code} {e.read()[:300]!r}; stopping", flush=True)
            break
        remaining = int(hdr.get("x-credits-remaining", remaining if remaining is not None else 0))
        props = body.get("data", {}).get("props", [])
        rows += [{k: p.get(k) for k in FIELDS} for p in props]
        print(f"{gid}: {len(props)} rows, credits used {hdr.get('x-credits-used')}, left {remaining}", flush=True)
    if rows:
        buf = io.StringIO()
        w = csv.DictWriter(buf, FIELDS)
        w.writeheader()
        w.writerows(rows)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(buf.getvalue())
        print(path)


if __name__ == "__main__":
    main()
