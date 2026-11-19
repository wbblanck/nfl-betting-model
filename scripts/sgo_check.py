"""Check SportsGameOdds closes against our own pre-kickoff ParlayAPI snapshots (docs/sgo_closes.md, "Check").

  python scripts/sgo_check.py      # -> docs/sgo_close_check.md, data/live/sgo/check_2026.csv

For each DK / FanDuel prop (our 9 markets, over side) in a saved SGO game, take the latest ParlayAPI snapshot taken
in the 7 days before that game's kickoff and compare the line and the over price with SGO's close. Descriptive; the usability
criterion is fixed in docs/sgo_closes.md before any comparison was run.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json

import polars as pl

from nflbet import config
from nflbet.sources import parlay as Pa

SEASON = 2026
SGO = config.ROOT / "data" / "live" / "sgo"
PARLAY = config.ROOT / "data" / "live" / "parlay"
DOC = config.ROOT / "docs" / "sgo_close_check.md"
OUT = SGO / f"check_{SEASON}.csv"
BOOKS = {"draftkings": "dk", "fanduel": "fd"}
BUCKETS = [(0, 30, "0-30 min"), (30, 120, "30 min-2 h"), (120, 360, "2-6 h"), (360, 10**6, "over 6 h")]


def sgo_rows() -> pl.DataFrame:
    files = sorted((SGO / str(SEASON)).glob("*.csv.gz"))
    if not files:
        return pl.DataFrame()
    d = pl.concat([pl.read_csv(f, infer_schema_length=0) for f in files], how="vertical")
    return (d.filter(pl.col("book").is_in(list(BOOKS)), pl.col("market").is_not_null(), pl.col("side") == "over")
             .with_columns(pl.col("book").replace(BOOKS), pl.col("close_line").cast(pl.Float64),
                           pl.col("close_odds").cast(pl.Float64),
                           pl.col("starts_at").str.to_datetime("%Y-%m-%dT%H:%M:%S%.fZ", time_zone="UTC").alias("kick")))


def parlay_rows() -> pl.DataFrame:
    parts = []
    for f in sorted(PARLAY.glob("*.json.gz")):
        snap = dt.datetime.strptime(f.name[:14], "%Y%m%dT%H%MZ").replace(tzinfo=dt.timezone.utc)
        with gzip.open(f) as g:
            rows = json.load(g)
        if not isinstance(rows, list):
            continue
        p = Pa.parse(rows)
        if p.height:
            parts.append(p.with_columns(pl.lit(snap).cast(pl.Datetime("us", "UTC")).alias("snap")))
    return pl.concat(parts, how="vertical") if parts else pl.DataFrame()


def check() -> pl.DataFrame:
    s, p = sgo_rows(), parlay_rows()
    if not s.height or not p.height:
        return pl.DataFrame()
    j = s.join(p.rename({"line": "pa_line", "over": "pa_over"}).select("book", "game", "nkey", "market", "pa_line",
                                                                      "pa_over", "snap"),
               on=["book", "game", "nkey", "market"], how="inner").filter(pl.col("snap") < pl.col("kick"),
                                                                         pl.col("snap") > pl.col("kick") - dt.timedelta(days=7))
    j = j.sort("snap").group_by(["book", "game", "nkey", "market"], maintain_order=True).last()
    return j.with_columns(((pl.col("kick") - pl.col("snap")).dt.total_seconds() / 60).alias("lead_min"),
                          (pl.col("pa_line") == pl.col("close_line")).alias("same_line"),
                          (pl.col("pa_over") - pl.col("close_odds")).abs().alias("over_diff"))


def report(j: pl.DataFrame) -> str:
    lines = ["# SportsGameOdds close vs our last pre-kickoff ParlayAPI snapshot", "",
             f"Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/sgo_check.py`. Descriptive "
             "check of a data source (docs/sgo_closes.md); not a test of any betting rule.", ""]
    if not j.height:
        return "\n".join(lines + ["No overlapping props yet."]) + "\n"
    lines += ["| Snapshot lead before kickoff | Book | Props | SGO close missing | Same line | Same line and over price within 10 cents |",
              "|---|---|---|---|---|---|"]
    for lo, hi, lab in BUCKETS:
        for b in ("dk", "fd"):
            x = j.filter(pl.col("book") == b, pl.col("lead_min") >= lo, pl.col("lead_min") < hi)
            if not x.height:
                continue
            has = x.filter(pl.col("close_line").is_not_null())
            same = has.filter(pl.col("same_line"))
            close_px = same.filter(pl.col("over_diff") <= 10)
            pct = lambda a, n: f"{a}/{n} ({100 * a / n:.1f}%)" if n else "-"
            lines.append(f"| {lab} | {b.upper()} | {x.height} | {x.height - has.height} | {pct(same.height, has.height)} "
                         f"| {pct(close_px.height, has.height)} |")
    lines += ["", "Price gap is the plain difference of American odds on the over (both sides of +-100 are rare in "
              "these markets; a pair straddling +-100 counts as more than 10 apart).",
              "", "Games covered: " + ", ".join(sorted(set(j["game"].to_list())))[:2000]]
    return "\n".join(lines) + "\n"


def main() -> None:
    j = check()
    if j.height:
        j.drop("kick", "snap").write_csv(OUT)
    DOC.write_text(report(j))
    print(DOC.read_text())


if __name__ == "__main__":
    main()
