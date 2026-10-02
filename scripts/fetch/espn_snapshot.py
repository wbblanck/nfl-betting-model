"""Snapshot ESPN injuries and depth charts for all 32 teams (current state only; ESPN keeps no history).

Writes data/espn/snapshots/<UTC stamp>.json.gz: {team_id: {"abbr", "injuries": [items], "depthcharts": obj}}.
Run on Saturdays (after Friday's final injury reports) and Sunday mornings so the projection model can later
use teammate absences that were known before kickoff.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def get(url: str):
    for i in range(3):
        time.sleep(0.25 + (2 ** i if i else 0))
        try:
            req = urllib.request.Request(url.replace("http://", "https://"), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:  # noqa: BLE001 - retried
            pass
    return None


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    season = now.year if now.month >= 3 else now.year - 1
    teams = get(f"{CORE}/teams?limit=40") or {}
    snap = {"taken_utc": now.isoformat(), "season": season, "teams": {}}
    for ref in teams.get("items", []):
        t = get(ref["$ref"]) or {}
        tid = str(t.get("id"))
        inj = get(f"{CORE}/teams/{tid}/injuries?limit=100") or {}
        items = [get(i["$ref"]) for i in inj.get("items", []) if "$ref" in i]
        snap["teams"][tid] = {"abbr": t.get("abbreviation"), "injuries": [i for i in items if i],
                              "depthcharts": get(f"{CORE}/seasons/{season}/teams/{tid}/depthcharts")}
        print(f"{t.get('abbreviation')}: injuries {len(items)}", flush=True)
    out = Path("data/espn/snapshots") / f"{now.strftime('%Y%m%dT%H%MZ')}.json.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt") as fh:
        json.dump(snap, fh)
    print("wrote", out)


if __name__ == "__main__":
    main()
