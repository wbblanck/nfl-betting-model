"""Download the nflverse files the game simulator scripts read into a cache directory:
pbp_<season>.parquet (2015-2025), schedules, injuries, snaps, players.

Usage: python scripts/gamesim_cache.py <cache dir>"""
from __future__ import annotations

import sys
from pathlib import Path

import nflreadpy as nfl

SEASONS = list(range(2015, 2026))


def main(d):
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    for s in SEASONS:
        f = p / f"pbp_{s}.parquet"
        if not f.exists():
            nfl.load_pbp(seasons=[s]).write_parquet(f)
            print("pbp", s, flush=True)
    nfl.load_schedules(seasons=list(range(1999, 2027))).write_parquet(p / "schedules.parquet")
    nfl.load_injuries(seasons=SEASONS).write_parquet(p / "injuries.parquet")
    nfl.load_snap_counts(seasons=SEASONS).write_parquet(p / "snaps.parquet")
    nfl.load_players().write_parquet(p / "players.parquet")
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
