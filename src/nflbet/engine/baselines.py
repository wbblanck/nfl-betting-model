"""Simple baselines (docs/engine/MODEL_SPECIFICATION.md section 6). An engine is used for a market only if it beats
the best of these on the tune seasons. Each baseline is a mean from the feature table and a negative binomial
around it whose size is fitted on the fit seasons.

B1 last season per game; B2 this season to date per game; B3 last 8 games per game; B4 opportunity only (the
player's share of his team's volume over his last 8 games x the team's volume per game over its last 8 x the
position's average efficiency in the fit seasons); B5 the average of players at the same position and volume band.
When a baseline has no history for a row it falls back along FALLBACK and ends at B5, which always has a value.
"""
from __future__ import annotations

import numpy as np
import polars as pl

MARKETS = {            # market -> (outcome column, volume column used for eligibility and bands, min volume per game)
    "pass_att": ("attempts", "attempts", 15.0), "pass_yds": ("passing_yards", "attempts", 15.0),
    "rush_att": ("carries", "carries", 5.0), "rush_yds": ("rushing_yards", "carries", 5.0),
    "rec": ("receptions", "targets", 3.0), "rec_yds": ("receiving_yards", "targets", 3.0),
}
B4 = {                 # market -> (player volume, team volume in the player's games, team volume, efficiency numerator or None)
    "pass_att": ("attempts", "team_att", "team_att", None), "pass_yds": ("attempts", "team_att", "team_att", "passing_yards"),
    "rush_att": ("carries", "team_carries", "team_carries", None), "rush_yds": ("carries", "team_carries", "team_carries", "rushing_yards"),
    "rec": ("targets", "team_targets", "team_targets", "receptions"), "rec_yds": ("targets", "team_targets", "team_targets", "receiving_yards"),
}
FALLBACK = {"B1": ("B3", "B5"), "B2": ("B3", "B1", "B5"), "B3": ("B1", "B5"), "B4": ("B3", "B1", "B5"), "B5": ()}
BANDS = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 1e9)       # volume per game over the last 3 games, as a multiple of the market minimum
MIN_GAMES = 2


def eligible(df: pl.DataFrame, market: str) -> pl.Series:
    """Rows a prop was plausible for, decided only from earlier games: at least 2 of the player's last 3 games on
    record and volume per game in them at or above the market's minimum. Chosen in advance, not tuned."""
    _, vol, lo = MARKETS[market]
    return ((df["p_n_w3"] >= MIN_GAMES) & (df[f"p_{vol}_w3"] / df["p_n_w3"].clip(lower_bound=1) >= lo)).fill_null(False)


def _per_game(df: pl.DataFrame, col: str, window: str) -> np.ndarray:
    n = df[f"p_n_{window}"].to_numpy().astype(float)
    return np.where(n > 0, df[f"p_{col}_{window}"].to_numpy() / np.maximum(n, 1), np.nan)


def band(df: pl.DataFrame, market: str) -> np.ndarray:
    _, vol, lo = MARKETS[market]
    v = df[f"p_{vol}_w3"].to_numpy() / np.maximum(df["p_n_w3"].to_numpy(), 1) / lo
    return np.digitize(v, BANDS[1:-1])


def fit(df: pl.DataFrame, market: str) -> dict:
    """Constants from the fit seasons: efficiency per unit of volume by position, and the mean outcome by position
    and volume band. df: eligible fit-season rows with the outcome columns joined on."""
    y, _, _ = MARKETS[market]
    pv, _, _, num = B4[market]
    eff = {}
    if num:
        for pos, g in df.group_by("position"):
            eff[pos[0]] = float(g[num].sum() / max(g[pv].sum(), 1))
        eff["_all"] = float(df[num].sum() / max(df[pv].sum(), 1))
    b = band(df, market)
    cell = {}
    for pos in df["position"].unique().to_list():
        m = (df["position"] == pos).to_numpy()
        for k in np.unique(b[m]):
            cell[f"{pos}|{int(k)}"] = float(df[y].to_numpy()[m & (b == k)].mean())
    return {"efficiency": eff, "cell_mean": cell, "overall_mean": float(df[y].mean())}


def means(df: pl.DataFrame, market: str, const: dict) -> dict[str, np.ndarray]:
    """Baseline name -> mean per row, after fallbacks. Uses feature columns only; the outcome is never read."""
    y, _, _ = MARKETS[market]
    pv, tv_in, tv, num = B4[market]
    raw = {"B1": _per_game(df, y, "prev"), "B2": _per_game(df, y, "std"), "B3": _per_game(df, y, "w8")}
    share = df[f"p_{pv}_w8"].to_numpy() / np.maximum(df[f"p_{tv_in}_w8"].to_numpy(), 1)
    team = df[f"o_{tv}_w8"].to_numpy() / np.maximum(df["o_n_w8"].to_numpy(), 1)
    eff = np.array([const["efficiency"].get(p, const["efficiency"].get("_all", 1.0)) for p in df["position"].to_list()]) if num else 1.0
    ok = (df["p_n_w8"].to_numpy() > 0) & (df[f"p_{tv_in}_w8"].to_numpy() > 0) & (df["o_n_w8"].to_numpy() > 0)
    raw["B4"] = np.where(ok, share * team * eff, np.nan)
    b = band(df, market)
    raw["B5"] = np.array([const["cell_mean"].get(f"{p}|{int(k)}", const["overall_mean"]) for p, k in zip(df["position"].to_list(), b)])
    out = {}
    for name, chain in FALLBACK.items():
        m = raw[name].copy()
        for nxt in chain:
            m = np.where(np.isnan(m), raw[nxt], m)
        out[name] = np.maximum(m, 0.05)
    return out
