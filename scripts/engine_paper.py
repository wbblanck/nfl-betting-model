"""Engine paper fills at Novig for one 2026 week (docs/engine/paper_rules.md). Paper only, labeled unvalidated.

  python scripts/engine_paper.py 11       fills and grades week 11; needs that week's Test M forecasts first
                                          (their saved nflverse inputs are reused). Writes data/live/engine_paper/
                                          2026_w11/fills.csv and forecasts/, then data/live/engine_paper/summary.json

Steps: every recorded Novig snapshot with books -> quote rows (engine/quotes.py: exact match, roster-resolved,
fresh, pregame fee) for the week's games and the six markets at 1,000 contracts -> per contract the last book
before kickoff -> per game, forecasts rebuilt with the latest injury snapshot at or before each book's fetch time
(scripts/engine_forecast.py --book-cutoffs) -> engine.paper.choose per engine -> graded from nflverse.
"""
import collections
import datetime as dt
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import polars as pl

import engine_novig_quotes as NQ
import engine_test_m as TM
from nflbet.config import ROOT
from nflbet.engine import forecast as FO, paper as PP, quotes as Q, scoring as S
from nflbet.engine.data import nflverse as N, player_week as PW
from nflbet.sources import ids

OUT = ROOT / "data" / "live" / "engine_paper"
BOOKS = ROOT / "data" / "live" / "novig_books"
INJ = ROOT / "data" / "live" / "injuries"


def game_ids(week: int) -> dict:
    """Test M game_id -> (game key 'BUF|NYJ', kickoff ET) for the week's forecast games."""
    man = json.loads((TM.FC / f"{TM.SEASON}_w{week:02d}" / "manifest.json").read_text())
    out = {}
    for g, u in man["games"].items():
        _, _, away, home = g.split("_")
        out[g] = (ids.game_key(NQ.fix(away), NQ.fix(home)), u["kickoff_et"])
    return out


def last_books(week: int) -> pl.DataFrame:
    """Quote rows at SIZE for the week's games, keeping per contract the last book before kickoff."""
    games = game_ids(week)
    keys = {k: g for g, (k, _) in games.items()}
    rows = []
    for stamp in sorted(p.name for p in BOOKS.iterdir() if p.is_dir()):
        summ = json.loads((BOOKS / stamp / "summary.json").read_text())
        if summ.get("books_saved", 0) == 0:
            continue
        snap = Q.load(BOOKS / stamp)
        saved = ROOT / "data" / "live" / "novig_quotes" / stamp / "rosters.json.gz"
        ros = json.load(gzip.open(saved, "rt"))["rosters"] if saved.exists() else NQ.rosters_for(snap, TM.SEASON)[0]
        if not any(k in ros for k in keys):
            continue
        q, _ = Q.quotes(snap, ros)
        rows += [r for r in q if r["game"] in keys and r["market"] in FO.MARKETS and r["size"] == PP.SIZE]
    if not rows:
        return pl.DataFrame()
    df = pl.DataFrame(rows, infer_schema_length=None).with_columns(pl.col("game").replace_strict(keys).alias("game_id"))
    last = df.group_by("market_id").agg(pl.col("book_fetched_utc").max().alias("_last"))
    return df.join(last, on="market_id").filter(pl.col("book_fetched_utc") == pl.col("_last")).drop("_last")


def forecasts_for(week: int, books: pl.DataFrame, out: Path) -> dict:
    """(game_id, injury snapshot) -> forecasts.parquet path, running the forecaster once per needed snapshot set."""
    games = game_ids(week)
    names = sorted(p.name for p in INJ.glob("*.json.gz"))
    need = collections.defaultdict(set)                       # game -> injury snapshots needed by its books
    for g, t in books.select("game_id", "book_fetched_utc").unique().iter_rows():
        snap = FO.snapshot_at_or_before(names, games[g][1], dt.datetime.fromisoformat(t.replace("Z", "+00:00")))
        if snap is not None:
            need[g].add(snap)
    paths, r = {}, 0
    while any(need.values()):
        cut = {g: sorted(s)[0] for g, s in need.items() if s}
        run = out / f"run{r}"
        run.mkdir(parents=True, exist_ok=True)
        (run / "cutoffs.json").write_text(json.dumps({g: FO.stamp_utc(n).isoformat() for g, n in cut.items()}, indent=1))
        env = {**os.environ, "PYTHONPATH": str(ROOT / "scripts")}
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "engine_forecast.py"), str(TM.SEASON), str(week),
                             f"--book-cutoffs={run / 'cutoffs.json'}", f"--out={run}",
                             f"--inputs={TM.FC / f'{TM.SEASON}_w{week:02d}' / 'inputs'}"], env=env).returncode
        if rc != 0:
            raise SystemExit(f"forecaster refused for paper run {r}")
        for g, n in cut.items():
            paths[(g, n)] = run / "forecasts.parquet"
            need[g].discard(n)
        r += 1
    return paths


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    week = int(sys.argv[1])
    out = OUT / f"{TM.SEASON}_w{week:02d}"
    books = last_books(week)
    fills = []
    if books.height:
        paths = forecasts_for(week, books, out / "forecasts")
        games = game_ids(week)
        names = sorted(p.name for p in INJ.glob("*.json.gz"))
        import nflreadpy as nr
        pw, _ = PW.build(nr.load_player_stats([TM.SEASON]), nr.load_snap_counts([TM.SEASON]), N.read("players"))
        pw = pw.filter(pl.col("week") == week)
        cache = {}
        for (mid,), c in books.group_by(["market_id"], maintain_order=True):
            r0 = c.row(0, named=True)
            snap = FO.snapshot_at_or_before(names, games[r0["game_id"]][1],
                                            dt.datetime.fromisoformat(r0["book_fetched_utc"].replace("Z", "+00:00")))
            path = paths.get((r0["game_id"], snap))
            if path is None:
                continue
            if path not in cache:
                cache[path] = pl.read_parquet(path)
            fc = cache[path]
            side = {r["side"]: r for r in c.iter_rows(named=True)}
            line = float(r0["line"])
            y_row = pw.filter((pl.col("player_id") == r0["player_id"]) & (pl.col("game_id") == r0["game_id"]))
            y = int(y_row[FO.MARKETS[r0["market"]]][0]) if y_row.height else None
            for e in TM.ENGINES:
                h = fc.filter((pl.col("engine") == e) & (pl.col("game_id") == r0["game_id"])
                              & (pl.col("player_id") == r0["player_id"]) & (pl.col("market") == r0["market"]))
                if not h.height:
                    continue
                f = PP.choose(side.get("Over"), side.get("Under"), FO.p_over(h, line))
                if f is None:
                    continue
                res, profit = PP.settle(f["side"], line, y, f["cost"])
                fills.append({"engine": e, "week": week, "game_id": r0["game_id"], "player_id": r0["player_id"],
                              "player": r0["player_name"], "market": r0["market"], "line": line, "side": f["side"],
                              "p": round(f["p"], 4), "all_in": round(f["all_in"], 4), "edge": round(f["edge"], 4),
                              "cost": round(f["cost"], 4), "market_id": mid, "book_stamp": r0["stamp"],
                              "book_fetched_utc": r0["book_fetched_utc"], "injury_snapshot": snap,
                              "minutes_before_start": r0["minutes_before_start"], "result": res, "profit": round(profit, 4)})
    out.mkdir(parents=True, exist_ok=True)
    schema = {"engine": pl.Utf8, "week": pl.Int64, "game_id": pl.Utf8, "player_id": pl.Utf8, "player": pl.Utf8,
              "market": pl.Utf8, "line": pl.Float64, "side": pl.Utf8, "p": pl.Float64, "all_in": pl.Float64,
              "edge": pl.Float64, "cost": pl.Float64, "market_id": pl.Utf8, "book_stamp": pl.Utf8, "book_fetched_utc": pl.Utf8,
              "injury_snapshot": pl.Utf8, "minutes_before_start": pl.Float64, "result": pl.Utf8, "profit": pl.Float64}
    pl.DataFrame(fills, schema=schema).write_csv(out / "fills.csv")
    (out / "books.json").write_text(json.dumps({"contracts_with_a_book": books["market_id"].n_unique() if books.height else 0,
                                                "games_with_a_book": books["game_id"].n_unique() if books.height else 0}, indent=1) + "\n")
    print(summary())
    return 0


def summary() -> str:
    """Season-to-date per engine and per week, from every fills.csv; writes summary.json."""
    files = sorted(OUT.glob("2026_w*/fills.csv"))
    df = pl.concat([pl.read_csv(f, schema_overrides={"player_id": pl.Utf8, "market_id": pl.Utf8}) for f in files], how="diagonal_relaxed") \
        if files else pl.DataFrame()
    res = {"engines": {}, "weeks": sorted(int(f.parent.name[-2:]) for f in files)}
    for e in TM.ENGINES:
        d = df.filter(pl.col("engine") == e) if df.height else df
        n = d.height
        live = d.filter(pl.col("result") != "void") if n else d        # a void returns its cost: not staked
        cost, profit = (float(live["cost"].sum()), float(live["profit"].sum())) if n else (0.0, 0.0)
        r = {"fills": n, "void": n - live.height, "cost": cost, "profit": profit, "roi": profit / cost if cost else None,
             "mean_edge": float(d["edge"].mean()) if n else None,
             "by_week": {str(w): {"fills": g.height, "cost": float(g["cost"].sum()), "profit": float(g["profit"].sum())}
                         for (w,), g in live.group_by(["week"], maintain_order=True)} if live.height else {},
             "by_market": {m: {"fills": g.height, "cost": float(g["cost"].sum()), "profit": float(g["profit"].sum())}
                           for (m,), g in live.group_by(["market"], maintain_order=True)} if live.height else {}}
        if live.height >= 2 and live["week"].n_unique() >= 2:      # descriptive interval, week-clustered
            ratio = (live["profit"] / live["cost"]).to_numpy()
            r["roi_interval_per_fill"] = list(S.paired_bootstrap(ratio, live["week"].to_numpy(), level=0.05))
        res["engines"][e] = r
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(res, indent=1) + "\n")
    return json.dumps(res, indent=1)


if __name__ == "__main__":
    sys.exit(main())
