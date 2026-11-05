"""Fit the G4 simulator coefficients (G3 personnel inputs + elo_gap) on 2016-2020 and freeze them into
data/backtests/elo_constants.json (docs/elo_preregistration.md, "Simulator with an Elo input"). Reads games up to 2020
only. Writes docs/elo_g4_fit.txt.

Usage: python scripts/elo_g4_fit.py <cache dir>"""
from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.ats import elo as E
from nflbet.gamesim import personnel as P, teams as TM

FIT = list(range(2016, 2021))
INPUTS = [*P.INPUTS, "elo_gap"]


def elo_gaps(sched, k, last):
    """{(game_id, team): (own − opponent pre-game rating) / 100}, home field not included."""
    g = E.prep(sched.filter(pl.col("season") <= last))
    r = E.run(g, k["k"], k["h"], k["c"])
    out = {}
    for gid, ht, at, rh, ra in zip(r["game_id"], r["home_team"], r["away_team"], r["r_home"], r["r_away"]):
        out[(gid, ht)] = (rh - ra) / 100
        out[(gid, at)] = (ra - rh) / 100
    return out


def add_elo(inp, gaps):
    v = [gaps.get((g, t), 0.0) for g, t in zip(inp["game_id"], inp["team"])]
    return inp.with_columns(pl.Series("elo_gap", v))


def fit_coefs(res, inp):
    x = res.join(inp, on=["game_id", "team"])
    X = x.select(INPUTS).to_numpy()
    coefs = {}
    for r in P.RATES:
        w, y = x["w_" + r].to_numpy(), x["y_" + r].to_numpy()
        Xc = np.c_[np.ones(len(y)), X]
        W = np.sqrt(w)[:, None]
        coefs[r] = dict(zip(["const", *INPUTS], map(float, np.linalg.lstsq(Xc * W, y * W[:, 0], rcond=None)[0])))
    return coefs


def shifts(inp, coefs):
    return {(row["game_id"], row["team"]): {r: sum(coefs[r][i] * row[i] for i in INPUTS) for r in P.RATES}
            for row in inp.iter_rows(named=True)}


def build_inputs(d, sched, seasons, pk):
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in seasons], how="diagonal_relaxed")
    sc = sched.filter(pl.col("season").is_in(seasons))
    qg = P.qb_games(pbp)
    qbd = P.qb_delta(sc, qg, P.QBRater(qg, pk["replacement"]))
    inj = P.injury_loss(pl.read_parquet(f"{d}/injuries.parquet").filter(pl.col("season").cast(pl.Int64).is_in(seasons)),
                        pl.read_parquet(f"{d}/snaps.parquet").filter(pl.col("season").cast(pl.Int64).is_in(seasons)),
                        pl.read_parquet(f"{d}/players.parquet"), sc)
    return pbp, P.inputs(qbd, inj, sc)


def main(d):
    path = config.ROOT / "data" / "backtests" / "elo_constants.json"
    ek = json.loads(path.read_text())
    k = json.loads((config.ROOT / "data" / "backtests" / "gamesim_constants.json").read_text())
    T = json.loads((config.ROOT / "data" / "backtests" / "gamesim_league.json").read_text())
    sched = pl.read_parquet(f"{d}/schedules.parquet")
    pbp, inp = build_inputs(d, sched, [2015, *FIT], k["personnel"])
    inp = add_elo(inp, elo_gaps(sched, ek, max(FIT)))
    gs = TM.game_stats(pbp, T)
    fac = TM.factors(gs, k["league"], k["h"], k["k"], k["r"])
    res = P.residuals(gs.filter(pl.col("season").is_in(FIT), pl.col("week") >= 2), fac, k["league"])
    coefs = fit_coefs(res, inp)
    g3 = P.fit_coefs(res, inp.drop("elo_gap"))
    L = ["G4 coefficients (fit 2016-2020, weeks 2+), with the G3 refit on the same rows for comparison:"]
    for r in P.RATES:
        L.append(f"{r}: G4 " + ", ".join(f"{a} {b:+.4f}" for a, b in coefs[r].items()))
        L.append(f"{r}: G3 " + ", ".join(f"{a} {b:+.4f}" for a, b in g3[r].items()))
        L.append(f"{r}: frozen G3 " + ", ".join(f"{a} {b:+.4f}" for a, b in k["personnel"]["coefs"][r].items()))
    ek["g4_coefs"] = coefs
    path.write_text(json.dumps(ek, indent=1))
    (config.ROOT / "docs" / "elo_g4_fit.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1])
