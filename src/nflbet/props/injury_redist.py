"""Injury usage redistribution (docs/injury_redist_preregistration.md).

When pool teammates are listed Out / Doubtful, each remaining recent pool player's projected usage is raised by
alpha x q, where q = (usage of the listed players) / (usage of the rest), capped at 1. Idea from
MirageGiri/SportsProps (`injury_impact.py`, unlicensed; not copied). Pre-game information only: the injury report
and games strictly before the one projected.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from nflbet.props.player_proj import HALF_LIFE

WINDOW = 4                                   # recent = last game for the team within the previous 4 weeks
OUT_STATUS = ["Out", "Doubtful"]
POOL = {"rec": ["RB", "WR", "TE"], "rec_yds": ["RB", "WR", "TE"], "rush_rec_yds": ["RB", "WR", "TE"],
        "rush_att": ["RB"], "rush_yds": ["RB"]}
ALPHAS = np.round(np.arange(0.0, 1.51, 0.25), 2)


def usage_post(st: pl.DataFrame, markets: list[str]) -> pl.DataFrame:
    """Per player-game: U_m = weighted mean of m over the player's games up to AND including this one (sorted by t).
    Used only for games after this one."""
    return st.sort("t").with_columns(
        *[pl.col(m).cast(pl.Float64).ewm_mean(half_life=HALF_LIFE, ignore_nulls=True).over("player_id").alias(f"U_{m}")
          for m in markets])


def recent(su: pl.DataFrame, markets: list[str]) -> pl.DataFrame:
    """For every team-game in `su`: each player whose latest game for that team was in the same season within the
    previous WINDOW weeks, with his U values from that latest game."""
    games = su.select("team", "season", "week").unique()
    hist = su.select("team", "season", pl.col("week").alias("pw"), "player_id", "pos", *[f"U_{m}" for m in markets])
    r = games.join(hist, on=["team", "season"]).filter(pl.col("pw") < pl.col("week"),
                                                        pl.col("pw") >= pl.col("week") - WINDOW)
    return r.sort("pw").group_by("team", "season", "week", "player_id", maintain_order=True).last()


def shares(rec: pl.DataFrame, inj: pl.DataFrame, markets: list[str]) -> pl.DataFrame:
    """Long frame (team, season, week, player_id, market, q, active). `inj`: player_id, team, season, week,
    report_status. active = recent pool player not listed; q is the team-game-market freed ratio."""
    listed = inj.filter(pl.col("report_status").is_in(OUT_STATUS)).select("player_id", "team", "season", "week") \
        .unique().with_columns(pl.lit(True).alias("listed"))
    r = rec.join(listed, on=["player_id", "team", "season", "week"], how="left") \
        .with_columns(pl.col("listed").fill_null(False))
    parts = []
    for m in markets:
        x = r.filter(pl.col("pos").is_in(POOL[m]), pl.col(f"U_{m}").is_not_null()) \
            .select("team", "season", "week", "player_id", "listed", pl.col(f"U_{m}").alias("U"))
        k = ["team", "season", "week"]
        tot = x.group_by(k).agg(pl.col("U").filter(pl.col("listed")).sum().alias("F"),
                                pl.col("U").filter(~pl.col("listed")).sum().alias("S"))
        x = x.join(tot, on=k).with_columns(
            pl.when(pl.col("S") > 0).then((pl.col("F") / pl.col("S")).clip(upper_bound=1.0)).otherwise(0.0).alias("q"),
            pl.lit(m).alias("market"), (~pl.col("listed")).alias("active"))
        parts.append(x.select("team", "season", "week", "player_id", "market", "q", "active"))
    return pl.concat(parts)


def attach(proj: pl.DataFrame, sh: pl.DataFrame) -> pl.DataFrame:
    """Add q to projection rows (player_id, season, week, team, market, usage, ...). Rows of non-pool, listed, or
    not-recent players get q = 0 (unchanged)."""
    s = sh.filter(pl.col("active")).select("player_id", "season", "week", "team", "market", "q")
    return proj.join(s, on=["player_id", "season", "week", "team", "market"], how="left") \
        .with_columns(pl.col("q").fill_null(0.0))


def adjusted(x: pl.DataFrame, alpha: dict) -> pl.Expr:
    """Adjusted projection expression; x must carry proj and q."""
    a = pl.col("market").replace_strict(alpha, default=0.0, return_dtype=pl.Float64)
    return pl.col("proj") * (1 + a * pl.col("q"))


def fit_alpha(train: pl.DataFrame) -> dict:
    """alpha per market from ALPHAS minimizing squared error of proj x (1 + alpha q) on `train` (proj, q, actual)."""
    out = {}
    for m in train["market"].unique().sort().to_list():
        z = train.filter(pl.col("market") == m)
        p, q, y = z["proj"].to_numpy(), z["q"].to_numpy(), z["actual"].to_numpy()
        out[m] = float(min(ALPHAS, key=lambda a: (float(np.mean((p * (1 + a * q) - y) ** 2)), a)))
    return out
