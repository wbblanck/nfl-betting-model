"""Market EV: a price judged against the other venues' consensus instead of a model (docs/market_ev_preregistration.md).

Part A (live, display only): `live_fair` reads a best-price row's `venues` / `venues_opp` columns.
Part B (2025 test): `props_books`, `bets` and `week_bootstrap` implement rules M1 (EV > 0) and M2 (EV >= 3%).
"""
from __future__ import annotations

import json
import random
import statistics

import polars as pl

from nflbet.quant.odds import implied

EXCHANGES = ("Novig", "Kalshi", "Polymarket US")
MIN_SIZE = 10.0
MAX_COST = 0.97
RULES = {"M1": 0.0, "M2": 0.03}       # EV threshold; M1 is strict (> 0), M2 inclusive (>= 3%)


def devig(c_side: float, c_other: float) -> float:
    """Multiplicative de-vig: the side's share of the two costs (fees and spread included in both)."""
    return c_side / (c_side + c_other)


def fair_loo(p: dict[str, float], best: str, min_n: int = 2) -> tuple[float | None, int]:
    """Median fair probability over venues other than `best`; None when fewer than `min_n` remain."""
    others = [v for k, v in p.items() if k != best]
    return (statistics.median(others) if len(others) >= min_n else None), len(others)


def ev(fair: float, cost: float) -> float:
    return fair / cost - 1


def _name(v: str) -> str:
    return v.replace(" (ParlayAPI)", "")


def _counts(cost, size, venue: str) -> bool:
    if cost is None or float(cost) >= MAX_COST:
        return False
    # as bestprice.MIN_SIZE: an exchange side needs $10 of payout; an unread size (Polymarket book down) still counts
    return not (_name(venue) in EXCHANGES and size is not None and float(size) < MIN_SIZE)


def live_fair(venues: str | None, venues_opp: str | None, best_venue: str | None) -> tuple[float | None, int]:
    """Part A: leave-one-out median of two-sided de-vigged probabilities at a pick's line. (None, n) when fewer
    than two venues other than the best one count; the caller then falls back to DraftKings' no-vig price."""
    try:
        a, b = json.loads(venues or "{}"), json.loads(venues_opp or "{}")
    except ValueError:
        return None, 0
    p = {}
    for v, (c, s) in a.items():
        if v in b and _counts(c, s, v) and _counts(b[v][0], b[v][1], v):
            p[_name(v)] = devig(float(c), float(b[v][0]))
    return fair_loo(p, _name(best_venue or ""))


# ---------------------------------------------------------------------------------------------- Part B: 2025 test

def screened(lines: pl.DataFrame) -> pl.DataFrame:
    """Two-sided over/under quotes passing the junk screen (de-vigged P(over) 0.35-0.65, hold < 10%)."""
    d = lines.filter(pl.col("market") != "anytime_td", pl.col("over_odds").is_not_null(), pl.col("under_odds").is_not_null())
    d = d.with_columns(pl.col("over_odds").map_elements(implied, return_dtype=pl.Float64).alias("c_over"),
                       pl.col("under_odds").map_elements(implied, return_dtype=pl.Float64).alias("c_under"))
    d = d.with_columns((pl.col("c_over") / (pl.col("c_over") + pl.col("c_under"))).alias("p_over"),
                       (pl.col("c_over") + pl.col("c_under") - 1).alias("hold"))
    return d.filter(pl.col("p_over").is_between(0.35, 0.65), pl.col("hold") < 0.10)


def prop_bet(books: dict[str, tuple[float, float, float]]) -> dict | None:
    """books: {book: (c_over, c_under, p_over)} for one prop. The side with the larger leave-one-out EV, with its
    best book, cost and fair; None with fewer than 3 books."""
    if len(books) < 3:
        return None
    best_side = None
    for side, i in (("over", 0), ("under", 1)):
        best = min(sorted(books), key=lambda b: books[b][i])                 # lowest cost; ties -> first name
        p = {b: (v[2] if side == "over" else 1 - v[2]) for b, v in books.items()}
        fair, _ = fair_loo(p, best)
        e = ev(fair, books[best][i])
        if best_side is None or e > best_side["ev"]:
            best_side = {"side": side, "book": best, "cost": books[best][i], "fair": fair, "ev": e}
    return best_side


def bets(d: pl.DataFrame) -> pl.DataFrame:
    """One candidate per prop (game, player, market, line) with 3+ screened books; `actual`, `week` carried."""
    keys = ["an_game_id", "an_player_id", "market", "line"]
    rows = []
    for k, g in d.group_by(keys, maintain_order=True):
        books = {r["book"]: (r["c_over"], r["c_under"], r["p_over"]) for r in g.iter_rows(named=True)}
        b = prop_bet(books)
        if b is None:
            continue
        r0 = g.row(0, named=True)
        rows.append({**dict(zip(keys, k)), "week": r0["week"], "actual": r0.get("actual"), "n_books": len(books), **b})
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def select(c: pl.DataFrame, rule: str) -> pl.DataFrame:
    t = RULES[rule]
    return c.filter(pl.col("ev") > t) if rule == "M1" else c.filter(pl.col("ev") >= t - 1e-12)


def units(c: pl.DataFrame) -> pl.DataFrame:
    """Result per bet: W pays 1/cost - 1, L -1; pushes and missing actuals dropped."""
    g = c.filter(pl.col("actual").is_not_null(), pl.col("actual") != pl.col("line"))
    won = (pl.col("actual") > pl.col("line")) == (pl.col("side") == "over")
    return g.with_columns(pl.when(won).then(1 / pl.col("cost") - 1).otherwise(-1.0).alias("units"))


def week_bootstrap(g: pl.DataFrame, reps: int = 10_000, seed: int = 7) -> tuple[float, float, float, float]:
    """(ROI, p = share of week-resampled ROIs <= 0, 2.5th and 97.5th percentiles)."""
    by = {w: (float(x["units"].sum()), x.height) for (w,), x in g.group_by(["week"])}
    weeks = list(by)
    roi = sum(u for u, _ in by.values()) / sum(n for _, n in by.values())
    rng = random.Random(seed)
    sims = []
    for _ in range(reps):
        s = [by[rng.choice(weeks)] for _ in weeks]
        sims.append(sum(u for u, _ in s) / sum(n for _, n in s))
    sims.sort()
    return roi, sum(x <= 0 for x in sims) / reps, sims[int(0.025 * reps)], sims[int(0.975 * reps) - 1]
