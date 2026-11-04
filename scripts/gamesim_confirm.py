"""Game simulator confirm on 2022-2025 (docs/gamesim_preregistration.md). Constants frozen in
data/backtests/gamesim_constants.json before this ran. Writes docs/gamesim_confirm.md and
data/backtests/gamesim_confirm.json.

Usage: python scripts/gamesim_confirm.py <cache dir>"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import ats_clv as C  # noqa: E402

from nflbet import config  # noqa: E402
from nflbet.ats import rating as A  # noqa: E402
from nflbet.gamesim import engine as E, personnel as P, run as R, teams as TM  # noqa: E402
from nflbet.props import core as PC  # noqa: E402

CONFIRM = [2022, 2023, 2024, 2025]
ALPHA = 0.05 / 6
SIMS = 1000


def t1(x):
    c, f, m = (x[k].to_numpy().astype(float) for k in ("spread_line", "fair", "result"))
    cl = (x["season"] * 100 + x["week"]).to_numpy()
    X = np.c_[np.ones_like(c), c, f - c]
    coef = lambda ix: float(np.linalg.lstsq(X[ix], m[ix], rcond=None)[0][2])  # noqa: E731
    ci = C.boot(coef, cl, ALPHA / 2)
    return {"n": len(m), "coef": coef(np.arange(len(m))), "ci": list(ci), "pass": ci[0] > 0}


def t2(x):
    ab = pl.read_csv(config.ROOT / "data" / "odds" / "asb_nfl_games.csv").select("game_id", "home_open", "home_close")
    y = x.filter(pl.col("season") <= 2024).join(ab, on="game_id").drop_nulls(["home_open", "home_close"])
    o, c, f = (y[k].to_numpy().astype(float) for k in ("home_open", "home_close", "fair"))
    cl = (y["season"] * 100 + y["week"]).to_numpy()
    X = np.c_[np.ones_like(o), f - o]
    coef = lambda ix: float(np.linalg.lstsq(X[ix], (c - o)[ix], rcond=None)[0][1])  # noqa: E731
    ci = C.boot(coef, cl, ALPHA / 2)
    return {"n": len(o), "coef": coef(np.arange(len(o))), "ci": list(ci), "pass": ci[0] > 0}


def bets(x, t):
    c, f, m = (x[k].to_numpy().astype(float) for k in ("spread_line", "fair", "result"))
    cl = (x["season"] * 100 + x["week"]).to_numpy()
    sel = np.abs(f - c) >= t
    home = (f > c)[sel]
    mm, cc = m[sel], c[sel]
    won = np.where(home, mm > cc, mm < cc)
    push = mm == cc
    px = np.where(home, x["home_spread_odds"].to_numpy()[sel], x["away_spread_odds"].to_numpy()[sel]).astype(float)
    px = np.where(np.isnan(px), -110.0, px)
    pnl = np.where(push, 0.0, PC.profit(px, won.astype(float)))
    return sel, pnl, won, push, cl[sel]


def t3(x):
    sel, pnl, won, push, cl = bets(x, 1.5)
    ci = C.boot(lambda ix: pnl[ix].mean(), cl, ALPHA) if len(pnl) else (None, None)
    n, wk = int(sel.sum()), int(len(np.unique(cl)))
    return {"n": n, "weeks": wk, "cover": float(won[~push].mean()), "roi": float(pnl.mean()), "ci": list(ci),
            "pass": bool(n >= 30 and wk >= 10 and ci[0] > 0)}


def describe(x):
    out = {"mae_fair": float((x["fair"] - x["result"]).abs().mean()),
           "mae_close": float((x["spread_line"] - x["result"]).abs().mean()), "by_season": {}, "thresholds": {}}
    for s in CONFIRM:
        y = x.filter(pl.col("season") == s)
        out["by_season"][s] = {"n": y.height, "mae_fair": float((y["fair"] - y["result"]).abs().mean()),
                               "mae_close": float((y["spread_line"] - y["result"]).abs().mean())}
    for t in (0.5, 1.0, 2.0, 3.0):
        sel, pnl, won, push, _ = bets(x, t)
        out["thresholds"][t] = {"n": int(sel.sum()), "cover": float(won[~push].mean()) if (~push).any() else None,
                                "roi": float(pnl.mean()) if len(pnl) else None}
    return out


def main(d):
    k = json.loads((config.ROOT / "data" / "backtests" / "gamesim_constants.json").read_text())
    T = json.loads((config.ROOT / "data" / "backtests" / "gamesim_league.json").read_text())
    tb = E.Tables(T)
    seasons = list(range(2015, 2026))
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in seasons], how="diagonal_relaxed")
    kicks, xps = R.kick_pools(pbp)
    gs = TM.game_stats(pbp, T)
    fac = TM.factors(gs, k["league"], k["h"], k["k"], k["r"])
    games = A.games(CONFIRM).filter(pl.col("week") >= 2)
    out2, _ = R.simulate_games(games, fac, tb, kicks, xps, k["hfa"], sims=SIMS, seed=101)
    # personnel
    sched = pl.read_parquet(f"{d}/schedules.parquet")
    qg = P.qb_games(pbp)
    pk = k["personnel"]
    rater = P.QBRater(qg, pk["replacement"])
    qbd = P.qb_delta(sched, qg, rater)
    inj = P.injury_loss(pl.read_parquet(f"{d}/injuries.parquet"), pl.read_parquet(f"{d}/snaps.parquet"),
                        pl.read_parquet(f"{d}/players.parquet"), sched)
    inp = P.inputs(qbd, inj, sched).filter(pl.col("game_id").is_in(games["game_id"].implode()))
    out3, _ = R.simulate_games(games, fac, tb, kicks, xps, k["hfa"], sims=SIMS, seed=101, shift=P.shifts(inp, pk["coefs"]))
    res = {}
    for name, o in (("G2", out2), ("G3", out3)):
        x = o.select("game_id", "fair").join(games, on="game_id")
        res[name] = {"T1": t1(x), "T2": t2(x), "T3": t3(x), "descriptive": describe(x)}
    res["G3_minus_G2_mae"] = res["G3"]["descriptive"]["mae_fair"] - res["G2"]["descriptive"]["mae_fair"]
    (config.ROOT / "data" / "backtests" / "gamesim_confirm.json").write_text(json.dumps(res, indent=1, default=str))
    pickle.dump((out2, out3), open(f"{d}/confirm_out.pkl", "wb"))
    L = ["# Game simulator: confirm 2022-2025", "", "Pre-registration: docs/gamesim_preregistration.md; constants: "
         "data/backtests/gamesim_constants.json (frozen before this ran). Regular season weeks 2-18, "
         f"{SIMS} simulations per game. Each test at 0.05 / 6.", ""]
    for name in ("G2", "G3"):
        r = res[name]
        a, b, c = r["T1"], r["T2"], r["T3"]
        dd = r["descriptive"]
        L += [f"## {name} ({'step 2: team factors' if name == 'G2' else 'step 3: team factors + QB and injuries'})", "",
              f"- MAE vs actual margin ({a['n']} games): simulator {dd['mae_fair']:.3f}, closing spread {dd['mae_close']:.3f}.",
              f"- **T1** information beyond the close: coefficient on (fair − close) {a['coef']:+.3f}, interval {a['ci'][0]:+.3f} to {a['ci'][1]:+.3f}: **{'PASS' if a['pass'] else 'FAIL'}**",
              f"- **T2** line movement (bet365 2022-2024, n {b['n']}): coefficient {b['coef']:+.3f}, interval {b['ci'][0]:+.3f} to {b['ci'][1]:+.3f}: **{'PASS' if b['pass'] else 'FAIL'}**",
              f"- **T3** |fair − close| ≥ 1.5 at the closing price: n {c['n']} in {c['weeks']} weeks, covers {c['cover']:.1%}, ROI {c['roi']:+.1%}, interval {c['ci'][0]:+.1%} to {c['ci'][1]:+.1%}: **{'PASS' if c['pass'] else 'FAIL'}**", "",
              "| Season | Games | MAE simulator | MAE close |", "|---|---|---|---|"]
        L += [f"| {s} | {v['n']} | {v['mae_fair']:.3f} | {v['mae_close']:.3f} |" for s, v in dd["by_season"].items()]
        L += ["", "| |fair − close| ≥ | Bets | Covers | ROI |", "|---|---|---|---|"]
        L += [f"| {t} | {v['n']} | {v['cover']:.1%} | {v['roi']:+.1%} |" for t, v in dd["thresholds"].items()] + [""]
    L += [f"G3 minus G2 MAE: {res['G3_minus_G2_mae']:+.3f} (negative = personnel layer closer to the actual margin).", ""]
    (config.ROOT / "docs" / "gamesim_confirm.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1])
