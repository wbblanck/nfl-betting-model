"""SportsGameOdds post-game closes (docs/sgo_closes.md). Record only, unvalidated; never feeds a pick or a test.

  python scripts/fetch/sgo_closes.py run [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--max 60]

Fetches finalized NFL games that started after the newest game already saved (or --since) and before --until
(default: now), one object per game, and writes one gzipped CSV per game under data/live/sgo/<season>/ plus a row in
data/live/sgo/events_<season>.csv. Stops if fewer than RESERVE objects would be left this month.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import sys

import polars as pl

from nflbet import config
from nflbet.sources import sgo

SEASON = 2026
SEASON_START = "2026-09-09"
OUT = config.ROOT / "data" / "live" / "sgo"
INDEX = OUT / f"events_{SEASON}.csv"
RESERVE = 300                     # objects kept back each month for checks and reruns


def _index() -> pl.DataFrame:
    if INDEX.exists():
        return pl.read_csv(INDEX, infer_schema_length=0)
    return pl.DataFrame(schema={c: pl.Utf8 for c in ("event_id", "starts_at", "season_week", "away", "home", "rows",
                                                     "rows_with_close", "file", "fetched_utc")})


def run(since: str | None, until: str | None, max_events: int) -> int:
    idx = _index()
    have = set(idx["event_id"].to_list())
    after = since or (max(idx["starts_at"].to_list())[:10] if idx.height else SEASON_START)
    before = until or (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    left = sgo.objects_left()
    budget = max_events if left is None else min(max_events, left - RESERVE)
    print(f"window {after} .. {before}; objects left this month: {left}; budget {budget}")
    if budget <= 0:
        print("budget exhausted; nothing fetched"); return 0
    evs = sgo.finalized_events(after, before, budget)
    new = []
    (OUT / str(SEASON)).mkdir(parents=True, exist_ok=True)
    for ev in evs:
        eid = ev.get("eventID")
        if not eid or eid in have:
            continue
        d = sgo.parse_event(ev)
        if not d.height:
            print(f"{eid}: no full-game odds; skipped"); continue
        r = d.row(0, named=True)
        name = f"{r['starts_at'][:10].replace('-', '')}_{r['away'] or 'UNK'}_{r['home'] or 'UNK'}_{eid}.csv.gz"
        path = OUT / str(SEASON) / name
        with path.open("wb") as f:
            with gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as g:
                d.write_csv(g)
        new.append({"event_id": eid, "starts_at": r["starts_at"], "season_week": r["season_week"], "away": r["away"],
                    "home": r["home"], "rows": str(d.height), "rows_with_close": str(d["close_odds"].is_not_null().sum()),
                    "file": str(path.relative_to(config.ROOT)),
                    "fetched_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        have.add(eid)
        print(f"{r['starts_at']} {r['away']} @ {r['home']} ({r['season_week']}): {d.height} rows, "
              f"{new[-1]['rows_with_close']} with a close")
    if new:
        idx = pl.concat([idx, pl.DataFrame(new, schema={c: pl.Utf8 for c in idx.columns})]).sort("starts_at")
        INDEX.parent.mkdir(parents=True, exist_ok=True)
        idx.write_csv(INDEX)
    print(f"{len(new)} new game(s) saved; {len(evs)} object(s) used")
    return len(new)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args()
    run(a.since, a.until, a.max)


if __name__ == "__main__":
    sys.exit(main())
