"""Outliers tracker (docs/outliers_live_rules.md; CLAUDE.md sixth exception). Record only, unvalidated.

  python scripts/outliers_live.py run      # one poll if the cadence and the Pinnacle budget allow it
  python scripts/outliers_live.py grade    # CLV for rows whose game has kicked off

Files in data/live/outliers/:
  records_2026.csv   one row per side, the first time it qualified; its latest Pinnacle quote is updated until kickoff
  current.csv        what qualifies at the newest poll (dashboard list)
  opens_2026.csv     each side's Pinnacle fair when first seen (for the move column)
  pinn_calls.csv     this job's PinnRadar calls (UTC time), for the daily cap
  summary.json       weekly CLV figures for the dashboard (descriptive)
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import re
import sys
from pathlib import Path

import numpy as np
import polars as pl

from nflbet import config
from nflbet.props import clv as C
from nflbet.props import sharp_lag as S

SEASON = 2026
OUT = config.ROOT / "data" / "live" / "outliers"
REC = OUT / f"records_{SEASON}.csv"
CUR = OUT / "current.csv"
OPENS = OUT / f"opens_{SEASON}.csv"
CALLS = OUT / "pinn_calls.csv"
SUMMARY = OUT / "summary.json"
PARLAY = config.ROOT / "data" / "live" / "parlay"

DAILY_CAP = 55          # PinnRadar calls per UTC day for this job (free key: 100 in total)
NEAR_H = 3              # 15-minute polls while a kickoff is this close
FAST_MIN, SLOW_MIN = 14, 55
MIN_EDGE, MIN_GAP, MAX_HOLD = 0.03, 0.05, 0.10
BOOK_MAX_AGE = dt.timedelta(minutes=60)
LEAD = dt.timedelta(minutes=10)
CLOSE_WINDOW = dt.timedelta(minutes=30)
REC_COLS = ["side_id", "week", "first_utc", "starts", "kind", "game", "side", "venue", "best_cost", "best_depth",
            "gap_next", "venues", "pin_price", "pin_other", "fair_mult", "fair_power", "edge_mult", "edge_power", "move_pp",
            "last_pin_utc", "last_pin_price", "last_pin_other", "status", "close_fair_power", "close_fair_mult",
            "clv_power", "clv_mult"]


def ts(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(x: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))


def read(p: Path) -> pl.DataFrame:
    return pl.read_csv(p, infer_schema_length=0) if p.exists() and p.stat().st_size else pl.DataFrame()


def et_hour(t: dt.datetime) -> int:
    from zoneinfo import ZoneInfo
    return t.astimezone(ZoneInfo("America/New_York")).hour


def due(now: dt.datetime, kickoffs: list[dt.datetime], calls: list[dt.datetime]) -> tuple[bool, str]:
    """Cadence and budget (rules: every 15 min within 3 h of a kickoff, else hourly 6 AM-2 AM ET, cap per UTC day)."""
    today = [c for c in calls if c.date() == now.date()]
    if len(today) >= DAILY_CAP:
        return False, f"daily cap reached ({len(today)} calls today)"
    near = any(now < k <= now + dt.timedelta(hours=NEAR_H) for k in kickoffs)
    h = et_hour(now)
    if not near and 2 <= h < 6:
        return False, "overnight (2-6 AM ET), no kickoff within 3 h"
    gap = dt.timedelta(minutes=FAST_MIN if near else SLOW_MIN)
    last = max(calls) if calls else None
    if last and now - last < gap:
        return False, f"last poll {int((now - last).total_seconds() // 60)} min ago ({'near kickoff' if near else 'hourly'})"
    return True, "near kickoff" if near else "hourly"


def qualify(df: pl.DataFrame, now: dt.datetime) -> pl.DataFrame:
    if not df.height:
        return df
    lead = ts(now + LEAD)
    return df.filter(pl.col("venue").is_not_null(), pl.col("edge_mult") >= MIN_EDGE, pl.col("edge_power") >= MIN_EDGE,
                     pl.col("gap_next") >= MIN_GAP, pl.col("pin_hold") < MAX_HOLD,
                     pl.col("starts").is_not_null(), pl.col("starts") >= lead)


def book_snapshot(now: dt.datetime) -> tuple[str | None, str]:
    files = sorted(PARLAY.glob("*.json.gz"))
    if not files:
        return None, "no ParlayAPI snapshot"
    m = re.match(r"(\d{8}T\d{4})Z", files[-1].name)
    t = dt.datetime.strptime(m.group(1), "%Y%m%dT%H%M").replace(tzinfo=dt.timezone.utc) if m else None
    if t is None or now - t > BOOK_MAX_AGE:
        return None, f"DK/FD snapshot {files[-1].name} older than 60 min: books left out"
    return str(files[-1]), f"DK/FD from {files[-1].name}"


def week_now(book: str | None) -> int:
    try:
        from nflbet.props.live import current_week
        w = current_week(SEASON)
        if w:
            return w
    except Exception as e:  # noqa: BLE001
        print(f"schedule unavailable: {e!r}"[:160])
    files = sorted(PARLAY.glob("*_w*.json.gz"))
    m = re.search(r"_w(\d+)", files[-1].name) if files else None
    return int(m.group(1)) if m else 0


def update_records(rec: pl.DataFrame, allq: pl.DataFrame, new: pl.DataFrame, now: dt.datetime, week: int) -> pl.DataFrame:
    """Add first-time qualifiers; refresh the latest Pinnacle quote of every open record seen at this poll."""
    seen = set(rec["side_id"].to_list()) if rec.height else set()
    add = new.filter(~pl.col("side_id").is_in(list(seen))) if new.height else new
    rows = rec.to_dicts() if rec.height else []
    for r in add.to_dicts():
        rows.append({c: None for c in REC_COLS} | {k: (None if r.get(k) is None else str(r[k])) for k in REC_COLS if k in r}
                    | {"week": str(week), "first_utc": ts(now), "status": "open"})
    q = {r["side_id"]: r for r in allq.to_dicts()} if allq.height else {}
    for r in rows:
        if r["status"] == "open" and r["side_id"] in q and parse(r["starts"]) > now:
            p = q[r["side_id"]]
            r.update(last_pin_utc=ts(now), last_pin_price=str(p["pin_price"]), last_pin_other=str(p["pin_other"]))
    return pl.DataFrame(rows, schema={c: pl.Utf8 for c in REC_COLS}) if rows else pl.DataFrame(schema={c: pl.Utf8 for c in REC_COLS})


def grade_rows(rec: pl.DataFrame, now: dt.datetime) -> pl.DataFrame:
    """Close = last Pinnacle quote of the same contract taken by this job, at most 30 min before kickoff."""
    out = []
    for r in rec.to_dicts():
        if r["status"] == "open" and parse(r["starts"]) <= now:
            last = parse(r["last_pin_utc"]) if r.get("last_pin_utc") else None
            if last is None or parse(r["starts"]) - last > CLOSE_WINDOW:
                r["status"] = "no close"
            else:
                a, b, cost = float(r["last_pin_price"]), float(r["last_pin_other"]), float(r["best_cost"])
                fp, fm = S.devig_power(a, b), S.devig_mult(a, b)
                r.update(status="graded", close_fair_power=f"{fp:.6f}", close_fair_mult=f"{fm:.6f}",
                         clv_power=f"{fp / cost - 1:.6f}", clv_mult=f"{fm / cost - 1:.6f}")
        out.append(r)
    return pl.DataFrame(out, schema={c: pl.Utf8 for c in REC_COLS}) if out else rec


def week_clustered_ci(d: pl.DataFrame, reps: int = 4000, seed: int = 7) -> tuple[float, float] | None:
    weeks = d["week"].unique().to_list()
    if len(weeks) < 2:
        return None
    rng = np.random.default_rng(seed)
    by = {w: d.filter(pl.col("week") == w)["clv"].to_numpy() for w in weeks}
    ms = []
    for _ in range(reps):
        pick = rng.choice(weeks, len(weeks), replace=True)
        v = np.concatenate([by[w] for w in pick])
        ms.append(v.mean())
    return float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))


def summarize(rec: pl.DataFrame) -> dict:
    g = rec.filter(pl.col("status") == "graded").with_columns(pl.col("clv_power").cast(pl.Float64).alias("clv")) if rec.height else pl.DataFrame()
    s = {"recorded": rec.height, "graded": g.height if g.height else 0,
         "no_close": rec.filter(pl.col("status") == "no close").height if rec.height else 0,
         "open": rec.filter(pl.col("status") == "open").height if rec.height else 0, "by_week": {}}
    if g.height:
        s.update(mean_clv=float(g["clv"].mean()), share_pos=float((g["clv"] > 0).mean()), ci=week_clustered_ci(g))
        for w in sorted(g["week"].unique().to_list(), key=int):
            x = g.filter(pl.col("week") == w)
            s["by_week"][w] = {"n": x.height, "mean_clv": float(x["clv"].mean()), "share_pos": float((x["clv"] > 0).mean())}
    return s


def run(now: dt.datetime | None = None) -> None:
    now = now or dt.datetime.now(dt.timezone.utc)
    OUT.mkdir(parents=True, exist_ok=True)
    nev, nms, t_nv = S.novig_now()
    kick = [dt.datetime.fromtimestamp(e["startsTs"] / 1000, dt.timezone.utc) for e in nev.values()
            if e.get("status") == "OPEN_PREGAME" and e.get("startsTs")]
    calls = [parse(x) for x in read(CALLS)["utc"].to_list()] if CALLS.exists() else []
    ok, why = due(now, kick, calls)
    print(f"{ts(now)}: {'poll' if ok else 'skip'} ({why})")
    if not ok:
        return
    with open(CALLS, "a") as f:
        if not calls:
            f.write("utc\n")
        f.write(ts(now) + "\n")
    board, hdr = C.fetch_pinnacle()
    state = {e["event_id"]: e for e in board.get("events") or [] if e.get("league_name") == "NFL"}
    book, note = book_snapshot(now)
    week = week_now(book)
    shop, times = S.shop_quotes(week, book)
    print(f"Pinnacle {len(state)} NFL events {hdr}; Novig {t_nv}; {note}; week {week}")
    op = read(OPENS)
    opens = {r["side_id"]: float(r["fair_mult"]) for r in op.to_dicts()} if op.height else {}
    df, _, _ = S.scan(shop, state=state, t_pin=ts(now), novig=(nev, nms, t_nv), opens=opens, keep_all=True)
    if not df.height:
        print("nothing matched")
        return
    newo = df.filter(~pl.col("side_id").is_in(list(opens))).select("side_id", "fair_mult").unique("side_id")
    if newo.height:
        with OPENS.open("a") as f:
            newo.with_columns(pl.lit(ts(now)).alias("utc")).select("side_id", "utc", "fair_mult").write_csv(
                f, include_header=not op.height)
    q = qualify(df, now)
    q.with_columns(pl.lit(ts(now)).alias("poll_utc")).drop("venues").write_csv(CUR) if q.height else \
        pl.DataFrame({"poll_utc": [ts(now)]}).write_csv(CUR)
    rec = update_records(read(REC), df, q, now, week)
    rec.write_csv(REC)
    print(f"{df.height} sides priced, {q.height} qualify, {rec.height} recorded in total")


def grade(now: dt.datetime | None = None) -> None:
    now = now or dt.datetime.now(dt.timezone.utc)
    rec = read(REC)
    if not rec.height:
        print("no records")
        return
    rec = grade_rows(rec, now)
    rec.write_csv(REC)
    s = summarize(rec)
    SUMMARY.write_text(json.dumps(s, indent=1))
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    {"run": run, "grade": grade}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
