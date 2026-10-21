"""Simulator check (docs/simulator_declaration.md): fit 2024, score 2024 (in-sample) and 2025 (check).

For each screened DraftKings over/under: simulated P(over) vs the de-vigged DraftKings P(over), log loss on the
result, calibration by decile, and how often the result falls inside the simulated 50% / 80% ranges.
Writes docs/sim_eval.txt."""
from __future__ import annotations

import io
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.props import core as P
from nflbet.props import confirm as C
from nflbet.props.sim import Simulator

MARKETS = ["rec", "rec_yds", "rush_att", "rush_yds", "rush_rec_yds", "pass_att", "pass_cmp", "pass_yds", "pass_rush_yds"]


def ll(p, y):
    p = np.clip(p, 0.02, 0.98)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def main() -> None:
    buf = io.StringIO()
    pr = lambda *a: print(*a, file=buf, flush=True)  # noqa: E731
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    pr("team volume fit (2024):", {k: [round(x, 3) for x in v["coef"]] + [round(v["sd"], 2)] for k, v in sim.vol.items()})
    for season in (2024, 2025):
        g = P.graded(P.join(P.load_lines(season), P.load_stats(season), P.load_snaps(season)))
        dk = C.screened(g).filter(pl.col("book") == "DK NJ", pl.col("result") != "push", pl.col("market").is_in(MARKETS)) \
            .unique(subset=C.KEY)
        out = sim.run(season, keep=set(zip(dk["player_id"].to_list(), dk["week"].to_list())))
        rows = []
        for r in dk.iter_rows(named=True):
            s = out.get((r["player_id"], r["week"]), {}).get(r["market"])
            if s is None:
                continue
            rows.append({**{k: r[k] for k in ("player_id", "week", "market", "line", "p_over", "over_odds", "under_odds",
                                              "actual", "result")},
                         "p_sim": float(np.mean(s > r["line"])),
                         "in50": float(np.quantile(s, .25) <= r["actual"] <= np.quantile(s, .75)),
                         "in80": float(np.quantile(s, .10) <= r["actual"] <= np.quantile(s, .90)),
                         "sim_mean": float(s.mean())})
        x = pl.DataFrame(rows)
        y = (x["result"] == "over").cast(pl.Float64).to_numpy()
        pr(f"\n== {season} ({'fit, in-sample' if season == 2024 else 'check'}): {x.height} of {dk.height} DK props simulated")
        pr(f"  log loss: simulator {ll(x['p_sim'].to_numpy(), y):.4f} | DK de-vigged {ll(x['p_over'].to_numpy(), y):.4f} | coin 0.6931")
        pr(f"  inside simulated 50% range {x['in50'].mean():.3f} (target 0.50), 80% range {x['in80'].mean():.3f} (target 0.80)")
        pr(f"  mean |actual - sim mean| {float((x['actual'] - x['sim_mean']).abs().mean()):.2f} vs |actual - line| {float((x['actual'] - x['line']).abs().mean()):.2f}")
        pr("  calibration (simulator P(over) decile: mean p, over rate):")
        q = np.quantile(x["p_sim"].to_numpy(), np.linspace(0, 1, 11))
        for lo, hi in zip(q[:-1], q[1:]):
            z = x.filter(pl.col("p_sim").is_between(lo, hi, closed="left" if hi < q[-1] else "both"))
            if z.height:
                pr(f"    [{lo:.2f},{hi:.2f}] n {z.height:5d}  p {z['p_sim'].mean():.3f}  over {np.mean(z['result'].to_numpy() == 'over'):.3f}")
        for mk in MARKETS:
            z = x.filter(pl.col("market") == mk)
            if z.height >= 100:
                yz = (z["result"] == "over").cast(pl.Float64).to_numpy()
                pr(f"    {mk:13s} n {z.height:5d}  log loss sim {ll(z['p_sim'].to_numpy(), yz):.4f}  DK {ll(z['p_over'].to_numpy(), yz):.4f}"
                   f"  in50 {z['in50'].mean():.2f} in80 {z['in80'].mean():.2f}")
        for k in (0.05, 0.10, 0.15):
            for side, cond, oc, res in (("over", pl.col("p_sim") - pl.col("p_over") >= k, "over_odds", "over"),
                                        ("under", pl.col("p_over") - pl.col("p_sim") >= k, "under_odds", "under")):
                z = x.filter(cond)
                if z.height:
                    won = (z["result"] == res).cast(pl.Float64).to_numpy()
                    pr(f"  bet {side:5s} when the simulator is >= {k:.2f} off DK: n {z.height:5d}  win {won.mean():.3f}  ROI {P.profit(z[oc].to_numpy(), won).mean():+.3f}")
    (config.ROOT / "docs" / "sim_eval.txt").write_text(buf.getvalue())
    sys.stdout.write(buf.getvalue())


if __name__ == "__main__":
    main()
