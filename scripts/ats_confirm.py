"""ATS confirm on 2022-2025 (docs/ats_declaration.md), run once with the frozen constants in
data/backtests/ats_constants.json. Writes docs/ats_confirm.md and data/backtests/ats_confirm.json."""
from __future__ import annotations

import json

import numpy as np
import polars as pl

from nflbet import ats as A, config, props as P

CONFIRM = [2022, 2023, 2024, 2025]
B = 4000


def week_boot(stat, cl, idx_all, level, seed=7):
    ids = np.unique(cl)
    grp = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    bs = [stat(np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])) for _ in range(B)]
    return float(np.quantile(bs, level)), float(np.quantile(bs, 1 - level))


def main() -> None:
    k = json.loads((config.ROOT / "data" / "backtests" / "ats_constants.json").read_text())
    tg = A.team_games(list(range(min(CONFIRM) - 1, max(CONFIRM) + 1)))
    x = A.fair(A.with_ratings(A.games(CONFIRM), A.ratings(tg, k["h"], k["k"], k["r"])), k["c"], k["hfa"])
    x = x.filter(pl.col("week") >= 2)                      # the rating's weeks 2-18, as fitted
    m, close, fr = x["result"].to_numpy().astype(float), x["spread_line"].to_numpy(), x["fair"].to_numpy()
    cl = (x["season"] * 100 + x["week"]).to_numpy()
    # T1: margin ~ close + (fair - close)
    X = np.c_[np.ones_like(m), close, fr - close]

    def coef(ix):
        return float(np.linalg.lstsq(X[ix], m[ix], rcond=None)[0][2])
    b = coef(np.arange(len(m)))
    lo1, hi1 = week_boot(coef, cl, None, 0.05 / 2 / 2)
    t1 = {"n": len(m), "coef": b, "ci": [lo1, hi1], "pass": lo1 > 0}
    # T2 and descriptive thresholds: bet the model's side at the closing price
    res = {}
    for t in (0.5, 1.0, 1.5, 2.0, 3.0):
        z = x.filter((pl.col("fair") - pl.col("spread_line")).abs() >= t)
        home = (z["fair"] > z["spread_line"]).to_numpy()
        mm, sl = z["result"].to_numpy(), z["spread_line"].to_numpy()
        odds = np.where(home, z["home_spread_odds"].to_numpy(), z["away_spread_odds"].to_numpy()).astype(float)
        won = np.where(home, mm > sl, mm < sl).astype(float)
        push = mm == sl
        pnl = np.where(push, 0.0, P.profit(odds, won))
        zc = (z["season"] * 100 + z["week"]).to_numpy()
        lo, hi = week_boot(lambda ix: pnl[ix].mean(), zc, None, 0.025 / 2) if len(pnl) else (None, None)
        res[t] = {"n": int(len(pnl)), "weeks": int(len(np.unique(zc))), "cover": float(won[~push].mean()) if (~push).any() else None,
                  "roi": float(pnl.mean()) if len(pnl) else None, "ci": [lo, hi]}
    t2 = dict(res[1.5], **{"pass": bool(res[1.5]["n"] >= 30 and res[1.5]["weeks"] >= 10 and res[1.5]["ci"][0] > 0)})
    mae_f, mae_c = float(np.abs(fr - m).mean()), float(np.abs(close - m).mean())
    by_season = {int(s): {"mae_fair": float((z["fair"] - z["result"]).abs().mean()), "mae_close": float((z["spread_line"] - z["result"]).abs().mean())}
                 for (s,), z in x.group_by("season")}
    out = {"constants": k, "T1": t1, "T2": t2, "thresholds": res, "mae_fair": mae_f, "mae_close": mae_c, "by_season": by_season}
    (config.ROOT / "data" / "backtests" / "ats_confirm.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["# ATS model: confirm 2022-2025", "", "Pre-registration: docs/ats_declaration.md; constants frozen in data/backtests/ats_constants.json.", "",
         f"- MAE vs actual margin (weeks 2-18, {len(m)} games): fair {mae_f:.3f}, closing spread {mae_c:.3f}.",
         f"- **T1** information beyond the close: coefficient on (fair − close) {b:+.3f}, interval {lo1:+.3f} to {hi1:+.3f}: **{'PASS' if t1['pass'] else 'FAIL'}**.",
         f"- **T2** |fair − close| ≥ 1.5 at the closing price: n {t2['n']} in {t2['weeks']} weeks, covers {t2['cover']:.1%}, ROI {t2['roi']:+.1%}, "
         f"interval {t2['ci'][0]:+.1%} to {t2['ci'][1]:+.1%}: **{'PASS' if t2['pass'] else 'FAIL'}**.", "",
         "| Threshold | Bets | Covers | ROI | Interval (one-sided 0.025/2) |", "|---|---|---|---|---|"]
    L += [f"| ≥ {t} | {r['n']} | {r['cover']:.1%} | {r['roi']:+.1%} | {r['ci'][0]:+.1%} to {r['ci'][1]:+.1%} |" for t, r in res.items()]
    L += ["", "| Season | MAE fair | MAE close |", "|---|---|---|"] + [f"| {s} | {v['mae_fair']:.3f} | {v['mae_close']:.3f} |" for s, v in sorted(by_season.items())]
    (config.ROOT / "docs" / "ats_confirm.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
