"""Probe api.nfldata.org from a runner (evidence only): the docs page and any OpenAPI spec, so we can see which
datasets exist (in particular defensive coverage, routes, personnel) and whether 2026 is covered. Read-only GETs."""
from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.nfldata.org"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
PATHS = ["/v1/meta", "/v1/health",
         "/v1/participation?game_id=2026_04_IND_WAS&limit=3",      # 2026 week 4
         "/v1/participation?game_id=2025_04_MIN_PIT&limit=3",      # a 2025 control game
         "/v1/participation?game_id=2025_06_PHI_MIN&limit=3",
         "/v1/charting?season=2026&week=4&limit=2",
         "/v1/stats/ngs/receiving?season=2026&week=4&limit=2",
         "/v1/plays?season=2026&week=4&limit=2",
         "/v1/games?season=2026&week=4&limit=20"]


def get(path: str):
    time.sleep(0.5)
    try:
        req = urllib.request.Request(BASE + path, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), (e.read() or b"")
    except Exception as e:  # noqa: BLE001
        return str(e)[:100], {}, b""


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/nfldata") / stamp
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    for p in PATHS:
        st, hdr, body = get(p)
        name = re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_") or "root"
        (out / f"{name}.txt").write_bytes(body[:400_000])
        summary.append({"path": p, "status": st, "bytes": len(body), "content_type": hdr.get("Content-Type"),
                        "rate_limit": {k: v for k, v in hdr.items() if "limit" in k.lower() or "retry" in k.lower()}})
        print(p, st, len(body))
    # follow script/spec links named in the docs html, if any
    try:
        html = (out / "docs.txt").read_text(errors="ignore")
        for ref in sorted(set(re.findall(r'(?:src|href)="([^"]+\.(?:json|yaml|yml|js))"', html)))[:6]:
            path = ref if ref.startswith("/") else "/" + ref
            if ref.startswith("http"):
                continue
            st, hdr, body = get(path)
            (out / ("linked_" + re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") + ".txt")).write_bytes(body[:400_000])
            summary.append({"path": path, "status": st, "bytes": len(body), "linked_from_docs": True})
    except Exception as e:  # noqa: BLE001
        summary.append({"link_scan_error": str(e)[:100]})
    (out / "summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
