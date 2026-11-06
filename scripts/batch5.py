"""Batch 5 (docs/batch5_preregistration.md).

  python scripts/batch5.py fit  <cache>   reads games and play-by-play through 2020 only; writes
                                          data/backtests/batch5_constants.json and docs/batch5_fit.txt
  python scripts/batch5.py test <cache>   runs S1, K1, D3 (2022-2025) and R1, R2 (2005-2015 weeks 2-6) once; writes
                                          data/backtests/batch5.json
"""
from __future__ import annotations

import itertools
import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.ats import batch5 as B5, elo as E, rating as A, tdfg as T
from nflbet.gamesim import engine as GE, personnel as P, run as R, teams as TM

BT = config.ROOT / "data" / "backtests"
FIT, SCORE_TEST, RATE_TEST = list(range(2016, 2021)), list(range(2022, 2026)), list(range(2005, 2016))
HS, LAMS, RHOS = [x / 4 for x in range(13)], [1, 2, 4, 8, 16], [0, 0.25, 0.5, 0.75, 1.0]
B, ALPHA, G3_MAE = 2000, 0.05, 9.983


def frame(d, last):
    ek = json.loads((BT / "elo_constants.json").read_text())
    sched = pl.read_parquet(f"{d}/schedules.parquet").filter(pl.col("season") <= last)
    games = E.prep(sched)
    r = E.run(games, ek["k"], ek["h"], ek["c"]).join(E.scoring_level(games), on="game_id")
    meta = sched.select("game_id", "game_type", "spread_line", "total_line", "over_odds", "under_odds", "home_score",
                        "away_score")
    r = r.join(meta, on="game_id").join(games.select("game_id", "result", "neutral"), on="game_id")
    return ek, sched, games, r.with_columns(pl.Series("elo", B5.fair(r["d"], r["level"], ek["b"])))


def reg_games(games):
    return games.filter(pl.col("game_type") == "REG").select("season", "week", "game_id", "home_team", "away_team",
                                                              "result", "neutral")


def fit(d):
    ek, _, games, r = frame(d, 2020)
    k3 = json.loads((BT / "batch3_constants.json").read_text())
    x = r.filter(pl.col("season").is_in(FIT), pl.col("game_type") == "REG")
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in FIT], how="diagonal_relaxed")
    c = x.join(T.counts(pbp), on="game_id")
    lt_h, lt_a = T.rates(c["d"], c["level"], k3["c_T"], k3["b_T"])
    c0 = B5.fit_c0(c["T_h"].to_numpy(), c["T_a"].to_numpy(), c["level"].to_numpy(), lt_h, lt_a)
    k1 = B5.fit_k1(x["elo"].to_numpy(), x["result"].to_numpy())
    # R2 grid on 2016-2020 weeks 2-6 (ratings run from 2010)
    g = reg_games(games).filter(pl.col("season") >= 2010)
    best, tab = None, []
    for h, lam, rho in itertools.product(HS, LAMS, RHOS):
        f = B5.ridge_run(g, h, lam, rho).join(g, on="game_id").filter(pl.col("season").is_in(FIT), pl.col("week").is_between(2, 6))
        mae = float((f["ridge"] - f["result"]).abs().mean())
        tab.append((h, lam, rho, mae))
        if best is None or mae < best[3]:
            best = (h, lam, rho, mae)
    elo_mae = float((r.filter(pl.col("season").is_in(FIT), pl.col("game_type") == "REG", pl.col("week").is_between(2, 6))
                     .pipe(lambda z: (z["elo"] - z["result"]).abs().mean())))
    out = {"s1": {"c0": c0}, "k1": k1, "r2": {"h": best[0], "lam": best[1], "rho": best[2], "fit_mae": best[3]},
           "elo_fit_mae_w2_6": elo_mae}
    (BT / "batch5_constants.json").write_text(json.dumps(out, indent=1))
    w = k1["w"]
    lines = [f"S1: c0 {c0:.5f} (shared touchdown rate per point of scoring level; 0 = batch 3's independent model)",
             f"K1: sigma {k1['sigma']:.3f} (first pass {k1['sigma0']:.3f}); weights |m| 0-14: "
             + ", ".join(f"{i}:{w[i]:.2f}" for i in range(15)),
             f"R2: h {best[0]}, lambda {best[1]}, rho {best[2]}, 2016-2020 weeks 2-6 MAE {best[3]:.3f} (Elo {elo_mae:.3f}); "
             f"grid edges h 0-3, lambda 1-16, rho 0-1"]
    (config.ROOT / "docs" / "batch5_fit.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def boot(fn, cl, seed=7):
    ids = np.unique(cl)
    grp = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    return np.array([fn(np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])) for _ in range(B)])


def payout(o):
    o = np.asarray(o, float)
    return np.where(o > 0, o / 100.0, 100.0 / -o)


def sim_totals(d):
    k = json.loads((BT / "gamesim_constants.json").read_text())
    Tl = json.loads((BT / "gamesim_league.json").read_text())
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in range(2015, 2026)], how="diagonal_relaxed")
    kicks, xps = R.kick_pools(pbp)
    fac = TM.factors(TM.game_stats(pbp, Tl), k["league"], k["h"], k["k"], k["r"])
    games = A.games(SCORE_TEST).filter(pl.col("week") >= 2)
    sched = pl.read_parquet(f"{d}/schedules.parquet")
    qg = P.qb_games(pbp)
    pk = k["personnel"]
    qbd = P.qb_delta(sched, qg, P.QBRater(qg, pk["replacement"]))
    inj = P.injury_loss(pl.read_parquet(f"{d}/injuries.parquet"), pl.read_parquet(f"{d}/snaps.parquet"),
                        pl.read_parquet(f"{d}/players.parquet"), sched)
    inp = P.inputs(qbd, inj, sched).filter(pl.col("game_id").is_in(games["game_id"].implode()))
    out, _ = R.simulate_games(games, fac, GE.Tables(Tl), kicks, xps, k["hfa"], sims=1000, seed=101,
                              shift=P.shifts(inp, pk["coefs"]))
    x = out.select("game_id", "fair", "sim_total").join(games.select("game_id", "result"), on="game_id")
    mae = float((x["fair"] - x["result"]).abs().mean())
    if abs(mae - G3_MAE) >= 0.0005:
        raise SystemExit(f"simulator does not reproduce G3 (MAE {mae:.4f} vs {G3_MAE}); nothing run")
    return x.select("game_id", "sim_total"), mae


def holm(res):
    order = sorted(res, key=lambda n: res[n]["p"])
    stop = False
    for i, n in enumerate(order):
        lvl = ALPHA / (len(order) - i)
        ok = (not stop) and res[n]["p"] <= lvl and res[n].get("min_ok", True)
        res[n].update({"holm_level": lvl, "pass": bool(ok)})
        stop = stop or not ok
    for n in res:
        dr = res[n].pop("draws")
        lv = res[n]["holm_level"]
        res[n]["ci"] = [float(np.quantile(dr, lv)), float(np.quantile(dr, 1 - lv))]


def test(d):
    k5 = json.loads((BT / "batch5_constants.json").read_text())
    k3 = json.loads((BT / "batch3_constants.json").read_text())
    ek, sched, games, r = frame(d, 2025)
    res, desc = {}, {}
    # ---- S1, K1 on the batch 3 sample
    x = r.filter(pl.col("season").is_in(SCORE_TEST), pl.col("game_type") == "REG", pl.col("week").is_between(2, 18)) \
        .drop_nulls("spread_line").sort("game_id")
    dd, lv, m = x["d"].to_numpy(), x["level"].to_numpy(), x["result"].to_numpy().astype(int)
    mh, ma = E.means(dd, lv, ek["b"])
    _, pm_nb = E.margin_dist(E.nb_pmf(mh, ek["theta"]), E.nb_pmf(ma, ek["theta"]))
    lp = lambda pm, off: np.log(np.maximum(pm[np.arange(len(m)), m + off], 1e-300))  # noqa: E731
    lp_nb = lp(pm_nb, E.MAXPTS)
    pm_s1 = B5.s1_margin(dd, lv, k3, k5["s1"]["c0"])
    pm_k1 = B5.k1_dist(x["elo"].to_numpy(), k5["k1"]["sigma"], k5["k1"]["w"])
    lp_s1, lp_k1 = lp(pm_s1, E.MAXPTS), lp(pm_k1, 60)
    cl = (x["season"] * 100 + x["week"]).to_numpy()
    for name, v in (("S1", lp_s1 - lp_nb), ("K1", lp_k1 - lp_nb)):
        res[name] = {"n": len(v), "mean": float(v.mean()), "draws": boot(lambda ix, v=v: v[ix].mean(), cl)}
    full = np.arange(-E.MAXPTS, E.MAXPTS + 1)
    desc["margin_share"] = {}
    for v in (1, 2, 3, 6, 7, 10, 14):
        desc["margin_share"][v] = {"actual": float(np.mean(np.abs(m) == v)),
                                   "nb": float(pm_nb[:, np.abs(full) == v].sum(1).mean()),
                                   "s1": float(pm_s1[:, np.abs(full) == v].sum(1).mean()),
                                   "k1": float(pm_k1[:, np.abs(B5.M) == v].sum(1).mean())}
    line = x["spread_line"].to_numpy().astype(float)
    np_ = m != line
    desc["cover_logloss"] = {}
    for name, pm, ms in (("nb", pm_nb, full), ("s1", pm_s1, full), ("k1", pm_k1, B5.M)):
        over = (pm[np_] * (ms[None, :] > line[np_, None])).sum(1)
        push = (pm[np_] * (ms[None, :] == line[np_, None])).sum(1)
        p = np.clip(over / (1 - push), 1e-12, 1 - 1e-12)
        y = (m[np_] > line[np_]).astype(float)
        desc["cover_logloss"][name] = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    desc["cover_logloss"]["coin"] = float(np.log(2))
    desc["margin_lp_mean"] = {"nb": float(lp_nb.mean()), "s1": float(lp_s1.mean()), "k1": float(lp_k1.mean())}
    # ---- D3 simulator totals
    st, g3 = sim_totals(d)
    z = r.select("game_id", "season", "week", "total_line", "over_odds", "under_odds", "home_score", "away_score") \
        .join(st, on="game_id").drop_nulls(["total_line", "over_odds", "under_odds"]).sort("game_id")
    tot = (z["home_score"] + z["away_score"]).to_numpy().astype(float)
    tl, sim = z["total_line"].to_numpy().astype(float), z["sim_total"].to_numpy()
    oo, uo = z["over_odds"].to_numpy(), z["under_odds"].to_numpy()

    def tbets(gap):
        sel = np.abs(sim - tl) >= gap
        over = sim > tl
        win = np.where(over, tot > tl, tot < tl)
        push = tot == tl
        pnl = np.where(push, 0.0, np.where(win, payout(np.where(over, oo, uo)), -1.0))
        return sel, pnl, win, push
    sel, pnl, win, push = tbets(1.5)
    c3 = (z["season"] * 100 + z["week"]).to_numpy()[sel]
    ps = pnl[sel]
    res["D3"] = {"n": int(sel.sum()), "weeks": int(len(np.unique(c3))), "win": float(win[sel][~push[sel]].mean()),
                 "roi": float(ps.mean()), "min_ok": bool(sel.sum() >= 100 and len(np.unique(c3)) >= 30),
                 "draws": boot(lambda ix: ps[ix].mean(), c3)}
    desc["totals"] = {"games": z.height, "g3_margin_mae": g3, "mae_sim_total": float(np.abs(sim - tot).mean()),
                      "mae_close_total": float(np.abs(tl - tot).mean()), "mean_sim_minus_line": float((sim - tl).mean()),
                      "gaps": {}}
    for gp in (0.5, 1.0, 2.0, 3.0):
        s_, p_, w_, u_ = tbets(gp)
        desc["totals"]["gaps"][gp] = {"n": int(s_.sum()), "win": float(w_[s_][~u_[s_]].mean()), "roi": float(p_[s_].mean()),
                                      "share_over": float(np.mean((sim > tl)[s_]))}
    # ---- R1, R2 on 2005-2015 weeks 2-6
    lvl = dict(zip(r["game_id"].to_list(), r["level"].to_list()))
    close = dict(zip(r["game_id"].to_list(), r["spread_line"].to_list()))
    rg = games.filter(pl.col("season") <= 2015)
    r1 = B5.run_market_start(rg, ek["k"], ek["h"], ek["c"], ek["b"], lvl, {k_: v for k_, v in close.items() if v is not None})
    r1 = r1.join(r.select("game_id", "level"), on="game_id")
    r1 = r1.select("game_id", pl.Series("r1", B5.fair(r1["d"], r1["level"], ek["b"])))
    p2 = k5["r2"]
    r2 = B5.ridge_run(reg_games(games).filter(pl.col("season") <= 2015), p2["h"], p2["lam"], p2["rho"])
    y = r.filter(pl.col("season").is_in(RATE_TEST), pl.col("game_type") == "REG", pl.col("week").is_between(2, 6)) \
        .select("game_id", "season", "week", "result", "elo").join(r1, on="game_id").join(r2, on="game_id")
    mm = y["result"].to_numpy().astype(float)
    cy = (y["season"] * 100 + y["week"]).to_numpy()
    for name, col in (("R1", "r1"), ("R2", "ridge")):
        v = np.abs(y["elo"].to_numpy() - mm) - np.abs(y[col].to_numpy() - mm)
        res[name] = {"n": len(v), "mean": float(v.mean()), "draws": boot(lambda ix, v=v: v[ix].mean(), cy)}
    desc["early_mae_by_week"] = {int(w): {c: float((yy[c] - yy["result"]).abs().mean()) for c in ("elo", "r1", "ridge")}
                                 for w in range(2, 7) for yy in [y.filter(pl.col("week") == w)]}
    desc["early_mae"] = {c: float((y[c] - y["result"]).abs().mean()) for c in ("elo", "r1", "ridge")}
    for rr in res.values():
        rr["p"] = float((rr["draws"] <= 0).mean())
    holm(res)
    res["descriptive"] = desc
    (BT / "batch5.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    {"fit": fit, "test": test}[sys.argv[1]](sys.argv[2])
