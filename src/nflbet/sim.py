"""Monte Carlo simulator of a player's game (docs/simulator_declaration.md). Pre-game inputs only.

Per player-game, N_SIMS draws of:
  team volume   team pass attempts and carries ~ Normal(mean, sd); mean from the closing spread and total
                (OLS fitted on the fit season), sd = that fit's residual sd
  opportunities targets ~ Binomial(team pass att, target share); carries ~ Binomial(team carries, carry share);
                a QB's attempts ~ Binomial(team pass att, his share). Shares vary per draw (Beta, concentration
                SHARE_CONC) to carry role uncertainty.
  results       receptions ~ Binomial(targets, catch rate); completions ~ Binomial(attempts, completion rate);
                yards = sum of per-play yards drawn from the fit seasons' play-by-play for the position group,
                scaled by the player's own yards per play over the group mean.
Player rates use his last ROLL games before this one (any season), shrunk toward the position mean with SHRINK
pseudo-opportunities. A player needs MIN_GAMES earlier games.
"""
from __future__ import annotations

import numpy as np
import polars as pl

N_SIMS = 4000
ROLL = 8
MIN_GAMES = 3
SHRINK = {"catch": 20.0, "ypr": 15.0, "ypc": 40.0, "cmp": 60.0, "ypcmp": 60.0}
SHARE_CONC = 30.0
POS = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE"}
MAX_DRAWS = 45          # cap on per-play draws per simulation (covers 45 carries / completions)


# ----------------------------------------------------------------------------------------------- data

def player_games(seasons: list[int]) -> pl.DataFrame:
    import nflreadpy as nfl

    s = nfl.load_player_stats(seasons=seasons).filter(pl.col("season_type") == "REG")
    s = s.with_columns(pl.col("position").replace_strict(POS, default=None).alias("pos")).filter(pl.col("pos").is_not_null())
    cols = ["targets", "receptions", "receiving_yards", "carries", "rushing_yards", "attempts", "completions",
            "passing_yards"]
    s = s.select("player_id", "season", "week", "team", pl.col("opponent_team").alias("opp"), "pos",
                 *[pl.col(c).fill_null(0).cast(pl.Float64) for c in cols])
    team = s.group_by("season", "week", "team").agg(pl.col("attempts").sum().alias("team_att"),
                                                     pl.col("carries").sum().alias("team_car"),
                                                     pl.col("targets").sum().alias("team_tgt"))
    return s.join(team, on=["season", "week", "team"]).with_columns(
        (pl.col("season") * 100 + pl.col("week")).alias("t")).sort("t")


def schedule_features(seasons: list[int]) -> pl.DataFrame:
    import nflreadpy as nfl

    g = nfl.load_schedules(seasons=seasons).filter(pl.col("game_type") == "REG", pl.col("spread_line").is_not_null(),
                                                   pl.col("total_line").is_not_null())
    # nflverse spread_line > 0: home favored. team_spread < 0: this team favored
    return pl.concat([
        g.select("season", "week", pl.col("home_team").alias("team"),
                 ((pl.col("total_line") + pl.col("spread_line")) / 2).alias("implied"),
                 (-pl.col("spread_line")).alias("team_spread")),
        g.select("season", "week", pl.col("away_team").alias("team"),
                 ((pl.col("total_line") - pl.col("spread_line")) / 2).alias("implied"),
                 pl.col("spread_line").alias("team_spread"))])


def play_yards(seasons: list[int], pos_of: dict) -> dict:
    """Empirical per-play yards: receptions by receiver group, carries by rusher group, completions (all QBs)."""
    import nflreadpy as nfl

    p = nfl.load_pbp(seasons=seasons).filter(pl.col("season_type") == "REG", pl.col("two_point_attempt") == 0)
    rec = p.filter(pl.col("complete_pass") == 1, pl.col("receiver_player_id").is_not_null()) \
        .select(pl.col("receiver_player_id").alias("pid"), pl.col("receiving_yards").fill_null(0))
    rush = p.filter(pl.col("rush_attempt") == 1, pl.col("rusher_player_id").is_not_null()) \
        .select(pl.col("rusher_player_id").alias("pid"), pl.col("rushing_yards").fill_null(0))
    out = {"cmp": p.filter(pl.col("complete_pass") == 1)["passing_yards"].fill_null(0).to_numpy().astype(float)}
    for name, d, col in (("rec", rec, "receiving_yards"), ("rush", rush, "rushing_yards")):
        d = d.with_columns(pl.col("pid").replace_strict(pos_of, default=None).alias("pos")).filter(pl.col("pos").is_not_null())
        for pos, grp in d.group_by("pos"):
            out[(name, pos[0])] = grp[col].to_numpy().astype(float)
    return out


# --------------------------------------------------------------------------------------------- fitting

def fit_volume(pg: pl.DataFrame, sched: pl.DataFrame, season: int) -> dict:
    tg = pg.select("season", "week", "team", "team_att", "team_car").unique() \
        .join(sched, on=["season", "week", "team"]).filter(pl.col("season") == season)
    X = np.column_stack([np.ones(tg.height), tg["implied"], tg["team_spread"]])
    out = {}
    for col in ("team_att", "team_car"):
        y = tg[col].to_numpy()
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        out[col] = {"coef": b.tolist(), "sd": float(np.std(y - X @ b, ddof=3))}
    return out


def position_means(pg: pl.DataFrame) -> pl.DataFrame:
    """Per-position rates used for shrinkage; computed on the fit season only (passed to `rates`)."""
    return pg.group_by("pos").agg((pl.col("receptions").sum() / pl.col("targets").sum()).alias("m_catch"),
                                  (pl.col("receiving_yards").sum() / pl.col("receptions").sum()).alias("m_ypr"),
                                  (pl.col("rushing_yards").sum() / pl.col("carries").sum()).alias("m_ypc"),
                                  (pl.col("completions").sum() / pl.col("attempts").sum()).alias("m_cmp"),
                                  (pl.col("passing_yards").sum() / pl.col("completions").sum()).alias("m_ypcmp"))


def rates(pg: pl.DataFrame, pos_mean: pl.DataFrame) -> pl.DataFrame:
    """Each player's rates from his ROLL earlier games (shifted: the current game never enters), shrunk toward
    `pos_mean` (from the fit season, so no target-season game leaks in through the shrinkage target)."""
    def prior(c):
        return pl.col(c).shift(1).rolling_sum(ROLL, min_samples=1).over("player_id")
    r = pg.with_columns(*[prior(c).alias(f"p_{c}") for c in ("targets", "receptions", "receiving_yards", "carries",
                                                             "rushing_yards", "attempts", "completions",
                                                             "passing_yards", "team_att", "team_car", "team_tgt")],
                        (pl.col("t").cum_count().over("player_id") - 1).alias("n_prior"))
    r = r.join(pos_mean, on="pos", how="left")

    def shrunk(num, den, mean, k):
        return (pl.col(num).fill_null(0) + k * pl.col(mean).fill_nan(0).fill_null(0)) / (pl.col(den).fill_null(0) + k)
    return r.with_columns(
        (pl.col("p_targets") / pl.col("p_team_att").clip(lower_bound=1)).alias("tgt_share"),
        (pl.col("p_carries") / pl.col("p_team_car").clip(lower_bound=1)).alias("car_share"),
        (pl.col("p_attempts") / pl.col("p_team_att").clip(lower_bound=1)).alias("att_share"),
        shrunk("p_receptions", "p_targets", "m_catch", SHRINK["catch"]).alias("catch"),
        shrunk("p_receiving_yards", "p_receptions", "m_ypr", SHRINK["ypr"]).alias("ypr"),
        shrunk("p_rushing_yards", "p_carries", "m_ypc", SHRINK["ypc"]).alias("ypc"),
        shrunk("p_completions", "p_attempts", "m_cmp", SHRINK["cmp"]).alias("cmp"),
        shrunk("p_passing_yards", "p_completions", "m_ypcmp", SHRINK["ypcmp"]).alias("ypcmp"),
    ).filter(pl.col("n_prior") >= MIN_GAMES)


# ------------------------------------------------------------------------------------------- matchup

DEF_ROLL = 16           # the defense's last 16 games
DEF_SHRINK = {"catch": 80.0, "ypr": 60.0, "ypc": 150.0, "cmp": 150.0, "ypcmp": 100.0, "tshare": 200.0,
              "cshare": 200.0}


def defense_factors(pg: pl.DataFrame, pos_mean: pl.DataFrame, fit: pl.DataFrame) -> pl.DataFrame:
    """Per (defense, position group, game): what the defense allowed to that position in its EARLIER games,
    relative to the fit season's league average, shrunk toward 1. 1.0 = average defense."""
    cols = ["targets", "receptions", "receiving_yards", "carries", "rushing_yards", "attempts", "completions",
            "passing_yards"]
    by_pos = pg.group_by("opp", "pos", "t").agg(*[pl.col(c).sum() for c in cols])
    tot = pg.group_by("opp", "t").agg(pl.col("targets").sum().alias("all_tgt"), pl.col("carries").sum().alias("all_car"))
    d = by_pos.join(tot, on=["opp", "t"]).sort("t")

    def prior(c):
        return pl.col(c).shift(1).rolling_sum(DEF_ROLL, min_samples=1).over(["opp", "pos"])
    d = d.with_columns(*[prior(c).fill_null(0).alias(f"a_{c}") for c in cols + ["all_tgt", "all_car"]])
    lg = fit.group_by("pos").agg((pl.col("targets").sum() / fit["targets"].sum()).alias("lg_tshare"),
                                 (pl.col("carries").sum() / fit["carries"].sum()).alias("lg_cshare"))
    d = d.join(pos_mean, on="pos", how="left").join(lg, on="pos", how="left")

    def ratio(num, den, mean, k):
        m = pl.col(mean).fill_nan(0).fill_null(0)
        return ((pl.col(num) + k * m) / (pl.col(den) + k) / m).fill_nan(1.0).fill_null(1.0)
    return d.select("opp", "pos", "t",
                    ratio("a_receptions", "a_targets", "m_catch", DEF_SHRINK["catch"]).alias("d_catch"),
                    ratio("a_receiving_yards", "a_receptions", "m_ypr", DEF_SHRINK["ypr"]).alias("d_ypr"),
                    ratio("a_rushing_yards", "a_carries", "m_ypc", DEF_SHRINK["ypc"]).alias("d_ypc"),
                    ratio("a_completions", "a_attempts", "m_cmp", DEF_SHRINK["cmp"]).alias("d_cmp"),
                    ratio("a_passing_yards", "a_completions", "m_ypcmp", DEF_SHRINK["ypcmp"]).alias("d_ypcmp"),
                    ratio("a_targets", "a_all_tgt", "lg_tshare", DEF_SHRINK["tshare"]).alias("d_tshare"),
                    ratio("a_carries", "a_all_car", "lg_cshare", DEF_SHRINK["cshare"]).alias("d_cshare"))


# ------------------------------------------------------------------------------------------ simulation

def _beta_share(rng, m, n):
    if not m or m <= 0:
        return np.zeros(n)
    m = float(np.clip(m, 1e-4, 0.999))
    return rng.beta(m * SHARE_CONC, (1 - m) * SHARE_CONC, n)


def _sum_draws(rng, counts: np.ndarray, pool: np.ndarray, scale: float) -> np.ndarray:
    k = int(min(max(counts.max(), 1), MAX_DRAWS))
    draws = rng.choice(pool, size=(len(counts), k)) * scale
    mask = np.arange(k)[None, :] < np.minimum(counts, MAX_DRAWS)[:, None]
    return (draws * mask).sum(axis=1)


def simulate_row(r: dict, vol: dict, pools: dict, rng: np.random.Generator, n: int = N_SIMS, w: float = 0.0) -> dict:
    """Simulated stats for one player-game row (a dict from `inputs`). w = matchup weight: each opponent factor
    enters as factor**w (0 = ignore the matchup)."""
    if w:
        f = lambda k: float(r.get(k) or 1.0) ** w  # noqa: E731
        r = dict(r, tgt_share=(r["tgt_share"] or 0) * f("d_tshare"), car_share=(r["car_share"] or 0) * f("d_cshare"),
                 catch=r["catch"] * f("d_catch"), ypr=r["ypr"] * f("d_ypr"), ypc=r["ypc"] * f("d_ypc"),
                 cmp=r["cmp"] * f("d_cmp"), ypcmp=r["ypcmp"] * f("d_ypcmp"))
    def team(col):
        c = vol[col]["coef"]
        mu = c[0] + c[1] * r["implied"] + c[2] * r["team_spread"]
        return np.clip(np.round(rng.normal(mu, vol[col]["sd"], n)), 5, None).astype(int)

    att, car = team("team_att"), team("team_car")
    out = {}
    pos = r["pos"]
    tg = rng.binomial(att, _beta_share(rng, r["tgt_share"] or 0, n))
    rec = rng.binomial(tg, float(np.clip(r["catch"], 0.05, 0.99)))
    pool_r = pools.get(("rec", pos))
    out["rec"] = rec.astype(float)
    out["rec_yds"] = _sum_draws(rng, rec, pool_r, r["ypr"] / max(np.mean(pool_r), 1e-6)) if pool_r is not None else rec * r["ypr"]
    cr = rng.binomial(car, _beta_share(rng, r["car_share"] or 0, n))
    pool_c = pools.get(("rush", pos))
    out["rush_att"] = cr.astype(float)
    out["rush_yds"] = _sum_draws(rng, cr, pool_c, r["ypc"] / max(np.mean(pool_c), 1e-6)) if pool_c is not None else cr * r["ypc"]
    if pos == "QB":
        pa = rng.binomial(att, _beta_share(rng, r["att_share"] or 0, n))
        cm = rng.binomial(pa, float(np.clip(r["cmp"], 0.3, 0.85)))
        out["pass_att"], out["pass_cmp"] = pa.astype(float), cm.astype(float)
        out["pass_yds"] = _sum_draws(rng, cm, pools["cmp"], r["ypcmp"] / max(np.mean(pools["cmp"]), 1e-6))
        out["pass_rush_yds"] = out["pass_yds"] + out["rush_yds"]
    out["rush_rec_yds"] = out["rush_yds"] + out["rec_yds"]
    return out


def inputs(pg: pl.DataFrame, sched: pl.DataFrame, season: int, pos_mean: pl.DataFrame,
           dfac: pl.DataFrame | None = None) -> pl.DataFrame:
    x = rates(pg, pos_mean).filter(pl.col("season") == season).join(sched, on=["season", "week", "team"], how="inner")
    return x if dfac is None else x.join(dfac, on=["opp", "pos", "t"], how="left")


class Simulator:
    """Fit on one season; simulate any later season's player-games."""

    def __init__(self, fit_season: int, seasons: list[int], matchup_weight: float = 0.0):
        self.pg = player_games(seasons)
        self.sched = schedule_features(seasons)
        self.vol = fit_volume(self.pg, self.sched, fit_season)
        self.pos_mean = position_means(self.pg.filter(pl.col("season") == fit_season))
        self.w = matchup_weight
        self.dfac = defense_factors(self.pg, self.pos_mean, self.pg.filter(pl.col("season") == fit_season))
        pos_of = dict(zip(self.pg["player_id"].to_list(), self.pg["pos"].to_list()))
        self.pools = play_yards([s for s in seasons if s <= fit_season], pos_of)

    def run(self, season: int, keep: set | None = None, seed: int = 11) -> dict:
        """{(player_id, week): {market: samples}} for the season's player-games (optionally only `keep`)."""
        rng = np.random.default_rng(seed)
        out = {}
        for r in inputs(self.pg, self.sched, season, self.pos_mean, self.dfac).iter_rows(named=True):
            if keep is not None and (r["player_id"], r["week"]) not in keep:
                continue
            out[(r["player_id"], r["week"])] = simulate_row(r, self.vol, self.pools, rng, w=self.w)
        return out
