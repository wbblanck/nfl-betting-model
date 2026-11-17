"""PinnRadar (https://pinnradar.com, a reseller of Pinnacle prices): read-only probe of NFL player props (evidence only).

Question: which NFL player props does Pinnacle post, with what lines, prices and limits (max_risk), and how far ahead
of kickoff? Budget: the free key allows 100 requests a day, so this makes at most 1 board call plus PRICE_CALLS single
special calls. The key (secret PINN_API) is sent only as a request header and never written to disk.
Writes docs/evidence/pinnradar/<stamp>/summary.json and board.json.gz (the NFL part of the board only).
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://pinnradar.com"
SPORT_FOOTBALL = 5          # docs "Sport IDs": API 5 = Football (Pinnacle 15)
PRICE_CALLS = 3             # single-special calls, only if board rows carry no prices


def get(path: str, params: dict) -> tuple[int | str, dict, bytes]:
    time.sleep(3.5)  # under 20 a minute
    key = os.environ.get("PINN_API", "").strip()
    if not key:
        sys.exit("PINN_API is not set")
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-portal-apikey": key, "Accept": "application/json",
                                               "User-Agent": "nfl-betting-model-research"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, {k: v for k, v in r.headers.items() if k.lower().startswith(("x-rate", "retry", "content-type"))}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k: v for k, v in (e.headers or {}).items() if k.lower().startswith(("x-rate", "retry"))}, e.read(5000)
    except Exception as e:  # noqa: BLE001
        return str(e)[:200], {}, b""


def is_nfl(ev: dict) -> bool:
    return "nfl" in str(ev.get("league_name", "")).lower()


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/pinnradar") / stamp
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"stamp": stamp, "calls": []}

    status, headers, body = get("/kit/v1/prematch/fixtures", {"sport_id": SPORT_FOOTBALL, "include_specials": 1})
    summary["calls"].append({"path": "/kit/v1/prematch/fixtures", "status": status, "headers": headers, "bytes": len(body)})
    if status != 200:
        summary["error_body"] = body[:2000].decode("utf-8", "replace")
        (out / "summary.json").write_text(json.dumps(summary, indent=1))
        print(json.dumps(summary, indent=1))
        return
    board = json.loads(body)
    events = board.get("events", [])
    summary["leagues"] = collections.Counter(str(e.get("league_name")) for e in events).most_common()
    nfl = [e for e in events if is_nfl(e)]
    games = {e["event_id"]: e for e in nfl if not e.get("parent_id")}
    specials = [e for e in nfl if e.get("parent_id")]
    with gzip.open(out / "board.json.gz", "wt") as f:
        json.dump({k: v for k, v in board.items() if k != "events"} | {"events": nfl}, f)

    summary["nfl_games"] = [{"event_id": g["event_id"], "home": g.get("home"), "away": g.get("away"), "starts": g.get("starts"),
                             "n_specials": sum(1 for s in specials if s.get("parent_id") == g["event_id"])}
                            for g in games.values()]
    summary["n_specials"] = len(specials)
    summary["special_categories"] = collections.Counter(str(s.get("special_category")) for s in specials).most_common()
    summary["special_units"] = collections.Counter(str(s.get("special_units")) for s in specials).most_common()
    pp = [s for s in specials if s.get("special_category") == "Player Props"]
    # generic title: strip the player name (text before the first "(" or the last word group) is unknown, so keep raw
    summary["player_prop_titles_sample"] = sorted({str(s.get("special")) for s in pp})[:400]
    summary["special_row_keys"] = sorted({k for s in specials[:50] for k in s})

    priced = [s for s in pp if any((s.get("special_markets") or {}).values())]
    summary["player_props_with_prices_on_board"] = len(priced)
    risks, examples = [], []
    for s in priced:
        for per, mkts in (s.get("special_markets") or {}).items():
            for m in mkts or []:
                if m.get("max_risk") is not None:
                    risks.append(m["max_risk"])
        if len(examples) < 25:
            examples.append({k: s.get(k) for k in ("event_id", "parent_id", "home", "away", "starts", "special",
                                                  "special_category", "special_units", "special_markets")})
    summary["max_risk"] = {"n": len(risks), "min": min(risks) if risks else None, "max": max(risks) if risks else None,
                           "median": sorted(risks)[len(risks) // 2] if risks else None,
                           "counts": collections.Counter(risks).most_common(15)}
    summary["examples"] = examples

    if not priced and pp:
        summary["single_calls"] = []
        for s in pp[:PRICE_CALLS]:
            st, hd, b = get("/kit/v1/prematch/markets", {"event_id": s["event_id"]})
            summary["calls"].append({"path": "/kit/v1/prematch/markets", "status": st, "headers": hd, "bytes": len(b)})
            try:
                summary["single_calls"].append(json.loads(b))
            except ValueError:
                summary["single_calls"].append(b[:2000].decode("utf-8", "replace"))

    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: summary[k] for k in summary if k not in ("examples", "single_calls", "player_prop_titles_sample")},
                     indent=1, default=str)[:20000])


if __name__ == "__main__":
    main()
