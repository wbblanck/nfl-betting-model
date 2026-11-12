"""Pull nflverse tables season by season into Parquet and record what arrived (rows, columns, file hash).

A season a source does not publish is recorded as unavailable with the error; nothing is filled in.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import polars as pl

from nflbet.config import ROOT

DIR = ROOT / "data" / "cache" / "engine"
MANIFEST = DIR / "manifest.json"
SEASONS = range(2010, 2026)

# table -> (nflreadpy loader, extra arguments). Per-season tables only; `players` is loaded once.
TABLES: dict[str, tuple[str, dict]] = {
    "pbp": ("load_pbp", {}),
    "player_stats": ("load_player_stats", {}),
    "rosters_weekly": ("load_rosters_weekly", {}),
    "snap_counts": ("load_snap_counts", {}),
    "participation": ("load_participation", {}),
    "depth_charts": ("load_depth_charts", {}),
    "injuries": ("load_injuries", {}),
    "ngs_passing": ("load_nextgen_stats", {"stat_type": "passing"}),
    "ngs_receiving": ("load_nextgen_stats", {"stat_type": "receiving"}),
    "ngs_rushing": ("load_nextgen_stats", {"stat_type": "rushing"}),
    "ftn_charting": ("load_ftn_charting", {}),
}


def path(table: str, season: int | None = None) -> Path:
    return DIR / table / (f"{season}.parquet" if season is not None else "all.parquet")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _save(df: pl.DataFrame, p: Path) -> dict:
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)
    return {"status": "ok", "rows": df.height, "columns": df.width, "sha256": _sha(p)}


def ingest(seasons=SEASONS, tables=None, log=print) -> dict:
    """Fetch every (table, season) not already in the manifest as ok. Returns the manifest."""
    import nflreadpy as nfl
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    def done(key):
        return man.get(key, {}).get("status") == "ok" and (DIR / man[key]["file"]).exists()
    jobs = [("schedules", None, "load_schedules", {"seasons": True}), ("players", None, "load_players", {})]
    jobs += [(t, s, *TABLES[t]) for t in (tables or TABLES) for s in seasons]
    for table, season, loader, kw in jobs:
        key = f"{table}/{season if season is not None else 'all'}"
        if done(key):
            continue
        p = path(table, season)
        try:
            args = {**kw, **({"seasons": [season]} if season is not None else {})}
            df = getattr(nfl, loader)(**args)
            if season is not None and "season" in df.columns:
                df = df.filter(pl.col("season") == season)
            if df.height == 0:
                raise ValueError("no rows for this season")
            rec = _save(df, p)
        except Exception as e:  # noqa: BLE001 - recorded per source and season; absence is a finding
            rec = {"status": "unavailable", "error": f"{type(e).__name__}: {str(e)[:160]}"}
        man[key] = {**rec, "file": str(p.relative_to(DIR)), "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
        log(f"{key}: {rec.get('rows', rec.get('error'))}")
        DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(man, indent=1, sort_keys=True))
    return man


def read(table: str, seasons=None) -> pl.DataFrame:
    """Saved table for the given seasons (all saved seasons when None), columns unioned across seasons."""
    files = [path(table, s) for s in seasons] if seasons is not None else sorted((DIR / table).glob("*.parquet"))
    files = [f for f in files if f.exists()]
    if not files:
        raise FileNotFoundError(f"{table}: nothing ingested for {seasons}")
    return pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed")
