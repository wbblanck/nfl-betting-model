"""Feature table: one row per player per game (those who played, and those on the game-day active list who did not),
holding only sums over that player's, his team's and the opponent's EARLIER games. Nothing from the game itself or any later game enters its row.

How that is guaranteed: every input is a per-game fact with a kickoff. For each subject (a player, an offense, a
defense) the games are ordered by kickoff and every sum is a running total taken BEFORE the row's own game, so a
row's sums stop at the subject's previous played game. A team plays once a week, so its previous game always kicked
off before this one. tests/test_engine.py and scripts/engine_feature_check.py scramble every fact at or after a
cut-off and require the rows up to the cut-off to come out byte-identical.

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
    """Add, for each column: sums over the subject's previous 3, 5 and 8 PLAYED games (across seasons), this season
    before this game, and all of last season; plus the game counts behind each. df has one row per subject per game
    and a boolean `played`; a row with played = False (on the active list, did not play) adds nothing to any sum or
    count, but still gets features as of its kickoff."""
    df = df.sort(*subject, "kickoff").with_columns(pl.col("played").cast(pl.Int64).alias("_p"))
    df = df.with_columns([(pl.col(c).fill_null(0) * pl.col("_p")).alias(f"_v_{c}") for c in cols])
    # Before this row: how many games the subject has played (_n) and the running total of each column (_e_*).
    df = df.with_columns(
        (pl.col("_p").cum_sum().over(subject) - pl.col("_p")).alias("_n"),
        *[(pl.col(f"_v_{c}").cum_sum().over(subject) - pl.col(f"_v_{c}")).alias(f"_e_{c}") for c in cols],
        pl.when(pl.col("played")).then(pl.col("kickoff")).otherwise(None).shift(1).forward_fill().over(subject).alias(f"{prefix}last_kickoff"))
    # Running totals as they stood before the subject's k-th played game, looked up to cut a window's far end off.
    at = df.filter(pl.col("played")).select(*subject, pl.col("_n").alias("_k"), *[pl.col(f"_e_{c}").alias(f"_at_{c}") for c in cols])
    out = df
    for w in WINDOWS:
        out = (out.with_columns((pl.col("_n") - w).clip(lower_bound=0).alias("_k"))
               .join(at, on=[*subject, "_k"], how="left")
               .with_columns(pl.min_horizontal(pl.col("_n"), pl.lit(w)).alias(f"{prefix}n_w{w}"),
                             *[(pl.col(f"_e_{c}") - pl.col(f"_at_{c}").fill_null(0)).alias(f"{prefix}{c}_w{w}") for c in cols])
               .drop("_k", *[f"_at_{c}" for c in cols]))
    by_season = [*subject, "season"]
    out = out.with_columns(
        (pl.col("_p").cum_sum().over(by_season) - pl.col("_p")).alias(f"{prefix}n_std"),
        *[(pl.col(f"_v_{c}").cum_sum().over(by_season) - pl.col(f"_v_{c}")).alias(f"{prefix}{c}_std") for c in cols])
    last = (df.group_by(by_season).agg(pl.col("_p").sum().alias(f"{prefix}n_prev"), *[pl.col(f"_v_{c}").sum().alias(f"{prefix}{c}_prev") for c in cols])
            .with_columns((pl.col("season") + 1).alias("season")))
    out = out.join(last, on=by_season, how="left")
    out = out.with_columns([pl.col(f"{prefix}n_prev").fill_null(0)] + [pl.col(f"{prefix}{c}_prev").fill_null(0) for c in cols])
    return out.drop("_p", "_n", *[f"_v_{c}" for c in cols], *[f"_e_{c}" for c in cols])


def build(player_week: pl.DataFrame, team_game: pl.DataFrame, on_field: pl.DataFrame | None = None,
          active: pl.DataFrame | None = None) -> pl.DataFrame:
    """player_week: engine.data.player_week.build output. team_game, on_field, active: engine.features.facts outputs.
    Returns one row per (player_id, game_id) for everyone who played and, when `active` is given, everyone on the
    game-day active list who did not (`played` False). Columns: keys, kickoff, played, and p_* (player), o_* (his
    offense), d_* (the opposing defense, i.e. what offenses did against it) features. Outcome columns of the game
    itself are not returned; `played` is the one fact about the game a row carries, and it is not a feature."""
    tg = team_game.select("game_id", "team", "opponent", "season", "week", "kickoff", *TEAM).with_columns(pl.lit(True).alias("played"))
    base = player_week.select("player_id", "game_id", "team", "position", *[c for c in PLAYER if c in player_week.columns]).with_columns(pl.lit(True).alias("played"))
    if active is not None and active.height:
        extra = active.join(base.select("player_id", "game_id"), on=["player_id", "game_id"], how="anti").select("player_id", "game_id", "team", "position")
        base = pl.concat([base, extra.with_columns(pl.lit(False).alias("played"))], how="diagonal_relaxed")
    pw = base.join(tg.select("game_id", "team", "opponent", "season", "week", "kickoff", *[c for c in TEAM if c in PLAYER]), on=["game_id", "team"], how="inner")
    if on_field is not None and on_field.height:
        pw = pw.join(on_field.select("game_id", "team", "player_id", "db_on_field", "team_db_charted"),
                     on=["game_id", "team", "player_id"], how="left")
    else:
        pw = pw.with_columns(pl.lit(None, dtype=pl.Int64).alias("db_on_field"), pl.lit(None, dtype=pl.Int64).alias("team_db_charted"))
    dup = pw.group_by("player_id", "game_id").len().filter(pl.col("len") > 1)
    if dup.height:
        raise ValueError(f"{dup.height} player-games appear twice")
    p = _windows(pw.select("player_id", "game_id", "season", "week", "kickoff", "team", "opponent", "position", "played", *PLAYER),
                 ["player_id"], PLAYER, "p_").drop(PLAYER)
    o = _windows(tg, ["team"], TEAM, "o_").drop(TEAM, "opponent", "season", "week", "kickoff", "played")
    d = (_windows(tg.rename({"team": "offense", "opponent": "team"}), ["team"], TEAM, "d_")
         .drop(TEAM, "offense", "season", "week", "kickoff", "played").rename({"team": "opponent"}))
    out = p.join(o, on=["game_id", "team"], how="left").join(d, on=["game_id", "opponent"], how="left")
    return out.sort("kickoff", "game_id", "player_id")


def snapshot_hash(features: pl.DataFrame) -> str:
    """Hash of the table's contents (column names, row order and every value, floats to 6 places) for the ledger.
    Computed from a text rendering, so it does not depend on the dataframe library's internal hashing."""
    return hashlib.sha256(features.write_csv(float_precision=6).encode()).hexdigest()
