"""Engine B (challenger), MODEL_SPECIFICATION section 3: direct conditional distributions per player-market.

Each forecast is conditional on the player taking a snap (a prop on a player who does not play is void), and is made
from the feature table: earlier games plus the game-day active list. Models are fitted on played, eligible rows
(engine.baselines.eligible) of the fit seasons; tail scales of the yardage distributions on the tune seasons.

Markets and routes:
  pass_att, rush_att      negative binomial regression (counts.fit_nb)
  rec                     simulated targets (negative binomial) then beta-binomial catches
  pass_yds, rush_yds,     gradient-boosted quantiles with the count model's mean as a feature, rearranged, with
  rec_yds                 fitted tails (yardage)
The dependence layer (Gaussian copula and box reconciliation, spec 3.4) is not in this version: each market's
runs are drawn on their own, which leaves every marginal forecast unchanged and is all Test S scores.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from nflbet.engine import baselines as BL
from nflbet.engine.challenger import counts as C, design as D, yardage as Y

VERSION = "B-0.1"
VOLUME = {"pass_att": "attempts", "rush_att": "carries", "rec": "targets",
          "pass_yds": "attempts", "rush_yds": "carries", "rec_yds": "targets"}
ELIG = {"attempts": "pass_att", "carries": "rush_att", "targets": "rec"}      # which market's sample fits a volume model
# Family per market, chosen on the tune seasons (spec 3.5): "nb" or "hurdle" for counts (rec follows targets),
# "quantile" or "quantile+zero" for yardage. Chosen by scripts/engine_b_tune.py (docs/engine/engine_b_tune.md).
FAMILY = {"pass_att": "hurdle", "rush_att": "hurdle", "rec": "hurdle", "pass_yds": "quantile", "rush_yds": "quantile+zero",
          "rec_yds": "quantile+zero"}
OUTCOME = {"attempts": "attempts", "carries": "carries", "targets": "targets"}


def _mask(df: pl.DataFrame, market: str) -> np.ndarray:
    return BL.eligible(df, market).to_numpy() & df["played"].to_numpy()


def _hist_catch(df: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    rec = df["p_receptions_w8"].to_numpy() + df["p_receptions_prev"].to_numpy()
    tgt = df["p_targets_w8"].to_numpy() + df["p_targets_prev"].to_numpy()
    return rec.astype(float), tgt.astype(float)


def _count_inputs(P: dict, df: pl.DataFrame, vol: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X, _ = D.matrix(df, vol)
    return P["scaler"][vol](X), df["position"].to_numpy(), D.instability(df, vol)


def _yard_inputs(P: dict, df: pl.DataFrame, vol: str) -> np.ndarray:
    Xs, pos, inst = _count_inputs(P, df, vol)
    mu, _ = C.nb_params(P["count"][vol], Xs, pos, inst)
    return np.column_stack([Xs, np.log1p(mu)])


def fit(df: pl.DataFrame, seed: int = 0) -> dict:
    """df: fit-season feature rows with outcome columns joined on. Returns the fitted parameters (tails not set)."""
    P = {"version": VERSION, "scaler": {}, "count": {}, "hurdle": {}, "yards": {}, "yards_nz": {}, "zero": {}, "names": {},
         "family": dict(FAMILY)}
    for vol, market in ELIG.items():
        rows = df.filter(pl.Series(_mask(df, market)))
        X, names = D.matrix(rows, vol)
        P["scaler"][vol] = D.Scaler(X)
        P["names"][vol] = names
        Xs, y, pos, inst = P["scaler"][vol](X), rows[OUTCOME[vol]].to_numpy(), rows["position"].to_numpy(), D.instability(rows, vol)
        P["count"][vol] = C.fit_nb(Xs, y, pos, inst)
        pos_ = y > 0                                   # hurdle: zero model on every row, NB on the positive rows
        P["hurdle"][vol] = {"zero": C.fit_logit(Xs, (y == 0).astype(float)), "nb": C.fit_nb(Xs[pos_], y[pos_], pos[pos_], inst[pos_])}
    rows = df.filter(pl.Series(_mask(df, "rec")))
    hr, ht = _hist_catch(rows)
    prior = C.catch_prior(hr, ht, rows["position"].to_numpy())
    P["catch"] = C.fit_catch(rows["receptions"].to_numpy(), rows["targets"].to_numpy(), hr, ht, rows["position"].to_numpy(), prior)
    for market, ycol in (("pass_yds", "passing_yards"), ("rush_yds", "rushing_yards"), ("rec_yds", "receiving_yards")):
        rows = df.filter(pl.Series(_mask(df, market)))
        Xy, y = _yard_inputs(P, rows, VOLUME[market]), rows[ycol].to_numpy()
        P["yards"][market] = Y.fit(Xy, y, seed=seed)
        nz = y != 0                                    # zero-mass variant: P(yards = 0) by logistic, quantiles on the rest
        P["zero"][market] = C.fit_logit(Xy, (~nz).astype(float))
        P["yards_nz"][market] = Y.fit(Xy[nz], y[nz], seed=seed)
    P["tails"], P["tails_nz"] = {}, {}
    return P


def quantiles(P: dict, df: pl.DataFrame, market: str, nonzero: bool = False) -> np.ndarray:
    return Y.predict(P["yards_nz" if nonzero else "yards"][market], _yard_inputs(P, df, VOLUME[market]))


def fit_tails(P: dict, df: pl.DataFrame) -> dict:
    """Tail scales of the yardage distributions from tune-season rows (df: tune-season rows with outcomes)."""
    for market, ycol in (("pass_yds", "passing_yards"), ("rush_yds", "rushing_yards"), ("rec_yds", "receiving_yards")):
        rows = df.filter(pl.Series(_mask(df, market)))
        y = rows[ycol].to_numpy()
        P["tails"][market] = Y.fit_tails(quantiles(P, rows, market), y)
        nz = y != 0
        P["tails_nz"][market] = Y.fit_tails(quantiles(P, rows.filter(pl.Series(nz)), market, nonzero=True), y[nz])
    return P


def simulate(P: dict, df: pl.DataFrame, market: str, sims: int, rng: np.random.Generator) -> np.ndarray:
    """Runs [rows, sims] of the market's stat for every row of df, conditional on the player playing."""
    vol = VOLUME[market]
    if market in ("pass_att", "rush_att", "rec"):
        Xs, pos, inst = _count_inputs(P, df, vol)
        if P["family"][ELIG[vol]] == "hurdle":
            mu, r = C.nb_params(P["hurdle"][vol]["nb"], Xs, pos, inst)
            n = C.hurdle_draw(rng, C.logit_prob(P["hurdle"][vol]["zero"], Xs), mu, r, sims)
        else:
            mu, r = C.nb_params(P["count"][vol], Xs, pos, inst)
            n = C.nb_draw(rng, mu, r, sims)
        if market != "rec":
            return n
        hr, ht = _hist_catch(df)
        c = P["catch"]
        return C.catch_draw(rng, n, C.catch_rate(hr, ht, pos, c["prior"], c["m"]), c["kappa"])
    if P["family"][market] == "quantile+zero":
        x = Y.draw(rng, quantiles(P, df, market, nonzero=True), P["tails_nz"][market], sims)
        x[x == 0] = 1                                  # the zero mass belongs to the logistic part alone
        p0 = C.logit_prob(P["zero"][market], _yard_inputs(P, df, VOLUME[market]))
        return np.where(rng.random(x.shape) < p0[:, None], 0, x).astype(np.int32)
    return Y.draw(rng, quantiles(P, df, market), P["tails"][market], sims)
