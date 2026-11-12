"""One row per offensive skill player per regular-season game: the outcomes both engines fit to and are graded on.

Rules (CLAUDE.md data traps): a player with offensive snaps and no stat row gets zeros; a player with no snaps and
no stat row has no row (void). Snap counts carry PFR IDs, so they are mapped to nflverse IDs through the players
table; an ID that does not map to exactly one player is counted and left out, never guessed.
"""
from __future__ import annotations

import polars as pl

# Every code nflverse tables use for a franchise -> the one code player stats use (franchise, not city).
TEAM_ALIASES = {"ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU", "SL": "LA", "STL": "LA", "LAR": "LA", "SD": "LAC",
                "OAK": "LV", "JAC": "JAX", "WSH": "WAS"}


def team_code(col: str) -> pl.Expr:
    return pl.col(col).replace(TEAM_ALIASES)


POSITIONS = ("QB", "RB", "WR", "TE")
KEY = ["player_id", "season", "week"]
STATS = ["completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions", "sacks_suffered",
         "carries", "rushing_yards", "rushing_tds", "targets", "receptions", "receiving_yards", "receiving_tds",
         "special_teams_tds", "fumble_recovery_tds"]


def build(stats: pl.DataFrame, snaps: pl.DataFrame, players: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """(player-week table, report). Raises if a player has two stat rows in one week."""
    st = (stats.filter(pl.col("season_type") == "REG", pl.col("position").is_in(POSITIONS), pl.col("player_id").is_not_null())
          .select(*KEY, "game_id", "team", pl.col("opponent_team").alias("opponent"), "position",
                  *[pl.col(c).fill_null(0).cast(pl.Int64) for c in STATS]))
    dup = st.group_by(KEY).len().filter(pl.col("len") > 1)
    if dup.height:
        raise ValueError(f"{dup.height} player-weeks have more than one stat row, e.g. {dup.row(0)}")
    ids = players.filter(pl.col("pfr_id").is_not_null(), pl.col("gsis_id").is_not_null()).select("pfr_id", "gsis_id")
    one = ids.group_by("pfr_id").agg(pl.col("gsis_id").n_unique().alias("n"), pl.col("gsis_id").first()).filter(pl.col("n") == 1)
    cast = [pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64)]
    st = st.with_columns(cast)
    sn = snaps.with_columns(cast).filter(pl.col("game_type") == "REG", pl.col("position").is_in(POSITIONS), pl.col("offense_snaps") > 0)
    mapped = (sn.join(one.select("pfr_id", pl.col("gsis_id").alias("player_id")), left_on="pfr_player_id", right_on="pfr_id", how="left"))
    unmapped = mapped.filter(pl.col("player_id").is_null()).height
    mapped = mapped.filter(pl.col("player_id").is_not_null())
    dsn = mapped.group_by(KEY).len().filter(pl.col("len") > 1).height
    mapped = mapped.unique(subset=KEY, keep="first", maintain_order=True)
    snap_cols = mapped.select(*KEY, pl.col("offense_snaps").cast(pl.Int64), pl.col("offense_pct").cast(pl.Float64))
    only = (mapped.join(st.select(KEY), on=KEY, how="anti")
            .select(*KEY, "game_id", "team", "opponent", "position", *[pl.lit(0, dtype=pl.Int64).alias(c) for c in STATS]))
    out = (pl.concat([st.with_columns(pl.lit(True).alias("stat_row")), only.with_columns(pl.lit(False).alias("stat_row"))], how="vertical_relaxed")
           .join(snap_cols, on=KEY, how="left").sort(KEY))
    rep = {"stat_rows": st.height, "snap_rows": sn.height, "snap_rows_unmapped": unmapped, "snap_duplicate_keys": dsn,
           "zero_rows_added": only.height, "stat_rows_without_snaps": out.filter(pl.col("stat_row") & pl.col("offense_snaps").is_null()).height}
    return out, rep
