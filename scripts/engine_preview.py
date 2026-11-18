"""Engine paper fills, pre-game view (docs/engine/paper_rules.md, "Pre-game view"). Paper only, labeled provisional.

  python scripts/engine_preview.py           the week of the next kickoff: each engine's sides with a 0.03+ edge
                                             against the latest recorded Novig book of every game not yet started

Run after each Novig recorder run (.github/workflows/engine-preview.yml). Same machinery as the official fills
(scripts/engine_paper.py): the frozen engines, forecasts rebuilt with the latest injury snapshot at or before the
book's fetch time, engine.paper.choose at 1,000 contracts. The difference: the 2026 nflverse inputs are fetched fresh
on every run, and the book is the latest one so far, not the last before kickoff. Rows of games that have started are
kept as they stood at their last pre-game run. The official fills, graded after the week, are unchanged and are
computed only by scripts/engine_paper.py.

Writes data/live/engine_paper/2026_wNN/preview.csv (current view) and appends each run to preview_log.csv.
"""
import collections
import datetime as dt
import gzip
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import polars as pl

import engine_novig_quotes as NQ
import engine_paper as EP
import engine_test_m as TM
from nflbet.config import ROOT
from nflbet.engine import forecast as FO, paper as PP, quotes as Q
from nflbet.sources import ids

COLS = {"run_utc": pl.Utf8, "engine": pl.Utf8, "week": pl.Int64, "game_id": pl.Utf8, "kickoff_et": pl.Utf8,
        "player_id": pl.Utf8, "player": pl.Utf8, "market": pl.Utf8, "line": pl.Float64, "side": pl.Utf8, "p": pl.Float64,
        "all_in": pl.Float64, "edge": pl.Float64, "cost": pl.Float64, "market_id": pl.Utf8, "book_stamp": pl.Utf8,
        "book_fetched_utc": pl.Utf8, "injury_snapshot": pl.Utf8, "minutes_before_start": pl.Float64}


def schedule_games(sched: pl.DataFrame, now: dt.datetime) -> tuple[int | None, dict]:
    """(week of the next regular-season kickoff, {game_id: (game key, kickoff ET)} for that week)."""
    s = sched.filter(pl.col("game_type") == "REG").with_columns(
        (pl.col("gameday").cast(pl.Utf8) + " " + pl.col("gametime").fill_null("00:00")).alias("ko"))
    later = [(FO.kickoff_utc(k), w) for k, w in zip(s["ko"], s["week"]) if FO.kickoff_utc(k) > now]
    if not later:
        return None, {}
    week = min(later)[1]
    g = s.filter(pl.col("week") == week)
    return week, {gid: (ids.game_key(NQ.fix(a), NQ.fix(h)), ko) for gid, a, h, ko in zip(g["game_id"], g["away_team"], g["home_team"], g["ko"])}


def latest_books(games: dict, now: dt.datetime) -> pl.DataFrame:
    """Quote rows at SIZE for games not started, keeping per contract the latest fresh book."""
    keys = {k: g for g, (k, ko) in games.items() if FO.kickoff_utc(ko) > now}
    rows = []
    for stamp in sorted(p.name for p in EP.BOOKS.iterdir() if p.is_dir()):
        summ = json.loads((EP.BOOKS / stamp / "summary.json").read_text())
        if summ.get("books_saved", 0) == 0:
            continue
        snap = Q.load(EP.BOOKS / stamp)
        saved = ROOT / "data" / "live" / "novig_quotes" / stamp / "rosters.json.gz"
        ros = json.load(gzip.open(saved, "rt"))["rosters"] if saved.exists() else NQ.rosters_for(snap, TM.SEASON)[0]
        if not any(k in ros for k in keys):
            continue
        q, _ = Q.quotes(snap, ros)
        rows += [r for r in q if r["game"] in keys and r["market"] in FO.MARKETS and r["size"] == PP.SIZE]
    if not rows:
        return pl.DataFrame()
    df = pl.DataFrame(rows, infer_schema_length=None).with_columns(pl.col("game").replace_strict(keys).alias("game_id"))
    df = df.filter(pl.Series([dt.datetime.fromisoformat(t.replace("Z", "+00:00")) <= now for t in df["book_fetched_utc"]]))
    if not df.height:
        return df
    last = df.group_by("market_id").agg(pl.col("book_fetched_utc").max().alias("_last"))
    return df.join(last, on="market_id").filter(pl.col("book_fetched_utc") == pl.col("_last")).drop("_last")


def forecasts(week: int, games: dict, books: pl.DataFrame, work: Path) -> dict:
    """(game_id, injury snapshot) -> forecasts.parquet, one forecaster run per needed snapshot set; fresh inputs."""
    names = sorted(p.name for p in EP.INJ.glob("*.json.gz"))
    need = collections.defaultdict(set)
    for g, t in books.select("game_id", "book_fetched_utc").unique().iter_rows():
        snap = FO.snapshot_at_or_before(names, games[g][1], dt.datetime.fromisoformat(t.replace("Z", "+00:00")))
        if snap is not None:
            need[g].add(snap)
    paths, r = {}, 0
    while any(need.values()):
        cut = {g: sorted(s)[0] for g, s in need.items() if s}
        run = work / f"run{r}"
        run.mkdir(parents=True, exist_ok=True)
        (run / "cutoffs.json").write_text(json.dumps({g: FO.stamp_utc(n).isoformat() for g, n in cut.items()}))
        env = {**os.environ, "PYTHONPATH": str(ROOT / "scripts")}
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "engine_forecast.py"), str(TM.SEASON), str(week),
                             f"--book-cutoffs={run / 'cutoffs.json'}", f"--out={run}", f"--inputs={work / 'inputs'}"],
                            env=env).returncode
        if rc != 0:
            raise SystemExit(f"forecaster refused for preview run {r}")
        for g, n in cut.items():
            paths[(g, n)] = run / "forecasts.parquet"
            need[g].discard(n)
        r += 1
    return paths


def sides(week: int, games: dict, books: pl.DataFrame, paths: dict, run_utc: str) -> list[dict]:
    names = sorted(p.name for p in EP.INJ.glob("*.json.gz"))
    out, cache = [], {}
    for (mid,), c in books.group_by(["market_id"], maintain_order=True):
        r0 = c.row(0, named=True)
        snap = FO.snapshot_at_or_before(names, games[r0["game_id"]][1],
                                        dt.datetime.fromisoformat(r0["book_fetched_utc"].replace("Z", "+00:00")))
        path = paths.get((r0["game_id"], snap))
        if path is None:
            continue
        fc = cache.setdefault(path, pl.read_parquet(path))
        side = {r["side"]: r for r in c.iter_rows(named=True)}
        line = float(r0["line"])
        for e in TM.ENGINES:
            h = fc.filter((pl.col("engine") == e) & (pl.col("game_id") == r0["game_id"])
                          & (pl.col("player_id") == r0["player_id"]) & (pl.col("market") == r0["market"]))
            if not h.height:
                continue
            f = PP.choose(side.get("Over"), side.get("Under"), FO.p_over(h, line))
            if f is None:
                continue
            out.append({"run_utc": run_utc, "engine": e, "week": week, "game_id": r0["game_id"], "kickoff_et": games[r0["game_id"]][1],
                        "player_id": r0["player_id"], "player": r0["player_name"], "market": r0["market"], "line": line,
                        "side": f["side"], "p": round(f["p"], 4), "all_in": round(f["all_in"], 4), "edge": round(f["edge"], 4),
                        "cost": round(f["cost"], 4), "market_id": mid, "book_stamp": r0["stamp"],
                        "book_fetched_utc": r0["book_fetched_utc"], "injury_snapshot": snap,
                        "minutes_before_start": r0["minutes_before_start"]})
    return out


def merge(old: pl.DataFrame, new: pl.DataFrame, games: dict, now: dt.datetime) -> pl.DataFrame:
    """The current view: this run's rows, plus the rows of games that have started as they stood before kickoff."""
    if not old.height:
        return new
    started = [g for g, (_, ko) in games.items() if FO.kickoff_utc(ko) <= now]
    keep = old.filter(pl.col("game_id").is_in(started) & ~pl.col("game_id").is_in(new["game_id"].unique().to_list()))
    return pl.concat([keep.select(list(COLS)), new], how="vertical").sort("kickoff_et", "game_id", "engine", "edge", descending=[False, False, False, True])


def main(now: dt.datetime | None = None) -> int:
    import nflreadpy as nr
    now = now or dt.datetime.now(dt.timezone.utc)
    week, games = schedule_games(nr.load_schedules([TM.SEASON]), now)
    if week is None or week not in TM.WEEKS:
        print(f"no paper week ahead (next week {week})")
        return 0
    out = EP.OUT / f"{TM.SEASON}_w{week:02d}"
    run_utc = now.isoformat(timespec="seconds")
    books = latest_books(games, now)
    rows = []
    if books.height:
        with tempfile.TemporaryDirectory() as tmp:
            rows = sides(week, games, books, forecasts(week, games, books, Path(tmp)), run_utc)
    new = pl.DataFrame(rows, schema=COLS)
    out.mkdir(parents=True, exist_ok=True)
    cur = out / "preview.csv"
    old = pl.read_csv(cur, schema=COLS) if cur.exists() and cur.stat().st_size else pl.DataFrame(schema=COLS)
    merge(old, new, games, now).write_csv(cur)
    log = out / "preview_log.csv"
    prev = pl.read_csv(log, schema=COLS) if log.exists() and log.stat().st_size else pl.DataFrame(schema=COLS)
    pl.concat([prev, new], how="vertical").write_csv(log)
    (out / "preview_run.json").write_text(json.dumps({"run_utc": run_utc, "week": week, "rows": new.height,
                                                     "games_with_a_book": books["game_id"].n_unique() if books.height else 0}, indent=1) + "\n")
    print(f"week {week}: {new.height} provisional sides from {books['game_id'].n_unique() if books.height else 0} games with a book")
    return 0


if __name__ == "__main__":
    sys.exit(main())
