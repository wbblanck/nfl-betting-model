"""Exploration (2024-2025 only): does the pre-game projection predict ESPN BET's open-to-final prop line move,
and would betting its side at ESPN's opening price have paid? Writes docs/espn_clv_explore.txt.

Mechanism: OLS final = a + b*open + c*projection per season (c > 0: the projection knows where the line goes;
the biased form, regressing the move on projection - open, is not used). Bets: under at the open line and
price when the open line is >= k above the projection (over when below), graded on the actual stat."""
from __future__ import annotations

import io
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.sources import espn as E
from nflbet.props import core as P
from nflbet.props import projection as R


def main() -> None:
    buf = io.StringIO()
    pr = lambda *a: print(*a, file=buf)  # noqa: E731
    for s in (2024, 2025):
        try:
            e = E.with_player_id(E.paired(E.load(s))).filter(pl.col("player_id").is_not_null())
        except FileNotFoundError:
            pr(f"{s}: no ESPN file"); continue
        proj = R.projections(s).select("player_id", "week", "market", "proj", "actual")
        m = e.join(proj, on=["player_id", "week", "market"]).filter(pl.col("open_line").is_not_null())
        X = np.column_stack([np.ones(m.height), m["open_line"], m["proj"]])
        c = np.linalg.lstsq(X, m["cur_line"].to_numpy(), rcond=None)[0][2]
        rng = np.random.default_rng(7)
        wk = m["week"].to_numpy(); ids = np.unique(wk); grp = [np.where(wk == w)[0] for w in ids]
        cur, opn, prj = m["cur_line"].to_numpy(), m["open_line"].to_numpy(), m["proj"].to_numpy()
        bs = []
        for _ in range(1000):
            ix = np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])
            bs.append(np.linalg.lstsq(np.column_stack([np.ones(len(ix)), opn[ix], prj[ix]]), cur[ix], rcond=None)[0][2])
        moved = np.mean(cur != opn)
        pr(f"\n== {s}: {m.height} ESPN props with an open line and a projection; line moved on {moved:.1%}")
        pr(f"  final = a + b*open + c*projection: c = {c:+.3f} (week-bootstrap 95% {np.quantile(bs, .025):+.3f} to {np.quantile(bs, .975):+.3f})")
        m = m.with_columns(((pl.col("open_line") - pl.col("proj")) / pl.col("open_line").abs().clip(lower_bound=1)).alias("gap"))
        for side, cond, oc in (("UNDER", lambda k: pl.col("gap") >= k, "open_under"), ("OVER", lambda k: pl.col("gap") <= -k, "open_over")):
            for k in (0.05, 0.10, 0.20, 0.30):
                y = m.filter(cond(k), pl.col(oc).is_not_null(), pl.col("actual") != pl.col("open_line"))
                if y.height == 0:
                    continue
                won = ((y["actual"] < y["open_line"]) if side == "UNDER" else (y["actual"] > y["open_line"])).cast(pl.Float64).to_numpy()
                mv = (y["open_line"] - y["cur_line"]).to_numpy() * (1 if side == "UNDER" else -1)
                pr(f"  {side} at open, gap >= {k:.2f}: n {y.height:5d}  win {won.mean():.3f}  ROI {P.profit(y[oc].to_numpy(), won).mean():+.3f}"
                   f"  line then moved our way {np.mean(mv > 0):.1%} / against {np.mean(mv < 0):.1%}")
        for mk in ("rec", "rec_yds", "rush_yds", "rush_rec_yds", "pass_yds"):
            y = m.filter(pl.col("market") == mk, pl.col("gap") >= 0.10, pl.col("open_under").is_not_null(), pl.col("actual") != pl.col("open_line"))
            if y.height:
                won = (y["actual"] < y["open_line"]).cast(pl.Float64).to_numpy()
                pr(f"    UNDER gap>=0.10 {mk:12s} n {y.height:4d} win {won.mean():.3f} ROI {P.profit(y['open_under'].to_numpy(), won).mean():+.3f}")
    (config.ROOT / "docs" / "espn_clv_explore.txt").write_text(buf.getvalue())
    sys.stdout.write(buf.getvalue())


if __name__ == "__main__":
    main()
