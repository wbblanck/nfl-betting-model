"""Engine A event layer (phase 5): the plays behind each simulated box score, and the markets that need them.

Engine A draws a player's yards on n catches (or carries) as one column of a table of sums of n plays from his
position's pool (model.tables). This layer keeps the plays behind every column, each with its yards and whether it
was a touchdown, so for every run it can list the player's individual plays. Nothing here touches the random draws
of model.simulate: its runs, and so the six Test S markets of A-1.0, are the same with or without this layer.

Per run and player:
- plays: the m = min(n, table depth) pool plays behind his yards, each scaled by his yardage factor and the run's
  shock and rounded; the rounding remainder goes to his longest play, so the plays add up to his yards exactly.
  Plays beyond the table depth (more than 25 catches or 50 carries) carry 0 yards, as model.simulate gives them.
- touchdowns: the pool play's own flag (a long play is more often a touchdown), then thinned or topped up so his
  expected rate is the position's rate times a touchdown factor shrunk toward 1 from his touchdowns this season and
  last: g = (tds + c mu plays) / ((plays + c) mu), c fitted on 2018-2021.
- longest catch or carry: his longest play (0 with no play: how a book grades it is not confirmed here).
- quarterback: each catch is credited to a passer in proportion to the run's pass attempts, which gives passing
  touchdowns and longest completion; interceptions ~ Binomial(attempts, his rate shrunk toward the league's).
- combined: passing + rushing yards and rushing + receiving yards are added per run, never from marginals.
Not built: first touchdown scorer (needs the order of scores), touchdowns on defense and special teams.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from nflbet.engine.replication import efficiency as E

VERSION = "events-0.1"
C_GRID = (2.0, 5.0, 10.0, 20.0, 40.0, 80.0, 160.0, 320.0)


def pools(pbp: pl.DataFrame, players: pl.DataFrame) -> tuple[dict, dict]:
    """(yards pools, touchdown flags) per kind and position, built exactly as scripts/engine_a_tune.pools builds the
    yards (same filter, same order, same fallback), with each play's touchdown flag alongside."""
    posmap = players.select(pl.col("gsis_id"), pl.col("position"))
    reg = pbp.filter((pl.col("season_type") == "REG") & (pl.col("two_point_attempt") == 0))
    yards, flags = {}, {}
    for kind, flag, who, yd, td in (("rec", "complete_pass", "receiver_player_id", "receiving_yards", "pass_touchdown"),
                                    ("rush", "rush_attempt", "rusher_player_id", "rushing_yards", "rush_touchdown")):
        d = (reg.filter((pl.col(flag) == 1) & pl.col(yd).is_not_null())
             .join(posmap, left_on=who, right_on="gsis_id", how="left")
             .with_columns(pl.when(pl.col("position").is_in(["QB", "RB", "WR", "TE"])).then(pl.col("position")).otherwise(pl.lit("OTH")).alias("pos")))
        yards[kind] = {p: d.filter(pl.col("pos") == p)[yd].to_numpy().astype(float) for p in E.POSITIONS}
        flags[kind] = {p: d.filter(pl.col("pos") == p)[td].fill_null(0).to_numpy().astype(bool) for p in E.POSITIONS}
        for p in E.POSITIONS:
            if len(yards[kind][p]) < 200:
                yards[kind][p] = d[yd].to_numpy().astype(float)
                flags[kind][p] = d[td].fill_null(0).to_numpy().astype(bool)
    return yards, flags


def tables(yards: dict, flags: dict, seed: int = 0) -> tuple[dict, dict]:
    """(sum tables, play tables). The sum tables are exactly model.tables(yards, seed): the same random draws in the
    same order. Play tables: kind -> position -> (yards [depth, draws], touchdown [depth, draws]), the plays whose
    running sums the sum table holds."""
    rng = np.random.default_rng(seed)
    sums, plays = {}, {}
    for kind in ("rec", "rush"):
        sums[kind], plays[kind] = {}, {}
        for p, v in yards[kind].items():
            v = np.asarray(v, float)
            idx = rng.integers(0, len(v), size=(E.NMAX[kind], E.TABLE_DRAWS))        # as efficiency.sum_table draws
            y = v[idx]
            sums[kind][p] = np.vstack([np.zeros((1, E.TABLE_DRAWS)), np.cumsum(y, axis=0)])
            plays[kind][p] = (y, np.asarray(flags[kind][p], bool)[idx])
    return sums, plays


def history(feats: pl.DataFrame, outcomes: pl.DataFrame) -> pl.DataFrame:
    """Per feature row: the player's touchdowns, interceptions and plays this season before the game and all of last
    season, from earlier games only (the feature table's own running-sum rule). outcomes: player_id, game_id and
    receiving_tds, rushing_tds, passing_interceptions, receptions, carries, attempts for played rows."""
    from nflbet.engine.features.build import _windows
    cols = ["receiving_tds", "rushing_tds", "passing_interceptions", "receptions", "carries", "attempts"]
    df = (feats.select("player_id", "game_id", "season", "kickoff", "played")
          .join(outcomes.select("player_id", "game_id", *cols), on=["player_id", "game_id"], how="left"))
    w = _windows(df, ["player_id"], cols, "h_")
    keep = [f"h_{c}_{k}" for c in cols for k in ("std", "prev")]
    out = w.select("player_id", "game_id", *keep)
    return out.with_columns(*[(pl.col(f"h_{c}_std") + pl.col(f"h_{c}_prev")).alias(f"h_{c}") for c in cols]).select(
        "player_id", "game_id", *[f"h_{c}" for c in cols])


def factor(hist_events: np.ndarray, hist_plays: np.ndarray, mu: np.ndarray, c: float) -> np.ndarray:
    """Event-rate factor shrunk toward 1: (his events + c mu) / ((his plays + c) mu), clipped to 0.2-5."""
    return np.clip((hist_events + c * mu) / ((hist_plays + c) * mu), 0.2, 5.0)


def fit_strength(hist_events, hist_plays, mu, plays_now, events_now) -> float:
    """c maximizing the Poisson likelihood of this game's events given its plays x mu x factor."""
    best = None
    for c in C_GRID:
        lam = np.maximum(plays_now * mu * factor(hist_events, hist_plays, mu, c), 1e-9)
        ll = float((events_now * np.log(lam) - lam).sum())
        if best is None or ll > best[0]:
            best = (ll, c)
    return best[1]


def fit(df: pl.DataFrame, flags: dict) -> dict:
    """df: fit-season played rows with history() columns and outcomes. Touchdown rate per play by position comes from
    the pools' flags; the shrinkage strengths from the games."""
    pos = np.where(np.isin(df["position"].to_numpy(), ("QB", "RB", "WR", "TE")), df["position"].to_numpy(), "OTH")
    out = {"version": VERSION, "td_rate": {}, "c": {}}
    for kind, n_col, td_col in (("rec", "receptions", "receiving_tds"), ("rush", "carries", "rushing_tds")):
        out["td_rate"][kind] = {p: float(np.mean(v)) for p, v in flags[kind].items()}
        mu = np.array([out["td_rate"][kind][p] for p in pos])
        out["c"][kind] = fit_strength(df[f"h_{td_col}"].to_numpy(), df[f"h_{n_col}"].to_numpy(), mu,
                                      df[n_col].to_numpy(), df[td_col].to_numpy())
    qb = pos == "QB"
    att, ints = df["attempts"].to_numpy()[qb], df["passing_interceptions"].to_numpy()[qb]
    out["int_rate"] = float(ints.sum() / max(att.sum(), 1))
    out["c"]["int"] = fit_strength(df["h_passing_interceptions"].to_numpy()[qb], df["h_attempts"].to_numpy()[qb],
                                   np.full(qb.sum(), out["int_rate"]), att, ints)
    return out


def _plays(kind: str, tr: dict, ptab: dict, g: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """(play yards [sims, players, depth], touchdown [sims, players, depth]) for one kind; plays beyond each player's
    count are 0 yards and no touchdown. g: touchdown factor per player."""
    t = tr[kind]
    n, cols, f, shock, yards = t["n"], t["cols"], t["f"], t["shock"], t["yards"]
    sims, K = n.shape
    depth = E.NMAX[kind]
    py = np.zeros((sims, K, depth))
    pt = np.zeros((sims, K, depth), dtype=bool)
    live = np.arange(depth)[None, :] < np.minimum(n, depth)[:, :, None]
    for k, p in enumerate(tr["pos"]):
        y, td = ptab[kind][p]
        py[:, k, :] = y[:, cols[:, k]].T
        pt[:, k, :] = td[:, cols[:, k]].T
    ev = np.where(live, np.rint(py * f[None, :, None] * shock[:, None, None]), 0.0)
    diff = yards - ev.sum(axis=2)                                   # rounding remainder, to the longest play
    top = np.argmax(np.where(live, ev, -np.inf), axis=2)
    np.put_along_axis(ev, top[:, :, None], np.take_along_axis(ev, top[:, :, None], axis=2) + diff[:, :, None], axis=2)
    ev = np.where(live, ev, 0.0)
    mu = np.array([ptab["_rate"][kind][p] for p in tr["pos"]])
    keep = np.clip(g, 0, 1)[None, :, None]                          # factor below 1: thin the pool's touchdowns
    add = np.clip((g - 1) * mu / np.maximum(1 - mu, 1e-9), 0, 1)[None, :, None]   # above 1: top up on other plays
    u = rng.random(pt.shape)
    pt = live & np.where(pt, u < keep, u < add)
    return ev.astype(np.int64), pt


def simulate(P: dict, EV: dict, sums: dict, ptab: dict, rows: pl.DataFrame, hist: pl.DataFrame, sims: int,
             rng: np.random.Generator, ev_rng: np.random.Generator, index: np.ndarray | None = None, side: int = 0) -> tuple[dict, dict, dict]:
    """model.simulate plus the event layer. rng drives model.simulate exactly as without events; ev_rng drives only
    the touchdown and interception draws. Returns (box, samples, event samples [players, sims] per market) where the
    event samples follow the same runs as the samples (a player's forecast from the runs he plays in)."""
    from nflbet.engine.replication import model as M
    tr: dict = {}
    box, samples = M.simulate(P, sums, rows, sims, rng, index, side, trace=tr)
    h = rows.select("player_id", "game_id").join(hist, on=["player_id", "game_id"], how="left").fill_null(0)
    pos = tr["pos"]
    ptab = {**ptab, "_rate": EV["td_rate"]}
    out = {}
    for kind, n_col, td_col in (("rec", "receptions", "receiving_tds"), ("rush", "carries", "rushing_tds")):
        mu = np.array([EV["td_rate"][kind][p] for p in pos])
        he = np.append(h[f"h_{td_col}"].to_numpy().astype(float), 0.0)
        hp = np.append(h[f"h_{n_col}"].to_numpy().astype(float), 0.0)
        g = factor(he, hp, mu, EV["c"][kind])
        out[kind] = _plays(kind, tr, ptab, g, ev_rng)
    k, att = tr["k"], tr["att"]                                     # att [sims, k + 1]: players, then "other" passers
    rec_y, rec_t = out["rec"]
    rush_y, rush_t = out["rush"]
    # Credit each catch to a passer in proportion to the run's attempts (players' columns, then "other").
    w = att / np.maximum(att.sum(axis=1, keepdims=True), 1)
    cw = np.cumsum(w, axis=1)
    u = ev_rng.random(rec_y.shape)
    passer = (u[..., None] > cw[:, None, None, :]).sum(axis=-1)      # [sims, players + 1, depth] -> passer column
    caught = np.arange(E.NMAX["rec"])[None, None, :] < np.minimum(tr["rec"]["n"], E.NMAX["rec"])[:, :, None]
    pass_td = np.zeros((sims, k), dtype=np.int64)
    long_cmp = np.zeros((sims, k), dtype=np.int64)
    for q in tr["qbs"]:
        mine = caught & (passer == q)
        pass_td[:, q] = (rec_t & mine).sum(axis=(1, 2))
        long_cmp[:, q] = np.where(mine, rec_y, np.iinfo(np.int64).min).max(axis=(1, 2)).clip(min=0) * mine.any(axis=(1, 2))
    hi = h["h_passing_interceptions"].to_numpy().astype(float)
    ha = h["h_attempts"].to_numpy().astype(float)
    rate = EV["int_rate"] * factor(hi, ha, np.full(k, EV["int_rate"]), EV["c"]["int"])
    ints = ev_rng.binomial(att[:, :k], np.clip(rate, 0, 0.5)[None, :]).astype(np.int64)
    rec_n, rush_n = tr["rec"]["n"][:, :k], tr["rush"]["n"][:, :k]
    def longest_play(y, n, kind):
        live = np.arange(E.NMAX[kind])[None, None, :] < np.minimum(n, E.NMAX[kind])[:, :, None]
        return np.where(n > 0, np.where(live, y[:, :k], np.iinfo(np.int64).min).max(axis=2), 0)
    full = {"receiving_tds": rec_t.sum(axis=2)[:, :k], "rushing_tds": rush_t.sum(axis=2)[:, :k],
            "long_rec": longest_play(rec_y, rec_n, "rec"), "long_rush": longest_play(rush_y, rush_n, "rush"),
            "passing_tds": pass_td, "passing_interceptions": ints, "long_cmp": long_cmp}
    full["tds"] = full["receiving_tds"] + full["rushing_tds"]
    pick = tr["pick"]
    ev_samples = {name: np.take_along_axis(v.T, pick, axis=1) for name, v in full.items()}
    ev_samples["pass_rush_yds"] = samples["passing_yards"] + samples["rushing_yards"]
    ev_samples["rush_rec_yds"] = samples["rushing_yards"] + samples["receiving_yards"]
    box_ev = {"rec_plays": rec_y, "rec_td": rec_t, "rush_plays": rush_y, "rush_td": rush_t, "rec_n": tr["rec"]["n"],
              "rush_n": tr["rush"]["n"], "rec_yds": tr["rec"]["yards"], "rush_yds": tr["rush"]["yards"],
              "pass_td": pass_td, "team_rec_td": rec_t.sum(axis=(1, 2)), "long_rec": full["long_rec"], "ints": ints, "att": att[:, :k]}
    return box, samples, {"samples": ev_samples, "box": box_ev, "n_play": tr["n_play"]}


def violations(b: dict) -> dict[str, int]:
    """Event-to-box reconciliation, per run. An empty dict means every box agrees with its events."""
    rules = {
        "play yards != player yards": (b["rec_plays"].sum(axis=2) != b["rec_yds"]).any(axis=1)
                                      | (b["rush_plays"].sum(axis=2) != b["rush_yds"]).any(axis=1),
        "touchdowns > plays": (b["rec_td"].sum(axis=2) > b["rec_n"]).any(axis=1) | (b["rush_td"].sum(axis=2) > b["rush_n"]).any(axis=1),
        "passing tds > receiving tds": (b["pass_td"].sum(axis=1) > b["team_rec_td"]),
        "longest != yards on a single catch": ((b["rec_n"][:, :b["long_rec"].shape[1]] == 1) & (b["long_rec"] != b["rec_yds"][:, :b["long_rec"].shape[1]])).any(axis=1),
        "interceptions > attempts": (b["ints"] > b["att"]).any(axis=1),
        "negative count": (b["ints"] < 0).any(axis=1) | (b["pass_td"] < 0).any(axis=1),
    }
    return {k: int(v.sum()) for k, v in rules.items() if v.any()}
