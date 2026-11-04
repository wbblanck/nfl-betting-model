"""Player props from the game simulator: 2024 (descriptive) and 2025 (evaluation) against DraftKings
(docs/gamesim_props_preregistration.md). Writes docs/gamesim_props_eval.md and data/backtests/gamesim_props.json.

Usage: python scripts/gamesim_props_eval.py <cache dir>"""
from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.gamesim import engine as E, personnel as P, props as GP, run as R, teams as TM
from nflbet.gamesim.teams import FRANCHISE
from nflbet.props import confirm as C, core as PC
from nflbet.props.sim import Simulator, inputs

SIMS = 10000
MARKETS = ["rec", "rec_yds", "rush_att", "rush_yds", "pass_att", "pass_cmp", "pass_yds"]
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s, flush=True)


def ll(p, y):
    p = np.clip(p, 0.02, 0.98)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def game_volumes(d, seasons):
    k = json.loads((config.ROOT / "data" / "backtests" / "gamesim_constants.json").read_text())
    tb = E.Tables(json.loads((config.ROOT / "data" / "backtests" / "gamesim_league.json").read_text()))
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in range(2015, max(seasons) + 1)], how="diagonal_relaxed")
    kicks, xps = R.kick_pools(pbp)
    gs = TM.game_stats(pbp, tb_dict(k, d))
    fac = TM.factors(gs, k["league"], k["h"], k["k"], k["r"])
    sched = pl.read_parquet(f"{d}/schedules.parquet")
    qg = P.qb_games(pbp)
    qbd = P.qb_delta(sched, qg, P.QBRater(qg, k["personnel"]["replacement"]))
    inj = P.injury_loss(pl.read_parquet(f"{d}/injuries.parquet"), pl.read_parquet(f"{d}/snaps.parquet"),
                        pl.read_parquet(f"{d}/players.parquet"), sched)
    games = sched.filter(pl.col("game_type") == "REG", pl.col("season").is_in(seasons)).select(
        "season", "week", "game_id", "home_team", "away_team", (pl.col("location") == "Neutral").alias("neutral"))
    inp = P.inputs(qbd, inj, sched).filter(pl.col("game_id").is_in(games["game_id"].implode()))
    out, margins, att, car = R.simulate_games(games, fac, tb, kicks, xps, k["hfa"], sims=SIMS, seed=202,
                                              shift=P.shifts(inp, k["personnel"]["coefs"]), want_counts=True)
    return out, att, car


def tb_dict(k, d):
    return json.loads((config.ROOT / "data" / "backtests" / "gamesim_league.json").read_text())


def main(d):
    seasons = [2024, 2025]
    out, att, car = game_volumes(d, seasons)
    say(f"Game simulator: {out.height} games x {SIMS} runs; mean team pass attempts {att.mean():.2f}, carries {car.mean():.2f}")
    idx = {}
    for i, (s, w, h, a) in enumerate(zip(out["season"], out["week"], out["home_team"], out["away_team"])):
        idx[(s, w, h)] = (i, 0)
        idx[(s, w, a)] = (i, 1)
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    rng = np.random.default_rng(7)
    res = {}
    for season in seasons:
        g = PC.graded(PC.join(PC.load_lines(season), PC.load_stats(season), PC.load_snaps(season)))
        dk = C.screened(g).filter(pl.col("book") == "DK NJ", pl.col("result") != "push", pl.col("market").is_in(MARKETS)) \
            .unique(subset=C.KEY)
        keep = set(zip(dk["player_id"].to_list(), dk["week"].to_list()))
        old = sim.run(season, keep=keep)
        rows_in = {(r["player_id"], r["week"]): r for r in inputs(sim.pg, sim.sched, season, sim.pos_mean, sim.dfac).iter_rows(named=True)
                   if (r["player_id"], r["week"]) in keep}
        cache, rows, checks = {}, [], []
        for r in dk.iter_rows(named=True):
            key = (r["player_id"], r["week"])
            pr = rows_in.get(key)
            if pr is None:
                continue
            gi = idx.get((season, r["week"], FRANCHISE.get(pr["team"], pr["team"])))
            if gi is None:
                continue
            if key not in cache:
                cache[key] = GP.simulate_row_vol(pr, att[gi[0], :, gi[1]], car[gi[0], :, gi[1]], sim.pools, rng)
            s = cache[key].get(r["market"])
            o = old.get(key, {}).get(r["market"])
            if s is None or o is None:
                continue
            p = GP.p_over(s, r["line"])
            po = GP.p_over(o, r["line"])
            if p is None or po is None:
                continue
            rows.append({"player_id": r["player_id"], "week": r["week"], "market": r["market"], "line": r["line"],
                         "p_dk": r["p_over"], "p_sim": p, "p_old": po, "over_odds": r["over_odds"],
                         "under_odds": r["under_odds"], "y": float(r["result"] == "over")})
        x = pl.DataFrame(rows)
        y = x["y"].to_numpy()
        L = {"n": x.height, "of": dk.height, "ll_sim": ll(x["p_sim"].to_numpy(), y), "ll_dk": ll(x["p_dk"].to_numpy(), y),
             "ll_old": ll(x["p_old"].to_numpy(), y)}
        say(f"\n## {season} ({'player-layer fit season, descriptive' if season == 2024 else 'evaluation'}): {x.height} of {dk.height} screened DK props")
        say(f"Log loss: game-sim props {L['ll_sim']:.4f} | old prop simulator {L['ll_old']:.4f} | DK de-vigged {L['ll_dk']:.4f} | coin 0.6931")
        say("\nBy market | n | game-sim | old sim | DK")
        bym = {}
        for mk in MARKETS:
            z = x.filter(pl.col("market") == mk)
            if z.height:
                yz = z["y"].to_numpy()
                bym[mk] = [z.height, ll(z["p_sim"].to_numpy(), yz), ll(z["p_old"].to_numpy(), yz), ll(z["p_dk"].to_numpy(), yz)]
                say(f"{mk} | {z.height} | {bym[mk][1]:.4f} | {bym[mk][2]:.4f} | {bym[mk][3]:.4f}")
        say("\nCalibration: the side the game sim favors, by its probability | n | said | hit")
        side_p = np.maximum(x["p_sim"].to_numpy(), 1 - x["p_sim"].to_numpy())
        side_over = x["p_sim"].to_numpy() >= 0.5
        hit = np.where(side_over, y == 1, y == 0)
        cal = []
        for lo in (0.5, 0.6, 0.7, 0.8, 0.9):
            m = (side_p >= lo) & (side_p < lo + 0.1 if lo < 0.9 else side_p <= 1.0)
            if m.any():
                cal.append([lo, int(m.sum()), float(side_p[m].mean()), float(hit[m].mean())])
                say(f"{lo:.0%}-{min(lo + 0.1, 1):.0%} | {m.sum()} | {side_p[m].mean():.1%} | {hit[m].mean():.1%}")
        m75 = side_p >= 0.75
        odds = np.where(side_over, x["over_odds"].to_numpy(), x["under_odds"].to_numpy()).astype(float)
        pnl = PC.profit(odds[m75], hit[m75].astype(float)) if m75.any() else np.array([])
        say(f"\nGame sim at 75%+ on one side: {int(m75.sum())} props ({m75.mean():.1%} of all), hit {hit[m75].mean() if m75.any() else float('nan'):.1%}, "
            f"ROI at DK's price {pnl.mean() if len(pnl) else float('nan'):+.1%} (descriptive)")
        res[season] = {**L, "by_market": bym, "calibration": cal, "ge75": {"n": int(m75.sum()),
                       "hit": float(hit[m75].mean()) if m75.any() else None, "roi": float(pnl.mean()) if len(pnl) else None}}
        if season == 2025:
            # known answers: reproducible, share response, volume passthrough
            k0 = next(iter(cache))
            pr0 = rows_in[k0]
            gi = idx[(season, k0[1], FRANCHISE.get(pr0["team"], pr0["team"]))]
            a_, c_ = att[gi[0], :, gi[1]], car[gi[0], :, gi[1]]
            s1 = GP.simulate_row_vol(pr0, a_, c_, sim.pools, np.random.default_rng(1))
            s2 = GP.simulate_row_vol(pr0, a_, c_, sim.pools, np.random.default_rng(1))
            dbl = GP.simulate_row_vol(dict(pr0, tgt_share=min(0.9, 2 * (pr0["tgt_share"] or 0.05))), a_, c_, sim.pools, np.random.default_rng(1))
            checks = [f"same seed reproduces: {all(np.array_equal(s1[m], s2[m]) for m in s1)}",
                      f"doubled target share raises mean targets: {dbl['targets'].mean():.2f} vs {s1['targets'].mean():.2f}",
                      f"team attempts passed through: mean {a_.mean():.2f} from the game simulator"]
            say("\nKnown answers: " + "; ".join(checks))
    (config.ROOT / "data" / "backtests" / "gamesim_props.json").write_text(json.dumps(res, indent=1, default=str))
    head = ["# Game simulator player props: 2024-2025 vs DraftKings", "",
            "Pre-registration: docs/gamesim_props_preregistration.md. 10,000 game runs per game (G3 simulator); player layer "
            "from nflbet.props.sim, constants unchanged. Research only: no pick list.", ""]
    (config.ROOT / "docs" / "gamesim_props_eval.md").write_text("\n".join(head + OUT) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
