"""Action Network prop lines for 2022-2023 from a third-party archive (gcampb41/nfl_data-, no license).

The repo publishes per-season parquet files scraped from the same Action Network endpoint our own fetch used
(it went empty in 2026). We use them for our own analysis only: they are downloaded at run time from one pinned
commit, checked against a SHA-256, cached under data/cache/ (gitignored), and never committed or republished.

Coverage (checked 2026-11-04): 2022 has Consensus (15) and Open (30) only, 283 games. 2023 adds DraftKings (68),
FanDuel (69) and bet365 (79) in 208 of 285 games (weeks 4 and 6-22). 2023 also has first-half and quarter props
under the same bet types: only period == "event" is kept (the CLAUDE.md partial-game trap).

`load(season)` returns rows shaped like data/props/an_props_<season>.csv (season, week, an_game_id, market,
an_player_id, player, player_team, gsis_id, book_id, book, line, over_odds, under_odds, yes_odds), one per
book-player-game-market. A book-player-game-market with more than one two-sided line is dropped, and the count is
returned, rather than guessing which line was the main one.
"""
from __future__ import annotations

import hashlib
import urllib.request

import polars as pl

from nflbet import config

REPO = "gcampb41/nfl_data-"
COMMIT = "5133c1b7ff56608cd1c2924d60512a6f33eaf99d"
SHA256 = {2022: "2ba917de50e258ef0828aeee3427a107dbbf6669371f0aa213fb55a3704f3ea7",
          2023: "cf43a96e4d828b48e0db6cf63ea1f1eb699f2996e20b1d09b23b09257a9e3905"}
CACHE = config.ROOT / "data" / "cache" / "gc_props"
BOOKS = {15: "Consensus", 30: "Open", 68: "DK", 69: "FanDuel", 79: "bet365"}
MARKET = {"passing_yards": "pass_yds", "passing_tds": "pass_td", "completions": "pass_cmp", "attempts": "pass_att",
          "passing_interceptions": "pass_int", "rushing_yards": "rush_yds", "rushing_attempts": "rush_att",
          "receiving_yards": "rec_yds", "receptions": "rec", "rushing_receiving_yards": "rush_rec_yds",
          "passing_rushing_yards": "pass_rush_yds", "anytime_touchdown_scorer": "anytime_td"}
KEY = ["season", "week", "an_game_id", "an_player_id", "market", "book_id"]


def path(season: int):
    if season not in SHA256:
        raise ValueError(f"no pinned file for {season}; have {sorted(SHA256)}")
    p = CACHE / f"{season}.parquet"
    if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != SHA256[season]:
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/data/processed/football/nfl/player_props/{season}.parquet"
        with urllib.request.urlopen(url, timeout=120) as r:
            body = r.read()
        got = hashlib.sha256(body).hexdigest()
        if got != SHA256[season]:
            raise RuntimeError(f"{season}.parquet sha256 {got} != pinned {SHA256[season]}")
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    return p


def shape(raw: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """Raw long rows (one per side) -> one row per book-player-game-market. Returns (rows, groups dropped)."""
    d = (raw.filter(pl.col("period") == "event", pl.col("bet_type").is_in(list(MARKET)),
                    pl.col("book_id").is_in(list(BOOKS)))
         .select(pl.col("season").cast(pl.Int64), pl.col("week").cast(pl.Int64),
                 pl.col("event_id").cast(pl.String).alias("an_game_id"),
                 pl.col("bet_type").replace_strict(MARKET).alias("market"),
                 pl.col("action_network_player_id").cast(pl.String).alias("an_player_id"),
                 pl.col("join_name").alias("player"), pl.col("team").alias("player_team"),
                 pl.col("player_id").alias("gsis_id"), pl.col("book_id").cast(pl.Int64),
                 "side", pl.col("value").cast(pl.Float64), pl.col("odds").cast(pl.Float64)))
    yes = (d.filter(pl.col("market") == "anytime_td", pl.col("side").is_in(["over", "noside"]))
           .group_by(KEY).agg(pl.col("player", "player_team", "gsis_id").first(), pl.col("odds").first().alias("yes_odds"),
                              pl.len().alias("_n")))
    ou = d.filter(pl.col("market") != "anytime_td", pl.col("side").is_in(["over", "under"]))
    over = ou.filter(pl.col("side") == "over").rename({"odds": "over_odds", "value": "line"}).drop("side")
    under = ou.filter(pl.col("side") == "under").select(*KEY, pl.col("value").alias("line"),
                                                        pl.col("odds").alias("under_odds"))
    pairs = over.join(under, on=[*KEY, "line"], how="inner")
    n = pairs.group_by(KEY).agg(pl.len().alias("_n"))
    bad = n.filter(pl.col("_n") > 1).height + yes.filter(pl.col("_n") > 1).height
    pairs = pairs.join(n.filter(pl.col("_n") == 1).drop("_n"), on=KEY, how="semi")
    yes = yes.filter(pl.col("_n") == 1).drop("_n").with_columns(
        pl.lit(None, pl.Float64).alias("line"), pl.lit(None, pl.Float64).alias("over_odds"),
        pl.lit(None, pl.Float64).alias("under_odds"))
    pairs = pairs.with_columns(pl.lit(None, pl.Float64).alias("yes_odds"))
    cols = ["season", "week", "an_game_id", "market", "an_player_id", "player", "player_team", "gsis_id", "book_id",
            "line", "over_odds", "under_odds", "yes_odds"]
    out = pl.concat([pairs.select(cols), yes.select(cols)]).with_columns(
        pl.col("book_id").replace_strict(BOOKS, return_dtype=pl.String).alias("book")).sort(KEY)
    return out, bad


def load(season: int) -> tuple[pl.DataFrame, int]:
    return shape(pl.read_parquet(path(season)))
