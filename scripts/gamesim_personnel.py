"""Fit the personnel-layer coefficients on 2016-2020 with the frozen factor constants and add them to
data/backtests/gamesim_constants.json (docs/gamesim_preregistration.md, step 3). Writes docs/gamesim_personnel.txt.

Usage: python scripts/gamesim_personnel.py <cache dir>"""
from __future__ import annotations

import json
import pickle
import sys

import polars as pl

from nflbet import config
from nflbet.gamesim import personnel as P, teams as TM

FIT = list(range(2016, 2021))


def build_inputs(d, seasons):
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in seasons], how="diagonal_relaxed")
    sched = pl.read_parquet(f"{d}/schedules.parquet").filter(pl.col("season").is_in(seasons))
    qg = P.qb_games(pbp)
    prior = P.replacement(qg, pbp, FIT) if 2015 in seasons else None
    return pbp, sched, qg, prior


def main(d):
    path = config.ROOT / "data" / "backtests" / "gamesim_constants.json"
    k = json.loads(path.read_text())
    T = pickle.load(open(f"{d}/gamesim_T.pkl", "rb"))
    seasons = [2015, *FIT]
    pbp, sched, qg, prior = build_inputs(d, seasons)
    rater = P.QBRater(qg, prior)
    qbd = P.qb_delta(sched, qg, rater)
    inj = P.injury_loss(pl.read_parquet(f"{d}/injuries.parquet").filter(pl.col("season").cast(pl.Int64).is_in(seasons)),
                        pl.read_parquet(f"{d}/snaps.parquet").filter(pl.col("season").cast(pl.Int64).is_in(seasons)),
                        pl.read_parquet(f"{d}/players.parquet"), sched)
    inp = P.inputs(qbd, inj, sched)
    gs = TM.game_stats(pbp, T)
    fac = TM.factors(gs, k["league"], k["h"], k["k"], k["r"])
    res = P.residuals(gs.filter(pl.col("season").is_in(FIT), pl.col("week") >= 2), fac, k["league"])
    coefs = P.fit_coefs(res, inp)
    k["personnel"] = {"replacement": prior, "D_days": P.D_DAYS, "KQ": P.KQ, "window": P.WINDOW, "coefs": coefs}
    path.write_text(json.dumps(k, indent=1))
    L = [f"replacement-level EPA/dropback {prior:.4f}", "inputs (fit seasons, weeks 2+): " +
         str(inp.join(res.select("game_id", "team"), on=["game_id", "team"]).select(P.INPUTS).describe())]
    for r, c in coefs.items():
        L.append(f"{r}: " + ", ".join(f"{a} {b:+.4f}" for a, b in c.items()))
    (config.ROOT / "docs" / "gamesim_personnel.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1])
