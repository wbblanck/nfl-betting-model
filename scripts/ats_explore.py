"""ATS exploration on 2016-2021 ONLY (docs/ats_declaration.md): choose the rating constants by mean absolute error of
the fair margin against the actual margin, compare with the closing spread, and tabulate key numbers from 1999-2021
margins. Writes docs/ats_explore.txt and freezes data/backtests/ats_constants.json."""
from __future__ import annotations

import itertools
import json
import math

import numpy as np
import polars as pl

from nflbet import config
from nflbet.ats import rating as A

EXPLORE = list(range(2016, 2022))


def main() -> None:
    L = []
    pr = lambda *a: (L.append(" ".join(str(x) for x in a)), print(*a, flush=True))  # noqa: E731
    tg = A.team_games(list(range(2015, 2022)))
    g = A.games(EXPLORE)
    best = None
    pr("grid (weeks 2-18, 2016-2021): h k r -> MAE fair vs margin")
    for h, k, r in itertools.product([4.0, 8.0, math.inf], [2.0, 4.0, 8.0], [0.3, 0.5, 0.7]):
        x = A.with_ratings(g, A.ratings(tg, h, k, r)).filter(pl.col("week") >= 2)
        c, hfa = A.fit_line(x)
        mae = float((A.fair(x, c, hfa)["fair"] - x["result"]).abs().mean())
        pr(f"  h {h:>4} k {k:>3} r {r:.1f}: c {c:6.1f} hfa {hfa:4.2f} MAE {mae:.3f}")
        if best is None or mae < best[0]:
            best = (mae, h, k, r, c, hfa)
    mae, h, k, r, c, hfa = best
    x = A.fair(A.with_ratings(g, A.ratings(tg, h, k, r)), c, hfa)
    w2 = x.filter(pl.col("week") >= 2)
    pr(f"\nchosen: h {h}, k {k}, r {r}, c {c:.2f}, hfa {hfa:.2f}")
    pr(f"MAE vs actual margin, weeks 2-18: fair {mae:.3f} | closing spread {float((w2['spread_line'] - w2['result']).abs().mean()):.3f}")
    pr(f"MAE week 1 (prior only): fair {float((x.filter(pl.col('week') == 1)['fair'] - x.filter(pl.col('week') == 1)['result']).abs().mean()):.3f}"
       f" | close {float((x.filter(pl.col('week') == 1)['spread_line'] - x.filter(pl.col('week') == 1)['result']).abs().mean()):.3f}")
    pr(f"corr(fair, close) {float(np.corrcoef(w2['fair'], w2['spread_line'])[0, 1]):.3f}; mean |fair - close| {float((w2['fair'] - w2['spread_line']).abs().mean()):.2f}")
    # descriptive look at disagreements on the explore seasons (hypotheses only)
    pr("\ndisagreements at the closing price, 2016-2021 (explore, descriptive):")
    for t in (0.5, 1.0, 1.5, 2.0, 3.0):
        z = w2.filter((pl.col("fair") - pl.col("spread_line")).abs() >= t)
        home = (z["fair"] > z["spread_line"]).to_numpy()
        m, sl = z["result"].to_numpy(), z["spread_line"].to_numpy()
        win = np.where(home, m > sl, m < sl)
        push = m == sl
        n = int((~push).sum())
        pr(f"  |fair - close| >= {t}: n {z.height}, covers {win[~push].mean():.3f} of {n} decided" if n else f"  >= {t}: none")
    # key numbers: share of games decided by each margin, 1999-2021
    import nflreadpy as nfl
    s = nfl.load_schedules(seasons=list(range(1999, 2022))).filter(pl.col("game_type") == "REG", pl.col("result").is_not_null())
    m = s["result"].abs().to_numpy()
    pr(f"\nkey numbers 1999-2021 ({len(m)} games): share of games decided by exactly N points")
    tab = {int(v): float((m == v).mean()) for v in range(0, 22)}
    pr("  " + "  ".join(f"{v}: {p:.1%}" for v, p in tab.items() if p >= 0.01))
    (config.ROOT / "docs" / "ats_explore.txt").write_text("\n".join(L) + "\n")
    (config.ROOT / "data" / "backtests" / "ats_constants.json").write_text(json.dumps(
        {"h": h, "k": k, "r": r, "c": c, "hfa": hfa, "fit_seasons": EXPLORE, "margin_share_1999_2021": tab}, indent=1))


if __name__ == "__main__":
    main()
