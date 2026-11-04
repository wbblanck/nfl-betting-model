"""Game-time wind per outdoor game (docs/wind_totals_preregistration.md). Runs in GitHub Actions.

  python scripts/fetch/game_wind.py --stadiums   # data/weather/stadium_list.csv: ids, names, roof, game counts
  python scripts/fetch/game_wind.py              # data/weather/game_wind.csv: game_id, kickoff_utc, wind_kn

Reads only schedule fields that say where and when a game was played (no scores, no lines). Stops if any sample
game's stadium has no row in data/weather/stadiums.csv.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
import urllib.error
from pathlib import Path

import nflreadpy as nfl
import polars as pl

from nflbet import config
from nflbet.sources import weather

DIR = config.ROOT / "data" / "weather"
SEASONS = list(range(1999, 2027))
COLS = ["game_id", "season", "week", "gameday", "gametime", "stadium_id", "stadium", "roof", "location",
        "home_team"]


def sample_games() -> pl.DataFrame:
    s = nfl.load_schedules(seasons=SEASONS).select(COLS + ["game_type"])
    return s.filter(pl.col("game_type") == "REG", pl.col("location") != "Neutral",
                    pl.col("roof").is_in(["outdoors", "open"])).drop("game_type")


def dump_stadiums(g: pl.DataFrame) -> Path:
    out = (g.group_by("stadium_id").agg(pl.col("stadium").unique().sort().str.join(" | "),
                                        pl.col("home_team").unique().sort().str.join(" "),
                                        pl.col("roof").unique().sort().str.join(" "),
                                        pl.col("season").min().alias("first"), pl.col("season").max().alias("last"),
                                        pl.len().alias("games")).sort("stadium_id"))
    DIR.mkdir(parents=True, exist_ok=True)
    path = DIR / "stadium_list.csv"
    out.write_csv(path)
    return path


def fetch_wind(g: pl.DataFrame) -> Path | None:
    """Resumable: finished stadium-seasons are appended to game_wind_partial.csv and skipped on the next run. If
    Open-Meteo keeps refusing (rate limit), stop and keep the partial file; game_wind.csv is written only when every
    stadium-season is done."""
    coords = {r["stadium_id"]: (float(r["lat"]), float(r["lon"]))
              for r in csv.DictReader(open(DIR / "stadiums.csv"))}
    missing = sorted(set(g["stadium_id"].to_list()) - set(coords))
    if missing:
        sys.exit(f"stadiums without coordinates: {missing}")
    g = g.filter(pl.col("gameday").is_not_null(), pl.col("gametime").is_not_null())
    part = DIR / "game_wind_partial.csv"
    fields = ["game_id", "stadium_id", "season", "kickoff_utc", "wind_kn"]
    done = set()
    if part.exists():
        done = {(r["stadium_id"], int(r["season"])) for r in csv.DictReader(open(part))}
    else:
        with open(part, "w", newline="") as f:
            csv.DictWriter(f, fields).writeheader()
    groups = list(g.group_by(["stadium_id", "season"], maintain_order=True))
    todo = [(k, grp) for k, grp in groups if (k[0], int(k[1])) not in done]
    print(f"{len(groups)} stadium-seasons, {len(done)} already done, {len(todo)} to fetch", flush=True)
    for (sid, season), grp in todo:
        lat, lon = coords[sid]
        kicks = [weather.kickoff_utc(d, t) for d, t in zip(grp["gameday"], grp["gametime"])]
        start = min(kicks).date() - dt.timedelta(days=1)
        end = max(kicks).date() + dt.timedelta(days=1)
        try:
            hourly = weather.fetch_hourly_wind(lat, lon, start, end)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            print(f"rate limited at {sid} {season}; partial file kept, rerun to resume", flush=True)
            return None
        with open(part, "a", newline="") as f:
            w = csv.DictWriter(f, fields)
            for gid, k in zip(grp["game_id"], kicks):
                m = weather.window_mean(hourly, k)
                w.writerow({"game_id": gid, "stadium_id": sid, "season": season,
                            "kickoff_utc": k.strftime("%Y-%m-%dT%H:%MZ"),
                            "wind_kn": "" if m is None else round(m, 2)})
        print(f"{sid} {season}: {grp.height} games", flush=True)
    path = DIR / "game_wind.csv"
    pl.read_csv(part).drop("season").sort("game_id").write_csv(path)
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stadiums", action="store_true")
    a = ap.parse_args()
    g = sample_games()
    print(dump_stadiums(g) if a.stadiums else fetch_wind(g))


if __name__ == "__main__":
    main()
