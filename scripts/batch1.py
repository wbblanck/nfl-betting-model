"""Batch 1 (docs/batch1_preregistration.md).

  python scripts/batch1.py fit  <cache>   reads games up to 2021 only; writes data/backtests/batch1_constants.json
  python scripts/batch1.py test <cache>   runs H1-H5 once on 2005-2015 / 2007-2015; writes docs/batch1_report.md
                                          and data/backtests/batch1.json
<cache> holds nflverse schedules.parquet and pbp_<season>.parquet for 1999-2021 (scripts/gamesim_cache.py + older pbp).
"""
from __future__ import annotations

import itertools
import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.ats import elo as E, kalman as K
from nflbet.gamesim import personnel as P

BT = config.ROOT / "data" / "backtests"
FIT, FIT_BLEND = list(range(2016, 2021)), list(range(2016, 2022))
TEST_M, TEST_L = list(range(2005, 2016)), list(range(2007, 2016))
QS, CS = list(range(0, 1001, 50)), [1 / 4, 1 / 3, 1 / 2, 2 / 3, 3 / 4, 1.0]
B, ALPHA = 2000, 0.05


def load(d, last):
    sched = pl.read_parquet(f"{d}/schedules.parquet").filter(pl.col("season") <= last)
    return sched, E.prep(sched)


def qb_map(d, sched, last, replacement):
    seasons = list(range(1999, last + 1))
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in seasons], how="diagonal_relaxed")
    qg = P.qb_games(pbp)
    qbd = P.qb_delta(sched.filter(pl.col("season").is_in(seasons)), qg, P.QBRater(qg, replacement))
    return {(g, E.FRANCHISE.get(t, t)): v for g, t, v in zip(qbd["game_id"], qbd["team"], qbd["qb_delta"])}


def elo_frame(games, k, h, c, b, qb=None, q=0.0):
    r = E.run(games, k, h, c, qb, q).join(E.scoring_level(games), on="game_id")
    mh, ma = E.means(r["d"], r["level"], b)
    return r.with_columns(pl.Series("fair", mh - ma))


def win_ll(x):
    y = x.filter(pl.col("result") != 0)
    return float(E.logloss(y["p"], (y["result"] > 0).cast(float)).mean())


def fit(d):
    ek = json.loads((BT / "elo_constants.json").read_text())
    gk = json.loads((BT / "gamesim_constants.json").read_text())
    sched, games = load(d, 2021)
    meta = games.select("game_id", "game_type", "home_score", "away_score", "result")
    reg_fit = lambda x: x.join(meta, on="game_id").filter(pl.col("season").is_in(FIT), pl.col("game_type") == "REG")  # noqa: E731
    qb = qb_map(d, sched, 2021, gk["personnel"]["replacement"])
    out = {"elo": {k: ek[k] for k in ("k", "h", "c", "b")}}
    lines = []
    best = None
    for q, c in itertools.product(QS, CS):
        ll = win_ll(reg_fit(E.run(games, ek["k"], ek["h"], c, qb, q)))
        if best is None or ll < best[0]:
            best = (ll, q, c)
    _, q, c = best
    x = reg_fit(E.run(games, ek["k"], ek["h"], c, qb, q).join(E.scoring_level(games), on="game_id"))
    b = E.fit_b(x["d"].to_numpy(), x["level"].to_numpy(), x["home_score"].to_numpy(), x["away_score"].to_numpy())
    out["eloqb"] = {"k": ek["k"], "h": ek["h"], "c": c, "q": q, "b": b, "logloss": best[0]}
    lines.append(f"Elo + QB: q {q}, c {c:.3f}, b {b:.4f}, fit log loss {best[0]:.5f} "
                 f"(grid edges: q 0-1000, c 1/4-1)")
    kp = K.fit(games, FIT)
    out["kalman"] = kp
    lines.append("Kalman: " + ", ".join(f"{a} {v:.4f}" for a, v in kp.items()))
    # blend weight on 2016-2021 with SBRO openers
    sb = pl.read_csv(config.ROOT / "data" / "odds" / "sbro_nfl_games.csv").select("game_id", "home_open")
    ef = elo_frame(games, ek["k"], ek["h"], ek["c"], ek["b"]).join(meta.select("game_id", "game_type", "result"), on="game_id")
    z = ef.filter(pl.col("season").is_in(FIT_BLEND), pl.col("game_type") == "REG", pl.col("week") >= 2) \
        .join(sb, on="game_id").drop_nulls("home_open")
    w = K.fit_blend(z["home_open"], z["fair"], z["result"])
    out["blend"] = {"w": w, "n": z.height}
    lines.append(f"Blend: w {w:.4f} on {z.height} games 2016-2021")
    (BT / "batch1_constants.json").write_text(json.dumps(out, indent=1))
    (config.ROOT / "docs" / "batch1_fit.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ---------------------------------------------------------------- test
def boot_p(v_fn, cl, seed=7):
    """Week-clustered bootstrap draws of a statistic; returns (point, draws)."""
    ids = np.unique(cl)
    grp = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    draws = np.array([v_fn(np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])) for _ in range(B)])
    return v_fn(np.arange(len(cl))), draws


def test(d):
    k = json.loads((BT / "batch1_constants.json").read_text())
    gk = json.loads((BT / "gamesim_constants.json").read_text())
    sched, games = load(d, 2015)
    meta = sched.select("game_id", "game_type", "spread_line")
    e, eq = k["elo"], k["eloqb"]
    qb = qb_map(d, sched, 2015, gk["personnel"]["replacement"])
    x = elo_frame(games, e["k"], e["h"], e["c"], e["b"]).select("game_id", "season", "week", pl.col("fair").alias("elo"))
    xq = elo_frame(games, eq["k"], eq["h"], eq["c"], eq["b"], qb, eq["q"]).select("game_id", pl.col("fair").alias("eloqb"))
    kf, _, _ = K.run(games, k["kalman"])
    x = x.join(xq, on="game_id").join(kf.select("game_id", "kalman"), on="game_id") \
        .join(games.select("game_id", "result"), on="game_id").join(meta, on="game_id") \
        .filter(pl.col("game_type") == "REG", pl.col("week").is_between(2, 17), pl.col("season").is_in(TEST_M))
    sb = pl.read_csv(config.ROOT / "data" / "odds" / "sbro_nfl_games.csv").select("game_id", "home_open", "home_close")
    xl = x.filter(pl.col("season").is_in(TEST_L)).join(sb, on="game_id").drop_nulls(["home_open", "home_close"])
    xl = xl.with_columns((pl.col("home_open") + k["blend"]["w"] * (pl.col("elo") - pl.col("home_open"))).alias("blend"))
    cl = lambda y: (y["season"] * 100 + y["week"]).to_numpy()  # noqa: E731
    res = {}
    # H1
    o, f, m = (xl[c].to_numpy().astype(float) for c in ("home_open", "elo", "result"))
    sel = np.abs(f - o) >= 1.5
    home = (f > o)[sel]
    won = np.where(home, m[sel] > o[sel], m[sel] < o[sel])
    push = m[sel] == o[sel]
    pnl = np.where(push, 0.0, np.where(won, 100 / 110, -1.0))
    c1 = cl(xl)[sel]
    pt, dr = boot_p(lambda ix: pnl[ix].mean(), c1)
    res["H1"] = {"n": int(sel.sum()), "weeks": int(len(np.unique(c1))), "cover": float(won[~push].mean()),
                 "roi": pt, "draws": dr, "min_ok": bool(sel.sum() >= 100 and len(np.unique(c1)) >= 30)}
    # H2
    cc = xl["home_close"].to_numpy().astype(float)
    X = np.c_[np.ones_like(o), f - o]
    pt, dr = boot_p(lambda ix: float(np.linalg.lstsq(X[ix], (cc - o)[ix], rcond=None)[0][1]), cl(xl))
    res["H2"] = {"n": len(o), "coef": pt, "draws": dr}
    # H3
    v = np.abs(o - m) - np.abs(xl["blend"].to_numpy() - m)
    pt, dr = boot_p(lambda ix: v[ix].mean(), cl(xl))
    res["H3"] = {"n": len(v), "mean": pt, "draws": dr}
    # H4, H5
    mm = x["result"].to_numpy().astype(float)
    for name, col in (("H4", "eloqb"), ("H5", "kalman")):
        v = np.abs(x["elo"].to_numpy() - mm) - np.abs(x[col].to_numpy() - mm)
        pt, dr = boot_p(lambda ix, v=v: v[ix].mean(), cl(x))
        res[name] = {"n": len(v), "mean": pt, "draws": dr}
    # Holm
    for r in res.values():
        r["p"] = float((r.pop("draws") <= 0).mean()) if "draws" in r else None
    order = sorted(res, key=lambda n: res[n]["p"])
    stop = False
    for i, n in enumerate(order):
        lvl = ALPHA / (len(order) - i)
        ok = (not stop) and res[n]["p"] <= lvl and res[n].get("min_ok", True)
        res[n]["holm_level"], res[n]["pass"] = lvl, bool(ok)
        stop = stop or not ok
    # intervals at each test's Holm level (recomputed draws for reporting)
    def ci(fn, cls, lvl):
        _, dr = boot_p(fn, cls)
        return [float(np.quantile(dr, lvl)), float(np.quantile(dr, 1 - lvl))]
    res["H1"]["ci"] = ci(lambda ix: pnl[ix].mean(), c1, res["H1"]["holm_level"])
    res["H2"]["ci"] = ci(lambda ix: float(np.linalg.lstsq(X[ix], (cc - o)[ix], rcond=None)[0][1]), cl(xl), res["H2"]["holm_level"])
    v3 = np.abs(o - m) - np.abs(xl["blend"].to_numpy() - m)
    res["H3"]["ci"] = ci(lambda ix: v3[ix].mean(), cl(xl), res["H3"]["holm_level"])
    for name, col in (("H4", "eloqb"), ("H5", "kalman")):
        v = np.abs(x["elo"].to_numpy() - mm) - np.abs(x[col].to_numpy() - mm)
        res[name]["ci"] = ci(lambda ix, v=v: v[ix].mean(), cl(x), res[name]["holm_level"])
    # descriptive
    desc = {"by_season": {}, "thresholds": {}}
    for s in TEST_M:
        y = x.filter(pl.col("season") == s)
        mm_ = y["result"].to_numpy()
        row = {"n": y.height, **{c: float(np.abs(y[c].to_numpy() - mm_).mean()) for c in ("elo", "eloqb", "kalman", "spread_line")}}
        yl = xl.filter(pl.col("season") == s)
        if yl.height:
            ml = yl["result"].to_numpy()
            row.update({c: float(np.abs(yl[c].to_numpy() - ml).mean()) for c in ("home_open", "home_close", "blend")})
            row["n_lines"] = yl.height
        desc["by_season"][s] = row
    allm = {c: float(np.abs(x[c].to_numpy() - mm).mean()) for c in ("elo", "eloqb", "kalman", "spread_line")}
    allm.update({c: float(np.abs(xl[c].to_numpy() - m).mean()) for c in ("home_open", "home_close", "blend", "elo")
                 if c != "elo"})
    allm["elo_on_line_games"] = float(np.abs(f - m).mean())
    desc["mae"] = allm
    for t in (0.5, 1.0, 2.0, 3.0):
        s_ = np.abs(f - o) >= t
        hm = (f > o)[s_]
        wn = np.where(hm, m[s_] > o[s_], m[s_] < o[s_])
        pu = m[s_] == o[s_]
        wc = np.where(hm, m[s_] > cc[s_], m[s_] < cc[s_])
        pc = m[s_] == cc[s_]
        desc["thresholds"][t] = {"n": int(s_.sum()), "cover_open": float(wn[~pu].mean()),
                                 "roi_open": float(np.where(pu, 0, np.where(wn, 100 / 110, -1)).mean()),
                                 "cover_close": float(wc[~pc].mean()),
                                 "line_moved_toward": float(np.mean(np.sign(cc[s_] - o[s_]) == np.sign(f[s_] - o[s_])))}
    res["descriptive"] = desc
    (BT / "batch1.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    {"fit": fit, "test": test}[sys.argv[1]](sys.argv[2])
