"""Ladder exploration on 2024-2025 ONLY (docs/simulator_declaration.md).

For each milestone ("N or more") price at a book that also posts a screened main over/under for the same
player-game-market: P(X >= N) from the simulator centered on that book's own main line, vs the milestone's implied
probability 1/decimal(price) (one-sided, vig included). Bets: "yes" when model minus implied >= k, graded on the
actual stat. Also reports how milestone "yes" bets do by price band with no model. Writes docs/ladder_explore.txt."""
from __future__ import annotations

import io
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.props import ladder as L
from nflbet.props import core as P
from nflbet.props import confirm as C
from nflbet.props.sim import Simulator


def main() -> None:
    buf = io.StringIO()
    pr = lambda *a: print(*a, file=buf, flush=True)  # noqa: E731
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    for season in (2024, 2025):
        try:
            ms = L.load_milestones(season)
        except FileNotFoundError:
            pr(f"{season}: no milestone file"); continue
        stats, snaps = P.load_stats(season), P.load_snaps(season)
        msj = P.join(ms, stats, snaps).filter(pl.col("actual").is_not_null())
        main = C.screened(P.graded(P.join(P.load_lines(season), stats, snaps))).unique(subset=C.KEY + ["book"]) \
            .select(*C.KEY, "book", pl.col("line").alias("main_line"), "p_over")
        x = msj.join(main, on=C.KEY + ["book"], how="inner")
        out = sim.run(season, keep=set(zip(x["player_id"].to_list(), x["week"].to_list())))
        rows, cache = [], {}
        for r in x.iter_rows(named=True):
            s = out.get((r["player_id"], r["week"]), {}).get(r["market"])
            if s is None:
                continue
            key = (r["player_id"], r["week"], r["market"], r["book"])
            if key not in cache:
                cache[key] = L.center(s, r["main_line"], r["p_over"], r["market"] in L.COUNT_MARKETS)
            q = 1 / P.american_to_decimal(r["yes_odds"])
            rows.append({"market": r["market"], "book": r["book"], "week": r["week"], "N": r["threshold"],
                         "rung": r["threshold"] - r["main_line"], "odds": r["yes_odds"], "q": q,
                         "p": float(np.mean(cache[key] >= r["threshold"])), "hit": float(r["actual"] >= r["threshold"])})
        d = pl.DataFrame(rows)
        pr(f"\n== {season}: {d.height} milestone prices with a same-book main line and a simulation; books {dict(d['book'].value_counts().iter_rows())}")
        pr("  no model, 'yes' at every milestone, by implied probability:")
        for lo, hi in [(0, .1), (.1, .25), (.25, .5), (.5, .75), (.75, 1.01)]:
            z = d.filter(pl.col("q").is_between(lo, hi, closed="left"))
            if z.height:
                pr(f"    implied [{lo:.2f},{hi:.2f}): n {z.height:6d}  implied {z['q'].mean():.3f}  model {z['p'].mean():.3f}"
                   f"  hit {z['hit'].mean():.3f}  ROI {P.profit(z['odds'].to_numpy(), z['hit'].to_numpy()).mean():+.3f}")
        for k in (0.03, 0.05, 0.10):
            z = d.filter(pl.col("p") - pl.col("q") >= k)
            if z.height:
                pr(f"  'yes' when model - implied >= {k:.2f}: n {z.height:6d}  hit {z['hit'].mean():.3f}  implied {z['q'].mean():.3f}"
                   f"  ROI {P.profit(z['odds'].to_numpy(), z['hit'].to_numpy()).mean():+.3f}  weeks {z['week'].n_unique()}")
        z = d.filter(pl.col("p") - pl.col("q") >= 0.05)
        for mk in sorted(z["market"].unique().to_list()):
            y = z.filter(pl.col("market") == mk)
            pr(f"    {mk:9s} n {y.height:5d} hit {y['hit'].mean():.3f} implied {y['q'].mean():.3f} ROI {P.profit(y['odds'].to_numpy(), y['hit'].to_numpy()).mean():+.3f}")
        for lab, c in {"rung below main line": pl.col("rung") < 0, "rung above main line": pl.col("rung") > 0}.items():
            y = z.filter(c)
            if y.height:
                pr(f"    {lab:21s} n {y.height:5d} hit {y['hit'].mean():.3f} ROI {P.profit(y['odds'].to_numpy(), y['hit'].to_numpy()).mean():+.3f}")
    (config.ROOT / "docs" / "ladder_explore.txt").write_text(buf.getvalue())
    sys.stdout.write(buf.getvalue())


if __name__ == "__main__":
    main()
