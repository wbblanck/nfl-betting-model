"""Dry run of the best-price record (src/nflbet/bestprice.py) on live prices, without touching any S1 record.

Uses this week's DraftKings props on Action Network (both sides) as stand-in picks, fetches Action Network, Polymarket
US and Novig the way scripts/live_s1.py does, and reports coverage: how many stand-in picks each venue priced at the
same line, and how often each venue was cheapest all-in. Writes docs/evidence/bestprice_dryrun/<stamp>/.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, "src")
from nflbet import bestprice as Bp, live as Lv  # noqa: E402


def main() -> None:
    season = 2026
    week = Lv.current_week(season)
    now = dt.datetime.now(dt.timezone.utc)
    tmp = Path("data/live/tmp/an_props_dryrun.csv")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "scripts/fetch/an_props.py", "--season", str(season), "--weeks", f"{week}-{week}", "--out", str(tmp)], check=True)
    an = pl.read_csv(tmp, infer_schema_length=0)
    dk = an.filter(pl.col("book_id") == "68", pl.col("over_odds").fill_null("") != "", pl.col("under_odds").fill_null("") != "")
    dk = dk.filter(pl.col("start_time").map_elements(Lv.parse_ts, return_dtype=pl.Datetime("us", "UTC")) > now)
    picks = pl.concat([dk.with_columns(pl.lit(s).alias("side"), pl.col(f"{s}_odds").cast(pl.Float64).alias("odds")) for s in ("over", "under")])
    picks = picks.select("week", "an_game_id", "start_time", "home", "away", "player", pl.col("an_player_id").alias("player_id"),
                         "market", pl.col("line").cast(pl.Float64), "side", "odds")
    rows = Bp.record(picks, tmp, None, week, now)
    n = rows.height
    has = collections.Counter(v for s in rows["venues"].to_list() for v in json.loads(s))
    best = collections.Counter(rows["best_venue"].drop_nulls().to_list())
    beat = rows.filter(pl.col("edge_cents") > 0.005)
    out = {"run_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "week": week, "stand_in_picks": n,
           "priced_by_venue": dict(has.most_common()), "cheapest_by_venue": dict(best.most_common()),
           "beat_dk": beat.height, "edge_cents_median_when_beat": float(beat["edge_cents"].median()) if beat.height else None,
           "edge_cents_mean_all": float(rows["edge_cents"].mean()) if n else None}
    p = Path(f"docs/evidence/bestprice_dryrun/{now.strftime('%Y%m%dT%H%M%SZ')}")
    p.mkdir(parents=True, exist_ok=True)
    rows.write_csv(p / "rows.csv")
    (p / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    for r in rows.sort("edge_cents", descending=True).head(10).iter_rows(named=True):
        print(f"  {r['player']:24s} {r['market']:12s} {r['side']:5s} {r['line']:6} DK {r['dk_odds']:+.0f} -> {r['best_venue']} {r['best_odds']:+.0f} "
              f"({r['edge_cents']:+.1f}c), {r['n_venues']} venues")


if __name__ == "__main__":
    main()
