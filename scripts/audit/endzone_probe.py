"""EndzoneAPI probe (evidence only): what a historical prop backfill would return and cost.

Schema check on ONE game (2023 week 1, DET @ KC), not analysed for any question. Steps:
  1. estimate_only for every-player props in that game (free), and for a whole season of game odds;
  2. the game's closing and opening props (10 credits each);
  3. a summary: books present per snapshot, markets, rows, which fields carry capture times, credits left.
Writes docs/evidence/endzone_probe/<UTC stamp>/. The key comes from ENDZONEAPI_API_KEY and is never written.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://mcp.endzoneapi.com/v1/"
ROOT = Path(__file__).resolve().parents[2]
GAME = "2023_01_DET_KC"


def call(tool: str, args: dict) -> tuple[int, dict, object]:
    req = urllib.request.Request(BASE + tool, data=json.dumps(args).encode(), method="POST", headers={
        "x-api-key": os.environ["ENDZONEAPI_API_KEY"], "content-type": "application/json",
        "accept": "application/json", "user-agent": "nfl-betting-model/1.0 (read-only research)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            hdr = {k.lower(): v for k, v in r.headers.items() if k.lower().startswith("x-credit")}
            return r.status, hdr, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}, e.read().decode(errors="replace")[:2000]


def walk_rows(obj):
    """Yield every dict that looks like a prop row (has a bookmaker-like key)."""
    if isinstance(obj, dict):
        if any(k in obj for k in ("bookmaker", "book")):
            yield obj
        for v in obj.values():
            yield from walk_rows(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_rows(v)


def summarize(payload) -> dict:
    rows = list(walk_rows(payload))
    books = collections.Counter(str(r.get("bookmaker", r.get("book"))) for r in rows)
    markets = collections.Counter(str(r.get("market")) for r in rows)
    keys = collections.Counter(k for r in rows for k in r)
    return {"rows": len(rows), "books": dict(books), "markets": dict(markets), "row_keys": dict(keys),
            "time_like_keys": sorted(k for k in keys if any(s in k.lower() for s in ("time", "captured", "at", "date")))}


def main() -> None:
    if not os.environ.get("ENDZONEAPI_API_KEY"):
        sys.exit("ENDZONEAPI_API_KEY not set")
    out = ROOT / "docs" / "evidence" / "endzone_probe" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    log = {}
    for name, tool, args in [
        ("estimate_game_props", "get_player_props", {"game_id": GAME, "estimate_only": True}),
        ("estimate_season_odds_2023", "get_odds", {"season": 2023, "estimate_only": True}),
        ("game_props_closing", "get_player_props", {"game_id": GAME, "snapshot_type": "closing"}),
        ("game_props_opening", "get_player_props", {"game_id": GAME, "snapshot_type": "opening"}),
    ]:
        status, hdr, body = call(tool, args)
        (out / f"{name}.json").write_text(json.dumps({"status": status, "credit_headers": hdr, "body": body},
                                                     indent=1)[:3_000_000])
        log[name] = {"status": status, "credit_headers": hdr,
                     "summary": summarize(body) if status == 200 and not args.get("estimate_only") else body}
        print(name, status, hdr, flush=True)
    (out / "summary.json").write_text(json.dumps(log, indent=1, default=str))
    print(json.dumps(log, indent=1, default=str)[:20000])


if __name__ == "__main__":
    main()
