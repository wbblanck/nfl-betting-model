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


def fetch_wind(g: pl.DataFrame) -> Path:
    coords = {r["stadium_id"]: (float(r["lat"]), float(r["lon"]))
              for r in csv.DictReader(open(DIR / "stadiums.csv"))}
    missing = sorted(set(g["stadium_id"].to_list()) - set(coords))
    if missing:
        sys.exit(f"stadiums without coordinates: {missing}")
    g = g.filter(pl.col("gameday").is_not_null(), pl.col("gametime").is_not_null())
    rows = []
    for (sid, season), grp in g.group_by(["stadium_id", "season"], maintain_order=True):
        lat, lon = coords[sid]
        kicks = [weather.kickoff_utc(d, t) for d, t in zip(grp["gameday"], grp["gametime"])]
        start = min(kicks).date() - dt.timedelta(days=1)
        end = max(kicks).date() + dt.timedelta(days=1)
        hourly = weather.fetch_hourly_wind(lat, lon, start, end)
        for gid, k in zip(grp["game_id"], kicks):
            w = weather.window_mean(hourly, k)
            rows.append({"game_id": gid, "stadium_id": sid, "kickoff_utc": k.strftime("%Y-%m-%dT%H:%MZ"),
                         "wind_kn": None if w is None else round(w, 2)})
        print(f"{sid} {season}: {grp.height} games", flush=True)
    path = DIR / "game_wind.csv"
    pl.DataFrame(rows).sort("game_id").write_csv(path)
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stadiums", action="store_true")
    a = ap.parse_args()
    g = sample_games()
    print(dump_stadiums(g) if a.stadiums else fetch_wind(g))


if __name__ == "__main__":
    main()
