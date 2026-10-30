"""ATS on Will's venues (docs/your_venues_rules.md): the official tracker's rules with the best number restricted to
Hard Rock (FL), Kalshi, Polymarket US and Novig. Descriptive and unvalidated; the official record
(src/nflbet/ats/live.py) is unchanged.

Inputs per run: the official evaluation (side, consensus, sharp reference, QB note), the unrounded fair lines, and
one quotes frame of every eligible-venue spread: game, venue, home_line (positive = home favored), side ("home" /
"away"), all-in cost per $1 of payout, dollars available (None if unknown).
"""
from __future__ import annotations

import json

import polars as pl

from nflbet import config
from nflbet.ats import rating as A
from nflbet.execution.records import before_kickoff
from nflbet.quant.fees import taker_fee

COST_CAP = 120 / 220            # -120: the most a quote may cost to count as "the best number"
MIN_SIZE = 10.0                 # $ of payout at an exchange's price for it to count (as the best-price record)
KALSHI_FEE, POLY_FEE = 0.07, 0.0695
CLV_PER_POINT = 0.235           # as the official tracker (docs/ats_clv2.md)
NO_LINE = "No line at your venues"
VENUE_NAME = {"Kalshi": "Kalshi", "PolymarketUS": "Polymarket US"}
RUNS = config.ROOT / "data" / "live" / "ats_yv_runs_2026.csv"
RECORD = config.ROOT / "data" / "live" / "ats_yv_record_2026.csv"
QUOTE_SCHEMA = {"game": pl.Utf8, "venue": pl.Utf8, "home_line": pl.Float64, "side": pl.Utf8, "cost": pl.Float64,
                "size": pl.Float64}


def exchange_quotes(q: pl.DataFrame, kalshi_mult: float = 1.0) -> pl.DataFrame:
    """OpenMarkets spread quotes (sources.openmarkets.spread_quotes) with each exchange's taker fee added."""
    rows = []
    for r in q.iter_rows(named=True):
        p = r["price"]
        coef = KALSHI_FEE * kalshi_mult if r["venue"] == "Kalshi" else POLY_FEE if r["venue"] == "PolymarketUS" else None
        if coef is None or not 0 < p < 1:
            continue
        rows.append({"game": r["game"], "venue": VENUE_NAME[r["venue"]], "home_line": r["home_line"], "side": r["side"],
                     "cost": p + taker_fee(coef, p), "size": r["avail"]})
    return pl.DataFrame(rows, schema=QUOTE_SCHEMA)


def eligible(quotes: pl.DataFrame, game: str, side: str) -> list[dict]:
    """Quotes for one game and side that may set the best number: cost at most COST_CAP, size unknown or >= MIN_SIZE."""
    q = quotes.filter(pl.col("game") == game, pl.col("side") == side, pl.col("cost") <= COST_CAP)
    return [r for r in q.iter_rows(named=True) if r["size"] is None or r["size"] >= MIN_SIZE]


def best_quote(cands: list[dict], home: bool) -> dict | None:
    """Most favorable line for the side (home: smallest home_line; away: largest); ties go to the lower cost."""
    if not cands:
        return None
    return min(cands, key=lambda r: ((r["home_line"] if home else -r["home_line"]), r["cost"]))


def label_for(gap: float, key: bool, beats: bool, qb: str) -> str:
    """The official tracker's label rules (docs/ats_live_rules.md), unchanged."""
    if gap >= 1 and key and beats:
        return "Wait" if qb else "Bet Now"
    if gap >= 1.5 or (gap >= 1 and key):
        return "Monitor"
    return "No Value"


def evaluate(fair: pl.DataFrame, ev: pl.DataFrame, quotes: pl.DataFrame) -> pl.DataFrame:
    """One row per game in `ev` (the official evaluation): the rating's side at the best number on Will's venues."""
    fair_by_id = dict(zip(fair["game_id"].to_list(), fair["fair"].to_list()))
    out = []
    for r in ev.iter_rows(named=True):
        home = r["side_is_home"] in (True, "true")
        side = "home" if home else "away"
        f = float(fair_by_id.get(r["game_id"], r["fair"]))
        cands = eligible(quotes, r["game"], side)
        per_venue = {}
        for c in cands:
            cur = per_venue.get(c["venue"])
            if cur is None or best_quote([cur, c], home) is c:
                per_venue[c["venue"]] = c
        b = best_quote(cands, home)
        base = {k: r[k] for k in ("game_id", "game", "start_time", "home", "away", "consensus", "exchange", "side", "side_is_home", "qb_note")}
        base["fair"] = round(f, 2)
        venues = json.dumps({v: [c["home_line"], round(c["cost"], 5), c["size"]] for v, c in sorted(per_venue.items())})
        if b is None:
            out.append({**base, "yv_venue": None, "yv_line": None, "yv_cost": None, "yv_size": None, "gap": None,
                        "key": None, "exp_clv": None, "beats_ref": None, "label": NO_LINE, "n_quotes": 0, "venues": venues})
            continue
        line = b["home_line"]
        gap = (f - line) if home else (line - f)
        key = A.crosses_key(line, f, home)
        ref = r["exchange"] if r["exchange"] is not None else r["consensus"]
        beats = (line <= ref) if home else (line >= ref)
        out.append({**base, "yv_venue": b["venue"], "yv_line": line, "yv_cost": round(b["cost"], 5), "yv_size": b["size"],
                    "gap": round(gap, 2), "key": key, "exp_clv": round(CLV_PER_POINT * max(gap, 0.0), 2), "beats_ref": beats,
                    "label": label_for(gap, key, beats, r["qb_note"] or ""), "n_quotes": len(cands), "venues": venues})
    return pl.DataFrame(out, infer_schema_length=None)


def official(runs: pl.DataFrame) -> pl.DataFrame:
    """The last run before each game's kickoff."""
    r = before_kickoff(runs)
    last = r.group_by("game_id").agg(pl.col("run_utc").max())
    return r.join(last, on=["game_id", "run_utc"])


def grade_rows(off: pl.DataFrame, sched: pl.DataFrame) -> pl.DataFrame:
    """Official rows graded against final scores (sched: game_id, result = home margin, spread_line = nflverse close):
    CLV from the recorded number; ATS result at that number and all-in cost (win pays 1/cost - 1, push 0). Rows with
    no line at Will's venues stay ungraded."""
    d = off.join(sched, on="game_id", how="left")
    res, units, clv = [], [], []
    for r in d.iter_rows(named=True):
        line = r["yv_line"]
        if line in (None, "") or r["result"] is None:
            res.append("no line" if line in (None, "") else "pending"); units.append(0.0); clv.append(None); continue
        line, cost = float(line), float(r["yv_cost"])
        home = r["side_is_home"] in (True, "true")
        clv.append(((r["spread_line"] - line) if home else (line - r["spread_line"])) if r["spread_line"] is not None else None)
        m = r["result"]
        if m == line:
            res.append("P"); units.append(0.0); continue
        won = (m > line) if home else (m < line)
        res.append("W" if won else "L")
        units.append((1 / cost - 1) if won else -1.0)
    return d.with_columns(pl.Series("result_ats", res), pl.Series("units", units), pl.Series("clv", clv, dtype=pl.Float64))


def grade(runs: pl.DataFrame, season: int) -> pl.DataFrame:
    import nflreadpy as nfl

    sch = nfl.load_schedules(seasons=[season]).select("game_id", "result", "spread_line")
    return grade_rows(official(runs), sch)
