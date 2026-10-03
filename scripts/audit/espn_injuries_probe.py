"""Probe ESPN injury statuses from a runner (evidence only): the league-wide site API list and one team's core
injury items (NYJ), saved raw so the live tracker's parser can be written against the real format."""
from __future__ import annotations

import datetime as dt
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
CORE_NYJ = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/teams/20/injuries?limit=100"


def get(url: str):
    time.sleep(0.3)
    try:
        req = urllib.request.Request(url.replace("http://", "https://"), headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # noqa: BLE001
        return str(e)[:80], None


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/espn_injuries") / stamp
    out.mkdir(parents=True, exist_ok=True)
    st, site = get(SITE)
    with gzip.open(out / "site_injuries.json.gz", "wt") as f:
        json.dump({"status": st, "body": site}, f)
    st2, lst = get(CORE_NYJ)
    items = []
    for r in (lst or {}).get("items", []):
        s, it = get(r["$ref"])
        items.append({"ref": r["$ref"], "status": s, "body": it})
    (out / "core_nyj_items.json").write_text(json.dumps({"list_status": st2, "items": items}, indent=1))
    print("site", st, "core list", st2, "items", len(items))


if __name__ == "__main__":
    main()
