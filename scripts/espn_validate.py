"""Is ESPN BET's final prop line pregame? (docs/espn_declaration.md). Compares, for the same player-week-market:
ESPN's open and final lines with DraftKings' line in the Action Network data, and checks the final line is not
closer to the actual result than DraftKings' (a line updated during the game would be). Writes
docs/espn_validation.txt."""
from __future__ import annotations

import io
import sys

import numpy as np
import polars as pl

from nflbet import config, espn as E, props as P


def main(seasons=(2024, 2025)) -> None:
    buf = io.StringIO()
    pr = lambda *a: print(*a, file=buf)  # noqa: E731
    for s in seasons:
        try:
            e = E.with_player_id(E.paired(E.load(s))).filter(pl.col("player_id").is_not_null())
        except FileNotFoundError:
            pr(f"{s}: no ESPN file"); continue
        an = P.join(P.load_lines(s), P.load_stats(s), P.load_snaps(s))
        dk = P.graded(an).filter(pl.col("book") == "DK NJ").unique(subset=["player_id", "week", "market"]) \
            .select("player_id", "week", "market", pl.col("line").alias("dk_line"), "actual")
        m = e.join(dk, on=["player_id", "week", "market"])
        d_cur = (m["cur_line"] - m["dk_line"]).to_numpy()
        d_open = (m["open_line"] - m["dk_line"]).drop_nulls().to_numpy()
        pr(f"\n== {s}: ESPN paired props {e.height}, matched to a DraftKings line {m.height}")
        pr(f"  final line vs DK: equal {np.mean(d_cur == 0):.1%}, within 1 {np.mean(np.abs(d_cur) <= 1):.1%}, "
           f"median |diff| {np.median(np.abs(d_cur)):.1f}")
        pr(f"  open line vs DK:  equal {np.mean(d_open == 0):.1%}, within 1 {np.mean(np.abs(d_open) <= 1):.1%}, "
           f"median |diff| {np.median(np.abs(d_open)):.1f}")
        a = m["actual"].to_numpy().astype(float)
        pr(f"  mean |actual - line|: ESPN final {np.mean(np.abs(a - m['cur_line'].to_numpy())):.2f}, "
           f"DK {np.mean(np.abs(a - m['dk_line'].to_numpy())):.2f}, ESPN open "
           f"{np.nanmean(np.abs(a - m['open_line'].to_numpy())):.2f}")
        x = m.filter(pl.col("cur_line") != pl.col("dk_line"))
        if x.height > 30:
            c = np.corrcoef((x["cur_line"] - x["dk_line"]).to_numpy(), (x["actual"] - x["dk_line"]).to_numpy())[0, 1]
            side = np.mean(np.sign((x["cur_line"] - x["dk_line"]).to_numpy()) == np.sign((x["actual"] - x["dk_line"]).to_numpy()))
            pr(f"  where ESPN final != DK (n {x.height}): corr(ESPN - DK, actual - DK) {c:+.3f}; "
               f"ESPN on the actual's side of DK {side:.1%}  (an in-game line would be far above 50%)")
        for mk in ("rec_yds", "rush_yds", "pass_yds", "rec"):
            y = m.filter(pl.col("market") == mk)
            if y.height:
                dd = (y["cur_line"] - y["dk_line"]).to_numpy()
                pr(f"    {mk:9s} n {y.height:5d} equal {np.mean(dd == 0):.1%} within 1 {np.mean(np.abs(dd) <= 1):.1%}")
    (config.ROOT / "docs" / "espn_validation.txt").write_text(buf.getvalue())
    sys.stdout.write(buf.getvalue())


if __name__ == "__main__":
    main()
