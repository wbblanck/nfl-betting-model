"""Four pre-game signals for the prop projection (docs/five_signals_preregistration.md, A-D).

Each builder takes raw nflverse tables as arguments (so tests can feed hand cases) and returns x keyed by team or
player and (season, week), using only games before the one it is attached to.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import polars as pl

GRIDS = {"qb": np.round(np.arange(-0.5, 0.501, 0.05), 3), "snap": np.round(np.arange(-2.0, 2.001, 0.25), 3),
         "ngs": np.round(np.arange(-0.5, 0.501, 0.05), 3), "wind": np.round(np.arange(-0.05, 0.0501, 0.005), 4)}


def _team_rows(sched: pl.DataFrame) -> pl.DataFrame:
    g = sched.filter(pl.col("game_type") == "REG")
    return pl.concat([
        g.select("season", "week", "gameday", pl.col("home_team").alias("team"), pl.col("home_qb_id").alias("qb"),
                 "roof", "wind"),
        g.select("season", "week", "gameday", pl.col("away_team").alias("team"), pl.col("away_qb_id").alias("qb"),
                 "roof", "wind")]).sort("team", "season", "week")


def qb_change(sched: pl.DataFrame) -> pl.DataFrame:
    """(team, season, week, qb, x): x = 1 if this game's starter differs from the most common starter of the team's
    previous 3 games this season (ties: the most recent of the tied); 0 with no earlier game."""
    rows = []
    for (team, season), grp in _team_rows(sched).group_by(["team", "season"], maintain_order=True):
        prev: list[str] = []
        for r in grp.sort("week").iter_rows(named=True):
            x = 0
            if prev:
                last3 = prev[-3:]
                c = Counter(last3)
                top = max(c.values())
                est = [q for q in reversed(last3) if c[q] == top][0]
                x = int(r["qb"] != est)
            rows.append({"team": team, "season": season, "week": r["week"], "qb": r["qb"], "x": x})
            prev.append(r["qb"])
    return pl.DataFrame(rows)


def wind(sched: pl.DataFrame) -> pl.DataFrame:
    """(team, season, week, x): max(wind - 10, 0) outdoors / open roof, else 0 (missing wind = 0)."""
    t = _team_rows(sched)
    return t.select("team", "season", "week", pl.when(pl.col("roof").is_in(["outdoors", "open"]))
                    .then((pl.col("wind").cast(pl.Float64).fill_null(0.0) - 10).clip(lower_bound=0)).otherwise(0.0).alias("x"))


def snap_trend(snaps: pl.DataFrame) -> pl.DataFrame:
    """snaps: player_id, season, week, offense_pct (one row per game played). x for each later game the player
    appears in = share in his previous row minus mean of the (up to) 4 rows before that; needs 3 of those 4.
    Returned for the row's own (season, week), built only from earlier rows."""
    s = snaps.with_columns((pl.col("season") * 100 + pl.col("week")).alias("t")).sort("player_id", "t")
    last = pl.col("offense_pct").shift(1).over("player_id")
    before = pl.col("offense_pct").shift(2).rolling_mean(4, min_samples=3).over("player_id")
    return s.with_columns((last - before).alias("x")).select("player_id", "season", "week", "x")


def ngs_prior(ngs: pl.DataFrame, col: str) -> pl.DataFrame:
    """ngs: player_id, season, week (> 0; week 0 rows are season totals and dropped), col. State after each NGS row:
    m = mean of the player's last up to 8 rows including it. `attach_ngs` takes the state strictly before a game."""
    n = ngs.filter(pl.col("week") > 0).with_columns((pl.col("season") * 100 + pl.col("week")).alias("t")) \
        .sort("player_id", "t").with_columns(pl.col(col).cast(pl.Float64))
    n = n.with_columns(pl.col(col).rolling_mean(8, min_samples=1).over("player_id").alias("m"))
    return n.select("player_id", "season", "t", "m")


def attach_ngs(rows: pl.DataFrame, state: pl.DataFrame, ngs: pl.DataFrame, col: str, center: bool) -> pl.DataFrame:
    """rows: player_id, season, week. Adds x = player's last `m` strictly before the row (asof join), centered."""
    r = rows.with_columns((pl.col("season") * 100 + pl.col("week")).alias("t")).sort("t")
    st = state.rename({"t": "ts"}).drop("season").sort("ts")
    j = r.join_asof(st, left_on="t", right_on="ts", by="player_id", strategy="backward", allow_exact_matches=False)
    if center:
        n = ngs.filter(pl.col("week") > 0).with_columns(pl.col(col).cast(pl.Float64))
        lg = []
        for (season, week) in r.select("season", "week").unique().iter_rows():
            v = n.filter(pl.col("season") == season, pl.col("week") < week)[col].mean()
            lg.append({"season": season, "week": week, "lg": v})
        j = j.join(pl.DataFrame(lg, schema={"season": r.schema["season"], "week": r.schema["week"], "lg": pl.Float64}),
                   on=["season", "week"], how="left").with_columns((pl.col("m") - pl.col("lg")).alias("m"))
    return j.with_columns(pl.col("m").alias("x")).drop("m", "ts", "t", *(["lg"] if center else []))


def fit_k(train: pl.DataFrame, grid) -> dict:
    """k per market minimizing mean squared error of proj x exp(k x) on train (proj, x, actual, market)."""
    out = {}
    for m in train["market"].unique().sort().to_list():
        z = train.filter(pl.col("market") == m)
        p, x, y = z["proj"].to_numpy(), z["x"].to_numpy(), z["actual"].to_numpy()
        out[m] = float(min(grid, key=lambda k: (float(np.mean((p * np.exp(k * x) - y) ** 2)), abs(k))))
    return out
