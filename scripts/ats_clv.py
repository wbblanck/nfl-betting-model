"""ATS rating vs opening lines (docs/ats_clv_preregistration.md). Writes docs/ats_clv.md and data/backtests/ats_clv.json."""
from __future__ import annotations

import json

import numpy as np
import polars as pl

from nflbet import ats as A, config, props as P

TEST, DESC = list(range(2008, 2016)), list(range(2016, 2022))
B = 4000


def boot(stat, cl, level, seed=7):
    ids = np.unique(cl)
    grp = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    bs = [stat(np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])) for _ in range(B)]
    return float(np.quantile(bs, level)), float(np.quantile(bs, 1 - level))


def frame(seasons, k):
    tg = A.team_games(list(range(min(seasons) - 1, max(seasons) + 1)))
    g = A.games(seasons)
    x = A.fair(A.with_ratings(g, A.ratings(tg, k["h"], k["k"], k["r"])), k["c"], k["hfa"]).filter(pl.col("week") >= 2)
    sb = pl.read_csv(config.ROOT / "data" / "odds" / "sbro_nfl_games.csv").select("game_id", "home_open", "home_close")
    return x.join(sb, on="game_id").filter(pl.col("home_open").is_not_null(), pl.col("home_close").is_not_null())


def evaluate(x, alpha):
    o, c, f, m = (x[k].to_numpy().astype(float) for k in ("home_open", "home_close", "fair", "result"))
    cl = (x["season"] * 100 + x["week"]).to_numpy()
    X = np.c_[np.ones_like(o), f - o]
    coef = lambda ix: float(np.linalg.lstsq(X[ix], (c - o)[ix], rcond=None)[0][1])  # noqa: E731
    c1 = {"n": len(o), "coef": coef(np.arange(len(o))), "ci": list(boot(coef, cl, alpha / 2))}
    c1["pass"] = c1["ci"][0] > 0
    res = {}
    for t in (0.5, 1.0, 1.5, 2.0, 3.0):
        sel = np.abs(f - o) >= t
        home = (f > o)[sel]
        oo, cc, mm, cls = o[sel], c[sel], m[sel], cl[sel]
        clv = np.where(home, cc - oo, oo - cc)
        won_o = np.where(home, mm > oo, mm < oo)
        push_o = mm == oo
        px = (np.where(home, x["home_open_odds"].to_numpy()[sel], x["away_open_odds"].to_numpy()[sel]).astype(float)
              if "home_open_odds" in x.columns else np.full(len(mm), -110.0))
        pnl_o = np.where(push_o, 0.0, P.profit(px, won_o.astype(float)))
        won_c = np.where(home, mm > cc, mm < cc)
        push_c = mm == cc
        r = {"n": int(sel.sum()), "weeks": int(len(np.unique(cls))), "mean_clv": float(clv.mean()) if len(clv) else None,
             "share_clv_pos": float((clv > 0).mean()) if len(clv) else None,
             "cover_open": float(won_o[~push_o].mean()) if (~push_o).any() else None, "roi_open": float(pnl_o.mean()) if len(pnl_o) else None,
             "cover_close": float(won_c[~push_c].mean()) if (~push_c).any() else None}
        if t == 1.5 and len(clv):
            r["clv_ci"] = list(boot(lambda ix: clv[ix].mean(), cls, alpha))
            r["roi_ci"] = list(boot(lambda ix: pnl_o[ix].mean(), cls, alpha))
        res[t] = r
    b = res[1.5]
    c2 = {**{k: b[k] for k in ("n", "weeks", "mean_clv", "share_clv_pos")}, "ci": b.get("clv_ci"),
          "pass": bool(b["n"] >= 30 and b["weeks"] >= 10 and b["clv_ci"][0] > 0)}
    c3 = {**{k: b[k] for k in ("n", "weeks", "cover_open", "roi_open")}, "ci": b.get("roi_ci"),
          "pass": bool(b["n"] >= 30 and b["weeks"] >= 10 and b["roi_ci"][0] > 0)}
    return {"C1": c1, "C2": c2, "C3": c3, "thresholds": res}


def main():
    k = json.loads((config.ROOT / "data" / "backtests" / "ats_constants.json").read_text())
    out = {"test_2008_2015": evaluate(frame(TEST, k), 0.05 / 3), "descriptive_2016_2021": evaluate(frame(DESC, k), 0.05 / 3)}
    (config.ROOT / "data" / "backtests" / "ats_clv.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["# ATS rating vs opening lines", "", "Pre-registration: docs/ats_clv_preregistration.md. Opening/closing spreads: SBRO (data/odds/README.md).", ""]
    for name, r in out.items():
        c1, c2, c3 = r["C1"], r["C2"], r["C3"]
        L += [f"## {name}", "",
              f"- **C1** (close − open) on (fair − open): coefficient {c1['coef']:+.3f}, interval {c1['ci'][0]:+.3f} to {c1['ci'][1]:+.3f}, n {c1['n']}: **{'PASS' if c1['pass'] else 'FAIL'}**",
              f"- **C2** CLV of the model's side, |fair − open| ≥ 1.5: n {c2['n']} in {c2['weeks']} weeks, mean {c2['mean_clv']:+.3f} pts "
              f"(moved toward the bet {c2['share_clv_pos']:.0%}), interval {c2['ci'][0]:+.3f} to {c2['ci'][1]:+.3f}: **{'PASS' if c2['pass'] else 'FAIL'}**",
              f"- **C3** ATS at the opening number, −110: covers {c3['cover_open']:.1%}, ROI {c3['roi_open']:+.1%}, interval {c3['ci'][0]:+.1%} to {c3['ci'][1]:+.1%}: **{'PASS' if c3['pass'] else 'FAIL'}**", "",
              "| |fair − open| ≥ | Bets | Mean CLV (pts) | CLV > 0 | Cover at open | ROI at open (−110) | Cover at close |", "|---|---|---|---|---|---|---|"]
        L += [f"| {t} | {v['n']} | {v['mean_clv']:+.3f} | {v['share_clv_pos']:.0%} | {v['cover_open']:.1%} | {v['roi_open']:+.1%} | {v['cover_close']:.1%} |"
              for t, v in r["thresholds"].items()] + [""]
    (config.ROOT / "docs" / "ats_clv.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
