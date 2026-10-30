"""S1 on Will's venues (docs/your_venues_rules.md): every official S1 pick priced at the cheapest of Hard Rock (FL),
Kalshi, Polymarket US, Novig, PrizePicks, Underdog and Sleeper, at a line at least as good for the side as the
pick's DraftKings line. Descriptive and unvalidated; S1 stays graded at DraftKings (docs/s1_live_rules.md).

A quote is (venue, line, all-in cost per $1 of payout, dollars available or None). Exchange quotes come from the
best-price record's fetch (src/nflbet/props/bestprice.py), pick'em quotes from ParlayAPI
(src/nflbet/sources/parlay.py parse_pickem), Hard Rock from OddsPapi once its reader exists.
"""
from __future__ import annotations

import json

import polars as pl

from nflbet.props.bestprice import MIN_SIZE
from nflbet.props.live import LIVE
from nflbet.quant.odds import american_from_prob
from nflbet.sources import venues as V
from nflbet.sources.ids import TEAM_FIX, game_key, norm_name

NO_LINE = "No line at your venues"
ROWS = LIVE / "s1_yv_2026.csv"
RECORD = LIVE / "s1_yv_record_2026.csv"
COLS = ["run_utc", "week", "an_game_id", "start_time", "home", "away", "player", "player_id", "market", "side", "dk_line",
        "dk_odds", "yv_venue", "yv_line", "yv_cost", "yv_odds", "yv_size", "label", "n_quotes", "quotes"]


def at_least_as_good(side: str, line: float, dk_line: float) -> bool:
    """Under: a higher line is better; over: a lower line is better."""
    return line >= dk_line if side == "under" else line <= dk_line


def pick_keys(p: dict) -> tuple[str, str, str]:
    return game_key(TEAM_FIX.get(p["home"], p["home"]), TEAM_FIX.get(p["away"], p["away"])), norm_name(p["player"]), p["market"]


def exchange_quotes(p: dict, pmq: dict, pm_size: dict, nv_idx: dict, nv_books: dict, ksq: dict) -> list[dict]:
    """Polymarket US, Novig and Kalshi quotes for the pick's side at every line at least as good as DK's."""
    g, nk, mk = pick_keys(p)
    side, dk = p["side"], float(p["line"])
    out = []
    for (g2, nk2, mk2, ln), q in pmq.items():
        if (g2, nk2, mk2) == (g, nk, mk) and at_least_as_good(side, ln, dk) and q.get(side) is not None:
            c = q[side]
            out.append({"venue": "Polymarket US", "line": ln, "cost": c + V.pm_fee(c, q["fee"]),
                        "size": (pm_size.get(q.get("slug")) or {}).get(side)})
    for (g2, nk2, mk2, ln), m in nv_idx.items():
        if (g2, nk2, mk2) == (g, nk, mk) and at_least_as_good(side, ln, dk) and m["marketId"] in nv_books:
            t = V.nv_taker(nv_books[m["marketId"]], m).get(side)
            if t:
                out.append({"venue": "Novig", "line": ln, "cost": t[0] + V.nv_fee(m, t[0]), "size": t[1]})
    for (g2, nk2, mk2, ln), k in ksq.items():
        if (g2, nk2, mk2) == (g, nk, mk) and at_least_as_good(side, ln, dk) and k.get(side) and k.get("mult") is not None:
            c, size = k[side]
            out.append({"venue": "Kalshi", "line": ln, "cost": c + V.ks_fee(c, k["mult"]), "size": size or 0.0})
    return out


def pickem_quotes(p: dict, pickem: pl.DataFrame | None) -> list[dict]:
    """PrizePicks, Underdog and Sleeper per-pick costs for the pick's side at lines at least as good as DK's."""
    if pickem is None or not pickem.height:
        return []
    g, nk, mk = pick_keys(p)
    side, dk = p["side"], float(p["line"])
    x = pickem.filter(pl.col("game") == g, pl.col("nkey") == nk, pl.col("market") == mk, pl.col("side") == side)
    return [{"venue": r["venue"], "line": r["line"], "cost": r["cost"], "size": None}
            for r in x.iter_rows(named=True) if at_least_as_good(side, r["line"], dk)]


def best(quotes: list[dict], side: str) -> dict | None:
    """Lowest all-in cost among eligible quotes (size unknown or at least MIN_SIZE); ties go to the better line for
    the side (under: higher, over: lower)."""
    elig = [q for q in quotes if q["size"] is None or q["size"] >= MIN_SIZE]
    if not elig:
        return None
    return min(elig, key=lambda q: (q["cost"], -q["line"] if side == "under" else q["line"]))


def rows(picks: pl.DataFrame, quotes_by_pick: list[list[dict]], run_utc: str) -> pl.DataFrame:
    out = []
    for p, qs in zip(picks.iter_rows(named=True), quotes_by_pick):
        b = best(qs, p["side"])
        out.append({"run_utc": run_utc, "week": str(p.get("week") or ""), "an_game_id": p["an_game_id"], "start_time": p["start_time"],
                    "home": p["home"], "away": p["away"], "player": p["player"], "player_id": p.get("player_id"),
                    "market": p["market"], "side": p["side"], "dk_line": float(p["line"]), "dk_odds": float(p["odds"]),
                    "yv_venue": b["venue"] if b else None, "yv_line": b["line"] if b else None,
                    "yv_cost": round(b["cost"], 5) if b else None, "yv_odds": round(american_from_prob(b["cost"])) if b else None,
                    "yv_size": b["size"] if b else None, "label": "priced" if b else NO_LINE, "n_quotes": len(qs),
                    "quotes": json.dumps(sorted(([q["venue"], q["line"], round(q["cost"], 5), q["size"]] for q in qs),
                                                key=lambda x: x[2]))})
    return pl.DataFrame(out, schema={c: (pl.Float64 if c in ("dk_line", "dk_odds", "yv_line", "yv_cost", "yv_odds", "yv_size")
                                         else pl.Int64 if c == "n_quotes" else pl.Utf8) for c in COLS})


def grade(yv: pl.DataFrame, s1_record: pl.DataFrame) -> pl.DataFrame:
    """Your-venue rows of each official S1 pick (same run), graded at the venue's own line and cost with the actual
    stat from the official S1 record. Void and pending follow the official record; no line = not graded."""
    keys = ["run_utc", "an_game_id", "player_id", "market", "side"]
    rec = s1_record.select(*keys, pl.col("result").alias("s1_result"), "actual")
    d = yv.join(rec, on=keys, how="inner")
    res, units = [], []
    for r in d.iter_rows(named=True):
        if r["yv_line"] in (None, ""):
            res.append("no line"); units.append(0.0); continue
        if r["s1_result"] in ("void", "pending") or r["actual"] in (None, ""):
            res.append(r["s1_result"]); units.append(0.0); continue
        a, ln, cost = float(r["actual"]), float(r["yv_line"]), float(r["yv_cost"])
        if a == ln:
            res.append("P"); units.append(0.0); continue
        won = (a > ln) if r["side"] == "over" else (a < ln)
        res.append("W" if won else "L")
        units.append((1 / cost - 1) if won else -1.0)
    return d.with_columns(pl.Series("result", res), pl.Series("units", units))
