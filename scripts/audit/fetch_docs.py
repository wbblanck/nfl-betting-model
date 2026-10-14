"""Fetch a documentation site's Markdown pages for offline reading (read-only, no key).

Usage: python scripts/audit/fetch_docs.py https://docs.novig.com docs/evidence/novig_docs
Pulls <base>/llms.txt, <base>/llms-full.txt and <base>/.md, then every <base> page listed in llms.txt (as .md).
Retries 429/5xx with backoff. Writes one file per page plus index.json (url, status, bytes) under <out>/<stamp>/.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
MAX_PAGES = 150


def get(url: str) -> tuple[int, bytes]:
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/markdown, text/plain, */*"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < 4:
                time.sleep(10 * 2 ** i)
                continue
            return e.code, e.read()[:2000]
        except Exception as e:  # noqa: BLE001 - recorded
            if i < 4:
                time.sleep(5 * 2 ** i)
                continue
            return -1, repr(e).encode()
    return -1, b""


def name_for(url: str, base: str) -> str:
    path = url[len(base):].strip("/")
    path = "root.md" if path in ("", ".md") else path
    return re.sub(r"[^A-Za-z0-9._-]+", "_", path)[:150] + ("" if path.endswith((".md", ".txt")) else ".md")


def main() -> None:
    base, out = sys.argv[1].rstrip("/"), Path(sys.argv[2])
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = out / stamp
    d.mkdir(parents=True, exist_ok=True)
    index, seen = [], set()

    def save(url: str) -> bytes:
        seen.add(url)
        st, body = get(url)
        f = name_for(url, base)
        if st == 200:
            (d / f).write_bytes(body)
        index.append({"url": url, "status": st, "bytes": len(body), "file": f if st == 200 else None})
        print(f"{st} {len(body):>8} {url}")
        time.sleep(0.5)
        return body if st == 200 else b""

    llms = save(f"{base}/llms.txt").decode("utf-8", "replace")
    save(f"{base}/llms-full.txt")
    save(f"{base}/.md")
    links = re.findall(r"\((https?://[^)\s]+)\)", llms) + re.findall(r"^(https?://\S+)$", llms, re.M)
    pages = [u for u in dict.fromkeys(links) if u.startswith(base)]
    for u in pages[:MAX_PAGES]:
        u = u if u.endswith((".md", ".txt")) else u.rstrip("/") + ".md"
        if u not in seen:
            save(u)
    (d / "index.json").write_text(json.dumps({"base": base, "fetched_utc": stamp, "pages_listed": len(pages), "results": index}, indent=1))
    ok = sum(1 for r in index if r["status"] == 200)
    print(f"saved {ok} of {len(index)} to {d}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
