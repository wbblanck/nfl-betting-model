"""Look at openmarkets.ai from a runner (evidence only; public pages, no login, no accounts).

Questions: what does the site serve; does it cover NFL player props; is there a public API (documented paths, or
API hosts the site's own JavaScript calls); is there any odds history? Writes docs/evidence/openmarkets/<UTC
stamp>/summary.json plus the first 20 KB of each text response.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HOSTS = ["https://openmarkets.ai", "https://app.openmarkets.ai", "https://www.openmarkets.ai", "https://api.openmarkets.ai",
         "https://docs.openmarkets.ai"]
PATHS = ["/", "/robots.txt", "/sitemap.xml", "/api", "/api/", "/docs", "/api/docs", "/openapi.json", "/api/openapi.json",
         "/developers", "/developer", "/pricing", "/odds", "/nfl", "/sports/nfl", "/props", "/llms.txt"]
WORDS = ["api", "api key", "apikey", "developer", "nfl", "player prop", "props", "receiving", "rushing", "passing",
         "historical", "history", "draftkings", "fanduel", "kalshi", "polymarket", "prophetx", "novig", "pinnacle",
         "websocket", "pricing", "free", "beta"]
URLRX = re.compile(r"""https?://[a-zA-Z0-9.\-]+(?:/[A-Za-z0-9_\-./{}:]*)?""")
PATHRX = re.compile(r"""["'`](/(?:api|v1|v2|graphql|odds|markets|props|events)[A-Za-z0-9_\-./{}:?=&]*)["'`]""")


def get(url: str):
    time.sleep(0.5)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("content-type", ""), r.geturl(), r.read(3_000_000)
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", "") if e.headers else "", url, (e.read(20000) if e.fp else b"")
    except Exception as e:  # noqa: BLE001
        return str(e)[:120], "", url, b""


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/openmarkets") / stamp
    out.mkdir(parents=True, exist_ok=True)
    summary = {"stamp": stamp, "pages": [], "scripts": [], "hosts_seen": [], "api_paths_seen": []}
    scripts, hosts, paths = set(), set(), set()
    for h in HOSTS:
        for p in PATHS:
            st, ct, final, body = get(h + p)
            text = body.decode("utf-8", "replace")
            low = text.lower()
            rec = {"url": h + p, "status": st, "final_url": final, "content_type": ct, "bytes": len(body),
                   "title": (re.search(r"<title>(.*?)</title>", text, re.S | re.I) or [None, None])[1],
                   "words": {w: low.count(w) for w in WORDS if w in low}}
            summary["pages"].append(rec)
            print(rec["url"], st, len(body), rec["title"], rec["words"], flush=True)
            if st == 200 and body:
                name = re.sub(r"[^A-Za-z0-9]+", "_", (h + p).split("//")[1]).strip("_")
                (out / f"{name}.txt").write_text(text[:20000])
                for s in re.findall(r"""<script[^>]+src=["']([^"']+)["']""", text):
                    scripts.add(urllib.parse.urljoin(final, s))
                hosts.update(u for u in URLRX.findall(text))
                paths.update(PATHRX.findall(text))
            if st != 200 and p == "/":
                break                                   # host does not answer: skip its other paths
    # second pass: full text of the pages that matter, and the one documented no-key endpoint
    for u in ["https://openmarkets.ai/odds/nfl", "https://openmarkets.ai/odds", "https://app.openmarkets.ai/developers/historical",
              "https://app.openmarkets.ai/developers/history", "https://app.openmarkets.ai/developers/rate-limits",
              "https://app.openmarkets.ai/developers/reference", "https://app.openmarkets.ai/developers/quickstart",
              "https://openmarkets.ai/pricing", "https://app.openmarkets.ai/pricing",
              "https://api.openmarkets.ai/flow/v1/public/live-sample", "https://api.openmarkets.ai/flow/v1/leagues"]:
        st, ct, final, body = get(u)
        text = body.decode("utf-8", "replace")
        summary["pages"].append({"url": u, "status": st, "final_url": final, "content_type": ct, "bytes": len(body), "pass": 2})
        print("pass2", u, st, len(body), flush=True)
        if body:
            name = "full_" + re.sub(r"[^A-Za-z0-9]+", "_", u.split("//")[1]).strip("_")
            (out / f"{name}.txt").write_text(text[:400000])
    for s in sorted(scripts)[:40]:
        st, ct, final, body = get(s)
        text = body.decode("utf-8", "replace")
        low = text.lower()
        found_hosts = sorted({u.split("/")[2] for u in URLRX.findall(text)})
        found_paths = sorted(set(PATHRX.findall(text)))[:200]
        hosts.update(URLRX.findall(text))
        paths.update(found_paths)
        summary["scripts"].append({"url": s, "status": st, "bytes": len(body), "hosts": found_hosts[:100],
                                   "api_paths": found_paths, "words": {w: low.count(w) for w in WORDS if w in low}})
        print("script", s, st, len(body), found_paths[:20], flush=True)
    summary["hosts_seen"] = sorted({u.split("/")[2] for u in hosts})
    summary["api_paths_seen"] = sorted(paths)[:400]
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
