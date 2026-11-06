"""Batch 3 (docs/batch3_preregistration.md).

  python scripts/batch3.py fit  <cache>   reads play-by-play and games through 2020 only; writes
                                          data/backtests/batch3_constants.json and docs/batch3_fit.txt
  python scripts/batch3.py test <cache>   runs T1, T2 once on 2022-2025 and the G1 description; writes
                                          data/backtests/batch3.json
<cache> holds nflverse schedules.parquet, injuries.parquet and pbp_<season>.parquet for 1999-2025.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.ats import elo as E, tdfg as T
from nflbet.gamesim import personnel as P

BT = config.ROOT / "data" / "backtests"
FIT, TEST = list(range(2016, 2021)), list(range(2022, 2026))
B, ALPHA = 2000, 0.05


def elo_level(d, last):
    ek = json.loads((BT / "elo_constants.json").read_text())
    sched = pl.read_parquet(f"{d}/schedules.parquet").filter(pl.col("season") <= last)
    games = E.prep(sched)
    r = E.run(games, ek["k"], ek["h"], ek["c"]).join(E.scoring_level(games), on="game_id")
    meta = sched.select("game_id", "game_type", "spread_line", "home_score", "away_score", "result")
    return ek, sched, games, r.join(meta, on="game_id")


def margin_lp(ph, pa, m):
    _, pm = E.margin_dist(ph, pa)
    return np.log(np.maximum(pm[np.arange(len(m)), m + E.MAXPTS], 1e-300)), pm


def cover_ll(pm, line, m):
    ms = np.arange(-E.MAXPTS, E.MAXPTS + 1)
    line = line[:, None]
    over = (pm * (ms > line)).sum(1)
    push = (pm * (ms == line)).sum(1)
    p = np.clip(over / (1 - push), 1e-12, 1 - 1e-12)
    y = (m > line[:, 0]).astype(float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p)), p


def fit(d):
    ek, _, _, r = elo_level(d, 2020)
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in FIT], how="diagonal_relaxed")
    c = T.counts(pbp)
    x = r.filter(pl.col("season").is_in(FIT), pl.col("game_type") == "REG").join(c, on="game_id")
    dd, lv = x["d"].to_numpy(), x["level"].to_numpy()
    ft = T.fit_counts(dd, lv, x["T_h"].to_numpy(), x["T_a"].to_numpy(), nb=True)
    ff = T.fit_counts(dd, lv, x["F_h"].to_numpy(), x["F_a"].to_numpy(), nb=False)
    nt = int(x["T_h"].sum() + x["T_a"].sum())
    n1, n2 = int(x["C1_h"].sum() + x["C1_a"].sum()), int(x["C2_h"].sum() + x["C2_a"].sum())
    p = [(nt - n1 - n2) / nt, n1 / nt, n2 / nt]
    s = float((x["S_h"].sum() + x["S_a"].sum()) / (2 * x.height))
    k = {"c_T": ft["c"], "b_T": ft["b"], "theta_T": ft["theta"], "c_F": ff["c"], "b_F": ff["b"], "s": s, "p": p,
         "n_games": x.height, "fit": FIT}
    # reconciliation of counted points with the final score
    exp_h = 6 * x["T_h"] + x["C1_h"] + 2 * x["C2_h"] + 3 * x["F_h"] + 2 * x["S_h"]
    exp_a = 6 * x["T_a"] + x["C1_a"] + 2 * x["C2_a"] + 3 * x["F_a"] + 2 * x["S_a"]
    off = np.r_[(x["home_score"] - exp_h).to_numpy(), (x["away_score"] - exp_a).to_numpy()]
    # power: in-sample per-game T1 difference SD
    ph, pa = T.game_pmfs(dd, lv, k)
    mh, ma = E.means(dd, lv, ek["b"])
    m = x["result"].to_numpy().astype(int)
    t1 = margin_lp(ph, pa, m)[0] - margin_lp(E.nb_pmf(mh, ek["theta"]), E.nb_pmf(ma, ek["theta"]), m)[0]
    k["power"] = {"t1_sd": float(t1.std()), "t1_mean_fit": float(t1.mean()), "se_1000": float(t1.std() / np.sqrt(1000))}
    (BT / "batch3_constants.json").write_text(json.dumps(k, indent=1))
    lines = [f"Touchdowns: c_T {ft['c']:.5f}, b_T {ft['b']:.4f}, theta_T {ft['theta']:.2f}",
             f"Field goals: c_F {ff['c']:.5f}, b_F {ff['b']:.4f}",
             f"Conversions per touchdown: 0 {p[0]:.4f}, 1 {p[1]:.4f}, 2 {p[2]:.4f}; safeties per team-game {s:.4f}",
             f"Fit games {x.height} (2016-2020 regular season)",
             f"Points not explained by the counts: {np.mean(off != 0):.4f} of team-games, mean {off.mean():.4f}",
             f"Power: in-sample T1 per-game SD {t1.std():.4f}, SE at 1,000 games {t1.std() / np.sqrt(1000):.4f} "
             f"(in-sample mean {t1.mean():.4f}, descriptive)"]
    (config.ROOT / "docs" / "batch3_fit.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def boot(v, cl, seed=7):
    ids = np.unique(cl)
    grp = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    return np.array([v[np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])].mean() for _ in range(B)])


def test(d):
    k = json.loads((BT / "batch3_constants.json").read_text())
    k1 = json.loads((BT / "batch1_constants.json").read_text())
    gk = json.loads((BT / "gamesim_constants.json").read_text())
    ek, sched, games, r = elo_level(d, 2025)
    x = r.filter(pl.col("season").is_in(TEST), pl.col("game_type") == "REG", pl.col("week").is_between(2, 18)) \
        .drop_nulls("spread_line").sort("game_id")
    dd, lv = x["d"].to_numpy(), x["level"].to_numpy()
    m = x["result"].to_numpy().astype(int)
    line = x["spread_line"].to_numpy().astype(float)
    mh, ma = E.means(dd, lv, ek["b"])
    nh, na = E.nb_pmf(mh, ek["theta"]), E.nb_pmf(ma, ek["theta"])
    th, ta = T.game_pmfs(dd, lv, k)
    lp_nb, pm_nb = margin_lp(nh, na, m)
    lp_td, pm_td = margin_lp(th, ta, m)
    cl = (x["season"] * 100 + x["week"]).to_numpy()
    res = {}
    v1 = lp_td - lp_nb
    res["T1"] = {"n": len(v1), "mean": float(v1.mean()), "draws": boot(v1, cl)}
    np_ = m != line
    ll_nb, pc_nb = cover_ll(pm_nb[np_], line[np_], m[np_])
    ll_td, pc_td = cover_ll(pm_td[np_], line[np_], m[np_])
    v2 = ll_nb - ll_td
    res["T2"] = {"n": int(np_.sum()), "mean": float(v2.mean()), "logloss_nb": float(ll_nb.mean()),
                 "logloss_tdfg": float(ll_td.mean()), "draws": boot(v2, cl[np_])}
    for rr in res.values():
        rr["p"] = float((rr["draws"] <= 0).mean())
    order = sorted(res, key=lambda n: res[n]["p"])
    stop = False
    for i, n in enumerate(order):
        lvl = ALPHA / (len(order) - i)
        ok = (not stop) and res[n]["p"] <= lvl
        dr = res[n].pop("draws")
        res[n].update({"holm_level": lvl, "pass": bool(ok), "ci": [float(np.quantile(dr, lvl)), float(np.quantile(dr, 1 - lvl))]})
        stop = stop or not ok
    # descriptive
    ms = np.arange(-E.MAXPTS, E.MAXPTS + 1)
    desc = {"margin_share": {}, "push": {}, "by_season": {}, "score_share": {}}
    for v in (3, 7, 10, 14, 1, 2):
        sel = np.abs(ms) == v
        desc["margin_share"][v] = {"actual": float(np.mean(np.abs(m) == v)), "nb": float(pm_nb[:, sel].sum(1).mean()),
                                   "tdfg": float(pm_td[:, sel].sum(1).mean())}
    for v in (3.0, 7.0):
        sel = np.abs(line) == v
        if sel.any():
            pl_ = lambda pm: float(np.mean([pm[i, ms == line[i]].sum() for i in np.where(sel)[0]]))  # noqa: E731
            desc["push"][v] = {"games": int(sel.sum()), "actual": float(np.mean(m[sel] == line[sel])),
                               "nb": pl_(pm_nb), "tdfg": pl_(pm_td)}
    sc = np.r_[x["home_score"].to_numpy(), x["away_score"].to_numpy()].astype(int)
    pn, pt = np.r_[nh, na].mean(0), np.r_[th, ta].mean(0)
    for v in (0, 3, 7, 10, 13, 14, 17, 20, 21, 24, 27, 28, 31):
        desc["score_share"][v] = {"actual": float(np.mean(sc == v)), "nb": float(pn[v]), "tdfg": float(pt[v])}
    mean_nb, mean_td = (pm_nb * ms).sum(1), (pm_td * ms).sum(1)
    for s in TEST:
        ix = x["season"].to_numpy() == s
        ixp = ix[np_]
        desc["by_season"][s] = {"n": int(ix.sum()), "mae_nb": float(np.abs(mean_nb[ix] - m[ix]).mean()),
                                "mae_tdfg": float(np.abs(mean_td[ix] - m[ix]).mean()),
                                "margin_lp_nb": float(lp_nb[ix].mean()), "margin_lp_tdfg": float(lp_td[ix].mean()),
                                "cover_ll_nb": float(ll_nb[ixp].mean()), "cover_ll_tdfg": float(ll_td[ixp].mean())}
    desc["mae_all"] = {"nb": float(np.abs(mean_nb - m).mean()), "tdfg": float(np.abs(mean_td - m).mean()),
                       "close": float(np.abs(line - m).mean())}
    res["descriptive"] = desc
    res["G1"] = g1(d, sched, games, x, k1, gk)
    (BT / "batch3.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


def g1(d, sched, games, x, k1, gk):
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet", columns=[
        "season_type", "qb_dropback", "qb_epa", "passer_player_id", "rusher_player_id", "posteam", "game_id",
        "game_date", "season", "week"]) for s in range(1999, 2026)], how="diagonal_relaxed")
    qg = P.qb_games(pbp)
    rater = P.QBRater(qg, gk["personnel"]["replacement"])
    inj = pl.read_parquet(f"{d}/injuries.parquet").filter(pl.col("game_type") == "REG", pl.col("season") >= 2022)
    exp = T.expected_starters(sched, qg, inj, P.FRANCHISE, P._day)
    reg = sched.filter(pl.col("game_type") == "REG")
    out = {}
    eq = k1["eloqb"]
    fr = {}
    for name, s in (("recorded", reg), ("expected", exp)):
        qbd = P.qb_delta(s, qg, rater)
        qb = {(g, E.FRANCHISE.get(t, t)): v for g, t, v in zip(qbd["game_id"], qbd["team"], qbd["qb_delta"])}
        rr = E.run(games, eq["k"], eq["h"], eq["c"], qb, eq["q"]).join(E.scoring_level(games), on="game_id")
        mh, ma = E.means(rr["d"], rr["level"], eq["b"])
        fr[name] = rr.select("game_id", pl.Series(name, mh - ma))
    ek = json.loads((BT / "elo_constants.json").read_text())
    mh, ma = E.means(x["d"], x["level"], ek["b"])
    y = x.select("game_id", "result", pl.Series("elo", mh - ma)).join(fr["recorded"], on="game_id").join(fr["expected"], on="game_id")
    ids = reg.select("game_id", "home_qb_id", "away_qb_id").join(
        exp.select("game_id", pl.col("home_qb_id").alias("eh"), pl.col("away_qb_id").alias("ea")), on="game_id")
    y = y.join(ids, on="game_id").with_columns(
        ((pl.col("home_qb_id") != pl.col("eh")) | (pl.col("away_qb_id") != pl.col("ea"))).alias("differ"),
        ((pl.col("home_qb_id") != pl.col("eh")).cast(int) + (pl.col("away_qb_id") != pl.col("ea")).cast(int)).alias("nd"))
    mae = lambda z: {c: float((z[c] - z["result"]).abs().mean()) for c in ("elo", "recorded", "expected")}  # noqa: E731
    out["games"] = y.height
    out["team_games_differ_share"] = float(y["nd"].sum() / (2 * y.height))
    out["games_differ"] = int(y["differ"].sum())
    out["mae_all"] = mae(y)
    out["mae_differ"] = mae(y.filter(pl.col("differ"))) if y["differ"].any() else None
    out["unknown_team_games"] = int((y["eh"] == "UNKNOWN").sum() + (y["ea"] == "UNKNOWN").sum())
    return out


if __name__ == "__main__":
    {"fit": fit, "test": test}[sys.argv[1]](sys.argv[2])
