"""Which live sources give NFL game spreads by book (evidence only): Action Network scoreboard (keyless),
ParlayAPI odds (one call), OpenMarkets exchange spreads (read-only). Writes docs/evidence/ats_live/<stamp>/."""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, {k: v for k, v in r.headers.items() if "request" in k.lower() or "limit" in k.lower()}, json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        return str(e)[:150], {}, None


def trim(o, d=0):
    if isinstance(o, list):
        return [trim(x, d + 1) for x in o[:3]]
    if isinstance(o, dict):
        return {k: trim(v, d + 1) for k, v in o.items()} if d < 7 else "..."
    return o


def main():
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/ats_live") / stamp
    out.mkdir(parents=True, exist_ok=True)
    s = {}
    st, h, an = get("https://api.actionnetwork.com/web/v2/scoreboard/nfl?season=2026&week=5&periods=event")
    g = (an or {}).get("games", [{}])[0] if an else {}
    s["an"] = {"status": st, "n_games": len((an or {}).get("games", [])), "game_keys": sorted(g.keys()),
               "markets_sample": trim(g.get("markets") or g.get("odds"))}
    (out / "an_game.json").write_text(json.dumps(trim(g), indent=1))
    key = os.environ.get("PARLAY_API_KEY")
    if key:
        st, h, po = get("https://parlay-api.com/v1/sports/americanfootball_nfl/odds?" + urllib.parse.urlencode(
            {"apiKey": key, "markets": "spreads", "oddsFormat": "american"}))
        s["parlay_odds"] = {"status": st, "headers": h, "type": type(po).__name__, "n": len(po) if isinstance(po, list) else None,
                            "sample": trim(po[:1] if isinstance(po, list) else po)}
    okey = os.environ.get("OPENMARKETS_API_KEY")
    if okey:
        import sys
        sys.path.insert(0, "src")
        from nflbet import openmarkets as Om
        rows = []
        lg = next(x for x in Om._get("/leagues", okey)["data"] if x.get("name") == "NFL")
        cs = Om._get("/contests", okey, league_id=lg["id"], limit=200)["data"]
        cs = [c for c in cs if c.get("type") != "tournament"][:2]
        for c in cs:
            for p in Om._get(f"/contests/{c['id']}/liquidity", okey)["data"]:
                if p.get("market_key") == "spread":
                    rows.append({"title": p["title"], "variable": p["variable"], "side": p["side_key"],
                                 "venues": [(v["partner_name"], v["american_odds"], round(v.get("available") or 0)) for v in p["partner_liquidities"] if v.get("actionable")]})
        s["openmarkets_spreads"] = {"n": len(rows), "venues": collections.Counter(v[0] for r in rows for v in r["venues"]).most_common(), "sample": rows[:8]}
    (out / "summary.json").write_text(json.dumps(s, indent=1, default=str))
    print(json.dumps(s, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
