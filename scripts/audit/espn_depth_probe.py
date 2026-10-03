"""Probe ESPN depth charts from a runner (evidence only): every team's core depth chart, untrimmed, plus the
league injury list at the same moment, so staleness can be measured (is an Out player still listed first?).
Also records whether the site API serves a depth chart and any freshness headers."""
from __future__ import annotations

import datetime as dt
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"


def get(url: str):
    time.sleep(0.3)
    try:
        req = urllib.request.Request(url.replace("http://", "https://"), headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            hdr = {k: r.headers.get(k) for k in ("Last-Modified", "Date", "Cache-Control", "Age", "ETag")}
            return r.status, json.loads(r.read()), hdr
    except urllib.error.HTTPError as e:
        return e.code, None, {}
    except Exception as e:  # noqa: BLE001
        return str(e)[:80], None, {}


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/espn_depth") / stamp
    out.mkdir(parents=True, exist_ok=True)
    st, teams, _ = get(f"{SITE}/teams")
    tl = [t["team"] for t in teams["sports"][0]["leagues"][0]["teams"]] if teams else []
    charts, log = {}, []
    for t in tl:
        s, body, hdr = get(f"{CORE}/seasons/2026/teams/{t['id']}/depthcharts")
        charts[t["abbreviation"]] = {"id": t["id"], "status": s, "headers": hdr, "body": body}
        log.append({"team": t["abbreviation"], "id": t["id"], "status": s, **hdr})
    s2, site_dc, hdr2 = get(f"{SITE}/teams/{tl[0]['id']}/depthcharts") if tl else (None, None, {})
    s3, inj, _ = get(f"{SITE}/injuries")
    with gzip.open(out / "core_depthcharts.json.gz", "wt") as f:
        json.dump(charts, f)
    with gzip.open(out / "site_injuries.json.gz", "wt") as f:
        json.dump({"status": s3, "body": inj}, f)
    (out / "site_depthchart_sample.json").write_text(json.dumps({"status": s2, "headers": hdr2, "body": site_dc}, indent=1)[:200_000])
    (out / "log.json").write_text(json.dumps({"teams_status": st, "n_teams": len(tl), "teams": log,
                                               "site_depthchart_status": s2, "injuries_status": s3}, indent=1))
    print("teams", len(tl), "charts ok", sum(1 for v in charts.values() if v["status"] == 200), "site dc", s2, "inj", s3)


if __name__ == "__main__":
    main()
