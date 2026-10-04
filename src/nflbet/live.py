"""S1 live tracker (docs/s1_live_rules.md): score upcoming props before kickoff, record the all-four-agree picks,
grade them after the games.

A run fetches the current week's Action Network lines, builds pre-game rows for every player on a team that has
not kicked off yet, and scores those props with exactly the logic of rule S1 (screener.score). Every run's picks
are appended to data/live/s1_picks_<season>.csv and every run is logged (data/live/s1_runs_<season>.csv) with
the games it evaluated. The OFFICIAL pick for a game is the last run that evaluated it before its kickoff.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import polars as pl

from nflbet import config, props as P, props_confirm as C, screener as Sc
from nflbet import player_proj as M
from nflbet.props_projection import FIT_SEASON
from nflbet.sim import Simulator, POS

LIVE = config.ROOT / "data" / "live"
PICK_COLS = ["run_utc", "season", "week", "an_game_id", "start_time", "home", "away", "player", "player_id", "team",
             "market", "side",
             "line", "odds", "p_over_dk", "proj", "p_sim", "v_disagree", "v_proj", "v_sim", "v_price"]


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def current_week(season: int) -> int | None:
    import nflreadpy as nfl

    g = nfl.load_schedules(seasons=[season]).filter(pl.col("game_type") == "REG", pl.col("result").is_null())
    return int(g["week"].min()) if g.height else None


def upcoming_rows(season: int, week: int) -> pl.DataFrame:
    """Each player's latest team/position (his most recent game, this season or last), placed in `week` against
    his team's scheduled opponent. Stats are null: these rows only carry identity for pre-game features."""
    import nflreadpy as nfl

    st = nfl.load_player_stats(seasons=[season - 1, season]).filter(pl.col("season_type") == "REG")
    latest = st.sort("season", "week").group_by("player_id").last() \
        .select("player_id", "player_display_name", "position", "team")
    g = nfl.load_schedules(seasons=[season]).filter(pl.col("game_type") == "REG", pl.col("week") == week)
    opp = pl.concat([g.select(pl.col("home_team").alias("team"), pl.col("away_team").alias("opp"), "game_id"),
                     g.select(pl.col("away_team").alias("team"), pl.col("home_team").alias("opp"), "game_id")])
    return latest.join(opp, on="team").with_columns(pl.lit(season).alias("season"), pl.lit(week).alias("week"))


def _sim_with_upcoming(season: int, up: pl.DataFrame) -> Simulator:
    sim = Simulator(fit_season=2024, seasons=sorted({2023, 2024, season - 1, season}))
    rows = up.with_columns(pl.col("position").replace_strict(POS, default=None).alias("pos")).filter(pl.col("pos").is_not_null())
    extra = rows.select("player_id", pl.col("season").cast(pl.Int32), pl.col("week").cast(pl.Int32), "team", "opp", "pos") \
        .with_columns((pl.col("season").cast(pl.Int64) * 100 + pl.col("week")).alias("t"))
    sim.pg = pl.concat([sim.pg, extra], how="diagonal_relaxed").sort("t")
    return sim


def _projections_with_upcoming(season: int, up: pl.DataFrame) -> pl.DataFrame:
    seasons = sorted({FIT_SEASON - 1, FIT_SEASON, season - 1, season})
    st = M.stats(seasons)
    extra = up.with_columns(pl.col("position").replace_strict(M.POS_GROUP, default=None).alias("pos")) \
        .filter(pl.col("pos").is_not_null()) \
        .select("player_id", "season", "week", "team", pl.col("opp").alias("opponent_team"), "pos") \
        .with_columns((pl.col("season") * 100 + pl.col("week")).alias("t"))
    st = pl.concat([st, extra], how="diagonal_relaxed").sort("t")
    L = M.long(M.features(st, M.implied_points(seasons)))
    params = M.fit(L.filter(pl.col("season") == FIT_SEASON, pl.col("actual").is_not_null()))
    return M.project(L.filter(pl.col("season") == season), params)


def priced(d: pl.DataFrame) -> pl.DataFrame:
    """Like props.graded but for games not yet played: de-vigged P(over) and hold, no result."""
    ou = d.filter(pl.col("market") != "anytime_td", pl.col("over_odds").is_not_null(), pl.col("under_odds").is_not_null())
    io = 1 / ou["over_odds"].map_elements(P.american_to_decimal, return_dtype=pl.Float64)
    iu = 1 / ou["under_odds"].map_elements(P.american_to_decimal, return_dtype=pl.Float64)
    return ou.with_columns((io / (io + iu)).alias("p_over"), (io + iu - 1).alias("hold"))


def run(season: int, lines_path: Path, when: dt.datetime | None = None) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Score one fetched lines file. Returns (picks, run log rows) for games that have not started at `when`."""
    when = when or now_utc()
    raw = pl.read_csv(lines_path, infer_schema_length=0)
    week = int(raw["week"].cast(pl.Int64).max())
    not_started = pl.col("start_time").map_elements(lambda s: parse_ts(s) > when, return_dtype=pl.Boolean)
    lines = P.load_lines(season, path=lines_path, where=not_started).filter(pl.col("week") == week)
    games = lines.select("an_game_id", "start_time", "home", "away").unique()
    up = upcoming_rows(season, week)
    stats = P.load_stats(season)
    ident = up.select("player_id", "player_display_name", "position", "week", "team", "game_id")
    joined = P.join(lines, pl.concat([stats, ident], how="diagonal_relaxed"))
    s = C.screened(priced(joined)).filter(pl.col("market").is_in(Sc.MARKETS))
    sim = _sim_with_upcoming(season, up)
    sim_out = sim.run(season, keep=set(zip(s["player_id"].to_list(), s["week"].to_list())))
    proj = _projections_with_upcoming(season, up)
    sc = Sc.with_votes(Sc.score(s, proj, sim_out))
    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    picks = sc.filter(pl.col("votes").abs() == 4).with_columns(
        pl.lit(stamp).alias("run_utc"), pl.lit(season).alias("season"),
        pl.when(pl.col("votes") < 0).then(pl.lit("under")).otherwise(pl.lit("over")).alias("side"),
        pl.when(pl.col("votes") < 0).then(pl.col("under_odds")).otherwise(pl.col("over_odds")).alias("odds"),
        pl.col("p_over").alias("p_over_dk")).select(PICK_COLS)
    n_scored = sc.group_by("an_game_id").len().rename({"len": "props_scored"})
    log = games.join(n_scored, on="an_game_id", how="left").with_columns(
        pl.lit(stamp).alias("run_utc"), pl.lit(season).alias("season"), pl.lit(week).alias("week"),
        pl.col("props_scored").fill_null(0))
    return picks, log.select("run_utc", "season", "week", "an_game_id", "start_time", "home", "away", "props_scored")


def append(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size:
        old = pl.read_csv(path, infer_schema_length=0)
        df = pl.concat([old, df.select([pl.col(c).cast(pl.Utf8) for c in df.columns])], how="diagonal_relaxed")
    df.write_csv(path)


# --------------------------------------------------------------------------------------------- grading

def official(picks: pl.DataFrame, runs: pl.DataFrame) -> pl.DataFrame:
    """Picks from the last run that evaluated each game before its kickoff."""
    r = runs.filter(pl.col("run_utc").map_elements(parse_ts, return_dtype=pl.Datetime("us", "UTC"))
                    < pl.col("start_time").map_elements(parse_ts, return_dtype=pl.Datetime("us", "UTC")))
    last = r.group_by("an_game_id").agg(pl.col("run_utc").max())
    return picks.join(last, on=["an_game_id", "run_utc"], how="inner")


def settle(off: pl.DataFrame, stats: pl.DataFrame, played: set, final_games: set) -> pl.DataFrame:
    """W / L / P / void / pending per official pick. `stats`: player_id, week, market, actual (long);
    `played`: (player_id, week) with offensive snaps; `final_games`: an_game_id whose game is final."""
    d = off.with_columns(pl.col("week").cast(pl.Int64), pl.col("line").cast(pl.Float64),
                         pl.col("odds").cast(pl.Float64)).join(stats, on=["player_id", "week", "market"], how="left")
    res = []
    for r in d.iter_rows(named=True):
        if r["an_game_id"] not in final_games:
            res.append("pending"); continue
        a = r["actual"]
        if a is None:
            if (r["player_id"], r["week"]) in played:
                a = 0.0
            else:
                res.append("void"); continue
        if a == r["line"]:
            res.append("P")
        else:
            res.append("W" if (a < r["line"]) == (r["side"] == "under") else "L")
    d = d.with_columns(pl.Series("result", res))
    units = [0.0 if x in ("P", "void", "pending") else (P.american_to_decimal(o) - 1 if x == "W" else -1.0)
             for x, o in zip(d["result"].to_list(), d["odds"].to_list())]
    return d.with_columns(pl.Series("units", units))


def gradable(games: pl.DataFrame, final: pl.DataFrame, published: set) -> set:
    """an_game_id of games that are final AND whose player stats nflverse has published. The schedule shows a final
    score hours before the player stats and snap counts arrive; grading in that gap would call every pick on the
    game void (no stat row, no snaps). games: an_game_id, week, home_team, away_team. final: week, home_team,
    away_team. published: {(week, team)} with at least one player stat row."""
    j = games.join(final, on=["week", "home_team", "away_team"])
    return {r["an_game_id"] for r in j.iter_rows(named=True)
            if (r["week"], r["home_team"]) in published or (r["week"], r["away_team"]) in published}


def record(d: pl.DataFrame) -> dict:
    w, l, p = (int((d["result"] == k).sum()) for k in ("W", "L", "P"))
    staked = w + l
    return {"W": w, "L": l, "P": p, "void": int((d["result"] == "void").sum()),
            "pending": int((d["result"] == "pending").sum()), "win_pct": w / staked if staked else None,
            "units": float(d["units"].sum()), "roi": float(d["units"].sum()) / staked if staked else None}
