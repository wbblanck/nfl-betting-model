"""Pass-rush pressure as a QB-prop input (docs/pressure_preregistration.md).

Two pre-game factors per team-game, both from strictly earlier games:
- D (opponent defense): pressures its opponents' passers suffered against it, per dropback faced.
- Q (own offense): pressures this team's passers suffered, per dropback.
Each is a weighted rate (exponential weights, half-life HALF_LIFE games, any season) over the league rate of the
previous season, shrunk toward 1 by SHRINK games and clipped to [0.5, 2], the same recipe as the projection's
opponent factor. Adjusted projection = proj x D^c x Q^d, with (c, d) fitted per market on training seasons.

Pressures: PFR `times_pressured` in nflverse `pfr_advstats` (weekly, passing), summed over a team's passers.
Dropbacks: nflverse player stats `attempts + sacks_suffered`, summed over the team's players.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from nflbet.props.player_proj import HALF_LIFE, SHRINK

TEAM_FIX = {"OAK": "LV"}                       # PFR files label the 2018-2019 Raiders OAK; player stats use LV
GRID = np.round(np.arange(-1.5, 1.51, 0.25), 2)
EXTRA_STAT = {"sacks": pl.col("sacks_suffered")}


def team_games(pfr: pl.DataFrame, st: pl.DataFrame) -> pl.DataFrame:
    """One row per regular-season team-game: team, opponent, season, week, t, pressures, dropbacks.
    `pfr`: pfr_advstats weekly passing rows; `st`: raw player stats rows (team, opponent_team, season, week,
    attempts, sacks_suffered). A team-game with no PFR passing row gets null pressures AND null dropbacks, so it
    drops out of both sides of the rate."""
    p = (pfr.filter(pl.col("game_type") == "REG")
         .with_columns(pl.col("team").replace(TEAM_FIX))
         .group_by("season", "week", "team").agg(pl.col("times_pressured").sum().alias("pressures"),
                                                  pl.col("times_pressured").is_null().all().alias("p_missing")))
    # one row per team-game even when a stray player row lacks the opponent (2018 week 7 ARI has one)
    d = (st.group_by("season", "week", "team")
         .agg(pl.col("opponent_team").drop_nulls().first(),
              (pl.col("attempts").fill_null(0) + pl.col("sacks_suffered").fill_null(0)).sum().cast(pl.Float64)
              .alias("dropbacks")))
    g = d.join(p, on=["season", "week", "team"], how="left").with_columns(
        pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64))
    ok = pl.col("pressures").is_not_null() & ~pl.col("p_missing").fill_null(True)
    return (g.with_columns(pl.when(ok).then(pl.col("pressures").cast(pl.Float64)).alias("pressures"),
                           pl.when(ok).then(pl.col("dropbacks")).alias("dropbacks"),
                           (pl.col("season") * 100 + pl.col("week")).alias("t"))
            .rename({"opponent_team": "opponent"})
            .select("team", "opponent", "season", "week", "t", "pressures", "dropbacks").sort("t"))


def league_rates(tg: pl.DataFrame) -> dict[int, float]:
    """Pooled pressures / dropbacks per season. A season's factors use the PREVIOUS season's rate; the first season
    in the frame (burn-in only) uses its own."""
    r = tg.drop_nulls(["pressures", "dropbacks"]).group_by("season").agg(
        (pl.col("pressures").sum() / pl.col("dropbacks").sum()).alias("r")).sort("season")
    rates = dict(zip(r["season"].to_list(), r["r"].to_list()))
    first = min(rates)
    return {s: rates.get(s - 1, rates[first]) if s != first else rates[first] for s in rates}


def _prior_rate(by: str, p: str, db: str) -> list[pl.Expr]:
    w = lambda c: pl.col(c).shift(1).ewm_mean(half_life=HALF_LIFE, ignore_nulls=True).over(by)  # noqa: E731
    n = pl.col(db).is_not_null().cast(pl.Int64).cum_sum().shift(1).fill_null(0).over(by)
    return [(w(p) / w(db)).alias("rate"), n.alias("n")]


def _factor(rate: str, n: str, lg: str) -> pl.Expr:
    raw = (pl.col(rate) / pl.col(lg)).fill_null(1.0).fill_nan(1.0)
    return ((pl.col(n) * raw + SHRINK) / (pl.col(n) + SHRINK)).clip(0.5, 2.0)


def factors(tg: pl.DataFrame) -> pl.DataFrame:
    """Per team-game (team, season, week): Q = own offense pressure-allowed factor, D = opponent defense
    pressure factor, both from strictly earlier games."""
    lg = league_rates(tg)
    off = (tg.sort("t").with_columns(*_prior_rate("team", "pressures", "dropbacks"))
           .with_columns(pl.col("season").replace_strict(lg, default=None, return_dtype=pl.Float64).alias("lg"))
           .with_columns(_factor("rate", "n", "lg").alias("Q"))
           .select("team", "opponent", "season", "week", "t", "Q", pl.col("n").alias("n_q")))
    # defense view: the row's opponent is the defense; it generated `pressures` on `dropbacks`
    dfn = (tg.sort("t").select(pl.col("opponent").alias("defense"), "season", "week", "t", "pressures", "dropbacks")
           .with_columns(*_prior_rate("defense", "pressures", "dropbacks"))
           .with_columns(pl.col("season").replace_strict(lg, default=None, return_dtype=pl.Float64).alias("lg"))
           .with_columns(_factor("rate", "n", "lg").alias("D"))
           .select("defense", "season", "week", "D", pl.col("n").alias("n_d")))
    return off.join(dfn, left_on=["opponent", "season", "week"], right_on=["defense", "season", "week"], how="left") \
        .with_columns(pl.col("D").fill_null(1.0), pl.col("n_d").fill_null(0))


def attach(rows: pl.DataFrame, fac: pl.DataFrame) -> pl.DataFrame:
    """Add D and Q to projection rows keyed by (team, season, week). Missing -> 1 (no adjustment)."""
    return rows.join(fac.select("team", "season", "week", "opponent", "D", "Q", "n_d", "n_q"),
                     on=["team", "season", "week"], how="left") \
        .with_columns(pl.col("D").fill_null(1.0), pl.col("Q").fill_null(1.0))


def adjusted(cd: dict) -> pl.Expr:
    """proj x D^c x Q^d with (c, d) per market from `cd` {market: (c, d)}."""
    c = pl.col("market").replace_strict({m: v[0] for m, v in cd.items()}, default=0.0, return_dtype=pl.Float64)
    d = pl.col("market").replace_strict({m: v[1] for m, v in cd.items()}, default=0.0, return_dtype=pl.Float64)
    return pl.col("proj") * pl.col("D").pow(c) * pl.col("Q").pow(d)


def fit_cd(train: pl.DataFrame) -> dict:
    """(c, d) per market from GRID x GRID minimizing squared error on `train` (market, proj, D, Q, actual).
    Ties go to the smaller |c| + |d|, then the smaller c, d."""
    out = {}
    for m in train["market"].unique().sort().to_list():
        z = train.filter(pl.col("market") == m)
        p, D, Q, y = (z[k].to_numpy().astype(float) for k in ("proj", "D", "Q", "actual"))
        lD, lQ = np.log(D), np.log(Q)
        best = min((float(np.mean((p * np.exp(c * lD + d * lQ) - y) ** 2)), abs(c) + abs(d), c, d)
                   for c in GRID for d in GRID)
        out[m] = (float(best[2]), float(best[3]))
    return out


def cluster_boot(diff: np.ndarray, cl: np.ndarray, n: int = 4000, seed: int = 7) -> np.ndarray:
    """Means of `diff` over n resamples of whole clusters."""
    ids, inv = np.unique(cl, return_inverse=True)
    sums, cnt = np.bincount(inv, diff), np.bincount(inv)
    rng = np.random.default_rng(seed)
    k = rng.integers(0, len(ids), (n, len(ids)))
    return sums[k].sum(1) / cnt[k].sum(1)


def boot_p(bs: np.ndarray) -> float:
    """Two-sided percentile-bootstrap p-value for mean 0: 2 x the smaller tail share, at least 1 / len(bs)."""
    return float(min(1.0, max(2 * min(np.mean(bs >= 0), np.mean(bs <= 0)), 1 / len(bs))))


def holm(p: dict, alpha: float = 0.05) -> dict:
    """Holm step-down: reject the k-th smallest p while p_(k) <= alpha / (m - k + 1); stop at the first failure."""
    order, m, rej, going = sorted(p, key=p.get), len(p), {}, True
    for k, key in enumerate(order):
        going = going and p[key] <= alpha / (m - k)
        rej[key] = going
    return rej
