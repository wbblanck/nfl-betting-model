"""Live wind-unders tracker (docs/wind_live_rules.md). Runs in GitHub Actions (the sandbox cannot reach nflverse,
Open-Meteo or ESPN).

  python scripts/wind_live.py record   # before kickoff: forecast wind + DraftKings total for upcoming outdoor games
  python scripts/wind_live.py grade    # after games: grade official rows, write docs/wind_live.md
"""
from __future__ import annotations

import csv
import datetime as dt
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nflbet.execution import wind as W  # noqa: E402
from nflbet.sources.http import BROWSER_UA, RESEARCH_UA, get_json  # noqa: E402
from nflbet.sources.weather import kickoff_utc, window_mean  # noqa: E402

SEASON = 2026
START_WEEK = 9  # first week recorded live (rules committed 2026-11-05, before week 9 kicks off)
HORIZON_H = 30
FORECAST = "https://api.open-meteo.com/v1/forecast"
ODDS = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{e}/competitions/{e}/odds"
OUT = ROOT / "data" / "live" / "wind"
RECORDS = OUT / f"records_{SEASON}.csv"
REPORT = ROOT / "docs" / "wind_live.md"
FIELDS = ["run_utc", "game_id", "week", "kickoff_utc", "away_team", "home_team", "stadium_id", "roof",
          "forecast_kn", "bucket", "pick", "book", "dk_total", "over_price", "under_price", "nflverse_total", "note"]


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def stadiums() -> dict[str, tuple[float, float]]:
    with open(ROOT / "data" / "weather" / "stadiums.csv") as f:
        return {r["stadium_id"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f) if r["lat"]}


def schedule():
    import nflreadpy as nfl
    return nfl.load_schedules(seasons=[SEASON]).to_dicts()


def forecast_hourly(lat: float, lon: float, day: dt.date) -> dict[str, float]:
    q = urllib.parse.urlencode({"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "hourly": "wind_speed_10m",
                                "wind_speed_unit": "kn", "timezone": "UTC", "start_date": day.isoformat(),
                                "end_date": (day + dt.timedelta(days=1)).isoformat()})
    h = get_json(f"{FORECAST}?{q}", {"User-Agent": RESEARCH_UA}, timeout=60, pace=0.5, retries_429=4, backoff=15)["hourly"]
    return {t: v for t, v in zip(h["time"], h["wind_speed_10m"]) if v is not None}


def dk_total(espn_id: str) -> tuple[str, float | None, float | None, float | None]:
    """(book, total, over price, under price) from ESPN's odds feed: DraftKings when listed, else the first book."""
    js = get_json(ODDS.format(e=espn_id), {"User-Agent": BROWSER_UA, "Accept": "application/json"}, timeout=45)
    items = js.get("items") or []
    if not items:
        return "", None, None, None
    it = next((i for i in items if "draftkings" in (i.get("provider") or {}).get("name", "").lower()), items[0])
    num = lambda v: float(v) if v not in (None, "") else None  # noqa: E731
    return (it.get("provider") or {}).get("name", ""), num(it.get("overUnder")), num(it.get("overOdds")), \
        num(it.get("underOdds"))


def read_records() -> list[dict]:
    if not RECORDS.exists():
        return []
    with open(RECORDS) as f:
        return list(csv.DictReader(f))


def record() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    coords = stadiums()
    rows = []
    for g in schedule():
        if g.get("week") is None or g["week"] < START_WEEK or not g.get("gameday") or not g.get("gametime"):
            continue
        ko = kickoff_utc(g["gameday"], g["gametime"])
        if not W.eligible(g, now, ko, HORIZON_H):
            continue
        row = {k: "" for k in FIELDS}
        row.update(run_utc=iso(now), game_id=g["game_id"], week=g["week"], kickoff_utc=iso(ko),
                   away_team=g["away_team"], home_team=g["home_team"], stadium_id=g.get("stadium_id") or "",
                   roof=g.get("roof") or "", nflverse_total=g.get("total_line") if g.get("total_line") is not None else "")
        notes = []
        w = None
        if row["stadium_id"] in coords:
            try:
                lat, lon = coords[row["stadium_id"]]
                w = window_mean(forecast_hourly(lat, lon, ko.date()), ko)
            except Exception as e:  # noqa: BLE001 - a failed fetch is recorded, never guessed
                notes.append(f"forecast error: {type(e).__name__}")
        else:
            notes.append("no stadium coordinates")
        if w is not None:
            row.update(forecast_kn=round(w, 2), bucket=W.bucket(w), pick="under" if W.is_pick(w) else "")
        if g.get("espn"):
            try:
                book, tot, op, up = dk_total(str(g["espn"]))
                row.update(book=book, dk_total="" if tot is None else tot, over_price="" if op is None else op,
                           under_price="" if up is None else up)
            except Exception as e:  # noqa: BLE001
                notes.append(f"odds error: {type(e).__name__}")
        else:
            notes.append("no ESPN id")
        row["note"] = "; ".join(notes)
        rows.append(row)
        print(row)
    OUT.mkdir(parents=True, exist_ok=True)
    new = not RECORDS.exists()
    with open(RECORDS, "a", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            wr.writeheader()
        wr.writerows(rows)
    print(f"recorded {len(rows)} games, {sum(r['pick'] == 'under' for r in rows)} picks")


def fnum(x) -> float | None:
    return float(x) if x not in (None, "") else None


def grade_rows(off: list[dict], games: dict[str, dict]) -> list[dict]:
    out = []
    for r in off:
        g = games.get(r["game_id"], {})
        r = dict(r)
        line = fnum(r["dk_total"])
        price = fnum(r["under_price"])
        if line is None:
            line, price, r["line_src"] = fnum(r["nflverse_total"]), None, "nflverse at -110"
        else:
            r["line_src"] = r["book"] or "book"
        hs, as_ = g.get("home_score"), g.get("away_score")
        if hs is None or as_ is None:
            r["result"], r["units"] = "", ""
        elif (g.get("roof") or "") not in W.ROOFS:
            r["result"], r["units"] = "void (roof)", 0.0
        elif line is None or r["forecast_kn"] == "":
            r["result"], r["units"] = "void (no line or wind)", 0.0
        else:
            r["points"] = hs + as_
            r["result"], r["units"] = W.grade(hs + as_, line, price)
        r["line"] = line
        out.append(r)
    return out


def summary(rows: list[dict]) -> tuple[int, int, int, float]:
    w = sum(r["result"] == "W" for r in rows)
    l_ = sum(r["result"] == "L" for r in rows)
    p = sum(r["result"] == "P" for r in rows)
    u = sum(float(r["units"]) for r in rows if r["result"] in ("W", "L", "P"))
    return w, l_, p, u


def grade() -> None:
    games = {g["game_id"]: g for g in schedule()}
    graded = grade_rows(W.official(read_records()), games)
    picks = [r for r in graded if r["pick"] == "under"]
    done = [r for r in picks if r["result"] in ("W", "L", "P")]
    w, l_, p, u = summary(done)
    n = w + l_
    lines = ["# Live wind unders (unvalidated)", "",
             "Rules: docs/wind_live_rules.md. **Not validated:** the 2000-2014 test FAILED (docs/wind_totals_report.md). "
             "This page records the frozen rule on games after the rules were committed and is graded on final scores.",
             f"Updated {iso(dt.datetime.now(dt.timezone.utc))}.", "",
             "## Record (official picks, 8 <= forecast wind < 15 knots)", ""]
    if n:
        lines += [f"**{w}-{l_}-{p}**, under rate {w / n:.3f} (break-even {W.BREAK_EVEN:.4f}), units {u:+.2f}, "
                  f"ROI {u / (n + p):+.1%}. Interim one-sided binomial p = {W.binom_p_greater(w, n):.3f} "
                  "(descriptive; the verdict is at the end of the sample in the rules)."]
    else:
        lines += ["No graded picks yet."]
    lines += ["", "## By week", "", "| week | W | L | P | units |", "|---|---|---|---|---|"]
    for wk in sorted({int(r["week"]) for r in done}):
        a = summary([r for r in done if int(r["week"]) == wk])
        lines.append(f"| {wk} | {a[0]} | {a[1]} | {a[2]} | {a[3]:+.2f} |")
    lines += ["", "## Every official pick", "",
              "| week | game | kickoff (UTC) | forecast kn | line | under price | source | points | result | units |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in picks:
        lines.append(f"| {r['week']} | {r['away_team']} @ {r['home_team']} | {r['kickoff_utc']} | {r['forecast_kn']} | "
                     f"{r['line'] if r['line'] is not None else ''} | {r['under_price']} | {r['line_src']} | "
                     f"{r.get('points', '')} | {r['result'] or 'pending'} | {r['units']} |")
    lines += ["", "## Descriptive: every recorded outdoor game by forecast bucket (not picks)", "",
              "| bucket | graded | unders | pushes |", "|---|---|---|---|"]
    for b in ("calm <8", "moderate 8-15", "strong 15+"):
        rs = [r for r in graded if r["bucket"] == b and r["result"] in ("W", "L", "P")]
        lines.append(f"| {b} | {len(rs)} | {sum(r['result'] == 'W' for r in rs)} | {sum(r['result'] == 'P' for r in rs)} |")
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))


if __name__ == "__main__":
    {"record": record, "grade": grade}[sys.argv[1]]()
