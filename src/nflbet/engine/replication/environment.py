"""Engine A layer 1: team volume. For each offense in a game, a joint draw of pass attempts and carries.

Means are a linear regression on the offense's and the opposing defense's earlier per-game volumes. The pair of
residuals (attempts, carries) is resampled together from the fit seasons, so a game that runs pass-heavy is
run-light the way real games are. Targets are a binomial share of attempts.
Game script enters twice: the mean includes the expected margin and total (from points scored and allowed, never a
betting line), and a game's two offenses can share one residual draw, so their surprises move together. Volume does
not yet respond play by play to a simulated score.
"""
from __future__ import annotations

import numpy as np
import polars as pl

PAIRS = (("team_att", "A"), ("team_carries", "C"))
MIN = {"A": 8, "C": 5}


def _rate(df: pl.DataFrame, prefix: str, col: str, window: str) -> np.ndarray:
    n = df[f"{prefix}n_{window}"].to_numpy().astype(float)
    return np.where(n > 0, df[f"{prefix}{col}_{window}"].to_numpy() / np.maximum(n, 1), np.nan)


def expected_script(team_rows: pl.DataFrame, league: dict) -> tuple[np.ndarray, np.ndarray]:
    """(expected margin, expected total points) for the offense in each row, from points over the last 8 games only:
    its points for and against, and the opponent's against and for. No betting line is used.
    Margin = (ours scored + theirs allowed) / 2 - (theirs scored + ours allowed) / 2."""
    half = league["points"]
    def r(prefix, col):
        v = _rate(team_rows, prefix, col, "w8")
        return np.where(np.isnan(v), half, v)
    ours, theirs = (r("o_", "team_points") + r("d_", "team_points")) / 2, (r("d_", "team_points_against") + r("o_", "team_points_against")) / 2
    return ours - theirs, ours + theirs


def design(team_rows: pl.DataFrame, league: dict) -> np.ndarray:
    """One row per offense-game. Columns: 1, then for attempts and for carries: offense last 8, offense season to
    date, offense last season, defense allowed last 8; then expected margin and expected total (the game-script
    terms: a team expected to lead runs more). A missing history is filled with the fit-season league mean."""
    cols = [np.ones(team_rows.height)]
    for col, _ in PAIRS:
        for prefix, window in (("o_", "w8"), ("o_", "std"), ("o_", "prev"), ("d_", "w8")):
            v = _rate(team_rows, prefix, col, window)
            cols.append(np.where(np.isnan(v), league[col], v))
    margin, total = expected_script(team_rows, league)
    return np.column_stack([*cols, margin, total])


def fit(team_rows: pl.DataFrame, y: np.ndarray, targets: np.ndarray, points: np.ndarray, opponent_row: np.ndarray | None = None) -> dict:
    """y: [n, 2] actual (attempts, carries); points: [n] points the offense scored; opponent_row: [n] index of the
    other team's row in the same game (or -1). Returns coefficients, the target rate and the residuals as rows of
    (our attempts, our carries, their attempts, their carries), so a game's two offenses can be drawn together."""
    league = {col: float(y[:, i].mean()) for i, (col, _) in enumerate(PAIRS)}
    league["points"] = float(np.nanmean(points))
    X = design(team_rows, league)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    if opponent_row is None:
        opponent_row = np.full(len(res), -1)
    both = np.column_stack([res, np.where(opponent_row[:, None] >= 0, res[np.maximum(opponent_row, 0)], np.nan)])
    return {"league": league, "coef": coef.tolist(), "resid": both[opponent_row >= 0].tolist() if (opponent_row >= 0).any() else np.column_stack([res, res]).tolist(),
            "target_rate": float(targets.sum() / y[:, 0].sum())}


def mean(params: dict, team_rows: pl.DataFrame) -> np.ndarray:
    return design(team_rows, params["league"]) @ np.array(params["coef"])


def draw_index(params: dict, sims: int, rng: np.random.Generator) -> np.ndarray:
    """Which fit-season game each run borrows its volume surprise from. Share one index between a game's two
    offenses (side 0 and side 1) and their volumes move together the way real opponents' do."""
    return rng.integers(0, len(params["resid"]), sims)


def draw(params: dict, mu: np.ndarray, sims: int, rng: np.random.Generator, index: np.ndarray | None = None,
         side: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """mu: (attempts, carries) mean for one offense-game. Returns integer arrays [sims]: attempts, carries, targets."""
    res = np.array(params["resid"])
    e = res[draw_index(params, sims, rng) if index is None else index][:, 2 * side:2 * side + 2]
    a = np.maximum(np.rint(mu[0] + e[:, 0]), MIN["A"]).astype(np.int64)
    c = np.maximum(np.rint(mu[1] + e[:, 1]), MIN["C"]).astype(np.int64)
    return a, c, rng.binomial(a, params["target_rate"]).astype(np.int64)
