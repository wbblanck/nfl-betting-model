"""ParlayAPI DraftKings and FanDuel prices as a second record next to Action Network (docs/s1_live_rules.md).

Descriptive only: rule S1 and its picks are unchanged and still come from Action Network, whose book set (DK, FanDuel,
BetMGM, BetRivers, Caesars) the "books disagree" vote was locked on. ParlayAPI carries DK and FanDuel but not BetMGM,
BetRivers or Caesars, so it cannot replace Action Network without changing the rule. It adds: two-sided DK prices
with an update time even when Action Network has none posted yet, and a check that both sources agree.

Probe (docs/evidence/parlay on branch claude/espn-props-full, 2026-10-08): an unfiltered call stops at its 10,000-row
cap, mostly correct-score and milestone markets, so the fetch asks for DK and FanDuel and the S1 market keys only:
751 two-sided full-game rows, all 15 week-5 games, one line per book, player and market. Each book files the same
market under its own key (DK player_receiving_yards, FanDuel player_rec_yds). One call = 3 credits of 1,000 a month.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import polars as pl

from nflbet.props import TEAM_FIX, norm_name

URL = "https://parlay-api.com/v1/sports/americanfootball_nfl/props"
BOOKS = {"draftkings": "dk", "fanduel": "fd"}
KEYS = {   # book's market key -> S1 market (keys as seen in the probe; FanDuel attempts/completions keys are guesses)
    "player_passing_yards": "pass_yds", "player_pass_yds": "pass_yds",
    "player_passing_attempts": "pass_att", "player_pass_attempts": "pass_att",
    "player_passing_completions": "pass_cmp", "player_pass_completions": "pass_cmp",
    "player_rushing_yards": "rush_yds", "player_rush_yds": "rush_yds",
    "player_rushing_attempts": "rush_att", "player_rush_attempts": "rush_att",
    "player_receiving_yards": "rec_yds", "player_rec_yds": "rec_yds",
    "player_receptions": "rec",
    "player_passing_+_rushing_yards": "pass_rush_yds",
    "player_rushing_+_receiving_yards": "rush_rec_yds", "player_rush_reception_yds": "rush_rec_yds",
}
TEAMS = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "Seattle Seahawks": "SEA",
    "San Francisco 49ers": "SF", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}
AN_BOOKS = {"DK NJ": "dk", "FanDuel NJ": "fd"}
SCHEMA = {"book": pl.Utf8, "game": pl.Utf8, "nkey": pl.Utf8, "player": pl.Utf8, "market": pl.Utf8, "line": pl.Float64,
          "over": pl.Float64, "under": pl.Float64, "last_update": pl.Utf8}
PICK_COLS = ["pa_dk_line", "pa_dk_odds", "pa_fd_line", "pa_fd_odds"]


def fetch(key: str | None = None) -> tuple[list, dict]:
    """(rows, credit headers). The key comes from PARLAY_API_KEY and is never returned or archived."""
    key = key or os.environ["PARLAY_API_KEY"]
    q = {"apiKey": key, "bookmakers": ",".join(BOOKS), "markets": ",".join(KEYS), "limit": 10000, "oddsFormat": "american"}
    req = urllib.request.Request(f"{URL}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "nfl-betting-model/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        hdr = {k: v for k, v in r.headers.items() if k.lower().startswith("x-requests")}
        return json.loads(r.read()), hdr


def game_key(a: str, b: str) -> str:
    """Teams in sorted order: neutral-site games may list home and away differently by source."""
    return "|".join(sorted((a, b)))


def parse(rows: list) -> pl.DataFrame:
    """Two-sided full-game rows in S1 markets: book (dk / fd), game, nkey (normalized name), market, line, prices."""
    out = []
    for r in rows:
        b, m = BOOKS.get(r.get("bookmaker")), KEYS.get(r.get("market_key"))
        h, a = TEAMS.get(r.get("home_team")), TEAMS.get(r.get("away_team"))
        if not (b and m and h and a) or (r.get("period") or "FULL") != "FULL" or r.get("line") is None \
                or r.get("over_price") is None or r.get("under_price") is None or not r.get("player"):
            continue
        out.append({"book": b, "game": game_key(h, a), "nkey": norm_name(r["player"]), "player": r["player"], "market": m,
                    "line": float(r["line"]), "over": float(r["over_price"]), "under": float(r["under_price"]),
                    "last_update": r.get("last_update") or ""})
    d = pl.DataFrame(out, schema=SCHEMA)
    return d.sort("last_update", descending=True).unique(["book", "game", "nkey", "market"], keep="first", maintain_order=True)


def an_lines(path) -> pl.DataFrame:
    """Action Network's DK and FanDuel two-sided rows from a fetched lines file, in parse()'s shape."""
    d = pl.read_csv(path, infer_schema_length=0).filter(pl.col("book").is_in(list(AN_BOOKS)),
                                                        pl.col("over_odds").fill_null("") != "",
                                                        pl.col("under_odds").fill_null("") != "")
    if not d.height:
        return pl.DataFrame(schema=SCHEMA)
    fix = lambda c: pl.col(c).replace(TEAM_FIX)  # noqa: E731
    return d.select(pl.col("book").replace_strict(AN_BOOKS).alias("book"),
                    pl.struct(fix("home").alias("h"), fix("away").alias("a")).map_elements(
                        lambda s: game_key(s["h"], s["a"]), return_dtype=pl.Utf8).alias("game"),
                    pl.col("player").map_elements(norm_name, return_dtype=pl.Utf8).alias("nkey"), "player", "market",
                    pl.col("line").cast(pl.Float64), pl.col("over_odds").cast(pl.Float64).alias("over"),
                    pl.col("under_odds").cast(pl.Float64).alias("under"), pl.lit("").alias("last_update")) \
        .unique(["book", "game", "nkey", "market"], keep="first", maintain_order=True)


def _p_over(o: float, u: float) -> float:
    io = -o / (-o + 100) if o < 0 else 100 / (o + 100)
    iu = -u / (-u + 100) if u < 0 else 100 / (u + 100)
    return io / (io + iu)


def compare(pa: pl.DataFrame, an: pl.DataFrame) -> list[dict]:
    """Per book: props at each source, props at both, share at the same line, and at the same line the mean absolute
    gap in de-vigged P(over) (points)."""
    res = []
    for b in BOOKS.values():
        x, y = pa.filter(pl.col("book") == b), an.filter(pl.col("book") == b)
        j = x.join(y, on=["game", "nkey", "market"], how="inner", suffix="_an")
        same = j.filter(pl.col("line") == pl.col("line_an"))
        gap = [abs(_p_over(r["over"], r["under"]) - _p_over(r["over_an"], r["under_an"])) * 100 for r in same.iter_rows(named=True)]
        res.append({"book": b, "n_parlay": x.height, "n_an": y.height, "n_both": j.height,
                    "same_line": same.height, "mean_p_gap_pts": round(sum(gap) / len(gap), 2) if gap else None})
    return res


def attach(picks: pl.DataFrame, pa: pl.DataFrame | None) -> pl.DataFrame:
    """Add ParlayAPI's DK and FanDuel line and price on the pick's side (null when absent)."""
    if pa is None:
        return picks.with_columns(*(pl.lit(None, pl.Float64).alias(c) for c in PICK_COLS))
    idx = {(r["book"], r["game"], r["nkey"], r["market"]): r for r in pa.iter_rows(named=True)}
    cols = {c: [] for c in PICK_COLS}
    for p in picks.iter_rows(named=True):
        g = game_key(TEAM_FIX.get(p["home"], p["home"]), TEAM_FIX.get(p["away"], p["away"]))
        for b in BOOKS.values():
            r = idx.get((b, g, norm_name(p["player"]), p["market"]))
            cols[f"pa_{b}_line"].append(r["line"] if r else None)
            cols[f"pa_{b}_odds"].append((r["under"] if p["side"] == "under" else r["over"]) if r else None)
    return picks.with_columns(*(pl.Series(c, v, dtype=pl.Float64) for c, v in cols.items()))
