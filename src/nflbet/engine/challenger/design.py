"""Engine B feature matrices, built from the shared feature table (engine.features.build) only.

Every column is computed from a row's own pre-kickoff sums and from the game's other feature rows (the game-day
active list): nothing about the game itself enters. Features are logs of per-game rates and shares, so the count
model's log link reads them as elasticities.
"""
from __future__ import annotations

import numpy as np
import polars as pl

VOLUMES = ("attempts", "carries", "targets")
TEAM = {"attempts": "team_att", "carries": "team_carries", "targets": "team_targets"}
YARDS = {"attempts": "passing_yards", "carries": "rushing_yards", "targets": "receiving_yards"}
TEAM_YARDS = {"attempts": "team_pass_yds", "carries": "team_rush_yds", "targets": "team_pass_yds"}
WINDOWS = ("w3", "w8", "std", "prev")


def _rate(df: pl.DataFrame, num: str, den: str) -> np.ndarray:
    """num / den from two feature columns; NaN where den is 0."""
    n, d = df[num].to_numpy().astype(float), df[den].to_numpy().astype(float)
    return np.where(d > 0, n / np.maximum(d, 1e-9), np.nan)


def active_share(df: pl.DataFrame, vol: str) -> np.ndarray:
    """Per row: the share of the team's volume over the last 8 games held by players on this game's list (rows of the
    same team-game, played or not). Below 1 when a usual contributor is not active. Computed from features only."""
    own = df[f"p_{vol}_w8"].to_numpy().astype(float)
    key = (df["game_id"] + "|" + df["team"]).to_numpy()
    _, inv = np.unique(key, return_inverse=True)
    tot = np.bincount(inv, weights=own)[inv]
    team = df[f"o_{TEAM[vol]}_w8"].to_numpy().astype(float) / np.maximum(df["o_n_w8"].to_numpy(), 1) * 8
    return np.where(team > 0, tot / np.maximum(team, 1e-9), np.nan)


def matrix(df: pl.DataFrame, vol: str, route_share: bool = True) -> tuple[np.ndarray, list[str]]:
    """Raw (unstandardized) features for a player's volume `vol` (attempts, carries or targets) and its yardage.
    route_share False (B-1.1 on) leaves out db_share_w3: nflverse publishes no participation for the current season,
    and B-1.0 read its absence as a fringe player (docs/engine_preregistration.md, amendment 2026-11-18 (3))."""
    cols, names = [], []

    def add(name, x, flag=False):
        x = np.asarray(x, float)
        if flag:
            cols.append(np.isnan(x).astype(float))
            names.append(f"{name}_missing")
        cols.append(np.nan_to_num(x, nan=0.0))
        names.append(name)

    for w in WINDOWS:
        add(f"log_{vol}_pg_{w}", np.log1p(_rate(df, f"p_{vol}_{w}", f"p_n_{w}")), flag=True)
        add(f"log_ypg_{w}", np.log1p(np.clip(_rate(df, f"p_{YARDS[vol]}_{w}", f"p_n_{w}"), 0, None)), flag=(w == "prev"))
    for w in ("w3", "w8"):
        add(f"share_{w}", _rate(df, f"p_{vol}_{w}", f"p_{TEAM[vol]}_{w}"), flag=(w == "w3"))
    ypu = (df[f"p_{YARDS[vol]}_w8"].to_numpy() + df[f"p_{YARDS[vol]}_prev"].to_numpy())
    vu = (df[f"p_{vol}_w8"].to_numpy() + df[f"p_{vol}_prev"].to_numpy())
    add("yards_per_unit", (ypu + 30.0 * {"attempts": 7.0, "carries": 4.2, "targets": 7.5}[vol]) / (vu + 30.0))
    act = active_share(df, vol)
    add("active_share", np.clip(act, 0, 2), flag=True)
    share8 = _rate(df, f"p_{vol}_w8", f"p_{TEAM[vol]}_w8")
    team_pg = _rate(df, f"o_{TEAM[vol]}_w8", "o_n_w8")
    add("log_expected", np.log1p(np.nan_to_num(share8 / np.clip(act, 0.3, None)) * np.nan_to_num(team_pg)))
    add("log_team_pg", np.log1p(team_pg), flag=True)
    add("log_opp_allowed_pg", np.log1p(_rate(df, f"d_{TEAM[vol]}_w8", "d_n_w8")), flag=True)
    add("log_opp_yds_allowed_pg", np.log1p(_rate(df, f"d_{TEAM_YARDS[vol]}_w8", "d_n_w8")))
    add("log_team_plays_pg", np.log1p(_rate(df, "o_team_plays_w8", "o_n_w8")))
    add("team_points_pg", _rate(df, "o_team_points_w8", "o_n_w8"))
    add("team_points_against_pg", _rate(df, "o_team_points_against_w8", "o_n_w8"))
    add("opp_points_allowed_pg", _rate(df, "d_team_points_w8", "d_n_w8"))
    add("opp_points_scored_pg", _rate(df, "d_team_points_against_w8", "d_n_w8"))
    add("log_snaps_pg_w3", np.log1p(_rate(df, "p_offense_snaps_w3", "p_n_w3")))
    if route_share:
        add("db_share_w3", _rate(df, "p_db_on_field_w3", "p_team_db_charted_w3"), flag=True)
    pos = df["position"].to_numpy()
    for p in ("RB", "WR", "TE"):
        add(f"pos_{p}", (pos == p).astype(float))
    rank = df["depth_rank"].to_numpy()
    add("qb_chart_starter", ((pos == "QB") & (rank == 1)).astype(float))
    add("qb_chart_listed_not_starter", ((pos == "QB") & (rank > 1) & (rank < 9)).astype(float))
    add("log_games_on_record", np.log1p(df["p_n_std"].to_numpy() + df["p_n_prev"].to_numpy()))
    return np.column_stack(cols), names


def instability(df: pl.DataFrame, vol: str) -> np.ndarray:
    """Role instability: |log of (last-3 per-game volume + 1) over (last-8 per-game volume + 1)|. 0 = steady role."""
    a = np.nan_to_num(_rate(df, f"p_{vol}_w3", "p_n_w3"))
    b = np.nan_to_num(_rate(df, f"p_{vol}_w8", "p_n_w8"))
    return np.abs(np.log1p(a) - np.log1p(b))


class Scaler:
    """Standardize with fit-season means and standard deviations (constant columns left as they are)."""

    def __init__(self, X: np.ndarray):
        self.mu = X.mean(axis=0)
        sd = X.std(axis=0)
        self.sd = np.where(sd > 1e-9, sd, 1.0)

    def __call__(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mu) / self.sd

    def to_dict(self) -> dict:
        return {"mu": self.mu.tolist(), "sd": self.sd.tolist()}
