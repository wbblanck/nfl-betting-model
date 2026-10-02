"""Milestone ladders priced off the book's own main line (docs/simulator_declaration.md).

center(): scale a simulated distribution so P(X > main line) equals the book's de-vigged P(over). Then
P(X >= N) for each milestone rung N comes from the shape alone; the mean is the book's, not ours.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from nflbet import config, props as P

COUNT_MARKETS = {"rec", "rush_att", "pass_att", "pass_cmp", "pass_td"}


def center(samples: np.ndarray, line: float, p_over: float, count: bool = False, iters: int = 40) -> np.ndarray:
    """Multiply samples by c (bisection on log c) so that mean(X > line) is as close to p_over as possible.
    Count markets are rounded after scaling."""
    lo, hi = -3.0, 3.0
    def p(c):
        x = samples * np.exp(c)
        x = np.round(x) if count else x
        return float(np.mean(x > line))
    for _ in range(iters):
        mid = (lo + hi) / 2
        if p(mid) < p_over:
            lo = mid
        else:
            hi = mid
    x = samples * np.exp((lo + hi) / 2)
    return np.round(x) if count else x


def load_milestones(season: int) -> pl.DataFrame:
    d = pl.read_csv(config.ROOT / "data" / "props" / f"an_milestones_{season}.csv", infer_schema_length=0)
    return d.filter(~pl.col("book_id").is_in(list(P.NON_BOOKS))).with_columns(
        pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64), pl.col("threshold").cast(pl.Int64),
        pl.col("yes_odds").cast(pl.Float64, strict=False), pl.col("player_team").replace(P.TEAM_FIX).alias("team"),
        pl.lit(None, dtype=pl.Float64).alias("line"), pl.lit(None, dtype=pl.Float64).alias("over_odds"),
        pl.lit(None, dtype=pl.Float64).alias("under_odds")).filter(pl.col("yes_odds").is_not_null())
