"""Batch 4 (docs/batch4_preregistration.md): XGBoost margin model.

  python scripts/batch4.py fit  <cache>   reads data through 2021 only; picks the tree count, trains on 2016-2021 and
                                          writes data/backtests/batch4_model.json and docs/batch4_fit.txt
  python scripts/batch4.py test <cache>   scores 2022-2025 once (X1, X2 + descriptive); writes data/backtests/batch4.json
<cache> holds nflverse schedules.parquet, injuries.parquet and pbp_<season>.parquet for 1999-2025.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl
import xgboost as xgb

from nflbet import config
from nflbet.ats import elo as E, kalman as K, tdfg as T, xgb as X
from nflbet.gamesim import personnel as P

BT = config.ROOT / "data" / "backtests"
TRAIN, TEST = list(range(2016, 2022)), list(range(2022, 2026))
B, ALPHA = 2000, 0.05
FR = E.FRANCHISE


def build(d, last):
    ek = json.loads((BT / "elo_constants.json").read_text())
    k1 = json.loads((BT / "batch1_constants.json").read_text())
    gk = json.loads((BT / "gamesim_constants.json").read_text())
    sched = pl.read_parquet(f"{d}/schedules.parquet").filter(pl.col("season") <= last)
    games = E.prep(sched)
    r = E.run(games, ek["k"], ek["h"], ek["c"]).join(E.scoring_level(games), on="game_id")
    mh, ma = E.means(r["d"], r["level"], ek["b"])
    f = r.select("game_id", pl.col("d").alias("elo_d"), "level", pl.Series("elo_fair", mh - ma))
    kf, _, _ = K.run(games, k1["kalman"])
    f = f.join(kf.select("game_id", "kalman", "kalman_var"), on="game_id")
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet", columns=[
        "season_type", "qb_dropback", "qb_epa", "passer_player_id", "rusher_player_id", "posteam", "defteam", "game_id",
        "game_date", "season", "week", "epa", "play_type"]) for s in range(1999, last + 1)], how="diagonal_relaxed")
    qg = P.qb_games(pbp)
    inj = pl.read_parquet(f"{d}/injuries.parquet").filter(pl.col("game_type") == "REG", pl.col("season") <= last)
    exp = T.expected_starters(sched, qg, inj, FR, P._day)
    qbd = P.qb_delta(exp, qg, P.QBRater(qg, gk["personnel"]["replacement"]))
    qbd = qbd.with_columns(pl.col("team").replace(FR))
    roll = X.rolling_epa(pbp.filter(pl.col("season") >= 2010))
    s = sched.filter(pl.col("game_type") == "REG").with_columns(
        pl.col("home_team").replace(FR).alias("ht"), pl.col("away_team").replace(FR).alias("at"),
        pl.col("roof").is_in(["dome", "closed"]).cast(int).alias("dome"), pl.col("div_game").cast(int))
    s = s.join(games.select("game_id", pl.col("neutral").cast(int)), on="game_id").join(f, on="game_id")
    s = s.join(qbd.select("game_id", pl.col("team").alias("ht"), pl.col("qb_delta").alias("qb_h")), on=["game_id", "ht"], how="left") \
        .join(qbd.select("game_id", pl.col("team").alias("at"), pl.col("qb_delta").alias("qb_a")), on=["game_id", "at"], how="left") \
        .join(roll.select("game_id", pl.col("team").alias("ht"), pl.col("off8").alias("off8_h"), pl.col("def8").alias("def8_h")),
              on=["game_id", "ht"], how="left") \
        .join(roll.select("game_id", pl.col("team").alias("at"), pl.col("off8").alias("off8_a"), pl.col("def8").alias("def8_a")),
              on=["game_id", "at"], how="left")
    return s.filter(pl.col("week").is_between(2, 18)).sort("game_id")


def fit(d):
    s = build(d, 2021).filter(pl.col("season").is_in(TRAIN))
    Xm, y, se = s.select(X.FEATURES).to_numpy().astype(float), s["result"].to_numpy().astype(float), s["season"].to_numpy()
    n, tab = X.choose_trees(Xm, y, se)
    m = X.model(n).fit(Xm, y)
    m.booster.save_model(str(BT / "batch4_model.json"))
    lines = [f"Training games {s.height} (2016-2021 weeks 2-18); missing feature cells {int(np.isnan(Xm).sum())}",
             f"Trees chosen: {n} (leave-one-season-out MAE " + ", ".join(f"{k} {v:.3f}" for k, v in tab.items()) + ")"]
    (config.ROOT / "docs" / "batch4_fit.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def boot(fn, cl, seed=7):
    ids = np.unique(cl)
    grp = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    return np.array([fn(np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])) for _ in range(B)])


def payout(odds):
    o = np.asarray(odds, float)
    return np.where(o > 0, o / 100.0, 100.0 / -o)


def bets(pred, line, m, ho, ao, gap):
    sel = np.abs(pred - line) >= gap
    home = pred > line
    win = np.where(home, m > line, m < line)
    push = m == line
    pnl = np.where(push, 0.0, np.where(win, payout(np.where(home, ho, ao)), -1.0))
    return sel, pnl, win, push


def test(d):
    s = build(d, 2025)
    tr = s.filter(pl.col("season").is_in(TRAIN))
    x = s.filter(pl.col("season").is_in(TEST)).drop_nulls(["spread_line", "home_spread_odds", "away_spread_odds"])
    booster = xgb.Booster()
    booster.load_model(str(BT / "batch4_model.json"))
    pred = booster.predict(xgb.DMatrix(x.select(X.FEATURES).to_numpy().astype(float)))
    m = x["result"].to_numpy().astype(float)
    elo = x["elo_fair"].to_numpy()
    line = x["spread_line"].to_numpy().astype(float)
    ho, ao = x["home_spread_odds"].to_numpy(), x["away_spread_odds"].to_numpy()
    cl = (x["season"] * 100 + x["week"]).to_numpy()
    res = {}
    v1 = np.abs(elo - m) - np.abs(pred - m)
    res["X1"] = {"n": len(v1), "mean": float(v1.mean()), "fn": lambda ix: v1[ix].mean(), "cl": cl}
    sel, pnl, win, push = bets(pred, line, m, ho, ao, 1.5)
    c2 = cl[sel]
    res["X2"] = {"n": int(sel.sum()), "weeks": int(len(np.unique(c2))), "cover": float(win[sel][~push[sel]].mean()),
                 "roi": float(pnl[sel].mean()), "fn": lambda ix: pnl[sel][ix].mean(), "cl": c2,
                 "min_ok": bool(sel.sum() >= 100 and len(np.unique(c2)) >= 30)}
    for r in res.values():
        r["p"] = float((boot(r["fn"], r["cl"]) <= 0).mean())
    order = sorted(res, key=lambda k: res[k]["p"])
    stop = False
    for i, k in enumerate(order):
        lvl = ALPHA / (len(order) - i)
        ok = (not stop) and res[k]["p"] <= lvl and res[k].get("min_ok", True)
        dr = boot(res[k].pop("fn"), res[k].pop("cl"))
        res[k].update({"holm_level": lvl, "pass": bool(ok), "ci": [float(np.quantile(dr, lvl)), float(np.quantile(dr, 1 - lvl))]})
        stop = stop or not ok
    # descriptive: linear regression on the same features (trained 2016-2021)
    A = tr.select(X.FEATURES).to_numpy().astype(float)
    ok_rows = ~np.isnan(A).any(1)
    beta = np.linalg.lstsq(np.c_[np.ones(ok_rows.sum()), A[ok_rows]], tr["result"].to_numpy()[ok_rows], rcond=None)[0]
    At = np.nan_to_num(x.select(X.FEATURES).to_numpy().astype(float), nan=0.0)
    lin = np.c_[np.ones(len(At)), At] @ beta
    desc = {"by_season": {}, "gaps": {}}
    for se in TEST:
        ix = x["season"].to_numpy() == se
        desc["by_season"][se] = {"n": int(ix.sum()), **{k: float(np.abs(v[ix] - m[ix]).mean())
                                                       for k, v in (("xgb", pred), ("elo", elo), ("linear", lin), ("close", line))}}
    desc["mae"] = {k: float(np.abs(v - m).mean()) for k, v in (("xgb", pred), ("elo", elo), ("linear", lin), ("close", line))}
    for g in (0.5, 1.0, 2.0, 3.0):
        sl, pn, wn, pu = bets(pred, line, m, ho, ao, g)
        desc["gaps"][g] = {"n": int(sl.sum()), "cover": float(wn[sl][~pu[sl]].mean()), "roi": float(pn[sl].mean())}
    gain = booster.get_score(importance_type="gain")
    desc["importance_gain"] = {X.FEATURES[int(k[1:])]: v for k, v in sorted(gain.items(), key=lambda t: -t[1])}
    desc["corr_xgb_elo"] = float(np.corrcoef(pred, elo)[0, 1])
    desc["missing_test_cells"] = int(np.isnan(x.select(X.FEATURES).to_numpy().astype(float)).sum())
    res["descriptive"] = desc
    (BT / "batch4.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    {"fit": fit, "test": test}[sys.argv[1]](sys.argv[2])
