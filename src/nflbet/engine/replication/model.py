"""Engine A, version 0.1: fit the layers and simulate one offense in one game.

A run draws team attempts, carries and targets; draws which players on the game-day active list take part; splits
the volume among them; draws catches and yards; and adds the quarterback's line as the sum of his receivers'.
Every run is a box score that reconciles (engine.accounting).

What the engine knows: the active list (published about 90 minutes before kickoff) and earlier games. It does not
know who goes on to play. A player's forecast is taken from the runs in which he plays, because a prop on a player
who does not play is void; whether his teammates play stays uncertain in those runs.

Not in 1.0 (docs/engine/MODEL_SPECIFICATION.md section 2): play-by-play game script (volume reacting to the simulated score),
availability draws, opponent-specific efficiency, touchdowns and interceptions.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from nflbet.engine.replication import efficiency as E, environment as V, opportunity as O

VERSION = "A-1.0"
KINDS = {"targets": ("targets", "team_targets"), "carries": ("carries", "team_carries")}
KEY = ["game_id", "team"]
# Chosen on the tune seasons (2022-2023), then frozen with the version. Multipliers on fit-season estimates, except
# the rushing shock, which is a value (its fit-season estimate was 0). {} means "use the fit-season estimates as is".
TUNING: dict = {}


def apply_tuning(P: dict, tuning: dict) -> dict:
    """Return P with the tune-season settings applied: 'kappa_targets' and 'kappa_carries' multiply the split
    concentrations, 'catch_strength' multiplies the catch-rate prior strength, 'shock_rec' and 'shock_rush' set the
    team-wide yardage shock."""
    import copy
    P = copy.deepcopy(P)
    for kind in ("targets", "carries"):
        P["opp"][kind]["kappa"] *= tuning.get(f"kappa_{kind}", 1.0)
    P["eff"]["c"]["catch"] *= tuning.get("catch_strength", 1.0)
    for kind in ("rec", "rush"):
        if f"shock_{kind}" in tuning:
            P["eff"]["shock"][kind] = float(tuning[f"shock_{kind}"])
    P["tuning"] = dict(tuning)
    return P


def _pos(df: pl.DataFrame) -> np.ndarray:
    return np.array([p if p in E.POSITIONS else "OTH" for p in df["position"].to_list()])


def _hist(df: pl.DataFrame, col: str) -> np.ndarray:
    return (df[f"p_{col}_std"] + df[f"p_{col}_prev"]).to_numpy().astype(float)


def starter_flag(df: pl.DataFrame) -> np.ndarray:
    """Quarterbacks expected to start, from earlier games only: he played in his team's previous game and threw more
    than half of the team's passes over his last 3 games. Whether anyone else ends up playing is not used."""
    share = df["p_attempts_w3"].to_numpy() / np.maximum(df["p_team_att_w3"].to_numpy(), 1)
    same = (df["p_last_kickoff"] == df["o_last_kickoff"]).fill_null(False).to_numpy()
    return (df["position"] == "QB").to_numpy() & same & (share > 0.5)


def play_bucket(df: pl.DataFrame) -> list[str]:
    """Group for the chance an active player takes a snap, from earlier games only: position, whether he played in
    his team's previous game, and his snaps per game over his last 3 (none, up to 10, up to 30, more)."""
    last = (df["p_last_kickoff"] == df["o_last_kickoff"]).fill_null(False).to_numpy()
    snaps = df["p_offense_snaps_w3"].to_numpy() / np.maximum(df["p_n_w3"].to_numpy(), 1)
    band = np.digitize(snaps, [0.5, 10.0, 30.0])
    return [f"{p}|{int(l)}|{int(b)}" for p, l, b in zip(_pos(df), last, band)]


def play_prob(P: dict, df: pl.DataFrame) -> np.ndarray:
    t = P["play"]
    return np.array([t["cell"].get(k, t["pos"].get(k.split("|")[0], t["all"])) for k in play_bucket(df)])


def pick_starter(df: pl.DataFrame) -> tuple[int | None, str]:
    """(row of the quarterback expected to start among those active, which share pool to draw from).
    Order: a recent starter (starter_flag) first; then the depth chart's rank; then volume over his last 8 games.
    On 2018-2021 this named the actual leader in attempts in 92.8% of team-games (history alone 91.1%).
    'starter_share' when he is a recent starter or the chart's number one, otherwise 'new_share'."""
    qbs = np.flatnonzero((df["position"] == "QB").to_numpy())
    if not len(qbs):
        return None, "new_share"
    flag = starter_flag(df)[qbs]
    depth = (df["depth_rank"].to_numpy() if "depth_rank" in df.columns else np.full(df.height, 9))[qbs]
    vol = df["p_attempts_w8"].to_numpy()[qbs]
    i = int(np.lexsort((-vol, depth, ~flag))[0])
    return int(qbs[i]), ("starter_share" if flag[i] or depth[i] == 1 else "new_share")


def _lookup(table: dict, pos: np.ndarray) -> np.ndarray:
    return np.array([table[p] for p in pos])


def fit(df: pl.DataFrame, teams: pl.DataFrame, pools: dict) -> dict:
    """df: fit-season feature rows with outcome columns; teams: team-game facts for the same games (team_att,
    team_carries, team_targets, team_sacks, team_scrambles); pools: {'rec' | 'rush': {position: yards per play}}."""
    if "played" not in df.columns:
        df = df.with_columns(pl.lit(True).alias("played"))
    everyone, df = df, df.filter(pl.col("played"))              # the split and efficiency layers are fitted on who played
    df = df.join(teams.select(*KEY, pl.col("team_att").alias("T_attempts"), pl.col("team_carries").alias("T_carries"),
                              pl.col("team_targets").alias("T_targets")), on=KEY, how="inner").sort(*KEY, "player_id")
    first = df.group_by(KEY, maintain_order=True).first()
    # Sorted: a join does not promise row order, and the residuals are later drawn by position in this list.
    tf = first.join(teams.select(*KEY, *[c for c in ("team_att", "team_carries", "team_targets", "team_sacks", "team_scrambles", "team_points")
                                             if c in teams.columns]), on=KEY).sort(KEY)
    where = {k: i for i, k in enumerate(zip(tf["game_id"].to_list(), tf["team"].to_list()))}
    by_game: dict = {}
    for (g, tm), i in where.items():
        by_game.setdefault(g, []).append(i)
    opp = np.array([next((j for j in by_game[g] if j != i), -1) for (g, tm), i in where.items()])
    pts = tf["team_points"].to_numpy().astype(float) if "team_points" in tf.columns else np.full(tf.height, np.nan)
    P = {"version": VERSION, "env": V.fit(tf, tf.select("team_att", "team_carries").to_numpy().astype(float), tf["team_targets"].to_numpy(),
                                          np.where(np.isnan(pts), 22.0, pts), opp)}
    played, keys = everyone["played"].to_numpy().astype(float), np.array(play_bucket(everyone))
    cell = {k: float(played[keys == k].mean()) for k in np.unique(keys) if (keys == k).sum() >= 30}
    by_pos = {p: float(played[_pos(everyone) == p].mean()) for p in np.unique(_pos(everyone))}
    P["play"] = {"cell": cell, "pos": by_pos, "all": float(played.mean())}
    pos = _pos(df)
    gid = df.select(pl.struct(KEY).rank("dense").alias("g"))["g"].to_numpy() - 1
    G = int(gid.max()) + 1
    slot = np.zeros(len(gid), dtype=int)
    for i in range(1, len(gid)):
        slot[i] = slot[i - 1] + 1 if gid[i] == gid[i - 1] else 0
    K = int(slot.max()) + 1

    def pad(v):
        out = np.zeros((G, K))
        out[gid, slot] = v
        return out

    P["opp"] = {}
    for kind, (col, tcol) in KINDS.items():
        x, total = df[col].to_numpy().astype(float), df[f"T_{kind}"].to_numpy().astype(float)
        share = x / np.maximum(total, 1)
        prior = {p: float(share[pos == p].mean()) for p in E.POSITIONS if (pos == p).any()}
        xp = pad(x)
        tot = pad(total).max(axis=1)
        x_other = np.maximum(tot - xp.sum(axis=1), 0)
        other = float(x_other.sum() / tot.sum())
        counts = {w: pad(df[f"p_{col}_{w}"].to_numpy().astype(float)) for w in O.WINDOWS}
        denoms = {w: pad(df[f"p_{tcol}_{w}"].to_numpy().astype(float)) for w in O.WINDOWS}
        f = O.fit(counts, denoms, pad(_lookup(prior, pos)), np.column_stack([xp, x_other]), max(other, 1e-4))
        P["opp"][kind] = {**f, "prior": prior}
    pools_qb = {"starter_share": [], "new_share": []}
    tot = dict(zip(zip(teams["game_id"].to_list(), teams["team"].to_list()), teams["team_att"].to_list()))
    for (g, tm), rows in everyone.sort(*KEY, "player_id").group_by(KEY, maintain_order=True):
        i, kind = pick_starter(rows)
        if i is not None and rows["played"][i] and tot.get((g, tm), 0) > 0:     # share he took, given that he played
            pools_qb[kind].append(float(min(rows["attempts"][i] / tot[(g, tm)], 1.0)))
    P["qb"] = pools_qb
    rate = {p: float(df["receptions"].to_numpy()[pos == p].sum() / max(df["targets"].to_numpy()[pos == p].sum(), 1)) for p in E.POSITIONS if (pos == p).any()}
    rate["OTH"] = float(df["receptions"].sum() / df["targets"].sum())
    eff = {"catch_rate": rate, "mu": {}, "var": {}, "c": {}, "shock": {}}
    eff["c"]["catch"] = E.fit_catch_strength(_hist(df, "receptions"), _hist(df, "targets"), _lookup(rate, pos),
                                             df["targets"].to_numpy(), df["receptions"].to_numpy())
    for kind, n_col, y_col in (("rec", "receptions", "receiving_yards"), ("rush", "carries", "rushing_yards")):
        eff["mu"][kind] = {p: float(np.mean(v)) for p, v in pools[kind].items()}
        eff["var"][kind] = {p: float(np.var(v)) for p, v in pools[kind].items()}
        mu, var = _lookup(eff["mu"][kind], pos), _lookup(eff["var"][kind], pos)
        n, y = df[n_col].to_numpy().astype(float), df[y_col].to_numpy().astype(float)
        c = E.fit_factor_strength(_hist(df, y_col), _hist(df, n_col), mu, n, y)
        f = E.factor(_hist(df, y_col), _hist(df, n_col), mu, c)
        eff["c"][kind] = c
        eff["shock"][kind] = E.shock_sd(pad(y).sum(axis=1), pad(n * mu * f).sum(axis=1), pad(n * var * f ** 2).sum(axis=1))
    P["eff"] = eff
    qb_car = float(df["carries"].to_numpy()[pos == "QB"].sum())
    P["sack_rate"] = float(tf["team_sacks"].sum() / tf["team_att"].sum())
    P["scramble_share"] = float(min(tf["team_scrambles"].sum() / max(qb_car, 1), 1.0))
    return P


def tables(pools: dict, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    return {kind: {p: E.sum_table(np.asarray(v, float), E.NMAX[kind], rng) for p, v in pools[kind].items()} for kind in ("rec", "rush")}


def _yards(rng, tab: dict, pos: np.ndarray, n: np.ndarray, f: np.ndarray, shock: np.ndarray) -> np.ndarray:
    """n [sims, K] plays -> whole yards [sims, K]; exactly 0 where n is 0."""
    out = np.zeros(n.shape, dtype=np.int64)
    for k, p in enumerate(pos):
        t = tab[p]
        base = t[np.minimum(n[:, k], t.shape[0] - 1), rng.integers(0, t.shape[1], n.shape[0])]
        out[:, k] = np.where(n[:, k] > 0, np.rint(base * f[k] * shock), 0)
    return out


def simulate_game(P: dict, tab: dict, sides: list[pl.DataFrame], sims: int, rng: np.random.Generator) -> list[tuple[dict, dict]]:
    """Both offenses of one game (or one, if only one is given), sharing the volume surprise of each run."""
    index = V.draw_index(P["env"], sims, rng)
    return [simulate(P, tab, rows, sims, rng, index, side) for side, rows in enumerate(sides[:2])]


def simulate(P: dict, tab: dict, rows: pl.DataFrame, sims: int, rng: np.random.Generator, index: np.ndarray | None = None,
             side: int = 0) -> tuple[dict, dict]:
    """rows: the feature rows of one offense in one game (its active skill players). Returns (box for
    engine.accounting.violations, samples: stat -> [players, sims] in the order of rows)."""
    pos = _pos(rows)
    posx = np.append(pos, "OTH")
    a, c, t = V.draw(P["env"], V.mean(P["env"], rows.head(1))[0], sims, rng, index, side)
    k = len(pos)
    play = rng.random((sims, k)) < play_prob(P, rows)[None, :]
    qbs = np.flatnonzero(pos == "QB")
    top, key = pick_starter(rows)
    if top is not None:
        play[:, top] = True                                     # someone has to take the snaps
    live = np.concatenate([play, np.ones((sims, 1), dtype=bool)], axis=1)
    alloc = {}
    for kind, total in (("targets", t), ("carries", c)):
        o = P["opp"][kind]
        col, tcol = KINDS[kind]
        mu = O.expected_shares(rows[f"p_{col}_{o['window']}"].to_numpy().astype(float), rows[f"p_{tcol}_{o['window']}"].to_numpy().astype(float),
                               _lookup(o["prior"], pos), o["m"], o["other"])
        mu = np.where(live, mu[None, :], 0.0)                   # a player not taking part in this run gets nothing
        alloc[kind] = O.allocate(rng, total, mu / mu.sum(axis=1, keepdims=True), o["kappa"])
    # Pass attempts: the expected starter takes a share of the team's attempts drawn from what expected starters took
    # in the fit seasons (usually all, sometimes less: injury, benching, blowout). His draw does not depend on whether
    # a backup has a row. Any other quarterback with a row splits what is left; with none, it goes to "other".
    att = np.zeros((sims, k + 1), dtype=np.int64)
    if top is not None:
        pool = np.array(P["qb"][key]) if len(P["qb"][key]) else np.array([1.0])
        att[:, top] = np.rint(a * pool[rng.integers(0, len(pool), sims)]).astype(np.int64)
        rest = [q for q in qbs if q != top]
        left = a - att[:, top]
        if rest:
            att[:, rest] = rng.multinomial(left, np.full(len(rest), 1 / len(rest)))
            play[:, rest] = att[:, rest] > 0                    # a backup quarterback "plays" in the runs where he throws
        else:
            att[:, -1] = left
    else:
        att[:, -1] = a
    e = P["eff"]
    rate = np.append(_lookup(e["catch_rate"], pos), e["catch_rate"]["OTH"])
    rh, th = np.append(_hist(rows, "receptions"), 0.0), np.append(_hist(rows, "targets"), 0.0)
    theta = rng.beta(e["c"]["catch"] * rate + rh, e["c"]["catch"] * (1 - rate) + np.maximum(th - rh, 0), size=(sims, len(posx)))
    rec = rng.binomial(alloc["targets"], theta).astype(np.int64)
    out = {}
    for kind, n, n_col, y_col in (("rec", rec, "receptions", "receiving_yards"), ("rush", alloc["carries"], "carries", "rushing_yards")):
        mu = _lookup(e["mu"][kind], posx)
        f = np.append(E.factor(_hist(rows, y_col), _hist(rows, n_col), mu[:-1], e["c"][kind]), 1.0)
        s = e["shock"][kind]
        out[kind] = _yards(rng, tab[kind], posx, n, f, np.exp(s * rng.standard_normal(sims) - s * s / 2))
    cmp_team, yds_team = rec.sum(axis=1), out["rec"].sum(axis=1)
    w = att / np.maximum(a, 1)[:, None]
    sacks = rng.poisson(P["sack_rate"] * a).astype(np.int64)
    qb_carries = alloc["carries"][:, :-1][:, pos == "QB"].sum(axis=1)
    scr = rng.binomial(qb_carries, P["scramble_share"]).astype(np.int64)
    box = {"targets": alloc["targets"], "rec": rec, "rec_yds": out["rec"], "carries": alloc["carries"], "rush_yds": out["rush"],
           "pass_att": a, "pass_cmp": cmp_team, "pass_yds": yds_team, "sacks": sacks, "scrambles": scr,
           "dropbacks": a + sacks + scr, "team_carries": c}
    full = {"attempts": att[:, :k], "completions": np.rint(w[:, :k] * cmp_team[:, None]).astype(np.int64),
            "passing_yards": np.rint(w[:, :k] * yds_team[:, None]).astype(np.int64), "carries": alloc["carries"][:, :k],
            "rushing_yards": out["rush"][:, :k], "targets": alloc["targets"][:, :k], "receptions": rec[:, :k],
            "receiving_yards": out["rec"][:, :k]}
    # Each player's forecast: the runs in which he plays (a prop on a player who does not play is void), resampled
    # to a fixed number. With fewer than 50 such runs, all runs are used.
    pick = np.empty((k, sims), dtype=np.int64)
    for i in range(k):
        idx = np.flatnonzero(play[:, i])
        pick[i] = rng.choice(idx, sims) if 50 <= len(idx) < sims else np.arange(sims)   # plays in every run: runs kept in order
    samples = {name: np.take_along_axis(v.T, pick, axis=1) for name, v in full.items()}
    return box, samples
