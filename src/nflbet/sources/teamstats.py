"""Team-game pass-rush and coverage stats from free nflverse sources, for context and for future pre-registered tests.

- `participation(seasons)`: nflverse participation joined to play-by-play (2016-2025; nflverse publishes a season's
  participation only after it ends). Per team-game, defense: dropbacks faced, pressure rate, man / zone share,
  coverage shell shares, mean pass rushers, 5+ rusher rate, mean box; offense: pressure allowed rate, mean time to
  throw. Coverage fields are partial before 2022 (none in 2016).
- `ftn(seasons)`: FTN charting via nflverse (2022 on, current season included; CC-BY-SA 4.0, credit FTN Data via
  nflverse). Per team-game, defense: blitz rate (1+ blitzers), mean pass rushers, mean box; offense: play-action,
  motion, screen and no-huddle rates on dropbacks.
"""
from __future__ import annotations

import polars as pl

SHELLS = ["COVER_0", "COVER_1", "COVER_2", "2_MAN", "COVER_3", "COVER_4", "COVER_6", "COVER_9", "COMBO"]


def _pbp(seasons: list[int]) -> pl.DataFrame:
    import nflreadpy as nfl

    return nfl.load_pbp(seasons=seasons).filter(pl.col("season_type") == "REG", pl.col("qb_dropback") == 1) \
        .select("season", "week", "game_id", "play_id", "posteam", "defteam")


def participation(seasons: list[int]) -> pl.DataFrame:
    import nflreadpy as nfl

    pp = nfl.load_participation(seasons=seasons).select(
        pl.col("nflverse_game_id").alias("game_id"), pl.col("play_id").cast(pl.Float64), "was_pressure", "time_to_throw",
        "number_of_pass_rushers", "defenders_in_box", "defense_man_zone_type", "defense_coverage_type")
    x = _pbp(seasons).with_columns(pl.col("play_id").cast(pl.Float64)).join(pp, on=["game_id", "play_id"], how="inner")
    cov = pl.col("defense_man_zone_type").is_in(["MAN_COVERAGE", "ZONE_COVERAGE"])
    d = x.group_by("season", "week", "game_id", pl.col("defteam").alias("team")).agg(
        pl.len().alias("dropbacks_faced"),
        pl.col("was_pressure").cast(pl.Float64).mean().alias("def_pressure_rate"),
        pl.col("number_of_pass_rushers").cast(pl.Float64).mean().alias("def_pass_rushers"),
        (pl.col("number_of_pass_rushers") >= 5).cast(pl.Float64).mean().alias("def_5plus_rush_rate"),
        pl.col("defenders_in_box").cast(pl.Float64).mean().alias("def_box"),
        cov.sum().alias("coverage_charted"),
        ((pl.col("defense_man_zone_type") == "MAN_COVERAGE").sum() / cov.sum()).alias("def_man_rate"),
        *[((pl.col("defense_coverage_type") == s).sum() / pl.col("defense_coverage_type").is_not_null().sum()).alias(f"def_{s.lower()}")
          for s in SHELLS])
    o = x.group_by("season", "week", "game_id", pl.col("posteam").alias("team")).agg(
        pl.col("was_pressure").cast(pl.Float64).mean().alias("off_pressure_allowed_rate"),
        pl.col("time_to_throw").cast(pl.Float64).mean().alias("off_time_to_throw"))
    return d.join(o, on=["season", "week", "game_id", "team"], how="full", coalesce=True).sort("season", "week", "team")


def ftn(seasons: list[int]) -> pl.DataFrame:
    import nflreadpy as nfl

    f = nfl.load_ftn_charting(seasons=seasons).select(
        pl.col("nflverse_game_id").alias("game_id"), pl.col("nflverse_play_id").cast(pl.Float64).alias("play_id"),
        "n_blitzers", "n_pass_rushers", "n_defense_box", "is_play_action", "is_motion", "is_screen_pass", "is_no_huddle")
    x = _pbp(seasons).with_columns(pl.col("play_id").cast(pl.Float64)).join(f, on=["game_id", "play_id"], how="inner")
    d = x.group_by("season", "week", "game_id", pl.col("defteam").alias("team")).agg(
        pl.len().alias("dropbacks_faced"), (pl.col("n_blitzers") > 0).cast(pl.Float64).mean().alias("def_blitz_rate"),
        pl.col("n_pass_rushers").cast(pl.Float64).mean().alias("def_pass_rushers"),
        pl.col("n_defense_box").cast(pl.Float64).mean().alias("def_box"))
    o = x.group_by("season", "week", "game_id", pl.col("posteam").alias("team")).agg(
        pl.len().alias("dropbacks"), pl.col("is_play_action").cast(pl.Float64).mean().alias("off_play_action_rate"),
        pl.col("is_motion").cast(pl.Float64).mean().alias("off_motion_rate"),
        pl.col("is_screen_pass").cast(pl.Float64).mean().alias("off_screen_rate"),
        pl.col("is_no_huddle").cast(pl.Float64).mean().alias("off_no_huddle_rate"))
    return d.join(o, on=["season", "week", "game_id", "team"], how="full", coalesce=True).sort("season", "week", "team")


def season_to_date(tg: pl.DataFrame, season: int, before_week: int) -> pl.DataFrame:
    """Per team, dropback-weighted means of the rate columns over weeks strictly before `before_week`."""
    x = tg.filter(pl.col("season") == season, pl.col("week") < before_week)
    rates = [c for c in x.columns if c.startswith(("def_", "off_"))]
    w = pl.col("dropbacks_faced").fill_null(0)
    return x.group_by("team").agg(pl.len().alias("games"), *[((pl.col(c) * w).sum() / w.filter(pl.col(c).is_not_null()).sum()).alias(c) for c in rates])
