"""Feature table: one row per player per game, holding only sums over that player's, his team's and the opponent's
EARLIER games. Nothing from the game itself or any later game enters its row.

How that is guaranteed: every input is a per-game fact with a kickoff. For each subject (a player, an offense, a
defense) the games are ordered by kickoff and each window is shifted one game back, so a row's sums stop at the
subject's previous game. A team plays once a week, so its previous game always kicked off before this one.
tests/test_engine.py and scripts/engine_feature_check.py scramble every fact at or after a cut-off and require the
rows up to the cut-off to come out byte-identical.

Features are sums and game counts, not ratios: a model divides (targets by team targets, yards by carries) so that
a ratio over a window is the window's total over its total, never an average of per-game ratios.
"""
from __future__ import annotations

import hashlib

import polars as pl

WINDOWS = (3, 5, 8)
PLAYER = ["offense_snaps", "attempts", "completions", "passing_yards", "sacks_suffered", "carries", "rushing_yards",
          "targets", "receptions", "receiving_yards", "team_att", "team_carries", "team_targets", "team_dropbacks",
          "db_on_field", "team_db_charted"]
TEAM = ["team_att", "team_cmp", "team_pass_yds", "team_sacks", "team_carries", "team_rush_yds", "team_targets",
        "team_scrambles", "team_dropbacks", "team_plays"]


def _windows(df: pl.DataFrame, subject: list[str], cols: list[str], prefix: str) -> pl.DataFrame:
    """Add, for each column: sums over the subject's previous 3, 5 and 8 games (across seasons), this season before
    this game, and all of last season; plus the game counts behind each. df has one row per subject per game."""
    df = df.sort(*subject, "kickoff").with_columns(pl.lit(1, dtype=pl.Int64).alias("_one"))
    prev = lambda e: e.shift(1)                                                # noqa: E731 - "before this game"
    exprs = [pl.col("kickoff").shift(1).over(subject).alias(f"{prefix}last_kickoff")]
    for w in WINDOWS:
        exprs.append(prev(pl.col("_one")).rolling_sum(w, min_samples=1).over(subject).fill_null(0).alias(f"{prefix}n_w{w}"))
        exprs += [prev(pl.col(c).fill_null(0)).rolling_sum(w, min_samples=1).over(subject).fill_null(0).alias(f"{prefix}{c}_w{w}") for c in cols]
    by_season = [*subject, "season"]
    exprs.append((pl.col("_one").cum_sum().over(by_season) - 1).alias(f"{prefix}n_std"))
    exprs += [(pl.col(c).fill_null(0).cum_sum().over(by_season) - pl.col(c).fill_null(0)).alias(f"{prefix}{c}_std") for c in cols]
    out = df.with_columns(exprs).drop("_one")
    last = (df.group_by(by_season).agg(pl.len().cast(pl.Int64).alias(f"{prefix}n_prev"),
                                       *[pl.col(c).fill_null(0).sum().alias(f"{prefix}{c}_prev") for c in cols])
            .with_columns((pl.col("season") + 1).alias("season")))
    out = out.join(last, on=by_season, how="left")
    return out.with_columns([pl.col(f"{prefix}n_prev").fill_null(0)] + [pl.col(f"{prefix}{c}_prev").fill_null(0) for c in cols])


def build(player_week: pl.DataFrame, team_game: pl.DataFrame, on_field: pl.DataFrame | None = None) -> pl.DataFrame:
    """player_week: engine.data.player_week.build output. team_game, on_field: engine.features.facts outputs.
    Returns one row per (player_id, game_id): keys, kickoff, and p_* (player), o_* (his offense), d_* (the opposing
    defense, i.e. what offenses did against it) features. Outcome columns of the game itself are not returned."""
    tg = team_game.select("game_id", "team", "opponent", "season", "week", "kickoff", *TEAM)
    pw = (player_week.with_columns(pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64))
          .drop("opponent")
          .join(tg.select("game_id", "team", "opponent", "kickoff", *[c for c in TEAM if c in PLAYER]), on=["game_id", "team"], how="inner"))
    if on_field is not None and on_field.height:
        pw = pw.join(on_field.select("game_id", "team", "player_id", "db_on_field", "team_db_charted"),
                     on=["game_id", "team", "player_id"], how="left")
    else:
        pw = pw.with_columns(pl.lit(None, dtype=pl.Int64).alias("db_on_field"), pl.lit(None, dtype=pl.Int64).alias("team_db_charted"))
    dup = pw.group_by("player_id", "game_id").len().filter(pl.col("len") > 1)
    if dup.height:
        raise ValueError(f"{dup.height} player-games appear twice")
    p = _windows(pw.select("player_id", "game_id", "season", "week", "kickoff", "team", "opponent", "position", *PLAYER),
                 ["player_id"], PLAYER, "p_").drop(PLAYER)
    o = _windows(tg, ["team"], TEAM, "o_").drop(TEAM, "opponent", "season", "week", "kickoff")
    d = (_windows(tg.rename({"team": "offense", "opponent": "team"}), ["team"], TEAM, "d_")
         .drop(TEAM, "offense", "season", "week", "kickoff").rename({"team": "opponent"}))
    out = p.join(o, on=["game_id", "team"], how="left").join(d, on=["game_id", "opponent"], how="left")
    return out.sort("kickoff", "game_id", "player_id")


def snapshot_hash(features: pl.DataFrame) -> str:
    """Hash of the table's contents (column names, row order and every value, floats to 6 places) for the ledger.
    Computed from a text rendering, so it does not depend on the dataframe library's internal hashing."""
    return hashlib.sha256(features.write_csv(float_precision=6).encode()).hexdigest()
