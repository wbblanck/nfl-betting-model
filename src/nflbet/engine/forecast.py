"""Test M forecasts: the frozen engines' distributions for games not yet played (docs/engine_preregistration.md,
amendment of 2026-11-17). Pure functions; scripts/engine_forecast.py runs them. Reads no price.

A forecast for a game is built only from what was known before its kickoff:
- earlier games' facts (nflverse), with every fact of the target week and later removed, so the target games enter
  the feature table as unplayed team-games (engine.features.build gives them features as of kickoff);
- a projected active list in place of the game-day list, which no free source publishes in time (projected_active:
  weekly roster before the game's week, corrected by the depth chart dated before the game's day, minus those the
  latest ESPN injury snapshot saved before kickoff lists as absent: Out, Doubtful, IR, suspended, PUP);
- the quarterback depth chart dated before the game's day (engine.features.facts.depth_rank, as in Test S).
"""
from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from nflbet.engine.data.player_week import team_code

SKILL = ("QB", "RB", "WR", "TE")
LISTED = ("ACT", "INA")
ABSENT = ("Out", "Doubtful", "Injured Reserve", "Suspension", "Physically Unable to Perform")   # sources.injuries.ABSENT
STAMP = re.compile(r"^(\d{8}T\d{4})Z_w(\d+)\.json\.gz$")
EASTERN = ZoneInfo("America/New_York")
MARKETS = {"pass_att": "attempts", "pass_yds": "passing_yards", "rush_att": "carries", "rush_yds": "rushing_yards",
           "rec": "receptions", "rec_yds": "receiving_yards"}


def kickoff_utc(kickoff: str) -> dt.datetime:
    """'2026-11-19 20:15' (Eastern, as engine.features.facts.games writes it) -> aware UTC time."""
    return dt.datetime.strptime(kickoff, "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN).astimezone(dt.timezone.utc)


def stamp_utc(name: str) -> dt.datetime | None:
    m = STAMP.match(name)
    return dt.datetime.strptime(m.group(1), "%Y%m%dT%H%M").replace(tzinfo=dt.timezone.utc) if m else None


def snapshot_before(names: list[str], kickoff: str, max_hours: float = 72.0) -> str | None:
    """The latest snapshot file whose stamp is strictly before kickoff and no more than max_hours earlier."""
    k = kickoff_utc(kickoff)
    ok = [(t, n) for n in names if (t := stamp_utc(n)) is not None and t < k and (k - t).total_seconds() <= max_hours * 3600]
    return max(ok)[1] if ok else None


def snapshot_at_or_before(names: list[str], kickoff: str, cutoff: dt.datetime, max_hours: float = 72.0) -> str | None:
    """Paper fills: the latest snapshot stamped at or before cutoff (a book's fetch time), before kickoff, and no more
    than max_hours before kickoff."""
    k = kickoff_utc(kickoff)
    ok = [(t, n) for n in names if (t := stamp_utc(n)) is not None and t <= cutoff and t < k
          and (k - t).total_seconds() <= max_hours * 3600]
    return max(ok)[1] if ok else None


def target_games(games_: pl.DataFrame, season: int, week: int) -> pl.DataFrame:
    """Both team rows of every regular-season game of the week, as unplayed team-games (played False, sums empty)."""
    g = games_.filter((pl.col("season") == season) & (pl.col("week") == week))
    rows = pl.concat([g.select("game_id", "season", "week", "kickoff", pl.col("home").alias("team"), pl.col("away").alias("opponent")),
                      g.select("game_id", "season", "week", "kickoff", pl.col("away").alias("team"), pl.col("home").alias("opponent"))])
    return rows.with_columns(pl.lit(False).alias("played")).sort("kickoff", "game_id", "team")


def chart_teams(depth: pl.DataFrame, targets: pl.DataFrame) -> dict[str, dict[str, str]]:
    """game_id -> {gsis id: team} from the latest dated depth-chart snapshot before the game's calendar day: every
    QB/RB/WR/TE listed by any team in that snapshot. depth: nflverse 2025-on depth charts (dt, team, gsis_id, pos_abb)."""
    d = (depth.filter(pl.col("pos_abb").is_in(SKILL) & pl.col("gsis_id").is_not_null())
         .select(pl.col("dt").str.slice(0, 19).str.to_datetime("%Y-%m-%dT%H:%M:%S").alias("dt"), team_code("team").alias("team"), "gsis_id"))
    stamps = sorted(set(d["dt"].to_list()))
    out = {}
    for gid, ko in targets.select("game_id", "kickoff").unique().iter_rows():
        day = dt.datetime.strptime(ko[:10], "%Y-%m-%d")
        before = [t for t in stamps if t < day]
        if not before:
            out[gid] = {}
            continue
        snap = d.filter(pl.col("dt") == before[-1])
        out[gid] = dict(zip(snap["gsis_id"].to_list(), snap["team"].to_list()))
    return out


def projected_active(rosters: pl.DataFrame, absent: dict[str, set[str]], targets: pl.DataFrame,
                     charts: dict[str, dict[str, str]] | None = None) -> pl.DataFrame:
    """(player_id, game_id, team, position) for each target team-game. rosters: nflverse weekly rosters of the season
    (gsis_id, week, team, position, status). A player is listed for a team when his latest weekly roster row before
    the game's week puts him there as ACT or INA, or the depth chart dated before the game's day (charts) lists him
    there; when that chart lists him on another team he is not listed (a trade since the last roster week). Anyone
    the game's injury snapshot lists as absent (absent: game_id -> gsis ids) is removed."""
    charts = charts or {}
    before = rosters.filter(pl.col("gsis_id").is_not_null())
    pos = dict(zip(before["gsis_id"].to_list(), before["position"].to_list()))
    out = []
    for r in targets.iter_rows(named=True):
        last = before.filter(pl.col("week") < r["week"]).sort("week").group_by("gsis_id", maintain_order=True).last()
        on = last.filter((team_code("team") == r["team"]) & pl.col("status").is_in(LISTED) & pl.col("position").is_in(SKILL))
        ch = charts.get(r["game_id"], {})
        keep = {g for g in on["gsis_id"].to_list() if ch.get(g, r["team"]) == r["team"]}
        keep |= {g for g, t in ch.items() if t == r["team"] and pos.get(g) in SKILL}
        keep -= absent.get(r["game_id"], set())
        ids_ = sorted(keep)
        out.append(pl.DataFrame({"player_id": ids_, "game_id": [r["game_id"]] * len(ids_), "team": [r["team"]] * len(ids_),
                                 "position": [pos[g] for g in ids_]}, schema={"player_id": pl.Utf8, "game_id": pl.Utf8, "team": pl.Utf8, "position": pl.Utf8}))
    return pl.concat(out) if out else pl.DataFrame(schema={"player_id": pl.Utf8, "game_id": pl.Utf8, "team": pl.Utf8, "position": pl.Utf8})


def absent_ids(injuries: pl.DataFrame, espn_to_gsis: pl.DataFrame) -> set[str]:
    """gsis ids of players an ESPN injury snapshot (sources.injuries.parse) lists with an absent status."""
    hit = injuries.filter(pl.col("status").is_in(ABSENT)).join(espn_to_gsis, on="espn_id", how="inner")
    return set(hit["player_id"].to_list())


def histogram(engine: str, rows: pl.DataFrame, market: str, runs: np.ndarray) -> pl.DataFrame:
    """Runs [rows, sims] of one market -> long table (engine, game_id, player_id, market, value, count)."""
    g, p, m, v, c = [], [], [], [], []
    for i, (gid, pid) in enumerate(zip(rows["game_id"].to_list(), rows["player_id"].to_list())):
        vals, cnt = np.unique(np.asarray(runs[i]), return_counts=True)
        g += [gid] * len(vals)
        p += [pid] * len(vals)
        v += vals.astype(np.int64).tolist()
        c += cnt.astype(np.int64).tolist()
    return pl.DataFrame({"engine": [engine] * len(g), "game_id": g, "player_id": p, "market": [market] * len(g), "value": v, "count": c},
                        schema={"engine": pl.Utf8, "game_id": pl.Utf8, "player_id": pl.Utf8, "market": pl.Utf8, "value": pl.Int64, "count": pl.Int64})


def p_over(hist: pl.DataFrame, line: float) -> float:
    """Share of runs strictly above the line, from one (engine, player-game, market) histogram."""
    n = int(hist["count"].sum())
    return float(hist.filter(pl.col("value") > line)["count"].sum()) / n if n else float("nan")
