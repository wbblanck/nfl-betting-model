"""Ladder exploration variant (2024-2025 ONLY): the simulator's OWN distribution, not centered on the book's
line, so "who goes over the milestone" comes only from NFL data (player game logs, team volume from the
spread/total, per-play yards). Same bets and grading as ladder_explore.py. Writes docs/ladder_explore_raw.txt."""
from __future__ import annotations

import io
import sys

import numpy as np
import polars as pl

from nflbet import config, ladder as L, props as P, props_confirm as C
from nflbet.sim import Simulator


def main() -> None:
    buf = io.StringIO()
    pr = lambda *a: print(*a, file=buf, flush=True)  # noqa: E731
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    for season in (2024, 2025):
        stats, snaps = P.load_stats(season), P.load_snaps(season)
        ms = P.join(L.load_milestones(season), stats, snaps).filter(pl.col("actual").is_not_null(),
                                                                    pl.col("player_id").is_not_null())
        out = sim.run(season, keep=set(zip(ms["player_id"].to_list(), ms["week"].to_list())))
        rows = []
        for r in ms.iter_rows(named=True):
            s = out.get((r["player_id"], r["week"]), {}).get(r["market"])
            if s is None:
                continue
            rows.append({"market": r["market"], "week": r["week"], "odds": r["yes_odds"],
                         "q": 1 / P.american_to_decimal(r["yes_odds"]), "p": float(np.mean(s >= r["threshold"])),
                         "hit": float(r["actual"] >= r["threshold"])})
        d = pl.DataFrame(rows)
        pr(f"\n== {season} ({'fit season' if season == 2024 else 'check'}): {d.height} milestone prices with a simulation")
        pr("  calibration of the simulator's own P(milestone):")
        for lo, hi in [(0, .1), (.1, .25), (.25, .5), (.5, .75), (.75, 1.01)]:
            z = d.filter(pl.col("p").is_between(lo, hi, closed="left"))
            if z.height:
                pr(f"    model [{lo:.2f},{hi:.2f}): n {z.height:6d}  model {z['p'].mean():.3f}  book implied {z['q'].mean():.3f}  hit {z['hit'].mean():.3f}")
        for k in (0.05, 0.10, 0.20):
            z = d.filter(pl.col("p") - pl.col("q") >= k)
            if z.height:
                pr(f"  'yes' when model - implied >= {k:.2f}: n {z.height:6d}  hit {z['hit'].mean():.3f}  implied {z['q'].mean():.3f}"
                   f"  ROI {P.profit(z['odds'].to_numpy(), z['hit'].to_numpy()).mean():+.3f}")
    (config.ROOT / "docs" / "ladder_explore_raw.txt").write_text(buf.getvalue())
    sys.stdout.write(buf.getvalue())


if __name__ == "__main__":
    main()
