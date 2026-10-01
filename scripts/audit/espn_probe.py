"""Probe ESPN's APIs for what this project needs (evidence only; no outcomes read).

Questions: do ESPN's core odds carry player props (propBets) for past and current games, by which providers,
and with open/close or timestamped movement? Which gist endpoints answer from a GitHub runner (cdn.espn.com,
site.web gamelogs, core injuries / depth charts / past-performances)?

Writes docs/evidence/espn/<UTC stamp>/summary.json plus small, valid-JSON samples (lists cut to 3 items).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
WEEKS = [(2024, 6), (2025, 6), (2026, 5)]        # 2026 week 5 is upcoming: live props, if any
GAMES_PER_WEEK = 2
FOLLOW = re.compile(r"(propBets|prop|history|movement|past-performances)", re.I)


def get(url: str):
    url = url.replace("http://", "https://")
    time.sleep(0.4)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read()
            try:
                return r.status, json.loads(body), len(body)
            except ValueError:
                return r.status, None, len(body)
    except urllib.error.HTTPError as e:
        return e.code, None, 0
    except Exception as e:  # noqa: BLE001 - record and continue
        return str(e)[:80], None, 0


def trim(o, depth=0):
    if isinstance(o, list):
        return [trim(x, depth + 1) for x in o[:3]] + ([f"... {len(o) - 3} more"] if len(o) > 3 else [])
    if isinstance(o, dict):
        return {k: trim(v, depth + 1) for k, v in o.items()} if depth < 8 else "..."
    return o


def refs(o) -> list[str]:
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "$ref" and isinstance(v, str):
                out.append(v)
            else:
                out += refs(v)
    elif isinstance(o, list):
        for v in o:
            out += refs(v)
    return out


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/espn") / stamp
    out.mkdir(parents=True, exist_ok=True)
    summary = {"stamp": stamp, "games": [], "other": []}

    def save(name, data):
        (out / f"{name}.json").write_text(json.dumps(trim(data), indent=1)[:300_000])

    for season, week in WEEKS:
        st, ev, _ = get(f"{CORE}/seasons/{season}/types/2/weeks/{week}/events?limit=50")
        ids = [re.search(r"events/(\d+)", r["$ref"]).group(1) for r in (ev or {}).get("items", [])][:GAMES_PER_WEEK]
        for eid in ids:
            g = {"season": season, "week": week, "event": eid, "providers": [], "followed": []}
            st, odds, n = get(f"{CORE}/events/{eid}/competitions/{eid}/odds?limit=100")
            g["odds_status"] = st
            save(f"odds_{season}w{week}_{eid}", odds or {})
            for item in (odds or {}).get("items", []):
                it = item if "provider" in item else (get(item["$ref"])[1] or {})
                prov = it.get("provider") or {}
                pid = prov.get("id")
                p = {"id": pid, "name": prov.get("name"), "has_open": "open" in json.dumps(it)[:20000],
                     "has_close": '"close"' in json.dumps(it), "keys": sorted(it.keys())[:30]}
                # propBets: by link if present, else the usual core pattern
                links = [r for r in refs(it) if FOLLOW.search(r)]
                if pid is not None:
                    links.append(f"{CORE}/events/{eid}/competitions/{eid}/odds/{pid}/propBets?limit=1000")
                    links.append(f"{CORE}/events/{eid}/competitions/{eid}/odds/{pid}/history/0/movement?limit=100")
                for url in dict.fromkeys(links):
                    st2, body, n2 = get(url)
                    rec = {"provider": prov.get("name"), "url": url, "status": st2, "bytes": n2,
                           "count": (body or {}).get("count") if isinstance(body, dict) else None}
                    if isinstance(body, dict) and body.get("items"):
                        first = body["items"][0]
                        rec["first_item_keys"] = sorted(first.keys())[:40] if isinstance(first, dict) else str(first)[:200]
                        rec["first_item"] = trim(first)
                        save(f"follow_{season}w{week}_{eid}_{pid}_{len(g['followed'])}", body)
                    g["followed"].append(rec)
                g["providers"].append(p)
            summary["games"].append(g)
            print(f"{season} w{week} event {eid}: odds {g['odds_status']}, providers "
                  f"{[p['name'] for p in g['providers']]}", flush=True)
            for f in g["followed"]:
                if f["status"] == 200:
                    print(f"   200 {f['bytes']:7d}B count={f['count']} {f['url'].split('/odds/')[-1][:70]}", flush=True)
    # other gist endpoints: reachability only
    eid = summary["games"][0]["event"] if summary["games"] else "401671651"
    for name, url in {
        "cdn_boxscore": f"https://cdn.espn.com/core/nfl/boxscore?xhr=1&gameId={eid}",
        "cdn_schedule": "https://cdn.espn.com/core/nfl/schedule?xhr=1&year=2025&week=6",
        "site_api_scoreboard": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2025&seasontype=2&week=6",
        "site_web_gamelog": "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/3139477/gamelog",
        "core_injuries_KC": f"{CORE}/teams/12/injuries?limit=100",
        "core_depthcharts_KC": f"{CORE}/seasons/2026/teams/12/depthcharts",
        "core_past_performances_KC": f"{CORE}/teams/12/odds/1002/past-performances?limit=200",
        "core_ats_KC_2025": f"{CORE}/seasons/2025/types/2/teams/12/ats",
    }.items():
        st, body, n = get(url)
        summary["other"].append({"name": name, "url": url, "status": st, "bytes": n})
        if body is not None:
            save(f"other_{name}", body)
        print(f"{name}: {st} {n}B", flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print("wrote", out)


if __name__ == "__main__":
    main()
