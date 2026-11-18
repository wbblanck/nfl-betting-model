"""Engine B (challenger), MODEL_SPECIFICATION section 3: direct conditional distributions per player-market.

Each forecast is conditional on the player taking a snap (a prop on a player who does not play is void), and is made
from the feature table: earlier games plus the game-day active list. Models are fitted on played, eligible rows
(engine.baselines.eligible) of the fit seasons; tail scales of the yardage distributions on the tune seasons.

Markets and routes:
  pass_att, rush_att      negative binomial regression (counts.fit_nb)
  rec                     simulated targets (negative binomial) then beta-binomial catches
  pass_yds, rush_yds,     gradient-boosted quantiles with the count model's mean as a feature, rearranged, with
  rec_yds                 fitted tails (yardage)
Every market has an inverse CDF (ppf), so the dependence layer (joint.py, spec 3.4) can drive the marginals with
correlated uniforms and leave each one exactly as it is here.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from nflbet.engine import baselines as BL
from nflbet.engine.challenger import counts as C, design as D, yardage as Y

VERSION = "B-1.1"
ROUTE_SHARE = False     # B-1.0 had True; parameters saved without the key are B-1.0 and read it as True
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
    X, _ = D.matrix(df, vol, P.get("route_share", True))
    return P["scaler"][vol](X), df["position"].to_numpy(), D.instability(df, vol)


def _yard_inputs(P: dict, df: pl.DataFrame, vol: str) -> np.ndarray:
    Xs, pos, inst = _count_inputs(P, df, vol)
    mu, _ = C.nb_params(P["count"][vol], Xs, pos, inst)
    return np.column_stack([Xs, np.log1p(mu)])


def fit(df: pl.DataFrame, seed: int = 0) -> dict:
    """df: fit-season feature rows with outcome columns joined on. Returns the fitted parameters (tails not set)."""
    P = {"version": VERSION, "scaler": {}, "count": {}, "hurdle": {}, "yards": {}, "yards_nz": {}, "zero": {}, "names": {},
         "family": dict(FAMILY), "route_share": ROUTE_SHARE}
    for vol, market in ELIG.items():
        rows = df.filter(pl.Series(_mask(df, market)))
        X, names = D.matrix(rows, vol, ROUTE_SHARE)
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


KCOUNT = {"attempts": 90, "carries": 60, "targets": 40}


def _ppf_table(cdf: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Smallest k with cdf[row, k] >= u, per row, for u [rows, sims]."""
    out = np.empty(u.shape, dtype=np.int32)
    for i in range(len(cdf)):
        out[i] = np.searchsorted(cdf[i], u[i], side="left")
    return np.minimum(out, cdf.shape[1] - 1)


def count_pmf(P: dict, df: pl.DataFrame, vol: str) -> np.ndarray:
    """[rows, KCOUNT + 1] probabilities of the volume (pass attempts, carries or targets) under the chosen family."""
    from scipy import stats
    Xs, pos, inst = _count_inputs(P, df, vol)
    k = np.arange(KCOUNT[vol] + 1)[None, :]
    if P["family"][ELIG[vol]] == "hurdle":
        mu, r = C.nb_params(P["hurdle"][vol]["nb"], Xs, pos, inst)
        nb = stats.nbinom.pmf(k, r[:, None], (r / (r + mu))[:, None])
        p0 = C.logit_prob(P["hurdle"][vol]["zero"], Xs)[:, None]
        pmf = (1 - p0) * np.where(k > 0, nb, 0) / np.maximum(1 - nb[:, :1], 1e-12)
        pmf[:, 0] = p0[:, 0]
    else:
        mu, r = C.nb_params(P["count"][vol], Xs, pos, inst)
        pmf = stats.nbinom.pmf(k, r[:, None], (r / (r + mu))[:, None])
    return pmf / pmf.sum(axis=1, keepdims=True)


def rec_pmf(P: dict, df: pl.DataFrame) -> np.ndarray:
    """[rows, KCOUNT['targets'] + 1] probabilities of receptions: targets mixed over beta-binomial catches."""
    from scipy import stats
    pt = count_pmf(P, df, "targets")
    hr, ht = _hist_catch(df)
    c = P["catch"]
    p = np.clip(C.catch_rate(hr, ht, df["position"].to_numpy(), c["prior"], c["m"]), 0.02, 0.98)[:, None]
    r = np.arange(pt.shape[1])[None, :]
    out = np.zeros_like(pt)
    for t in range(pt.shape[1]):
        out += pt[:, t:t + 1] * stats.betabinom.pmf(r, t, p * c["kappa"], (1 - p) * c["kappa"])
    return out / out.sum(axis=1, keepdims=True)


def ppf(P: dict, df: pl.DataFrame, market: str, u: np.ndarray) -> np.ndarray:
    """The market's stat at probabilities u [rows, sims] (inverse CDF), conditional on the player playing. Monotone
    in u, so correlated uniforms from the dependence layer give correlated stats with these exact marginals."""
    if market in ("pass_att", "rush_att"):
        return _ppf_table(np.cumsum(count_pmf(P, df, VOLUME[market]), axis=1), u)
    if market == "rec":
        return _ppf_table(np.cumsum(rec_pmf(P, df), axis=1), u)
    if P["family"][market] != "quantile+zero":
        return np.rint(Y.quantile_fn(quantiles(P, df, market), P["tails"][market], u)).astype(np.int32)
    # Zero mass p0 placed at 0 inside the non-zero distribution G: F(y) = p0 1[y >= 0] + (1 - p0) G(y).
    q, t = quantiles(P, df, market, nonzero=True), P["tails_nz"][market]
    p0 = C.logit_prob(P["zero"][market], _yard_inputs(P, df, VOLUME[market]))[:, None]
    grid = np.tile(np.linspace(0.0005, 0.9995, 1000), (len(q), 1))
    g0 = (Y.quantile_fn(q, t, grid) < 0).mean(axis=1, keepdims=True)          # G(0): share of G below zero
    lo, hi = (1 - p0) * g0, (1 - p0) * g0 + p0
    v = np.where(u < lo, u / (1 - p0), (u - p0) / (1 - p0))
    x = Y.quantile_fn(q, t, np.clip(v, 1e-9, 1 - 1e-9))
    x = np.where(u < lo, np.minimum(np.rint(x), -1), np.maximum(np.rint(x), 1))   # G has no mass at 0
    return np.where((u >= lo) & (u < hi), 0, x).astype(np.int32)


def simulate(P: dict, df: pl.DataFrame, market: str, sims: int, rng: np.random.Generator) -> np.ndarray:
    """Runs [rows, sims] of the market's stat for every row of df, each market on its own (no dependence)."""
    return ppf(P, df, market, rng.random((df.height, sims), dtype=np.float32))
