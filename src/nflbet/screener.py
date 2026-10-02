"""Prop screener (docs/simulator_confirm.md): score every DraftKings over/under on four independent pre-game
signals, each a vote for the over or the under:
  disagree  books post different lines and DK has the highest -> under; DK has the lowest -> over
  proj      projection model >= 10% below DK's line -> under; >= 10% above -> over
  sim       simulator P(over) vs de-vigged DK P(over), >= 5 points -> that side
  price     DK prices the under below -120 -> under; the over below -120 -> over
Rule S1: bet only props where all four signals agree (votes = +4 or -4).
"""
from __future__ import annotations

import numpy as np
import polars as pl

from nflbet import props as P, props_confirm as C, props_projection as R
from nflbet.sim import Simulator

MARKETS = ["rec", "rec_yds", "rush_att", "rush_yds", "rush_rec_yds", "pass_att", "pass_cmp", "pass_yds", "pass_rush_yds"]


def score(s: pl.DataFrame, proj: pl.DataFrame, sim_out: dict) -> pl.DataFrame:
    """Votes for every DraftKings prop in `s` (screened rows from all real books, with p_over / hold / prices).
    `proj`: player_id, week, market, proj. `sim_out`: {(player_id, week): {market: samples}}."""
    agg = s.group_by(C.KEY).agg(pl.col("line").n_unique().alias("nl"), pl.col("line").max().alias("hi"),
                                pl.col("line").min().alias("lo"))
    dk = s.filter(pl.col("book") == "DK NJ").unique(subset=C.KEY).join(agg, on=C.KEY)
    dk = dk.join(proj.select("player_id", "week", "market", "proj"), on=["player_id", "week", "market"], how="left")
    p_sim = [float(np.mean(sim_out[(a, b)][m] > l)) if (a, b) in sim_out and m in sim_out[(a, b)] else None
             for a, b, m, l in zip(dk["player_id"], dk["week"], dk["market"], dk["line"])]
    dk = dk.with_columns(pl.Series("p_sim", p_sim, dtype=pl.Float64))
    gap = (pl.col("line") - pl.col("proj")) / pl.col("line").abs().clip(lower_bound=1)
    vote = lambda under, over: pl.when(under).then(-1).when(over).then(1).otherwise(0)  # noqa: E731
    return dk.with_columns(
        vote((pl.col("nl") >= 2) & (pl.col("line") == pl.col("hi")), (pl.col("nl") >= 2) & (pl.col("line") == pl.col("lo"))).alias("v_disagree"),
        vote(gap >= 0.10, gap <= -0.10).fill_null(0).alias("v_proj"),
        vote(pl.col("p_over") - pl.col("p_sim") >= 0.05,
             pl.col("p_sim") - pl.col("p_over") >= 0.05).fill_null(0).alias("v_sim"),
        vote(pl.col("under_odds") < -120, pl.col("over_odds") < -120).alias("v_price"),
        (pl.col("p_sim") - pl.col("p_over")).alias("sim_edge"))


def scored(season: int, sim: Simulator) -> pl.DataFrame:
    """Historical scoring: final lines, graded rows, pushes dropped before the books-disagree count."""
    g = P.graded(P.join(P.load_lines(season), P.load_stats(season), P.load_snaps(season)))
    s = C.screened(g).filter(pl.col("result") != "push", pl.col("market").is_in(MARKETS))
    out = sim.run(season, keep=set(zip(s["player_id"].to_list(), s["week"].to_list())))
    return score(s, R.projections(season), out)


def grade(x: pl.DataFrame) -> tuple[int, float, float, int]:
    if x.height == 0:
        return 0, float("nan"), float("nan"), 0
    under = x["votes"].to_numpy() < 0
    won = np.where(under, x["result"].to_numpy() == "under", x["result"].to_numpy() == "over").astype(float)
    odds = np.where(under, x["under_odds"].to_numpy(), x["over_odds"].to_numpy())
    return x.height, float(won.mean()), float(P.profit(odds, won).mean()), x["week"].n_unique()



def with_votes(d: pl.DataFrame) -> pl.DataFrame:
    return d.with_columns((pl.col("v_disagree") + pl.col("v_proj") + pl.col("v_sim") + pl.col("v_price")).alias("votes"))


def rule_s1(d: pl.DataFrame) -> pl.DataFrame:
    return with_votes(d).filter(pl.col("votes").abs() == 4)


def bets_frame(x: pl.DataFrame) -> pl.DataFrame:
    """Rows in the shape props_selective.evaluate grades: the side bet, its price and result."""
    under = pl.col("votes") < 0
    return x.with_columns(pl.when(under).then(pl.col("under_odds")).otherwise(pl.col("over_odds")).alias("under_odds"),
                          pl.when(under).then(pl.col("result"))
                          .otherwise(pl.when(pl.col("result") == "over").then(pl.lit("under")).otherwise(pl.lit("over")))
                          .alias("result"))
