"""Player props from the game simulator (docs/gamesim_props_preregistration.md).

Run i of a player's game gives his team's pass attempts and carries; the player's line in run i is drawn with the
existing prop simulator's player layer (nflbet.props.sim, constants unchanged), so game script drives volume.
"""
from __future__ import annotations

import numpy as np

from nflbet.props import sim as S


def simulate_row_vol(r: dict, att: np.ndarray, car: np.ndarray, pools: dict, rng: np.random.Generator) -> dict:
    """As nflbet.props.sim.simulate_row (matchup weight 0), with team attempts and carries supplied per run."""
    n = len(att)
    att, car = np.maximum(att.astype(int), 0), np.maximum(car.astype(int), 0)
    out = {}
    pos = r["pos"]
    tg = rng.binomial(att, S._beta_share(rng, r["tgt_share"] or 0, n))
    rec = rng.binomial(tg, float(np.clip(r["catch"], 0.05, 0.99)))
    pool_r = pools.get(("rec", pos))
    out["targets"] = tg.astype(float)
    out["rec"] = rec.astype(float)
    out["rec_yds"] = S._sum_draws(rng, rec, pool_r, r["ypr"] / max(np.mean(pool_r), 1e-6)) if pool_r is not None else rec * r["ypr"]
    cr = rng.binomial(car, S._beta_share(rng, r["car_share"] or 0, n))
    pool_c = pools.get(("rush", pos))
    out["rush_att"] = cr.astype(float)
    out["rush_yds"] = S._sum_draws(rng, cr, pool_c, r["ypc"] / max(np.mean(pool_c), 1e-6)) if pool_c is not None else cr * r["ypc"]
    if pos == "QB":
        pa = rng.binomial(att, S._beta_share(rng, r["att_share"] or 0, n))
        cm = rng.binomial(pa, float(np.clip(r["cmp"], 0.3, 0.85)))
        out["pass_att"], out["pass_cmp"] = pa.astype(float), cm.astype(float)
        out["pass_yds"] = S._sum_draws(rng, cm, pools["cmp"], r["ypcmp"] / max(np.mean(pools["cmp"]), 1e-6))
    return out


def p_over(samples: np.ndarray, line: float) -> float | None:
    """Share of runs above the line; runs on the line are pushes and leave the denominator."""
    over, push = float(np.mean(samples > line)), float(np.mean(samples == line))
    return over / (1 - push) if push < 1 else None
