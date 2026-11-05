"""Game simulator: fit league tables on 2016-2020, known-answer checks, then explore the factor grid on 2021
(docs/gamesim_preregistration.md). Writes docs/gamesim_explore.txt and data/backtests/gamesim_constants.json.

Usage: python scripts/gamesim_explore.py <pbp cache dir with pbp_<season>.parquet>"""
from __future__ import annotations

import itertools
import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.ats import rating as A
from nflbet.gamesim import engine as E, league as L, run as R, teams as TM

FIT = list(range(2016, 2021))
EXPLORE = 2021
GRID = {"h": [4.0, 8.0, 16.0], "k": [4.0, 8.0, 16.0], "r": [0.5, 0.7]}
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s, flush=True)


def load(d, seasons):
    return pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in seasons], how="diagonal_relaxed")


def actual(p):
    g = p.filter(pl.col("season_type") == "REG").group_by("game_id").agg(
        pl.col("total_home_score").max().alias("h"), pl.col("total_away_score").max().alias("a"))
    return g


def main(d):
    fit = load(d, FIT)
    T = L.fit(fit)
    tb = E.Tables(T)
    kicks, xps = R.kick_pools(load(d, [2015, *FIT, EXPLORE]))
    ks = kicks.filter(pl.col("season").is_in(FIT))["y"].to_numpy().astype(float)
    xpr = float(xps.filter(pl.col("season").is_in(FIT))["good"].mean())
    # ---- known answers
    N = 40000
    z = {f: np.zeros((N, 2)) for f in E.FACTORS}
    a1 = E.simulate(tb, z, z, ([ks], np.zeros(N, int)), np.full(N, xpr), np.full(N, 2019), 0.0, seed=5)
    a2 = E.simulate(tb, z, z, ([ks], np.zeros(N, int)), np.full(N, xpr), np.full(N, 2019), 0.0, seed=5)
    say("K1 same seed reproduces:", bool(np.array_equal(a1[0], a2[0]) and np.array_equal(a1[1], a2[1])))
    st = {}
    h, a = E.simulate(tb, z, z, ([ks], np.zeros(N, int)), np.full(N, xpr), np.full(N, 2019), 0.0, seed=6, stats=st)
    ac = actual(fit)
    am, at = (ac["h"] - ac["a"]).to_numpy(), (ac["h"] + ac["a"]).to_numpy()
    r = fit.filter(pl.col("season_type") == "REG")
    ng = r["game_id"].n_unique()
    sc = L.scrimmage(r)
    real = {"points per team-game": at.mean() / 2, "snaps per game": sc.height / ng,
            "touchdowns per game": r.filter(pl.col("touchdown") == 1, pl.col("play_type") != "no_play").height / ng,
            "field goals made per game": r.filter(pl.col("field_goal_result") == "made").height / ng,
            "share of margins = 3": float((np.abs(am) == 3).mean()), "share of margins = 7": float((np.abs(am) == 7).mean())}
    m = h - a
    simv = {"points per team-game": (h + a).mean() / 2, "snaps per game": st["snap"], "touchdowns per game": st["td"],
            "field goals made per game": st["fg"], "share of margins = 3": float((np.abs(m) == 3).mean()),
            "share of margins = 7": float((np.abs(m) == 7).mean())}
    say("K2 average teams vs 2016-2020 actual (pass = within 10%):")
    for k in real:
        rel = simv[k] / real[k] - 1
        say(f"   {k}: sim {simv[k]:.3f}, actual {real[k]:.3f}, {rel:+.1%} {'PASS' if abs(rel) <= 0.10 else 'FAIL'}")
    # home field: mean margin is linear in hfa; choose it so equal teams match the fit seasons' home margin
    sch = A.games(FIT)
    target = float(sch.filter(~pl.col("neutral"))["result"].mean())
    m0 = (h - a).mean()
    NH = 100000
    zz = {f: np.zeros((NH, 2)) for f in E.FACTORS}
    xs, ys = [0.0, 0.05, 0.1], []
    for i, v in enumerate(xs):
        hh_, aa_ = E.simulate(tb, zz, zz, ([ks], np.zeros(NH, int)), np.full(NH, xpr), np.full(NH, 2019), v, seed=20 + i)
        ys.append(float((hh_ - aa_).mean()))
    slope, icpt = np.polyfit(xs, ys, 1)
    hfa = float((target - icpt) / slope)
    say(f"HFA calibration: mean margin at yard factor {xs} = {[round(y, 3) for y in ys]}")
    hc, ac_ = E.simulate(tb, zz, zz, ([ks], np.zeros(NH, int)), np.full(NH, xpr), np.full(NH, 2019), hfa, seed=8)
    say(f"HFA: target home margin {target:.3f} (2016-2020, non-neutral); yard factor {hfa:.4f}; check mean margin {(hc - ac_).mean():.3f}")
    say(f"K3a equal teams: mean margin {(hc - ac_).mean():.3f} vs home-field term {target:.3f}: "
        f"{'PASS' if abs((hc - ac_).mean() - target) <= 0.5 else 'FAIL'}")
    # planted strength: home offense completions and yards up
    pl_ = {f: np.zeros((N, 2)) for f in E.FACTORS}
    pl_["comp"][:, 0] = 0.4
    pl_["ypc"][:, 0] = np.log(1.2)
    hp, ap = E.simulate(tb, pl_, z, ([ks], np.zeros(N, int)), np.full(N, xpr), np.full(N, 2019), 0.0, seed=9)
    say(f"K3b planted stronger home passing offense: mean margin {(hp - ap).mean():+.2f} (equal teams {m0:+.2f}): "
        f"{'PASS' if (hp - ap).mean() > m0 + 1 else 'FAIL'}")
    # no look-ahead: factors for 2020 week 10 unchanged when week 10+ games are removed
    gs = TM.game_stats(load(d, [2015, *FIT, EXPLORE]), T)
    lg = TM.league_rates(gs.filter(pl.col("season").is_in(FIT)))
    f_all = TM.factors(gs, lg, 8, 8, 0.7).filter(pl.col("season") == 2020, pl.col("week") == 10)
    cut = gs.filter((pl.col("season") < 2020) | ((pl.col("season") == 2020) & (pl.col("week") <= 10)))
    f_cut = TM.factors(cut, lg, 8, 8, 0.7).filter(pl.col("season") == 2020, pl.col("week") == 10)
    j = f_all.join(f_cut, on=["game_id", "team"], suffix="_c")
    same = all(np.allclose(j[c].to_numpy(), j[c + "_c"].to_numpy()) for c in f_all.columns if c[0] in "od" and c != "dummy")
    say(f"K1b no look-ahead (2020 week 10 factors with later games deleted are identical): {same}")
    # ---- explore 2021: grid by margin MAE
    games = A.games([EXPLORE]).filter(pl.col("week") >= 2)
    res = []
    for hh, kk, rr in itertools.product(GRID["h"], GRID["k"], GRID["r"]):
        fac = TM.factors(gs.filter(pl.col("season") <= EXPLORE), lg, hh, kk, rr)
        out, _ = R.simulate_games(games, fac, tb, kicks, xps, hfa, sims=300, seed=11)
        x = out.join(games.select("game_id", "result", "spread_line"), on="game_id")
        mae = float((x["fair"] - x["result"]).abs().mean())
        res.append({"h": hh, "k": kk, "r": rr, "mae": mae})
        say(f"   2021 h={hh} k={kk} r={rr}: MAE {mae:.3f}")
    best = min(res, key=lambda q: q["mae"])
    close_mae = float((games["spread_line"] - games["result"]).abs().mean())
    say(f"2021 chosen: {best}; closing spread MAE on the same games {close_mae:.3f}")
    const = {"h": best["h"], "k": best["k"], "r": best["r"], "hfa": hfa, "fit_seasons": FIT, "explore": EXPLORE,
             "league": lg, "grid": res}
    (config.ROOT / "data" / "backtests" / "gamesim_constants.json").write_text(json.dumps(const, indent=1))
    import pickle
    with open(f"{d}/gamesim_T.pkl", "wb") as fh:
        pickle.dump(T, fh)
    (config.ROOT / "data" / "backtests" / "gamesim_league.json").write_text(json.dumps(T))
    (config.ROOT / "docs" / "gamesim_explore.txt").write_text("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
