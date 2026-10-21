"""ESPN BET props (data/espn/espn_props_<season>.csv.gz): load, map to markets, pair over/under, join to
nflverse by ESPN athlete id (nflverse players.espn_id -> gsis player_id)."""
from __future__ import annotations

import re

import polars as pl

from nflbet import config

# ESPN type name (lower case, "(incl. overtime)" removed) -> market used in props.STAT
MARKET = {
    "total passing yards": "pass_yds", "total passing attempts": "pass_att", "total completions": "pass_cmp",
    "total passing completions": "pass_cmp", "total passing touchdowns": "pass_td", "total interceptions": "pass_int",
    "total interceptions thrown": "pass_int", "total rushing yards": "rush_yds", "total rushing attempts": "rush_att",
    "total receptions": "rec", "total receiving yards": "rec_yds", "total rushing + receiving yards": "rush_rec_yds",
    "total rush + rec yards": "rush_rec_yds", "total passing + rushing yards": "pass_rush_yds",
    "total rushing plus receiving yards": "rush_rec_yds", "total passing plus rushing yards": "pass_rush_yds",
    "total carries": "rush_att", "total pass completions": "pass_cmp",
}


def clean_type(s: str | None) -> str:
    return re.sub(r"\s*\(incl\.? overtime\)", "", (s or "")).strip().lower()


def load(season: int) -> pl.DataFrame:
    d = pl.read_csv(config.ROOT / "data" / "espn" / f"espn_props_{season}.csv.gz", infer_schema_length=0)
    return d.with_columns(pl.col("week").cast(pl.Int64), pl.col("season").cast(pl.Int64),
                          *(pl.col(c).cast(pl.Float64) for c in ("open_line", "cur_line")),
                          *(pl.col(c).str.replace("EVEN", "100").cast(pl.Float64, strict=False)
                            for c in ("open_odds", "cur_odds")),
                          pl.col("type_name").map_elements(clean_type, return_dtype=pl.Utf8).alias("tname"))


def paired(d: pl.DataFrame) -> pl.DataFrame:
    """One row per event-athlete-market with both sides at the final line (and at the open line when the
    open record carries both sides). Groups with more than one final line per side (alternates) are dropped."""
    d = d.with_columns(pl.col("tname").replace_strict(MARKET, default=None).alias("market")) \
        .filter(pl.col("market").is_not_null())
    k = ["season", "week", "event_id", "athlete_id", "market"]
    multi = d.group_by(k + ["side"]).agg(pl.col("cur_line").n_unique().alias("n")).filter(pl.col("n") > 1).select(k).unique()
    d = d.join(multi, on=k, how="anti")
    o = d.filter(pl.col("side") == "over").select(*k, "open_line", "cur_line", pl.col("open_odds").alias("open_over"),
                                                  pl.col("cur_odds").alias("cur_over"))
    u = d.filter(pl.col("side") == "under").select(*k, pl.col("open_line").alias("open_line_u"),
                                                   pl.col("cur_line").alias("cur_line_u"),
                                                   pl.col("open_odds").alias("open_under"), pl.col("cur_odds").alias("cur_under"))
    p = o.join(u, on=k).filter(pl.col("cur_line") == pl.col("cur_line_u"))
    return p.with_columns(pl.when(pl.col("open_line") == pl.col("open_line_u")).then(pl.col("open_under"))
                          .otherwise(None).alias("open_under")).drop("cur_line_u", "open_line_u")


def with_player_id(p: pl.DataFrame) -> pl.DataFrame:
    import nflreadpy as nfl

    ids = nfl.load_players().select(pl.col("espn_id").cast(pl.Utf8).alias("athlete_id"),
                                    pl.col("gsis_id").alias("player_id")).filter(pl.col("athlete_id").is_not_null())
    return p.join(ids.unique(subset="athlete_id"), on="athlete_id", how="left")
