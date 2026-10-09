"""NFL against-the-spread power rating (docs/ats_declaration.md).

Opponent-adjusted EPA/play, exponentially weighted within a season, regressed toward a prior carried from the previous
season. Every rating is computed from games strictly before the week it is used in (no look-ahead).
"""
from __future__ import annotations

import math

import numpy as np
import polars as pl

KEYS = ["season", "week", "game_id"]


def team_games(seasons: list[int]) -> pl.DataFrame:
    """One row per team-game: offensive EPA/play and defensive EPA/play allowed (regular season, competitive plays)."""
    import nflreadpy as nfl

    p = nfl.load_pbp(seasons=seasons).filter(
        pl.col("season_type") == "REG", pl.col("play_type").is_in(["pass", "run"]), pl.col("epa").is_not_null(),
        pl.col("wp").is_between(0.05, 0.95), pl.col("qb_kneel").fill_null(0) == 0, pl.col("qb_spike").fill_null(0) == 0)
    off = p.group_by(*KEYS, pl.col("posteam").alias("team"), pl.col("defteam").alias("opp")) \
        .agg(pl.col("epa").mean().alias("off_epa"), pl.len().alias("plays"))
    d = off.join(off.select(*KEYS, pl.col("team").alias("opp"), pl.col("off_epa").alias("def_epa")), on=[*KEYS, "opp"])
    return d.sort("season", "week", "game_id", "team")


def ratings(tg: pl.DataFrame, h: float, k: float, r: float) -> pl.DataFrame:
    """Pre-game offense / defense ratings (relative to league average, EPA/play) for every team-game in `tg`.
    The first season in `tg` starts from a zero prior and serves only as history for the next."""
    out = []
    prior = {}
    for season in sorted(tg["season"].unique().to_list()):
        s = tg.filter(pl.col("season") == season)
        hist: dict[str, list[tuple[float, float]]] = {}
        lg_vals: list[float] = []
        lg_prev = float(tg.filter(pl.col("season") == season - 1)["off_epa"].mean()) if season - 1 in tg["season"] else float(s["off_epa"].mean())

        def rating(team: str) -> tuple[float, float]:
            po, pd = prior.get(team, (0.0, 0.0))
            xs = hist.get(team, [])
            n = len(xs)
            ws = [0.5 ** ((n - 1 - i) / h) if math.isfinite(h) else 1.0 for i in range(n)]
            so = sum(w * x[0] for w, x in zip(ws, xs)) + k * po
            sd = sum(w * x[1] for w, x in zip(ws, xs)) + k * pd
            return so / (sum(ws) + k), sd / (sum(ws) + k)

        for week in sorted(s["week"].unique().to_list()):
            g = s.filter(pl.col("week") == week)
            lg = float(np.mean(lg_vals)) if lg_vals else lg_prev
            pre = {t: rating(t) for t in set(g["team"].to_list()) | set(g["opp"].to_list())}
            for row in g.iter_rows(named=True):
                o, d = pre[row["team"]]
                out.append({"season": season, "week": week, "game_id": row["game_id"], "team": row["team"],
                            "off": o, "def": d, "net": o - d})
            for row in g.iter_rows(named=True):     # update after the week: adjusted for the opponent's pre-game rating
                oo, od = pre[row["opp"]]
                hist.setdefault(row["team"], []).append((row["off_epa"] - lg - od, row["def_epa"] - lg - oo))
            lg_vals += g["off_epa"].to_list()
        prior = {t: tuple(r * v for v in rating(t)) for t in hist}
    return pl.DataFrame(out)


def games(seasons: list[int]) -> pl.DataFrame:
    """Regular-season games with the closing spread (home favored > 0), prices, margin and neutral-site flag."""
    import nflreadpy as nfl

    s = nfl.load_schedules(seasons=seasons).filter(pl.col("game_type") == "REG", pl.col("result").is_not_null())
    return s.select("season", "week", "game_id", "home_team", "away_team", "result", "spread_line", "home_spread_odds",
                    "away_spread_odds", (pl.col("location") == "Neutral").alias("neutral"), "roof", "temp", "wind")


def with_ratings(g: pl.DataFrame, rt: pl.DataFrame) -> pl.DataFrame:
    h = rt.select("game_id", pl.col("team").alias("home_team"), pl.col("net").alias("net_home"))
    a = rt.select("game_id", pl.col("team").alias("away_team"), pl.col("net").alias("net_away"))
    return g.join(h, on=["game_id", "home_team"]).join(a, on=["game_id", "away_team"]) \
        .with_columns((pl.col("net_home") - pl.col("net_away")).alias("diff"))


def fit_line(x: pl.DataFrame) -> tuple[float, float]:
    """Least squares: margin = HFA * (not neutral) + c * diff. Returns (c, hfa)."""
    X = np.c_[x["diff"].to_numpy(), (~x["neutral"]).cast(pl.Float64).to_numpy()]
    c, hfa = np.linalg.lstsq(X, x["result"].to_numpy().astype(float), rcond=None)[0]
    return float(c), float(hfa)


def fair(x: pl.DataFrame, c: float, hfa: float) -> pl.DataFrame:
    return x.with_columns((c * pl.col("diff") + hfa * (~pl.col("neutral")).cast(pl.Float64)).alias("fair"))
