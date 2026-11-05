"""Market calibration of the game simulator (docs/gamesim_calibration_preregistration.md).

Usage: python scripts/gamesim_calibration.py <cache dir> m1|m2"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import ats_clv as C  # noqa: E402
import gamesim_props_dist as D  # noqa: E402

from nflbet import config  # noqa: E402
from nflbet.ats import rating as A  # noqa: E402
from nflbet.gamesim.teams import FRANCHISE  # noqa: E402
from nflbet.props import confirm as PCF, core as PC  # noqa: E402
from nflbet.props.sim import Simulator, inputs  # noqa: E402

BT = config.ROOT / "data" / "backtests"
TAIL = 0.025 / 2
GROUPS = {"receiving": ["rec", "rec_yds"], "rushing": ["rush_att", "rush_yds"], "passing": ["pass_att", "pass_cmp", "pass_yds"]}
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s, flush=True)


def lg(p):
    p = np.clip(p, 0.02, 0.98)
    return np.log(p / (1 - p))


def fit_logit(X, y, iters=50, ridge=1e-6):
    """Maximum-likelihood logistic regression by Newton's method."""
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        g = X.T @ (y - p) - ridge * b
        H = (X * (p * (1 - p))[:, None]).T @ X + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        b += step
        if np.abs(step).max() < 1e-10:
            break
    return b


def season_data(d, season, sim, idx, att, car, size):
    g = PC.graded(PC.join(PC.load_lines(season), PC.load_stats(season), PC.load_snaps(season)))
    dk = PCF.screened(g).filter(pl.col("book") == "DK NJ", pl.col("result") != "push", pl.col("market").is_in(D.MARKETS)) \
        .unique(subset=PCF.KEY)
    keep = set(zip(dk["player_id"].to_list(), dk["week"].to_list()))
    rows_in = {(r["player_id"], r["week"]): r for r in inputs(sim.pg, sim.sched, season, sim.pos_mean, sim.dfac).iter_rows(named=True)
               if (r["player_id"], r["week"]) in keep}
    ok = [(k in rows_in) and ((season, k[1], FRANCHISE.get(rows_in[k]["team"], rows_in[k]["team"])) in idx)
          for k in zip(dk["player_id"].to_list(), dk["week"].to_list())]
    dk = dk.filter(pl.Series(ok))
    p = D.probs(season, dk, rows_in, idx, att, car, sim.pools, "nb", size)
    good = ~np.isnan(p)
    dk = dk.filter(pl.Series(good))
    return dk, p[good]


def design(dk, psim):
    mk = dk["market"].to_numpy()
    grp = np.array([next(g for g, ms in GROUPS.items() if m in ms) for m in mk])
    return grp, lg(dk["p_over"].to_numpy()), lg(psim), (dk["result"] == "over").cast(pl.Float64).to_numpy()


def m1(d):
    size = json.loads((BT / "gamesim_props_dist.json").read_text())["chosen"]
    out, att, car = D.volumes(d)
    idx = {}
    for i, (s, w, h, a) in enumerate(zip(out["season"], out["week"], out["home_team"], out["away_team"])):
        idx[(s, w, h)], idx[(s, w, a)] = (i, 0), (i, 1)
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    dk24, p24 = season_data(d, 2024, sim, idx, att, car, size)
    dk25, p25 = season_data(d, 2025, sim, idx, att, car, size)
    g24, ldk24, ls24, y24 = design(dk24, p24)
    g25, ldk25, ls25, y25 = design(dk25, p25)
    coefs = {}
    say(f"## M1 props: fit on 2024 ({len(y24)} DraftKings props)")
    say("Group | n 2024 | intercept a | weight on DK b | weight on simulator c")
    for g in GROUPS:
        m = g24 == g
        X = np.c_[np.ones(m.sum()), ldk24[m], ls24[m]]
        coefs[g] = fit_logit(X, y24[m]).tolist()
        say(f"{g} | {m.sum()} | {coefs[g][0]:+.4f} | {coefs[g][1]:+.4f} | {coefs[g][2]:+.4f}")
    pm = np.empty(len(y25))
    for g in GROUPS:
        m = g25 == g
        a, b, c = coefs[g]
        pm[m] = 1 / (1 + np.exp(-(a + b * ldk25[m] + c * ls25[m])))
    pdk = dk25["p_over"].to_numpy()
    Lm, Ld, Ls = D.ll_each(pm, y25), D.ll_each(pdk, y25), D.ll_each(p25, y25)
    diff = Lm - Ld
    cl = dk25["week"].to_numpy()
    ci = C.boot(lambda ix: diff[ix].mean(), cl, TAIL)
    better = bool(ci[1] < 0)
    say(f"\n## M1 test on 2025 ({len(y25)} props)")
    say(f"Log loss: mix {Lm.mean():.5f} | DK de-vigged {Ld.mean():.5f} | simulator alone {Ls.mean():.5f} | coin 0.69315")
    say(f"- **Mix minus DK:** {diff.mean():+.5f}, interval {ci[0]:+.5f} to {ci[1]:+.5f}: **{'BETTER' if better else 'NOT BETTER'}**")
    say("\nBy group | n | mix | DK")
    for g in GROUPS:
        m = g25 == g
        say(f"{g} | {m.sum()} | {Lm[m].mean():.5f} | {Ld[m].mean():.5f}")
    # descriptive, not registered: the same refit without the simulator term, to see how much of the gain is the
    # simulator and how much is recalibrating DraftKings' own price
    po = np.empty(len(y25))
    for g in GROUPS:
        m24, m25 = g24 == g, g25 == g
        a, b = fit_logit(np.c_[np.ones(m24.sum()), ldk24[m24]], y24[m24])
        po[m25] = 1 / (1 + np.exp(-(a + b * ldk25[m25])))
    Lo = D.ll_each(po, y25)
    d2 = Lm - Lo
    ci2 = C.boot(lambda ix: d2[ix].mean(), cl, TAIL)
    say(f"\nDescriptive (not registered): DK-only refit {Lo.mean():.5f}; mix minus DK-only refit {d2.mean():+.5f}, "
        f"interval {ci2[0]:+.5f} to {ci2[1]:+.5f}")
    np.savez(f"{d}/calib_m1_arrays.npz", g24=g24, ldk24=ldk24, ls24=ls24, y24=y24, g25=g25, ldk25=ldk25, ls25=ls25, y25=y25, cl=cl)
    sp = np.maximum(pm, 1 - pm)
    hit = np.where(pm >= 0.5, y25 == 1, y25 == 0)
    say("\nCalibration of the mix: band | n | said | hit")
    for lo, hi in ((0.5, 0.55), (0.55, 0.6), (0.6, 0.7), (0.7, 1.01)):
        m = (sp >= lo) & (sp < hi)
        if m.any():
            say(f"{lo:.0%}-{min(hi, 1):.0%} | {m.sum()} | {sp[m].mean():.1%} | {hit[m].mean():.1%}")
    m55 = sp >= 0.55
    odds = np.where(pm >= 0.5, dk25["over_odds"].to_numpy().astype(float), dk25["under_odds"].to_numpy().astype(float))
    pnl = PC.profit(odds[m55], hit[m55].astype(float)) if m55.any() else np.array([])
    say(f"Descriptive: mix gives a side 55%+ on {m55.sum()} props: hit {hit[m55].mean() if m55.any() else float('nan'):.1%}, "
        f"ROI at DK prices {pnl.mean() if len(pnl) else float('nan'):+.1%}")
    json.dump({"coefs": coefs, "n24": int(len(y24)), "n25": int(len(y25)), "ll": {"mix": float(Lm.mean()), "dk": float(Ld.mean()),
               "sim": float(Ls.mean())}, "diff": float(diff.mean()), "ci": list(ci), "better": better,
               "ge55": {"n": int(m55.sum()), "roi": float(pnl.mean()) if len(pnl) else None}},
              open(BT / "gamesim_calibration_m1.json", "w"), indent=1)
    (config.ROOT / "docs" / "gamesim_calibration_m1.txt").write_text("\n".join(OUT) + "\n")


def m2(d):
    with open(f"{d}/confirm_out.pkl", "rb") as f:
        _, out3 = pickle.load(f)
    ab = pl.read_csv(config.ROOT / "data" / "odds" / "asb_nfl_games.csv").select(
        "game_id", "home_open", "home_close", "home_open_odds", "away_open_odds")
    games = A.games([2022, 2023, 2024, 2025]).filter(pl.col("week") >= 2).select("game_id", "season", "week", "result")
    x = out3.select("game_id", "fair").join(games, on="game_id").join(ab, on="game_id").drop_nulls(["home_open"])
    res = {}
    say("## M2 spreads: bet the simulator's side at the opener when |fair − open| ≥ 1.5")
    say("Sample | games | bets | weeks | covers | ROI | interval | avg CLV (pts toward bet)")
    plaus = pl.col("home_open_odds").is_between(-130, 110) & pl.col("away_open_odds").is_between(-130, 110)
    for name, ss, flt in (("2022-2024 (descriptive)", [2022, 2023, 2024], False), ("2025 (test)", [2025], False),
                          ("2025 sensitivity: implausible opener prices dropped (not registered)", [2025], True)):
        y = x.filter(pl.col("season").is_in(ss))
        if flt:
            y = y.filter(plaus.fill_null(True))
        f, o, c, m = (y[k].to_numpy().astype(float) for k in ("fair", "home_open", "home_close", "result"))
        sel = np.abs(f - o) >= 1.5
        home = (f > o)[sel]
        mm, oo, cc = m[sel], o[sel], c[sel]
        won = np.where(home, mm > oo, mm < oo)
        push = mm == oo
        px = np.where(home, y["home_open_odds"].to_numpy()[sel], y["away_open_odds"].to_numpy()[sel]).astype(float)
        px = np.where(np.isnan(px), -110.0, px)
        pnl = np.where(push, 0.0, PC.profit(px, won.astype(float)))
        clv = np.where(home, cc - oo, oo - cc)
        cl = (y["season"] * 100 + y["week"]).to_numpy()[sel]
        ci = C.boot(lambda ix: pnl[ix].mean(), cl, TAIL) if len(pnl) else (float("nan"), float("nan"))
        wk = int(len(np.unique(cl)))
        ok = bool(len(pnl) >= 30 and wk >= 10 and ci[0] > 0)
        res[name] = {"games": y.height, "n": int(sel.sum()), "weeks": wk, "cover": float(won[~push].mean()), "roi": float(pnl.mean()),
                     "ci": list(ci), "clv": float(np.nanmean(clv)), "pass": ok}
        say(f"{name} | {y.height} | {sel.sum()} | {wk} | {won[~push].mean():.1%} | {pnl.mean():+.1%} | {ci[0]:+.1%} to {ci[1]:+.1%} | "
            f"{np.nanmean(clv):+.2f}")
    t = res["2025 (test)"]
    say(f"- **M2 on 2025: {'PASS' if t['pass'] else 'FAIL'}** (needs 30+ bets in 10+ weeks and ROI interval above 0).")
    json.dump(res, open(BT / "gamesim_calibration_m2.json", "w"), indent=1)
    (config.ROOT / "docs" / "gamesim_calibration_m2.txt").write_text("\n".join(OUT) + "\n")


if __name__ == "__main__":
    {"m1": m1, "m2": m2}[sys.argv[2]](sys.argv[1])
