"""Players on every play of the game simulator (docs/gamesim_players_preregistration.md).

Roster per team-game: the players in nflbet.props.sim `inputs` for that team and week (3+ earlier games), with their
target share, carry share, catch rate, yards per catch and yards per carry from earlier games only. Shares are
normalized within the team; the QB with the largest attempt share is the passer (rusher slot 0, which also takes
scrambles and kneels). Each run draws the team's shares from a Dirichlet with mean = the shares and concentration c.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from . import engine as E
from . import run as R
from .teams import FRANCHISE

STATS = ("tgt", "rec", "ryd", "car", "uyd", "cmp", "pyd")


def _logit(p):
    p = np.clip(p, 0.05, 0.99)
    return np.log(p / (1 - p))


def scramble_share(pbp: pl.DataFrame) -> float:
    """Share of all rush attempts that are QB scrambles (fit seasons' play-by-play)."""
    r = pbp.filter(pl.col("season_type") == "REG", pl.col("rush_attempt") == 1, pl.col("two_point_attempt") == 0)
    return float(r["qb_scramble"].fill_null(0).mean())


def team_roster(rows: list[dict], f_scr: float) -> dict | None:
    """rows: `inputs` rows for one team-week. Returns ids and base rates for receiver and rusher slots."""
    qbs = [r for r in rows if r["pos"] == "QB" and (r.get("att_share") or 0) > 0]
    if not qbs:
        return None
    qb = max(qbs, key=lambda r: r["att_share"])
    rec = [r for r in rows if (r.get("tgt_share") or 0) > 0]
    rus = [qb] + [r for r in rows if (r.get("car_share") or 0) > 0 and r["player_id"] != qb["player_id"]]
    if not rec:
        return None
    ts = np.array([r["tgt_share"] for r in rec], float)
    ts /= ts.sum()
    catch = np.clip(np.array([r["catch"] for r in rec], float), 0.05, 0.99)
    ypr = np.array([r["ypr"] for r in rec], float)
    cshift = _logit(catch) - (ts * _logit(catch)).sum()
    w = ts * catch
    yscale = ypr / ((w * ypr).sum() / w.sum())
    cs = np.array([r.get("car_share") or 0.0 for r in rus], float)
    if cs.sum() <= 0:
        cs[0] = 1.0
    cs /= cs.sum()
    cs[0] = max(cs[0] - f_scr, 0.0)                  # the passer's scrambles are credited separately
    cs = cs / cs.sum() if cs.sum() > 0 else np.r_[1.0, np.zeros(len(cs) - 1)]
    ypc = np.array([r["ypc"] for r in rus], float)
    rscale = ypc / (cs * ypc).sum()
    return {"rec_ids": [r["player_id"] for r in rec], "rus_ids": [r["player_id"] for r in rus], "qb": qb["player_id"],
            "ts": ts, "cshift": cshift, "yscale": yscale, "cs": cs, "rscale": rscale}


def rosters(rows: pl.DataFrame, f_scr: float) -> dict:
    """{(season, week, franchise team): roster} from an `inputs` frame (must carry a season column)."""
    out = {}
    for (s, w, t), grp in rows.group_by("season", "week", "team"):
        r = team_roster(grp.to_dicts(), f_scr)
        if r is not None:
            out[(s, w, FRANCHISE.get(t, t))] = r
    return out


def _pad(x, k, fill=0.0):
    return np.r_[x, np.full(k - len(x), fill)]


def draw(rs: list, sims: int, c: float, rng: np.random.Generator) -> dict:
    """rs: list over games of (home roster, away roster). Engine roster arrays for len(rs) * sims elements."""
    K = max(len(r["ts"]) for pair in rs for r in pair)
    Kc = max(len(r["cs"]) for pair in rs for r in pair)

    def stack(key, k, fill):
        return np.stack([np.stack([_pad(r[key], k, fill) for r in pair]) for pair in rs])   # (G, 2, k)

    ts, cs = stack("ts", K, 0.0), stack("cs", Kc, 0.0)
    rep = lambda a: np.repeat(a, sims, axis=0)  # noqa: E731
    tsh, csh = rep(ts), rep(cs)
    if c and np.isfinite(c):
        tsh = rng.standard_gamma(c * tsh)
        csh = rng.standard_gamma(c * csh)
        for a, base in ((tsh, rep(ts)), (csh, rep(cs))):
            tot = a.sum(2, keepdims=True)
            bad = tot[..., 0] <= 0
            a[bad] = base[bad]
            a /= a.sum(2, keepdims=True)
    tcum, rcum = np.cumsum(tsh, 2), np.cumsum(csh, 2)
    tcum[..., -1] = rcum[..., -1] = 1.0
    return {"tcum": tcum, "rcum": rcum, "cshift": rep(stack("cshift", K, 0.0)), "yscale": rep(stack("yscale", K, 1.0)),
            "rscale": rep(stack("rscale", Kc, 1.0))}


def simulate(games: pl.DataFrame, fac: pl.DataFrame, tb: E.Tables, kicks, xps, hfa: float, ros: dict, sims: int,
             c: float, seed: int = 0, chunk: int = 60000, shift: dict | None = None, keep_games=None):
    """Simulate games with players. Games without a roster for both teams are skipped.
    Returns (game frame, list per game of {stat: array (sims, 2, K)}, list per game of (home roster, away roster),
    home points (G, sims), away points (G, sims))."""
    g, pools, pidx, xp = R.prep(games, fac, kicks, xps)
    ok = [((s, w, h) in ros) and ((s, w, a) in ros)
          for s, w, h, a in zip(g["season"], g["week"], g["home_team"], g["away_team"])]
    if keep_games is not None:
        ok = [o and (gid in keep_games) for o, gid in zip(ok, g["game_id"])]
    sel = np.flatnonzero(ok)
    g = g[sel]
    pidx, xp = pidx[sel], xp[sel]
    G = g.height
    per = max(1, chunk // sims)
    res, pairs = [], []
    H, A = np.zeros((G, sims), np.float32), np.zeros((G, sims), np.float32)
    for c0 in range(0, G, per):
        sl = slice(c0, min(G, c0 + per))
        gg = g[sl]
        pr = [(ros[(s, w, h)], ros[(s, w, a)]) for s, w, h, a in zip(gg["season"], gg["week"], gg["home_team"], gg["away_team"])]
        rng = np.random.default_rng(seed + 7919 * c0)
        roster = draw(pr, sims, c, rng)
        off, dfn = R.chunk_inputs(gg, sims, shift)
        h = np.where(np.repeat(gg["neutral"].to_numpy(), sims), 0.0, hfa)
        kid = np.repeat(pidx[sl], sims)
        xpe, sea = np.repeat(xp[sl], sims), np.repeat(gg["season"].to_numpy(), sims)
        n = len(h)
        hh, aa = np.zeros(n), np.zeros(n)
        out = {}
        for v in np.unique(h):
            m = h == v
            rr = {k: a[m] for k, a in roster.items()}
            cnt = {}
            a1, a2 = E.simulate(tb, {f: a[m] for f, a in off.items()}, {f: a[m] for f, a in dfn.items()},
                                (pools, kid[m]), xpe[m], sea[m], float(v), seed=seed + c0 + int(v * 1000), roster=rr,
                                counts=cnt)
            hh[m], aa[m] = a1, a2
            rr["out"]["qscore"] = cnt["qscore"]
            for k, a in rr["out"].items():
                if k not in out:
                    out[k] = np.zeros((n,) + a.shape[1:], np.int16)
                out[k][m] = a
        H[sl], A[sl] = hh.reshape(-1, sims), aa.reshape(-1, sims)
        for j in range(gg.height):
            res.append({k: a[j * sims:(j + 1) * sims] for k, a in out.items()})
        pairs += pr
    return g, res, pairs, H, A


def player_samples(res_g: dict, pair: tuple, side: int, pid: str) -> dict:
    """One player's simulated lines in one game: {market: array (sims,)}. Pass markets only for the passer."""
    r = pair[side]
    sims = next(iter(res_g.values())).shape[0]
    z = np.zeros(sims)
    out = {"targets": z, "rec": z, "rec_yds": z, "rush_att": z, "rush_yds": z}
    if pid in r["rec_ids"]:
        k = r["rec_ids"].index(pid)
        out.update(targets=res_g["tgt"][:, side, k].astype(float), rec=res_g["rec"][:, side, k].astype(float),
                   rec_yds=res_g["ryd"][:, side, k].astype(float))
    if pid in r["rus_ids"]:
        k = r["rus_ids"].index(pid)
        out.update(rush_att=res_g["car"][:, side, k].astype(float), rush_yds=res_g["uyd"][:, side, k].astype(float))
    if pid == r["qb"]:
        out.update(pass_att=res_g["tgt"][:, side].sum(1).astype(float), pass_cmp=res_g["cmp"][:, side].astype(float),
                   pass_yds=res_g["pyd"][:, side].astype(float))
    if pid not in r["rec_ids"] and pid not in r["rus_ids"] and pid != r["qb"]:
        return {}
    return out
