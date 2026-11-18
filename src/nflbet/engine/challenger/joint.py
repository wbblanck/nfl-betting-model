"""Engine B dependence layer (MODEL_SPECIFICATION 3.4).

The marginals of model.py are joined by a Gaussian copula per team-game. Each forecast (a player and a market) is a
variable; the correlation between two variables is looked up by their kind:
    (market, market, same player or not), with the rushing markets split by quarterback or not,
estimated on the fit seasons as the correlation of normal scores of the randomized probability integral transform
(the "residual ranks": where each outcome fell in its own forecast). Pairs with fewer than MIN_PAIRS examples get 0.
A team-game's matrix is made positive definite by clipping eigenvalues and restoring the unit diagonal.

Runs are drawn as u = Phi(L z) per team-game and pushed through model.ppf, so every marginal is exactly the one in
model.py. Then the box is reconciled (spec 3.4), which can only lower a value:
  - always: a player with no carries, catches or pass attempts in a run has no yards of that kind in it;
  - only with caps=True: the receivers' yards in a run are scaled down to the forecast quarterback's passing yards
    when they add up to more, and their catches to his pass attempts. This is not a true accounting rule: another
    quarterback may throw some of the team's passes (on 2022-2023 the forecast receivers out-gained the forecast
    quarterback in about 12% of real team-games), and on the tune seasons the caps worsened the receiving scores
    (docs/engine/engine_b_tune.md). So the default is caps=False; the spec's full reconciliation needs a team
    passing total, which Engine B does not forecast.
Not modelled: the link between the two offenses of a game and between backs and the game margin (Engine B has no
margin variable).
"""
from __future__ import annotations

import itertools

import numpy as np
import polars as pl
from scipy import special

from nflbet.engine.challenger import model as M

MARKETS = ("pass_att", "pass_yds", "rush_att", "rush_yds", "rec", "rec_yds")
MIN_PAIRS = 50
PIT_GRID = 1000


def tag(market: str, position: str) -> str:
    return f"{market}_qb" if market.startswith("rush") and position == "QB" else market


def key(t1: str, t2: str, same: bool) -> str:
    a, b = sorted((t1, t2))
    return f"{a}|{b}|{'same' if same else 'other'}"


def variables(df: pl.DataFrame, masks: dict) -> pl.DataFrame:
    """One row per forecast: frame row index, market, team-game, player and tag. masks: market -> boolean array."""
    out = []
    for m in MARKETS:
        if m not in masks:
            continue
        idx = np.nonzero(masks[m])[0]
        sub = df[idx]
        out.append(pl.DataFrame({"row": idx, "market": m, "tg": (sub["game_id"] + "|" + sub["team"]).to_list(),
                                 "player_id": sub["player_id"].to_list(),
                                 "tag": [tag(m, p) for p in sub["position"].to_list()]}))
    return pl.concat(out).with_row_index("v")


def normal_scores(P: dict, df: pl.DataFrame, masks: dict, outcomes: dict, rng: np.random.Generator) -> dict:
    """market -> normal score of each masked row's outcome under its forecast (randomized PIT for whole numbers)."""
    grid = (np.arange(PIT_GRID) + 0.5) / PIT_GRID
    out = {}
    for m, mask in masks.items():
        rows = df.filter(pl.Series(mask))
        y = np.asarray(outcomes[m])[mask]
        V = M.ppf(P, rows, m, np.tile(grid, (rows.height, 1)))
        lo, hi = (V < y[:, None]).mean(axis=1), (V <= y[:, None]).mean(axis=1)
        u = lo + rng.random(len(y)) * (hi - lo)
        out[m] = special.ndtri(np.clip(u, 0.5 / PIT_GRID, 1 - 0.5 / PIT_GRID))
    return out


def fit(P: dict, df: pl.DataFrame, masks: dict, outcomes: dict, seed: int = 0) -> dict:
    """Correlation per pair kind from the rows in masks (fit seasons). Returns {key: {rho, n}}."""
    z = normal_scores(P, df, masks, outcomes, np.random.default_rng(seed))
    var = variables(df, masks)
    zz = np.concatenate([z[m] for m in MARKETS if m in masks])
    acc: dict[str, list[float]] = {}
    for (_,), g in var.group_by(["tg"]):
        v, t, p = g["v"].to_numpy(), g["tag"].to_list(), g["player_id"].to_list()
        for i, j in itertools.combinations(range(len(v)), 2):
            k = key(t[i], t[j], p[i] == p[j])
            a = acc.setdefault(k, [0.0, 0.0, 0.0, 0])
            a[0] += zz[v[i]] * zz[v[j]]
            a[1] += zz[v[i]] ** 2
            a[2] += zz[v[j]] ** 2
            a[3] += 1
    return {k: {"rho": float(a[0] / np.sqrt(a[1] * a[2])) if a[3] >= MIN_PAIRS else 0.0, "n": int(a[3])}
            for k, a in sorted(acc.items())}


def nearest_corr(R: np.ndarray, floor: float = 1e-4) -> np.ndarray:
    w, V = np.linalg.eigh((R + R.T) / 2)
    R2 = (V * np.maximum(w, floor)) @ V.T
    d = np.sqrt(np.diag(R2))
    return R2 / d[:, None] / d[None, :]


def matrix(rho: dict, tags: list[str], players: list[str]) -> np.ndarray:
    n = len(tags)
    R = np.eye(n)
    for i, j in itertools.combinations(range(n), 2):
        R[i, j] = R[j, i] = rho.get(key(tags[i], tags[j], players[i] == players[j]), {"rho": 0.0})["rho"]
    return nearest_corr(R)


def simulate(P: dict, rho: dict, df: pl.DataFrame, masks: dict, sims: int, rng: np.random.Generator,
             reconcile_box: bool = True, caps: bool = False) -> tuple[dict, dict]:
    """(market -> runs [masked rows, sims], reconciliation counts). Same rows and order as df.filter(masks[market])."""
    var = variables(df, masks)
    U = np.empty((var.height, sims), dtype=np.float32)
    for (_,), g in var.group_by(["tg"], maintain_order=True):
        v = g["v"].to_numpy()
        L = np.linalg.cholesky(matrix(rho, g["tag"].to_list(), g["player_id"].to_list()))
        U[v] = special.ndtr(L @ rng.standard_normal((len(v), sims))).astype(np.float32)
    runs, at = {}, 0
    for m in MARKETS:
        if m not in masks:
            continue
        n = int(np.sum(masks[m]))
        runs[m] = M.ppf(P, df.filter(pl.Series(masks[m])), m, np.clip(U[at:at + n], 1e-7, 1 - 1e-7))
        at += n
    fixes = reconcile(runs, var, caps) if reconcile_box else {}
    return runs, fixes


def reconcile(runs: dict, var: pl.DataFrame, caps: bool = False) -> dict:
    """Apply the box rules in the module doc in place; return how many values each rule changed."""
    pos = {m: {} for m in MARKETS}                 # market -> (team-game, player) -> position in runs[market]
    for m in MARKETS:
        if m in runs:
            sub = var.filter(pl.col("market") == m)
            pos[m] = {(tg, p): i for i, (tg, p) in enumerate(zip(sub["tg"].to_list(), sub["player_id"].to_list()))}
    fixes = {"yards_without_volume": 0, "receiving_yards_over_passing": 0, "catches_over_attempts": 0}
    for vol, yds in (("pass_att", "pass_yds"), ("rush_att", "rush_yds"), ("rec", "rec_yds")):
        for k, i in pos[yds].items():
            if k in pos[vol]:
                bad = (runs[vol][pos[vol][k]] == 0) & (runs[yds][i] != 0)
                fixes["yards_without_volume"] += int(bad.sum())
                runs[yds][i][bad] = 0
    if not caps:
        return fixes
    by_tg: dict[str, list] = {}
    for (tg, p), i in pos["rec_yds"].items():
        by_tg.setdefault(tg, []).append(i)
    qbs = {tg: i for (tg, _), i in pos["pass_yds"].items()}
    for tg, rec_rows in by_tg.items():
        if tg not in qbs:
            continue
        tot = runs["rec_yds"][rec_rows].sum(axis=0)
        cap = np.maximum(runs["pass_yds"][qbs[tg]], 0)
        over = tot > cap
        if over.any():
            for i in rec_rows:
                x = runs["rec_yds"][i]
                scaled = np.floor(x * cap / np.maximum(tot, 1)).astype(np.int32)
                changed = over & (scaled != x)
                fixes["receiving_yards_over_passing"] += int(changed.sum())
                x[over] = np.minimum(x[over], scaled[over])
    qba = {tg: i for (tg, _), i in pos["pass_att"].items()}
    rec_by_tg: dict[str, list] = {}
    for (tg, p), i in pos["rec"].items():
        rec_by_tg.setdefault(tg, []).append(i)
    for tg, rows in rec_by_tg.items():
        if tg not in qba:
            continue
        tot = runs["rec"][rows].sum(axis=0)
        cap = runs["pass_att"][qba[tg]]
        over = tot > cap
        if over.any():
            for i in rows:
                x = runs["rec"][i]
                scaled = np.floor(x * cap / np.maximum(tot, 1)).astype(np.int32)
                changed = over & (scaled != x)
                fixes["catches_over_attempts"] += int(changed.sum())
                x[over] = np.minimum(x[over], scaled[over])
    for k, i in pos["rec_yds"].items():               # a catch scaled to zero takes its yards with it
        if k in pos["rec"]:
            bad = (runs["rec"][pos["rec"][k]] == 0) & (runs["rec_yds"][i] != 0)
            fixes["yards_without_volume"] += int(bad.sum())
            runs["rec_yds"][i][bad] = 0
    return fixes
