"""Elo baseline: fit on 2016-2020, describe 2021, freeze constants (docs/elo_preregistration.md).
Reads only games up to 2021. Writes data/backtests/elo_constants.json and docs/elo_explore.txt.

Usage: python scripts/elo_fit.py <cache dir>"""
from __future__ import annotations

import itertools
import json
import sys

import numpy as np
import polars as pl

from nflbet import config, elo as E
from nflbet.gamesim import personnel as P

FIT = list(range(2016, 2021))
EXPLORE = 2021
GRID = {"k": [15, 20, 25, 30], "h": [20, 35, 50, 65], "c": [1 / 4, 1 / 3, 1 / 2]}
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s, flush=True)


def qb_inputs(d, sched):
    seasons = list(range(2015, EXPLORE + 1))
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in seasons], how="diagonal_relaxed")
    qg = P.qb_games(pbp)
    rater = P.QBRater(qg, P.replacement(qg, pbp, FIT))
    sc = sched.filter(pl.col("season").is_in(seasons))
    qbd = P.qb_delta(sc, qg, rater)
    return {(g, E.FRANCHISE.get(t, t)): v for g, t, v in zip(qbd["game_id"], qbd["team"], qbd["qb_delta"])}


def frame(games, k, h, c, qb=None, q=0.0):
    r = E.run(games, k, h, c, qb, q)
    x = r.join(games.select("game_id", "game_type", "home_score", "away_score", "result"), on="game_id")
    return x.join(E.scoring_level(games), on="game_id")


def win_ll(x):
    y = x.filter(pl.col("result") != 0)
    return float(E.logloss(y["p"], (y["result"] > 0).cast(float)).mean())


def main(d):
    sched = pl.read_parquet(f"{d}/schedules.parquet")
    games = E.prep(sched.filter(pl.col("season") <= EXPLORE))
    fitsel = lambda x: x.filter(pl.col("season").is_in(FIT), pl.col("game_type") == "REG")  # noqa: E731
    best = None
    say("grid: win-probability log loss, 2016-2020 regular season (ties dropped)")
    for k, h, c in itertools.product(GRID["k"], GRID["h"], GRID["c"]):
        ll = win_ll(fitsel(frame(games, k, h, c)))
        say(f"  K {k} H {h} c {c:.3f}: {ll:.5f}")
        if best is None or ll < best[0]:
            best = (ll, k, h, c)
    _, k, h, c = best
    say(f"chosen K {k} H {h} c {c:.3f} (log loss {best[0]:.5f})")
    x = fitsel(frame(games, k, h, c))
    dd, lv = x["d"].to_numpy(), x["level"].to_numpy()
    hs, as_ = x["home_score"].to_numpy(), x["away_score"].to_numpy()
    b = E.fit_b(dd, lv, hs, as_)
    th = E.fit_theta(dd, lv, hs, as_, b)
    say(f"score model: b {b:.4f} (points ratio per 100 Elo = exp(2b) = {np.exp(2 * b):.3f}), NB size theta {th:.3f}")
    mh, ma = E.means(dd, lv, b)
    say(f"fit check: mean predicted home pts {mh.mean():.2f} vs actual {hs.mean():.2f}; away {ma.mean():.2f} vs {as_.mean():.2f}")
    say(f"fit check: score variance {np.var(np.r_[hs, as_]):.1f} vs mean {np.mean(np.r_[hs, as_]):.1f} (Poisson would make them equal)")
    # QB adjustment (descriptive variant)
    qb = qb_inputs(d, sched)
    qs = list(range(0, 1001, 50))
    lls = {q: win_ll(fitsel(frame(games, k, h, c, qb, q))) for q in qs}
    q = min(lls, key=lls.get)
    say("QB term q (Elo points per EPA/dropback) log loss: " + ", ".join(f"{a} {v:.5f}" for a, v in lls.items()))
    say(f"chosen q {q}")
    # 2021 descriptive
    say(f"\nexplore {EXPLORE} (descriptive only), regular season weeks 2-18")
    for name, qq in (("Elo", 0.0), ("Elo+QB", q)):
        z = frame(games, k, h, c, qb, qq).filter(pl.col("season") == EXPLORE, pl.col("game_type") == "REG", pl.col("week") >= 2)
        z = z.join(sched.select("game_id", "spread_line"), on="game_id")
        mh, ma = E.means(z["d"], z["level"], b)
        fair = mh - ma
        m = z["result"].to_numpy()
        say(f"  {name}: n {z.height}, win log loss {win_ll(z):.5f}, margin MAE {np.abs(fair - m).mean():.3f}, "
            f"close MAE {np.abs(z['spread_line'].to_numpy() - m).mean():.3f}")
        if name == "Elo":
            ln = z["spread_line"].to_numpy()
            keep = m != ln
            yc = (m > ln)[keep].astype(float)
            for nm, pm in (("Poisson", E.pois_pmf), ("NB", lambda mu: E.nb_pmf(mu, th))):
                win, cov = E.probs(pm(mh), pm(ma), ln)
                yw = z.filter(pl.col("result") != 0)
                say(f"    {nm}: count-model win log loss {E.logloss(win[m != 0], (m[m != 0] > 0)).mean():.5f}, "
                    f"cover log loss {E.logloss(cov[keep], yc).mean():.5f} (coin 0.69315)")
    const = {"k": k, "h": h, "c": c, "b": b, "theta": th, "q": q, "fit": FIT, "explore": EXPLORE,
             "grid": GRID, "chosen_logloss": best[0]}
    (config.ROOT / "data" / "backtests" / "elo_constants.json").write_text(json.dumps(const, indent=1))
    (config.ROOT / "docs" / "elo_explore.txt").write_text("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
