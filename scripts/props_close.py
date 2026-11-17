"""Props closing-line value record (docs/props_clv_rules.md). Record only, unvalidated; never feeds a pick.

  python scripts/props_close.py watch [--hours 5.7]   # snapshot Pinnacle + DK/FD ~20 and ~6 min before each kickoff
  python scripts/props_close.py snapshot              # one snapshot now (games kicking off within 60 minutes)
  python scripts/props_close.py fitcheck              # line-move conversion: fit weeks 5-8, check weeks 9-10 (run once)
  python scripts/props_close.py clv                   # CLV per official mix pick -> data/live/mix_clv_2026.csv, docs/props_clv.md
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

from nflbet import config
from nflbet.props import clv as C
from nflbet.quant.odds import no_vig_over
from nflbet.sources import parlay as Pa
from nflbet.sources.ids import game_key, norm_name

SEASON = 2026
LIVE = config.ROOT / "data" / "live"
CLOSE = LIVE / "close"
PINN = CLOSE / f"pinnacle_{SEASON}.csv"
BOOKS = CLOSE / f"books_{SEASON}.csv"
FIT = config.ROOT / "data" / "backtests" / "props_clv_linemove.json"
OUT = LIVE / f"mix_clv_{SEASON}.csv"
DOC = config.ROOT / "docs" / "props_clv.md"
OFFSETS = (20, 6)                   # minutes before kickoff
WINDOW_MIN = 60                     # save games kicking off within this many minutes
PARLAY_FLOOR = 200                  # skip ParlayAPI if fewer requests than this are left this month
ROW_COLS = ["snap_utc", "source", "game", "home", "away", "kickoff", "lead_min", "nkey", "player", "market", "line",
            "over_dec", "under_dec", "fair_over", "hold", "max_risk"]


# ------------------------------------------------------------------------------------------ schedule

def kickoffs(season: int = SEASON) -> pl.DataFrame:
    """Regular-season games with kickoff in UTC (nflverse schedule: gameday + gametime, US Eastern)."""
    import nflreadpy as nfl

    g = nfl.load_schedules(seasons=[season]).filter(pl.col("game_type") == "REG")
    et = ZoneInfo("America/New_York")
    ko = [dt.datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M").replace(tzinfo=et).astimezone(dt.timezone.utc)
          if d and t else None for d, t in zip(g["gameday"], g["gametime"])]
    return g.select("week", "home_team", "away_team").with_columns(pl.Series("kickoff", ko, dtype=pl.Datetime("us", "UTC")),
                                                                   pl.struct("home_team", "away_team").map_elements(
                                                                       lambda r: game_key(r["home_team"], r["away_team"]),
                                                                       return_dtype=pl.Utf8).alias("game"))


# ------------------------------------------------------------------------------------------ snapshot

def _append(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not df.height:
        return
    df = df.select(ROW_COLS)
    if path.exists() and path.stat().st_size:
        old = pl.read_csv(path, infer_schema_length=0)
        df = pl.concat([old, df.cast({c: pl.Utf8 for c in df.columns})], how="diagonal")
    df.write_csv(path)


def _with_meta(d: pl.DataFrame, source: str, when: dt.datetime, ko: dict) -> pl.DataFrame:
    rows = []
    for r in d.iter_rows(named=True):
        k = ko.get(r["game"])
        if k is None:
            continue
        lead = (k - when).total_seconds() / 60
        if not (0 < lead <= WINDOW_MIN):
            continue
        f = C.fair_over(r["over_dec"], r["under_dec"])
        rows.append({**r, "snap_utc": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "source": source,
                     "kickoff": k.strftime("%Y-%m-%dT%H:%M:%SZ"), "lead_min": round(lead, 2),
                     "fair_over": f[0] if f else None, "hold": f[1] if f else None})
    if not rows:
        return pl.DataFrame()
    out = pl.DataFrame(rows, infer_schema_length=None)
    for c in ROW_COLS:
        if c not in out.columns:
            out = out.with_columns(pl.lit(None).alias(c))
    return out


def snapshot(ko_table: pl.DataFrame | None = None) -> tuple[int, int]:
    """One snapshot now. Returns (pinnacle rows, book rows) saved. Each source fails on its own."""
    when = C.now_utc()
    kt = ko_table if ko_table is not None else kickoffs()
    ko = {r["game"]: r["kickoff"] for r in kt.drop_nulls("kickoff").iter_rows(named=True)
          if 0 < (r["kickoff"] - when).total_seconds() / 60 <= WINDOW_MIN}
    if not ko:
        print(f"{when:%H:%M} UTC: no game kicks off within {WINDOW_MIN} minutes"); return 0, 0
    n_p = n_b = 0
    try:
        board, hdr = C.fetch_pinnacle()
        d = _with_meta(C.parse_pinnacle(board), "pinnacle", when, ko)
        _append(d, PINN); n_p = d.height
        print(f"Pinnacle: {n_p} props for {len(ko)} game(s) {hdr}")
    except Exception as e:  # noqa: BLE001
        print(f"Pinnacle snapshot failed: {type(e).__name__}: {str(e)[:200]}")
    try:
        if not os.environ.get("PARLAY_API_KEY"):
            raise RuntimeError("PARLAY_API_KEY not set")
        if _parlay_low():
            raise RuntimeError(f"fewer than {PARLAY_FLOOR} ParlayAPI requests left this month; skipped to protect the trackers")
        rows, hdr = Pa.fetch()
        left = next((v for k, v in hdr.items() if "remaining" in k.lower()), None)
        pa = Pa.parse(rows)
        pa = pa.with_columns(pl.col("over").map_elements(C.american_to_dec, return_dtype=pl.Float64).alias("over_dec"),
                             pl.col("under").map_elements(C.american_to_dec, return_dtype=pl.Float64).alias("under_dec"),
                             pl.lit(None, pl.Float64).alias("max_risk"))
        parts = []
        for b in ("dk", "fd"):
            x = pa.filter(pl.col("book") == b).with_columns(pl.lit(None, pl.Utf8).alias("home"), pl.lit(None, pl.Utf8).alias("away"))
            parts.append(_with_meta(x.select("game", "home", "away", "nkey", "player", "market", "line", "over_dec",
                                             "under_dec", "max_risk"), b, when, ko))
        d = pl.concat([p for p in parts if p.height], how="diagonal") if any(p.height for p in parts) else pl.DataFrame()
        _append(d, BOOKS); n_b = d.height
        print(f"ParlayAPI: {n_b} DK/FD props; requests left {left}")
        if left is not None and str(left).isdigit() and int(left) < PARLAY_FLOOR:
            (CLOSE / "PARLAY_LOW").write_text(f"{when:%Y-%m} {left}")
    except Exception as e:  # noqa: BLE001
        print(f"ParlayAPI snapshot failed: {type(e).__name__}: {str(e)[:200]}")
    return n_p, n_b


def _parlay_low() -> bool:
    """True if an earlier snapshot this calendar month saw fewer than PARLAY_FLOOR requests left (resets monthly)."""
    f = CLOSE / "PARLAY_LOW"
    if not f.exists():
        return False
    month, _, left = f.read_text().strip().partition(" ")
    return month == f"{C.now_utc():%Y-%m}" and left.isdigit() and int(left) < PARLAY_FLOOR


def _taken(kick: dt.datetime, offset: int) -> bool:
    """A snapshot for this kickoff near this offset (+-4 min) is already saved (an overlapping run took it)."""
    if not PINN.exists() and not BOOKS.exists():
        return False
    for p in (PINN, BOOKS):
        if p.exists() and p.stat().st_size:
            d = pl.read_csv(p, infer_schema_length=0).filter(pl.col("kickoff") == kick.strftime("%Y-%m-%dT%H:%M:%SZ"))
            if d.height and (d["lead_min"].cast(pl.Float64) - offset).abs().min() <= 4:
                return True
    return False


def _commit(msg: str) -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    cmds = ["git add data/live/close", f'git commit -q -m "{msg}" || exit 0',
            'for i in 1 2 3 4; do git pull -q --rebase origin "$GITHUB_REF_NAME" && git push -q origin "HEAD:$GITHUB_REF_NAME" && break; sleep $((2**i)); done']
    subprocess.run(" && ".join(cmds[:1]) + "; " + "; ".join(cmds[1:]), shell=True, check=False)


def watch(hours: float) -> None:
    """Sleep to each kickoff's T-20 and T-6 minute marks within the next `hours`, snapshot, commit after each."""
    start = C.now_utc()
    end = start + dt.timedelta(hours=hours)
    kt = kickoffs()
    marks = sorted({(k - dt.timedelta(minutes=o), k, o) for k in kt.drop_nulls("kickoff")["kickoff"].to_list()
                    for o in OFFSETS if start - dt.timedelta(minutes=2) <= k - dt.timedelta(minutes=o) <= end
                    and k > start})
    if not marks:
        print(f"no kickoff windows between {start:%a %H:%M} and {end:%a %H:%M} UTC"); return
    print("windows:", ", ".join(f"{k:%a %H:%M} T-{o}" for _, k, o in marks))
    for at, kick, off in marks:
        wait = (at - C.now_utc()).total_seconds()
        if wait > 0:
            time.sleep(wait)
        if (kick - C.now_utc()).total_seconds() <= 60:
            print(f"{kick:%H:%M} T-{off}: too late, skipped"); continue
        if _taken(kick, off):
            print(f"{kick:%H:%M} T-{off}: already taken"); continue
        snapshot(kt)
        _commit(f"props close: {kick:%a %H:%M} T-{off}")


# ------------------------------------------------------------------------------------------ line-move check

def dkfd_pairs(weeks: range, last_only: bool) -> pl.DataFrame:
    out = []
    for f in sorted((LIVE / "parlay").glob("*.json.gz")):
        wk = int(f.name.split("_w")[-1].split(".")[0])
        if wk not in weeks:
            continue
        d = Pa.parse(json.load(gzip.open(f, "rt")))
        j = d.filter(pl.col("book") == "dk").join(d.filter(pl.col("book") == "fd"), on=["game", "nkey", "market"], suffix="_b")
        j = j.filter(pl.col("line") != pl.col("line_b")).with_columns(pl.lit(wk).alias("week"), pl.lit(f.name).alias("snap"))
        out.append(j)
    j = pl.concat(out)
    rows = []
    for r in j.iter_rows(named=True):
        fa = C.fair_over(C.american_to_dec(r["over"]), C.american_to_dec(r["under"]))
        fb = C.fair_over(C.american_to_dec(r["over_b"]), C.american_to_dec(r["under_b"]))
        if fa and fb:
            rows.append({"week": r["week"], "snap": r["snap"], "game": r["game"], "nkey": r["nkey"], "market": r["market"],
                         "line_a": r["line"], "q_a": fa[0], "line_b": r["line_b"], "q_b": fb[0]})
    p = pl.DataFrame(rows)
    if last_only:
        p = p.sort("snap").group_by(["week", "game", "nkey", "market"], maintain_order=True).last()
    return p


def fitcheck() -> None:
    fit = dkfd_pairs(range(5, 9), last_only=False)
    chk = dkfd_pairs(range(9, 11), last_only=True)
    res, use = {}, {}
    tot_m = tot_b = tot_n = 0.0
    for m in sorted(set(fit["market"].to_list()) | set(chk["market"].to_list())):
        s = C.fit_s(fit, m)
        mm, mb, n = C.mae(chk, m, s)
        ok = s is not None and n >= 30 and mm < mb
        res[m] = {"s": s, "n_fit": fit.filter(pl.col("market") == m).height, "n_check": n, "mae_model": mm,
                  "mae_baseline": mb, "use": ok}
        if ok:
            use[m] = s
        if s is not None and n:
            tot_m += mm * n; tot_b += mb * n; tot_n += n
    overall = {"mae_model": tot_m / tot_n, "mae_baseline": tot_b / tot_n, "n": int(tot_n)} if tot_n else {}
    if not overall or overall["mae_model"] >= overall["mae_baseline"]:
        use = {}                    # overall fail: no market converts
    FIT.write_text(json.dumps({"rules": "docs/props_clv_rules.md", "fit_weeks": "5-8", "check_weeks": "9-10",
                               "markets": res, "overall": overall, "use": use, "run_utc": f"{C.now_utc():%Y-%m-%dT%H:%M:%SZ}"},
                              indent=1))
    print(json.dumps({"markets": res, "overall": overall, "use": use}, indent=1))


# ------------------------------------------------------------------------------------------ CLV

def clv() -> None:
    rec_p = LIVE / f"mix_record_{SEASON}.csv"
    if not rec_p.exists():
        print("no mix record"); return
    rec = pl.read_csv(rec_p, infer_schema_length=0)
    rec = rec.with_columns(pl.struct("home", "away").map_elements(lambda r: game_key(r["home"], r["away"]),
                                                                  return_dtype=pl.Utf8).alias("game"),
                           pl.col("player").map_elements(norm_name, return_dtype=pl.Utf8).alias("nkey"))
    parts = [pl.read_csv(p, infer_schema_length=0) for p in (PINN, BOOKS) if p.exists() and p.stat().st_size]
    if not parts:
        print("no close snapshots yet"); closes = pl.DataFrame(schema={c: pl.Utf8 for c in ROW_COLS})
    else:
        closes = pl.concat(parts, how="diagonal")
    closes = closes.with_columns(pl.col("lead_min").cast(pl.Float64), pl.col("line").cast(pl.Float64),
                                 pl.col("fair_over").cast(pl.Float64)).drop_nulls("fair_over")
    last = C.last_close(closes) if closes.height else closes
    s_use = json.loads(FIT.read_text()).get("use", {}) if FIT.exists() else {}
    out = C.pick_clv(rec, last, s_use) if last.height else pl.DataFrame()
    if out.height:
        out.write_csv(OUT)
    sm = C.summary(out) if out.height else pl.DataFrame()
    names = {"pinnacle": "Pinnacle", "dk": "DraftKings", "fd": "FanDuel"}
    lines = [f"# Props mix closing-line value, {SEASON}", "",
             "Rules: docs/props_clv_rules.md. **Record only, unvalidated**; not part of any pick rule or of PR #27's test.",
             f"Updated {C.now_utc():%Y-%m-%d %H:%M} UTC. Close = last snapshot 30 minutes or less before kickoff.", "",
             "CLV = the pick's expected return at DraftKings' price if the close's no-vig chance is the truth.", ""]
    if sm.height:
        lines += ["Close | picks with a close | with CLV | mean CLV | CLV > 0 | mean CLV at best price | mean line move (pts toward pick)",
                  "---|---|---|---|---|---|---"]
        for r in sm.iter_rows(named=True):
            f = lambda v, p=True: "" if v is None else (f"{v:+.1%}" if p else f"{v:+.2f}")  # noqa: E731
            share = "" if r["share_pos"] is None else f"{r['share_pos']:.0%}"
            lines.append(f"{names.get(r['source'], r['source'])} | {r['with_close']} | {r['with_clv']} | {f(r['mean_clv'])} | {share} | "
                         f"{f(r['mean_clv_best'])} | {f(r['mean_line_move'], False)}")
    else:
        lines.append("No official pick has a close snapshot yet (snapshots start week 11).")
    DOC.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "watch":
        h = float(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 5.7
        watch(h)
    elif cmd == "snapshot":
        snapshot()
    elif cmd == "fitcheck":
        fitcheck()
    elif cmd == "clv":
        clv()
    else:
        print(__doc__)
