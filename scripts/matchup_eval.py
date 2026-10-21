"""Matchup weight (docs/simulator_declaration.md addendum): choose w on 2024 by over/under log loss of the
simulator's own P(over) against results; check the chosen w against w = 0 on 2025 (over/unders and data-only
milestone ladders). Writes docs/matchup_eval.txt."""
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

MARKETS = ["rec", "rec_yds", "rush_att", "rush_yds", "rush_rec_yds", "pass_att", "pass_cmp", "pass_yds", "pass_rush_yds"]
GRID = [0.0, 0.5, 1.0, 1.5]


def ll(p, y):
    p = np.clip(p, 0.02, 0.98)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def ou(sim, season):
    g = P.graded(P.join(P.load_lines(season), P.load_stats(season), P.load_snaps(season)))
    dk = C.screened(g).filter(pl.col("book") == "DK NJ", pl.col("result") != "push", pl.col("market").is_in(MARKETS)) \
        .unique(subset=C.KEY)
    out = sim.run(season, keep=set(zip(dk["player_id"].to_list(), dk["week"].to_list())))
    rows = []
    for r in dk.iter_rows(named=True):
        s = out.get((r["player_id"], r["week"]), {}).get(r["market"])
        if s is not None:
            rows.append({"p": float(np.mean(s > r["line"])), "mkt": r["p_over"], "y": float(r["result"] == "over"),
                         "miss": abs(r["actual"] - float(s.mean())), "lmiss": abs(r["actual"] - r["line"])})
    return pl.DataFrame(rows)


def ladders(sim, season):
    stats, snaps = P.load_stats(season), P.load_snaps(season)
    ms = P.join(L.load_milestones(season), stats, snaps).filter(pl.col("actual").is_not_null(), pl.col("player_id").is_not_null())
    out = sim.run(season, keep=set(zip(ms["player_id"].to_list(), ms["week"].to_list())))
    rows = []
    for r in ms.iter_rows(named=True):
        s = out.get((r["player_id"], r["week"]), {}).get(r["market"])
        if s is not None:
            rows.append({"odds": r["yes_odds"], "q": 1 / P.american_to_decimal(r["yes_odds"]),
                         "p": float(np.mean(s >= r["threshold"])), "hit": float(r["actual"] >= r["threshold"])})
    return pl.DataFrame(rows)


def main() -> None:
    buf = io.StringIO()
    pr = lambda *a: print(*a, file=buf, flush=True)  # noqa: E731
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    pr("== choose the matchup weight on 2024 (over/under log loss of the simulator's own P(over); lower is better)")
    best = None
    for w in GRID:
        sim.w = w
        x = ou(sim, 2024)
        v = ll(x["p"].to_numpy(), x["y"].to_numpy())
        pr(f"  w {w:.1f}: n {x.height}  log loss {v:.4f}  mean miss {x['miss'].mean():.2f}")
        best = (v, w) if best is None or v < best[0] else best
    w = best[1]
    pr(f"  chosen w = {w}")
    pr("\n== 2025 check: chosen weight vs no matchup")
    for lab, ww in (("no matchup (w 0)", 0.0), (f"matchup (w {w})", w)):
        sim.w = ww
        x = ou(sim, 2025)
        pr(f"  {lab}: over/unders n {x.height}  log loss {ll(x['p'].to_numpy(), x['y'].to_numpy()):.4f}"
           f" (DK {ll(x['mkt'].to_numpy(), x['y'].to_numpy()):.4f})  mean miss {x['miss'].mean():.2f} (line {x['lmiss'].mean():.2f})")
        for k in (0.05, 0.10):
            for side, cond in (("over", pl.col("p") - pl.col("mkt") >= k), ("under", pl.col("mkt") - pl.col("p") >= k)):
                z = x.filter(cond)
                if z.height:
                    won = z["y"].to_numpy() if side == "over" else 1 - z["y"].to_numpy()
                    pr(f"     {side:5s} when >= {k:.2f} off DK: n {z.height:5d} win {won.mean():.3f}")
        d = ladders(sim, 2025)
        for k in (0.05, 0.10, 0.20):
            z = d.filter(pl.col("p") - pl.col("q") >= k)
            pr(f"     ladder 'yes' when model - implied >= {k:.2f}: n {z.height:6d}  hit {z['hit'].mean():.3f}  implied {z['q'].mean():.3f}"
               f"  ROI {P.profit(z['odds'].to_numpy(), z['hit'].to_numpy()).mean():+.3f}")
    (config.ROOT / "docs" / "matchup_eval.txt").write_text(buf.getvalue())
    sys.stdout.write(buf.getvalue())


if __name__ == "__main__":
    main()
