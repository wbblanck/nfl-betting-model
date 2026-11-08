"""Live wind-unders tracker (docs/wind_live_rules.md): pure logic, no network.

record: before kickoff, each eligible game gets a forecast wind (mean of the kickoff hour and the next three, knots)
and the DraftKings total; a game whose forecast is 8 <= w < 15 is an under pick.
official: for each game, the last recorded row before kickoff.
grade: final score vs the recorded total, 1 unit at the recorded under price (-110 when none was recorded).
"""
from __future__ import annotations

import datetime as dt

LO, HI = 8.0, 15.0
BREAK_EVEN = 110 / 210
ROOFS = {"outdoors", "open"}


def bucket(w: float | None) -> str:
    if w is None:
        return ""
    return "calm <8" if w < LO else ("moderate 8-15" if w < HI else "strong 15+")


def is_pick(w: float | None) -> bool:
    return w is not None and LO <= w < HI


def eligible(game: dict, now: dt.datetime, kickoff: dt.datetime, horizon_h: float) -> bool:
    """Regular season, not neutral, roof outdoors/open (as nflverse lists it at run time), not started, kicks off
    within horizon_h hours."""
    return (game.get("game_type") == "REG" and game.get("location") != "Neutral"
            and (game.get("roof") or "") in ROOFS and now < kickoff <= now + dt.timedelta(hours=horizon_h))


def official(rows: list[dict]) -> list[dict]:
    """rows: recorded rows with ISO 'run_utc' and 'kickoff_utc'. Keep, per game_id, the latest run before kickoff
    that has a forecast; a row whose forecast fetch failed counts only when no run before kickoff has one."""
    best: dict[str, dict] = {}
    for r in rows:
        if r["run_utc"] >= r["kickoff_utc"]:
            continue
        b = best.get(r["game_id"])
        has, bhas = r.get("forecast_kn", "x") not in ("", None), b is not None and b.get("forecast_kn", "x") not in ("", None)
        if b is None or (has, r["run_utc"]) > (bhas, b["run_utc"]):
            best[r["game_id"]] = r
    return sorted(best.values(), key=lambda r: (r["kickoff_utc"], r["game_id"]))


def payout(american: float) -> float:
    """Profit per 1 unit staked."""
    return american / 100 if american > 0 else 100 / -american


def grade(total_points: float, line: float, under_price: float | None) -> tuple[str, float]:
    """Under bet: ('W'|'L'|'P', units)."""
    if total_points == line:
        return "P", 0.0
    if total_points < line:
        return "W", payout(under_price if under_price is not None else -110.0)
    return "L", -1.0


def binom_p_greater(k: int, n: int, p: float = BREAK_EVEN) -> float:
    """One-sided exact binomial P(X >= k), computed in log space so large n does not overflow."""
    if n == 0:
        return 1.0
    from math import exp, lgamma, log
    lp, lq = log(p), log(1 - p)
    tot = 0.0
    for i in range(k, n + 1):
        tot += exp(lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1) + i * lp + (n - i) * lq)
    return min(1.0, tot)


__all__ = ["bucket", "is_pick", "eligible", "official", "payout", "grade", "binom_p_greater"]
