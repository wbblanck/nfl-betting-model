"""Screener exploration on 2024-2025 ONLY: score every DraftKings over/under prop on independent signals and bet
only the strongest few each week. No weights are fitted: each signal is a vote for the over or the under, and
props are ranked by votes, then by the simulator's edge.

Signals (all pre-game, all computed earlier in this repo):
  disagree  books post different lines and DK has the highest -> under; DK has the lowest -> over
  proj      projection model (props_projection) >= 10% below DK's line -> under; >= 10% above -> over
  sim       simulator P(over) vs de-vigged DK P(over), >= 5 points -> that side
  price     DK already prices the under below -120 -> under; the over below -120 -> over
Writes docs/screener_explore.txt."""
from __future__ import annotations

import io
import sys

import numpy as np
import polars as pl

from nflbet import config, props as P
from nflbet.sim import Simulator

from nflbet.screener import MARKETS, grade, scored  # noqa: E402,F401


def main() -> None:
    buf = io.StringIO()
    pr = lambda *a: print(*a, file=buf, flush=True)  # noqa: E731
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    for season in (2024, 2025):
        d = scored(season, sim).with_columns(
            (pl.col("v_disagree") + pl.col("v_proj") + pl.col("v_sim") + pl.col("v_price")).alias("votes"))
        d = d.with_columns(pl.col("votes").abs().alias("strength"),
                           (pl.col("sim_edge").abs().fill_null(0) * pl.col("votes").sign()).abs().alias("tiebreak"))
        pr(f"\n== {season}: {d.height} DK props scored")
        for v in ("v_disagree", "v_proj", "v_sim", "v_price"):
            pr(f"  {v:10s} votes under {int((d[v] < 0).sum()):5d}  over {int((d[v] > 0).sum()):5d}")
        pr("  bet every prop with at least k signals agreeing (and none against):")
        for k in (1, 2, 3, 4):
            x = d.filter(pl.col("strength") >= k,
                         ~(((pl.col("v_disagree") * pl.col("votes")) < 0) | ((pl.col("v_proj") * pl.col("votes")) < 0)
                           | ((pl.col("v_sim") * pl.col("votes")) < 0) | ((pl.col("v_price") * pl.col("votes")) < 0)))
            n, w, roi, wk = grade(x)
            pr(f"    >= {k} agree: n {n:5d}  win {w:.3f}  ROI {roi:+.3f}  weeks {wk}")
        pr("  bet only the top K per week (most signals agreeing, then the simulator's edge):")
        ranked = d.filter(pl.col("strength") > 0).sort(["week", "strength", "tiebreak"], descending=[False, True, True])
        for K in (3, 5, 10, 20):
            x = ranked.group_by("week", maintain_order=True).head(K)
            n, w, roi, wk = grade(x)
            pr(f"    top {K:2d}/week: n {n:5d}  win {w:.3f}  ROI {roi:+.3f}  weeks {wk}")
    (config.ROOT / "docs" / "screener_explore.txt").write_text(buf.getvalue())
    sys.stdout.write(buf.getvalue())


if __name__ == "__main__":
    main()
