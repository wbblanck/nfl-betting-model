"""ATS rating vs bet365 opening lines and prices, 2022-2024 (docs/ats_clv2_preregistration.md); Pinnacle 2014-2017
descriptive. Writes docs/ats_clv2.md and data/backtests/ats_clv2.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import ats_clv as C  # noqa: E402

from nflbet import ats as A, config  # noqa: E402


def frame(seasons, k):
    tg = A.team_games(list(range(min(seasons) - 1, max(seasons) + 1)))
    x = A.fair(A.with_ratings(A.games(seasons), A.ratings(tg, k["h"], k["k"], k["r"])), k["c"], k["hfa"]).filter(pl.col("week") >= 2)
    ab = pl.read_csv(config.ROOT / "data" / "odds" / "asb_nfl_games.csv").select(
        "game_id", "home_open", "home_close", "home_open_odds", "away_open_odds")
    return x.join(ab, on="game_id").drop_nulls(["home_open", "home_close", "home_open_odds", "away_open_odds"])


def main():
    k = json.loads((config.ROOT / "data" / "backtests" / "ats_constants.json").read_text())
    out = {"test_bet365_2022_2024": C.evaluate(frame([2022, 2023, 2024], k), 0.05 / 3),
           "descriptive_pinnacle_2014_2017": C.evaluate(frame([2014, 2015, 2016, 2017], k), 0.05 / 3)}
    (config.ROOT / "data" / "backtests" / "ats_clv2.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["# ATS rating vs bettable opening lines", "", "Pre-registration: docs/ats_clv2_preregistration.md. Lines: data/odds/asb (personal use only).", ""]
    for name, r in out.items():
        c1, c2, c3 = r["C1"], r["C2"], r["C3"]
        L += [f"## {name}", "",
              f"- **C1** (close − open) on (fair − open): coefficient {c1['coef']:+.3f}, interval {c1['ci'][0]:+.3f} to {c1['ci'][1]:+.3f}, n {c1['n']}: **{'PASS' if c1['pass'] else 'FAIL'}**",
              f"- **C2** CLV, |fair − open| ≥ 1.5: n {c2['n']} in {c2['weeks']} weeks, mean {c2['mean_clv']:+.3f} pts (toward the bet {c2['share_clv_pos']:.0%}), interval {c2['ci'][0]:+.3f} to {c2['ci'][1]:+.3f}: **{'PASS' if c2['pass'] else 'FAIL'}**",
              f"- **C3** at the actual opening price: covers {c3['cover_open']:.1%}, ROI {c3['roi_open']:+.1%}, interval {c3['ci'][0]:+.1%} to {c3['ci'][1]:+.1%}: **{'PASS' if c3['pass'] else 'FAIL'}**", "",
              "| |fair − open| ≥ | Bets | Mean CLV (pts) | CLV > 0 | Cover at open | ROI at open price | Cover at close |", "|---|---|---|---|---|---|---|"]
        L += [f"| {t} | {v['n']} | {v['mean_clv']:+.3f} | {v['share_clv_pos']:.0%} | {v['cover_open']:.1%} | {v['roi_open']:+.1%} | {v['cover_close']:.1%} |" for t, v in r["thresholds"].items()] + [""]
    (config.ROOT / "docs" / "ats_clv2.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
