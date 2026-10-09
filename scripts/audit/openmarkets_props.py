"""NFL player props on OpenMarkets (evidence only; read-only API calls, no orders, no account linking).

With OPENMARKETS_API_KEY: list leagues, this week's NFL contests, and each contest's liquidity; summarize market
keys, which are player props, which venues quote them, how many lines are actionable and how much is fillable.
The key is read from the environment and never written. Writes docs/evidence/openmarkets_props/<UTC stamp>/
summary.json and liquidity.jsonl.gz (positions as returned).
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.openmarkets.ai/flow/v1"
GAME = {"moneyline", "spread", "total"}


def get(path: str, **q):
    url = f"{BASE}{path}" + (("?" + urllib.parse.urlencode(q)) if q else "")
    time.sleep(1.0)
    req = urllib.request.Request(url, headers={"X-API-Key": os.environ["OPENMARKETS_API_KEY"], "Accept": "application/json",
                                               "User-Agent": "nfl-betting-model/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            hdr = {k: v for k, v in r.headers.items() if "limit" in k.lower() or "remaining" in k.lower()}
            return r.status, hdr, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}, (e.read()[:600].decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return str(e)[:120], {}, None


def main() -> None:
    if not os.environ.get("OPENMARKETS_API_KEY"):
        raise SystemExit("OPENMARKETS_API_KEY not set")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/openmarkets_props") / stamp
    out.mkdir(parents=True, exist_ok=True)
    s = {"stamp": stamp}
    st, hdr, lg = get("/leagues")
    s["leagues"] = {"status": st, "headers": hdr, "body": lg if not isinstance(lg, dict) else lg.get("data", lg)}
    print("leagues", st, hdr, str(lg)[:400], flush=True)
    items = (lg or {}).get("data", []) if isinstance(lg, dict) else []
    nfl = next((x for x in items if isinstance(x, dict) and "nfl" in json.dumps(x).lower() and "ncaa" not in json.dumps(x).lower()), None)
    s["nfl_league"] = nfl
    lid = (nfl or {}).get("league_id") or (nfl or {}).get("id")
    contests, cursor = [], None
    for _ in range(10):
        q = {"league_id": lid, "limit": 200} if lid else {"limit": 200}
        if cursor:
            q["cursor"] = cursor
        st, hdr, c = get("/contests", **q)
        print("contests", st, hdr, str(c)[:300], flush=True)
        if not isinstance(c, dict):
            s["contests_error"] = {"status": st, "body": c}
            break
        contests += c.get("data", [])
        pg = c.get("pagination") or {}
        cursor = pg.get("next_cursor")
        if not pg.get("has_more"):
            break
    now = dt.datetime.now(dt.timezone.utc)
    def soon(x):   # games (not season-long "tournament" contests) starting within the next 8 days
        try:
            t = dt.datetime.fromisoformat(x["starts_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError, AttributeError):
            return False
        return x.get("type") != "tournament" and now - dt.timedelta(hours=4) <= t <= now + dt.timedelta(days=8)
    up = sorted([x for x in contests if soon(x)], key=lambda x: x["starts_at"])
    s["contest_types"] = collections.Counter(x.get("type") for x in contests).most_common()
    s["contest_statuses"] = collections.Counter(x.get("status") for x in contests).most_common()
    s["n_contests"], s["n_nfl_upcoming"] = len(contests), len(up)
    s["contest_sample"] = contests[:3]
    mk, venues_by_mk, act_by_mk, avail_by_mk, players = (collections.Counter(), collections.defaultdict(collections.Counter),
                                                         collections.Counter(), collections.defaultdict(float), collections.Counter())
    per_game = []
    with gzip.open(out / "liquidity.jsonl.gz", "wt") as f:
        for x in up[:16]:
            cid = x.get("contest_id") or x.get("id")
            st, hdr, liq = get(f"/contests/{cid}/liquidity")
            pos = liq.get("data", []) if isinstance(liq, dict) else []
            n_prop = 0
            for p in pos:
                f.write(json.dumps({"contest_id": cid, **p}) + "\n")
                k = p.get("market_key")
                mk[k] += 1
                prop = k not in GAME and p.get("participant_name") and p.get("participant_name") not in (x.get("home_name"), x.get("away_name"))
                if k not in GAME:
                    n_prop += 1
                    players[p.get("participant_name")] += 1
                for v in p.get("partner_liquidities") or []:
                    if v.get("actionable"):
                        venues_by_mk[k][v.get("partner_name")] += 1
                        act_by_mk[k] += 1
                        avail_by_mk[k] += float(v.get("available") or 0)
            per_game.append({"contest_id": cid, "label": x.get("title") or x.get("contest_label"), "starts_at": x.get("starts_at"),
                             "status": st, "positions": len(pos), "non_game_positions": n_prop, "headers": hdr})
            print(cid, x.get("title"), st, len(pos), n_prop, flush=True)
    s["per_game"] = per_game
    s["market_keys"] = mk.most_common()
    s["venues_by_market"] = {k: v.most_common() for k, v in venues_by_mk.items()}
    s["actionable_quotes_by_market"] = act_by_mk.most_common()
    s["available_usd_by_market"] = dict(sorted(avail_by_mk.items(), key=lambda kv: -kv[1]))
    s["top_participants"] = players.most_common(40)
    st, hdr, m = get("/markets")
    s["markets_catalog"] = {"status": st, "body": m if not isinstance(m, dict) else m.get("data", m)}
    (out / "summary.json").write_text(json.dumps(s, indent=1, default=str))


if __name__ == "__main__":
    main()
