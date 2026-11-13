"""Per-game facts: what happened in each game, one row per team-game and per player-game. Each row belongs to exactly
one game and carries that game's kickoff, so "known before T" is a comparison of kickoff times.

Definitions match docs/engine/MODEL_SPECIFICATION.md section 1 and reconcile with nflverse player stats: pass
attempts exclude sacks and include spikes; carries include kneels and scrambles; two-point tries count for nothing.
"""
from __future__ import annotations

import polars as pl

from nflbet.engine.data.player_week import team_code

TEAM_SUMS = {"attempts": "team_att", "completions": "team_cmp", "passing_yards": "team_pass_yds", "sacks_suffered": "team_sacks",
             "carries": "team_carries", "rushing_yards": "team_rush_yds", "targets": "team_targets"}


def games(schedules: pl.DataFrame) -> pl.DataFrame:
    """Regular-season games with a kickoff string that sorts in time order ('2023-09-10 13:00', Eastern)."""
    return (schedules.filter(pl.col("game_type") == "REG")
            .select("game_id", pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64),
                    (pl.col("gameday").cast(pl.Utf8) + " " + pl.col("gametime").cast(pl.Utf8).fill_null("00:00")).alias("kickoff"),
                    team_code("home_team").alias("home"), team_code("away_team").alias("away")))


def team_game(stats: pl.DataFrame, pbp: pl.DataFrame, games_: pl.DataFrame) -> pl.DataFrame:
    """One row per offense per game (opponent taken from the schedule): volumes summed from every player's stat row (all positions), scrambles from
    play-by-play, dropbacks = attempts + sacks + scrambles, plays = dropbacks + designed runs."""
    s = (stats.filter(pl.col("season_type") == "REG")
         .group_by("game_id", team_code("team").alias("team"))
         .agg([pl.col(c).fill_null(0).sum().cast(pl.Int64).alias(n) for c, n in TEAM_SUMS.items()]))
    scr = (pbp.filter((pl.col("qb_scramble") == 1) & (pl.col("play_type") == "run") & (pl.col("two_point_attempt") == 0))
           .group_by("game_id", team_code("posteam").alias("team")).agg(pl.len().cast(pl.Int64).alias("team_scrambles")))
    out = (s.join(scr, on=["game_id", "team"], how="left").with_columns(pl.col("team_scrambles").fill_null(0))
           .with_columns((pl.col("team_att") + pl.col("team_sacks") + pl.col("team_scrambles")).alias("team_dropbacks"))
           .with_columns((pl.col("team_dropbacks") + pl.col("team_carries") - pl.col("team_scrambles")).alias("team_plays")))
    out = out.join(games_, on="game_id", how="inner")
    stray = out.filter((pl.col("team") != pl.col("home")) & (pl.col("team") != pl.col("away")))
    if stray.height:
        raise ValueError(f"{stray.height} team-games name a team that is not in the scheduled game, e.g. {stray.row(0)[:2]}")
    # The opponent comes from the schedule: the stats file leaves it blank on a few rows.
    return (out.with_columns(pl.when(pl.col("team") == pl.col("home")).then(pl.col("away")).otherwise(pl.col("home")).alias("opponent"))
            .drop("home", "away"))


def on_field(participation: pl.DataFrame, pbp: pl.DataFrame) -> pl.DataFrame:
    """Per player per game: dropbacks he was on the field for, and the team's charted dropbacks in that game.
    This is the stand-in for routes run (not published free): it counts a player who stayed in to block."""
    db = (pbp.filter((pl.col("qb_dropback") == 1) & pl.col("play_type").is_in(["pass", "run"]) & (pl.col("two_point_attempt") == 0))
          .select("game_id", pl.col("play_id").cast(pl.Int64), team_code("posteam").alias("team")))
    p = (participation.select(pl.col("nflverse_game_id").alias("game_id"), pl.col("play_id").cast(pl.Int64), "offense_players")
         .filter(pl.col("offense_players").is_not_null() & (pl.col("offense_players") != ""))
         .join(db, on=["game_id", "play_id"], how="inner"))
    team = p.group_by("game_id", "team").agg(pl.len().cast(pl.Int64).alias("team_db_charted"))
    per = (p.with_columns(pl.col("offense_players").str.split(";").alias("player_id")).explode("player_id")
           .filter(pl.col("player_id") != "").unique(subset=["game_id", "play_id", "player_id"])
           .group_by("game_id", "team", "player_id").agg(pl.len().cast(pl.Int64).alias("db_on_field")))
    return per.join(team, on=["game_id", "team"], how="left")


def active(rosters: pl.DataFrame, team_game_: pl.DataFrame, positions=("QB", "RB", "WR", "TE")) -> pl.DataFrame:
    """Skill players on each team's game-day active list (weekly roster status ACT), one row per player per game.
    The list is published about 90 minutes before kickoff, so it is known before the game; it says nothing about
    who goes on to play or get hurt."""
    r = (rosters.filter((pl.col("game_type") == "REG") & (pl.col("status") == "ACT") & pl.col("position").is_in(positions)
                        & pl.col("gsis_id").is_not_null())
         .select(pl.col("gsis_id").alias("player_id"), pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64),
                 team_code("team").alias("team"), "position"))
    return (r.join(team_game_.select("game_id", "season", "week", "team"), on=["season", "week", "team"], how="inner")
            .unique(subset=["player_id", "game_id"], keep="first", maintain_order=True))


def depth_rank(weekly: pl.DataFrame | None, dated: pl.DataFrame | None, team_game_: pl.DataFrame, position: str = "QB") -> pl.DataFrame:
    """Depth-chart rank (1 = starter) of each listed player at a position, per team-game.

    weekly: nflverse depth charts through 2024, one chart per team per week, taken as that week's pregame chart.
    dated: the 2025-on format, snapshots with a UTC timestamp; a game uses the team's latest snapshot dated before
    the game's calendar day. Charts do not track injuries (CLAUDE.md), so rank 1 may be inactive."""
    out = []
    tg = team_game_.select("game_id", "season", "week", "team", "kickoff")
    if weekly is not None and weekly.height:
        w = (weekly.filter((pl.col("game_type") == "REG") & (pl.col("position") == position) & (pl.col("formation") == "Offense")
                           & pl.col("gsis_id").is_not_null())
             .select(pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64), team_code("club_code").alias("team"),
                     pl.col("gsis_id").alias("player_id"), pl.col("depth_team").cast(pl.Int64, strict=False).alias("depth_rank")))
        out.append(w.join(tg, on=["season", "week", "team"], how="inner").select("game_id", "team", "player_id", "depth_rank"))
    if dated is not None and dated.height:
        d = (dated.filter((pl.col("pos_abb") == position) & pl.col("gsis_id").is_not_null())
             .select(team_code("team").alias("team"), pl.col("dt").str.slice(0, 19).str.to_datetime("%Y-%m-%dT%H:%M:%S").alias("dt"),
                     pl.col("gsis_id").alias("player_id"), pl.col("pos_rank").cast(pl.Int64).alias("depth_rank")))
        snaps = d.select("team", "dt").unique().sort("dt")
        day = tg.with_columns(pl.col("kickoff").str.slice(0, 10).str.to_datetime("%Y-%m-%d").alias("day")).sort("day")
        day = day.filter(pl.col("day") >= snaps["dt"].min()) if snaps.height else day.head(0)
        m = day.join_asof(snaps, left_on="day", right_on="dt", by="team", strategy="backward", allow_exact_matches=False)
        out.append(m.filter(pl.col("dt").is_not_null()).join(d, on=["team", "dt"], how="inner").select("game_id", "team", "player_id", "depth_rank"))
    if not out:
        return pl.DataFrame(schema={"game_id": pl.Utf8, "team": pl.Utf8, "player_id": pl.Utf8, "depth_rank": pl.Int64})
    return (pl.concat(out).drop_nulls("depth_rank").sort("depth_rank")
            .unique(subset=["game_id", "team", "player_id"], keep="first", maintain_order=True))
