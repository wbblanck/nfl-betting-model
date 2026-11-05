"""Elo baseline confirm on 2022-2025 (docs/elo_preregistration.md). Constants frozen in
data/backtests/elo_constants.json before this ran. Needs the regenerated G3 simulator output
(<cache>/confirm_out.pkl from scripts/gamesim_confirm.py). Writes docs/elo_report.md and data/backtests/elo_confirm.json.

Usage: python scripts/elo_confirm.py <cache dir>"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import elo_g4_fit as G4  # noqa: E402

from nflbet import config, elo as E  # noqa: E402
from nflbet.gamesim import engine as EN, personnel as P, run as R, teams as TM  # noqa: E402
from nflbet.props import core as PC  # noqa: E402

CONFIRM = [2022, 2023, 2024, 2025]
ALPHA = 0.05 / 7
B = 2000
G3_MAE = 9.983


def boot(stat, cl, level, seed=7):
    ids = np.unique(cl)
    grp = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    bs = [stat(np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])) for _ in range(B)]
    return float(np.quantile(bs, level)), float(np.quantile(bs, 1 - level))


def clus(x):
    return (x["season"] * 100 + x["week"]).to_numpy()


def ols_coef(X, y, j):
    return lambda ix: float(np.linalg.lstsq(X[ix], y[ix], rcond=None)[0][j])


def mean_test(v, cl, two_sided=True):
    ci = boot(lambda ix: v[ix].mean(), cl, ALPHA / 2 if two_sided else ALPHA)
    return {"n": len(v), "mean": float(v.mean()), "ci": list(ci), "pass": ci[0] > 0}


def e1(x):
    c, f, m = (x[k].to_numpy().astype(float) for k in ("spread_line", "elo", "result"))
    X = np.c_[np.ones_like(c), c, f - c]
    fn = ols_coef(X, m, 2)
    ci = boot(fn, clus(x), ALPHA / 2)
    return {"n": len(m), "coef": fn(np.arange(len(m))), "ci": list(ci), "pass": ci[0] > 0}


def e2(x):
    ab = pl.read_csv(config.ROOT / "data" / "odds" / "asb_nfl_games.csv").select("game_id", "home_open", "home_close")
    y = x.filter(pl.col("season") <= 2024).join(ab, on="game_id").drop_nulls(["home_open", "home_close"])
    o, c, f = (y[k].to_numpy().astype(float) for k in ("home_open", "home_close", "elo"))
    X = np.c_[np.ones_like(o), f - o]
    fn = ols_coef(X, c - o, 1)
    ci = boot(fn, clus(y), ALPHA / 2)
    return {"n": len(o), "coef": fn(np.arange(len(o))), "ci": list(ci), "pass": ci[0] > 0}


def bets(x, t, col="elo"):
    c, f, m = (x[k].to_numpy().astype(float) for k in ("spread_line", col, "result"))
    sel = np.abs(f - c) >= t
    home = (f > c)[sel]
    mm, cc = m[sel], c[sel]
    won = np.where(home, mm > cc, mm < cc)
    push = mm == cc
    px = np.where(home, x["home_spread_odds"].to_numpy()[sel], x["away_spread_odds"].to_numpy()[sel]).astype(float)
    px = np.where(np.isnan(px), -110.0, px)
    pnl = np.where(push, 0.0, PC.profit(px, won.astype(float)))
    return sel, pnl, won, push, clus(x)[sel]


def e3(x):
    sel, pnl, won, push, cl = bets(x, 1.5)
    ci = boot(lambda ix: pnl[ix].mean(), cl, ALPHA)
    n, wk = int(sel.sum()), int(len(np.unique(cl)))
    return {"n": n, "weeks": wk, "cover": float(won[~push].mean()), "roi": float(pnl.mean()), "ci": list(ci),
            "pass": bool(n >= 30 and wk >= 10 and ci[0] > 0)}


def implied(ml):
    ml = np.asarray(ml, float)
    return np.where(ml < 0, -ml / (-ml + 100), 100 / (ml + 100))


def e4(x):
    y = x.filter(pl.col("result") != 0).drop_nulls(["home_moneyline", "away_moneyline"])
    ph, pa = implied(y["home_moneyline"]), implied(y["away_moneyline"])
    pm = ph / (ph + pa)
    w = (y["result"].to_numpy() > 0).astype(float)
    v = E.logloss(pm, w) - E.logloss(y["p"].to_numpy(), w)
    r = mean_test(v, clus(y))
    r["ll_market"], r["ll_elo"] = float(E.logloss(pm, w).mean()), float(E.logloss(y["p"].to_numpy(), w).mean())
    return r


def e5(x):
    m, ln = x["result"].to_numpy(), x["spread_line"].to_numpy()
    keep = m != ln
    yc = (m > ln)[keep].astype(float)
    lp = E.logloss(x["cov_pois"].to_numpy()[keep], yc)
    ln_ = E.logloss(x["cov_nb"].to_numpy()[keep], yc)
    r = mean_test(lp - ln_, clus(x)[keep])
    r["ll_pois"], r["ll_nb"] = float(lp.mean()), float(ln_.mean())
    return r


def mae_diff(x, a, b):
    m = x["result"].to_numpy()
    v = np.abs(x[a].to_numpy() - m) - np.abs(x[b].to_numpy() - m)
    return mean_test(v, clus(x))


def main(d):
    ek = json.loads((config.ROOT / "data" / "backtests" / "elo_constants.json").read_text())
    k = json.loads((config.ROOT / "data" / "backtests" / "gamesim_constants.json").read_text())
    T = json.loads((config.ROOT / "data" / "backtests" / "gamesim_league.json").read_text())
    sched = pl.read_parquet(f"{d}/schedules.parquet")
    # ---- Elo through 2025 (and 2026 to date, descriptive ratings table)
    games = E.prep(sched.filter(pl.col("season") <= 2025))
    r = E.run(games, ek["k"], ek["h"], ek["c"])
    lvl = E.scoring_level(games)
    x = r.join(lvl, on="game_id").join(sched.select("game_id", "game_type", "result", "spread_line", "home_spread_odds",
                                                    "away_spread_odds", "home_moneyline", "away_moneyline"), on="game_id")
    x = x.filter(pl.col("season").is_in(CONFIRM), pl.col("game_type") == "REG", pl.col("week") >= 2)
    mh, ma = E.means(x["d"], x["level"], ek["b"])
    ln = x["spread_line"].to_numpy()
    wp, cp = E.probs(E.pois_pmf(mh), E.pois_pmf(ma), ln)
    wn, cn = E.probs(E.nb_pmf(mh, ek["theta"]), E.nb_pmf(ma, ek["theta"]), ln)
    x = x.with_columns(pl.Series("elo", mh - ma), pl.Series("cov_pois", cp), pl.Series("cov_nb", cn),
                       pl.Series("win_pois", wp), pl.Series("win_nb", wn))
    # ---- simulator G3 (regenerated) and G4
    out2, out3 = pickle.load(open(f"{d}/confirm_out.pkl", "rb"))[:2]
    g3 = out3.select("game_id", pl.col("fair").alias("g3"))
    seasons = list(range(2015, 2026))
    pbp, inp = G4.build_inputs(d, sched, seasons, k["personnel"])
    gaps = G4.elo_gaps(sched, ek, 2025)
    inp = G4.add_elo(inp, gaps)
    sim_games = sched.filter(pl.col("season").is_in(CONFIRM), pl.col("game_type") == "REG", pl.col("week") >= 2,
                             pl.col("result").is_not_null()).select(
        "season", "week", "game_id", "home_team", "away_team", (pl.col("location") == "Neutral").alias("neutral"))
    kicks, xps = R.kick_pools(pbp)
    gs = TM.game_stats(pbp, T)
    fac = TM.factors(gs, k["league"], k["h"], k["k"], k["r"])
    inp = inp.filter(pl.col("game_id").is_in(sim_games["game_id"].implode()))
    out4, _ = R.simulate_games(sim_games, fac, EN.Tables(T), kicks, xps, k["hfa"], sims=1000, seed=101,
                               shift=G4.shifts(inp, ek["g4_coefs"]))
    x = x.join(g3, on="game_id").join(out4.select("game_id", pl.col("fair").alias("g4")), on="game_id")
    m = x["result"].to_numpy()
    mae = {c: float(np.abs(x[c].to_numpy() - m).mean()) for c in ("elo", "g3", "g4", "spread_line")}
    if abs(mae["g3"] - G3_MAE) >= 0.0005:
        raise SystemExit(f"G3 MAE {mae['g3']:.4f} does not reproduce {G3_MAE}; comparison not run")
    res = {"E1": e1(x), "E2": e2(x), "E3": e3(x), "E4": e4(x), "E5": e5(x),
           "E6": mae_diff(x, "elo", "g3"), "E7": mae_diff(x, "g3", "g4")}
    e6 = res["E6"]
    res["E6"]["verdict"] = "simulator better" if e6["ci"][0] > 0 else "Elo better" if e6["ci"][1] < 0 else "no difference shown"
    # ---- descriptive
    desc = {"n": x.height, "mae": mae, "by_season": {}, "thresholds": {}}
    for s in CONFIRM:
        y = x.filter(pl.col("season") == s)
        mm = y["result"].to_numpy()
        desc["by_season"][s] = {"n": y.height, **{c: float(np.abs(y[c].to_numpy() - mm).mean()) for c in ("elo", "g3", "g4", "spread_line")}}
    for t in (0.5, 1.0, 2.0, 3.0):
        sel, pnl, won, push, _ = bets(x, t)
        desc["thresholds"][t] = {"n": int(sel.sum()), "cover": float(won[~push].mean()), "roi": float(pnl.mean())}
    nz = m != 0
    wy = (m[nz] > 0).astype(float)
    desc["win_ll"] = {"logistic": float(E.logloss(x["p"].to_numpy()[nz], wy).mean()),
                      "poisson": float(E.logloss(x["win_pois"].to_numpy()[nz], wy).mean()),
                      "nb": float(E.logloss(x["win_nb"].to_numpy()[nz], wy).mean())}
    # QB variant (descriptive)
    pq = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in seasons], how="diagonal_relaxed")
    qg = P.qb_games(pq)
    qbd = P.qb_delta(sched.filter(pl.col("season").is_in(seasons)), qg, P.QBRater(qg, k["personnel"]["replacement"]))
    qb = {(g, E.FRANCHISE.get(t, t)): v for g, t, v in zip(qbd["game_id"], qbd["team"], qbd["qb_delta"])}
    rq = E.run(games, ek["k"], ek["h"], ek["c"], qb, ek["q"]).join(lvl, on="game_id").filter(pl.col("game_id").is_in(x["game_id"].implode()))
    rq = x.select("game_id", "result").join(rq.select("game_id", "d", "p", "level"), on="game_id")
    qh, qa = E.means(rq["d"], rq["level"], ek["b"])
    rm = rq["result"].to_numpy()
    desc["qb_variant"] = {"mae": float(np.abs(qh - qa - rm).mean()),
                          "win_ll": float(E.logloss(rq["p"].to_numpy()[rm != 0], (rm[rm != 0] > 0)).mean())}
    # 2026 ratings to date (descriptive table, not picks)
    g26 = E.prep(sched.filter(pl.col("season") <= 2026))
    fin = E.run(g26, ek["k"], ek["h"], ek["c"]).final
    last = g26.filter(pl.col("season") == 2026)
    desc["ratings_2026"] = {"through_week": int(last["week"].max()) if last.height else None,
                            "ratings": dict(sorted(((t, round(v, 1)) for t, v in fin.items()), key=lambda z: -z[1]))}
    res["descriptive"] = desc
    (config.ROOT / "data" / "backtests" / "elo_confirm.json").write_text(json.dumps(res, indent=1, default=str))
    x.select("season", "week", "game_id", "home_team", "away_team", "result", "spread_line", "d", "p", "elo",
             "cov_pois", "cov_nb", "g3", "g4").write_csv(config.ROOT / "data" / "backtests" / "elo_confirm_games.csv")
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1])
