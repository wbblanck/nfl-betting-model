"""Turn the raw PinnRadar harvest (scripts/fetch/pinnradar_harvest.py) into tidy price-change tables. Record only.

  python scripts/fetch/pinnradar_tidy.py            # reads data/pinnacle/radar/*/, writes data/pinnacle/radar/tidy/

Replays every full board and 20-60 s delta (prematch and live boards) in time order. A delta event replaces that
event's stored state (deltas carry whole events). A row is written only when a quote differs from the last one seen
for the same key, so each table is a line history: first row = first seen, last row before kickoff = Pinnacle's close.
  game_lines.csv.gz  t, board, event_id, league, home, away, starts, period, market (money_line|spreads|totals|
                     team_total_home|team_total_away), line, price_a, price_b, max  (a/b = home/away or over/under;
                     spreads line is the home handicap)
  specials.csv.gz    t, board, event_id, parent_id, league, home, away, starts, category, special, units, mkt_type,
                     outcome, points, price, max_risk
Prices are decimal, as served. Nothing is de-vigged here.
"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import re
from pathlib import Path

ROOT = Path("data/pinnacle/radar")
OUT = ROOT / "tidy"
GAME_COLS = ["t", "board", "event_id", "league", "home", "away", "starts", "period", "market", "line",
             "price_a", "price_b", "max"]
SPEC_COLS = ["t", "board", "event_id", "parent_id", "league", "home", "away", "starts", "category", "special",
             "units", "mkt_type", "outcome", "points", "price", "max_risk"]


def snapshots():
    """Yield (t, board, events) in time order over every job folder."""
    items = []
    for d in sorted(glob.glob(str(ROOT / "2*"))):
        d = Path(d)
        for f in d.glob("*full_*.json.gz"):
            board = "live" if f.name.startswith("live_") else "prematch"
            items.append((re.search(r"(\d{8}T\d{6}Z)", f.name).group(1), board, f, None))
        for board in ("prematch", "live"):
            f = d / f"{board}_deltas.jsonl.gz"
            if f.exists():
                with gzip.open(f, "rt") as fh:
                    for i, line in enumerate(fh):
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue          # a line cut by a cancelled job
                        items.append((rec["t"], board, None, rec["events"]))
    items.sort(key=lambda x: (x[0], x[2] is None))   # a full board before a delta of the same second
    for t, board, f, evs in items:
        if f is not None:
            with gzip.open(f, "rt") as fh:
                evs = json.load(fh).get("events", [])
        yield t, board, evs


def game_rows(e: dict):
    for pk, p in (e.get("periods") or {}).items():
        per = p.get("number", pk)
        ml = p.get("money_line") or {}
        if ml:
            yield (per, "money_line", "", ml.get("home"), ml.get("away"), (p.get("meta") or {}).get("max_money_line"))
        for v in (p.get("spreads") or {}).values():
            yield (per, "spreads", v.get("hdp"), v.get("home"), v.get("away"), v.get("max"))
        for v in (p.get("totals") or {}).values():
            yield (per, "totals", v.get("points"), v.get("over"), v.get("under"), v.get("max"))
        tts = p.get("team_totals") or {}
        for side in ("home", "away"):
            for v in (tts.get(side) or {}).values():
                yield (per, f"team_total_{side}", v.get("points"), v.get("over"), v.get("under"), v.get("max"))


def special_rows(e: dict):
    for pk, mkts in (e.get("special_markets") or {}).items():
        for m in mkts or []:
            for pr in m.get("prices") or []:
                yield (m.get("type"), pr.get("name"), pr.get("points"), pr.get("price"), m.get("max_risk"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seen: dict = {}
    n_g = n_s = 0
    with gzip.open(OUT / "game_lines.csv.gz", "wt", newline="") as fg, \
            gzip.open(OUT / "specials.csv.gz", "wt", newline="") as fs:
        wg, ws = csv.writer(fg), csv.writer(fs)
        wg.writerow(GAME_COLS); ws.writerow(SPEC_COLS)
        for t, board, evs in snapshots():
            for e in evs:
                base = [e.get("event_id")]
                info = [e.get("league_name"), e.get("home"), e.get("away"), e.get("starts")]
                if e.get("parent_id") is None and e.get("periods"):
                    for per, mk, line, a, b, mx in game_rows(e):
                        k = (board, e["event_id"], per, mk, line)
                        if seen.get(k) != (a, b, mx):
                            seen[k] = (a, b, mx)
                            wg.writerow([t, board, *base, *info, per, mk, line, a, b, mx]); n_g += 1
                if e.get("special_markets"):
                    for typ, name, pts, price, mx in special_rows(e):
                        k = (board, e["event_id"], typ, name, pts)
                        if seen.get(k) != (price, mx):
                            seen[k] = (price, mx)
                            ws.writerow([t, board, *base, e.get("parent_id"), *info, e.get("special_category"),
                                         e.get("special"), e.get("special_units"), typ, name, pts, price, mx]); n_s += 1
    print(f"game line changes {n_g}, special changes {n_s} -> {OUT}")


if __name__ == "__main__":
    main()
