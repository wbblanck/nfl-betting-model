"""Poisson and negative binomial counts vs binomial in the game-simulator prop layer
(docs/gamesim_props_dist_preregistration.md). Writes docs/gamesim_props_dist.md and
data/backtests/gamesim_props_dist.json.

Usage: python scripts/gamesim_props_dist.py <cache dir>"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import ats_clv as C  # noqa: E402
import gamesim_props_eval as G  # noqa: E402

from nflbet import config  # noqa: E402
from nflbet.gamesim import props as GP  # noqa: E402
from nflbet.gamesim.teams import FRANCHISE  # noqa: E402
from nflbet.props import confirm as PCF, core as PC  # noqa: E402
from nflbet.props.sim import Simulator, inputs  # noqa: E402

MARKETS = G.MARKETS
GROUPS = {"targets": ["rec", "rec_yds"], "carries": ["rush_att", "rush_yds"], "qb_att": ["pass_att", "pass_cmp", "pass_yds"]}
GRID = [2, 4, 8, 16, 32]
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s, flush=True)


def volumes(d):
    f = f"{d}/gamesim_volumes_2024_2025.npz"
    if os.path.exists(f):
        z = np.load(f, allow_pickle=True)
        return pl.DataFrame(z["out"].item()), z["att"], z["car"]
    out, att, car = G.game_volumes(d, [2024, 2025])
    np.savez(f, out=np.array(out.to_dict(as_series=False), dtype=object), att=att, car=car)
    return out, att, car


def probs(season, dk, rows_in, idx, att, car, pools, dist, size):
    rng = np.random.default_rng(31)         # same seed for every version (common random numbers)
    cache, p = {}, []
    for r in dk.iter_rows(named=True):
        key = (r["player_id"], r["week"])
        pr = rows_in[key]
        gi = idx[(season, r["week"], FRANCHISE.get(pr["team"], pr["team"]))]
        if key not in cache:
            cache[key] = GP.simulate_row_vol(pr, att[gi[0], :, gi[1]], car[gi[0], :, gi[1]], pools, rng, dist, size)
        p.append(GP.p_over(cache[key][r["market"]], r["line"]))
    return np.array([np.nan if v is None else v for v in p], float)


def ll_each(p, y):
    p = np.clip(p, 0.02, 0.98)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def main(d):
    out, att, car = volumes(d)
    idx = {}
    for i, (s, w, h, a) in enumerate(zip(out["season"], out["week"], out["home_team"], out["away_team"])):
        idx[(s, w, h)], idx[(s, w, a)] = (i, 0), (i, 1)
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    data = {}
    for season in (2024, 2025):
        g = PC.graded(PC.join(PC.load_lines(season), PC.load_stats(season), PC.load_snaps(season)))
        dk = PCF.screened(g).filter(pl.col("book") == "DK NJ", pl.col("result") != "push", pl.col("market").is_in(MARKETS)) \
            .unique(subset=PCF.KEY)
        keep = set(zip(dk["player_id"].to_list(), dk["week"].to_list()))
        rows_in = {(r["player_id"], r["week"]): r for r in inputs(sim.pg, sim.sched, season, sim.pos_mean, sim.dfac).iter_rows(named=True)
                   if (r["player_id"], r["week"]) in keep}
        ok = [(k in rows_in) and ((season, k[1], FRANCHISE.get(rows_in[k]["team"], rows_in[k]["team"])) in idx)
              for k in zip(dk["player_id"].to_list(), dk["week"].to_list())]
        dk = dk.filter(pl.Series(ok))
        data[season] = (dk, rows_in)
    # ---- choose NB size per count on 2024
    dk24, rows24 = data[2024]
    y24 = (dk24["result"] == "over").cast(pl.Float64).to_numpy()
    mk24 = dk24["market"].to_numpy()
    grid_ll = {}
    for size in GRID:
        p = probs(2024, dk24, rows24, idx, att, car, sim.pools, "nb", {"targets": size, "carries": size, "qb_att": size})
        for grp, mks in GROUPS.items():
            m = np.isin(mk24, mks) & ~np.isnan(p)
            grid_ll[(grp, size)] = float(ll_each(p[m], y24[m]).mean())
    chosen = {grp: min(GRID, key=lambda s: grid_ll[(grp, s)]) for grp in GROUPS}
    say("## Negative binomial size chosen on 2024 (log loss on that count's markets)")
    for grp in GROUPS:
        say(f"- {grp}: " + ", ".join(f"r={s}: {grid_ll[(grp, s)]:.4f}" for s in GRID) + f" -> **{chosen[grp]}**")
    # ---- 2025 test
    res = {"chosen": chosen, "grid_2024": {f"{a}_{b}": v for (a, b), v in grid_ll.items()}}
    for season in (2024, 2025):
        dk, rows_in = data[season]
        y = (dk["result"] == "over").cast(pl.Float64).to_numpy()
        cl = (dk["week"]).to_numpy()
        pv = {"B": probs(season, dk, rows_in, idx, att, car, sim.pools, "binom", None),
              "P": probs(season, dk, rows_in, idx, att, car, sim.pools, "pois", None),
              "NB": probs(season, dk, rows_in, idx, att, car, sim.pools, "nb", chosen)}
        good = ~np.isnan(pv["B"]) & ~np.isnan(pv["P"]) & ~np.isnan(pv["NB"])
        y, cl = y[good], cl[good]
        pv = {k: v[good] for k, v in pv.items()}
        pdk = dk["p_over"].to_numpy()[good]
        odds_o, odds_u = dk["over_odds"].to_numpy()[good].astype(float), dk["under_odds"].to_numpy()[good].astype(float)
        mk = dk["market"].to_numpy()[good]
        L = {k: ll_each(v, y) for k, v in pv.items()}
        say(f"\n## {season} ({'NB size chosen here; descriptive' if season == 2024 else 'test'}): {len(y)} DraftKings props")
        say(f"Log loss: binomial {L['B'].mean():.4f} | Poisson {L['P'].mean():.4f} | negative binomial {L['NB'].mean():.4f} | "
            f"DK de-vigged {ll_each(pdk, y).mean():.4f} | coin 0.6931")
        r = {"n": int(len(y)), "ll": {k: float(v.mean()) for k, v in L.items()}, "ll_dk": float(ll_each(pdk, y).mean())}
        if season == 2025:
            for v in ("P", "NB"):
                diff = L[v] - L["B"]
                ci = C.boot(lambda ix: diff[ix].mean(), cl, 0.05 / 2 / 2)
                r[f"{v}_minus_B"] = {"mean": float(diff.mean()), "ci": list(ci), "better": bool(ci[1] < 0)}
                say(f"- **{v} minus binomial:** {diff.mean():+.4f}, interval {ci[0]:+.4f} to {ci[1]:+.4f}: "
                    f"**{'BETTER' if ci[1] < 0 else 'NOT BETTER'}**")
        say("\nBy market (log loss) | n | binomial | Poisson | neg. binomial | DK")
        for m_ in MARKETS:
            m = mk == m_
            if m.any():
                say(f"{m_} | {m.sum()} | {L['B'][m].mean():.4f} | {L['P'][m].mean():.4f} | {L['NB'][m].mean():.4f} | {ll_each(pdk[m], y[m]).mean():.4f}")
        say("\nCalibration: favored side's probability band | version | n | said | hit")
        cal = {}
        for k, p in pv.items():
            sp = np.maximum(p, 1 - p)
            hit = np.where(p >= 0.5, y == 1, y == 0)
            cal[k] = []
            for lo in (0.6, 0.7, 0.8, 0.9):
                m = (sp >= lo) & ((sp < lo + 0.1) if lo < 0.9 else (sp <= 1))
                if m.any():
                    cal[k].append([lo, int(m.sum()), float(sp[m].mean()), float(hit[m].mean())])
                    say(f"{lo:.0%}-{min(lo + .1, 1):.0%} | {k} | {m.sum()} | {sp[m].mean():.1%} | {hit[m].mean():.1%}")
            m75 = sp >= 0.75
            odds = np.where(p >= 0.5, odds_o, odds_u)
            pnl = PC.profit(odds[m75], hit[m75].astype(float)) if m75.any() else np.array([])
            cal[k].append({"ge75_n": int(m75.sum()), "hit": float(hit[m75].mean()) if m75.any() else None,
                           "roi": float(pnl.mean()) if len(pnl) else None})
            say(f"75%+ | {k} | {m75.sum()} | hit {hit[m75].mean() if m75.any() else float('nan'):.1%} | ROI {pnl.mean() if len(pnl) else float('nan'):+.1%}")
        r["calibration"] = cal
        res[season] = r
    (config.ROOT / "data" / "backtests" / "gamesim_props_dist.json").write_text(json.dumps(res, indent=1, default=str))
    head = ["# Game simulator props: Poisson and negative binomial vs binomial", "",
            "Pre-registration: docs/gamesim_props_dist_preregistration.md. Same 10,000 game runs per game for every version; "
            "only the count distribution for targets, carries and QB attempts changes.", ""]
    (config.ROOT / "docs" / "gamesim_props_dist.md").write_text("\n".join(head + OUT) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
