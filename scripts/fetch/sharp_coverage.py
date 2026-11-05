"""Weekly snapshot of Sharp Football Analysis' free coverage page (team man/zone and middle-of-field rates).

The page is season-to-date and overwritten on each update, so we keep our own dated copies: the history of "what was
known before kickoff" exists only from these snapshots. Finds the page from the site's sitemap (slug containing
"coverage"), saves the raw HTML (gzip) and every HTML table as CSV under data/live/sharp_coverage/<UTC stamp>/,
plus any iframe sources (the table may be embedded). Evidence and data only; nothing is graded. Runs in Actions.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import html.parser
import json
import re
import sys
import urllib.request

from nflbet import config

SITE = "https://www.sharpfootballanalysis.com"
CANDIDATES = [f"{SITE}/stats-nfl/nfl-coverage-schemes/", f"{SITE}/stats-nfl/nfl-coverage-scheme-stats/"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
OUT = config.ROOT / "data" / "live" / "sharp_coverage"


def get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


class Tables(html.parser.HTMLParser):
    """Every <table> as a list of rows of cell text; also iframe srcs."""

    def __init__(self):
        super().__init__()
        self.tables, self.iframes, self._t, self._row, self._cell = [], [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._t = []
        elif tag == "tr" and self._t is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "iframe":
            self.iframes += [v for k, v in attrs if k == "src" and v]

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self._t.append(self._row)
            self._row = None
        elif tag == "table" and self._t is not None:
            self.tables.append(self._t)
            self._t = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def find_url() -> str | None:
    for u in CANDIDATES:
        if get(u)[0] == 200:
            return u
    for sm in (f"{SITE}/sitemap_index.xml", f"{SITE}/sitemap.xml"):
        st, body = get(sm)
        if st != 200:
            continue
        locs = re.findall(r"<loc>([^<]+)</loc>", body)
        hits = [u for u in locs if "coverage" in u.lower() and "stats" in u.lower()]
        if hits:
            return hits[0]
        for sub in [u for u in locs if "sitemap" in u and ("page" in u or "stats" in u)]:
            st2, b2 = get(sub)
            hits = [u for u in re.findall(r"<loc>([^<]+)</loc>", b2) if "coverage" in u.lower()]
            if hits:
                return hits[0]
    return None


def main() -> None:
    url = find_url()
    if not url:
        sys.exit("coverage page not found")
    st, body = get(url)
    if st != 200:
        sys.exit(f"{url}: HTTP {st}")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%MZ")
    d = OUT / stamp
    d.mkdir(parents=True, exist_ok=True)
    with gzip.open(d / "page.html.gz", "wt", encoding="utf-8") as f:
        f.write(body)
    p = Tables()
    p.feed(body)
    for i, t in enumerate(p.tables, 1):
        with open(d / f"table_{i}.csv", "w", newline="") as f:
            csv.writer(f).writerows(t)
    upd = re.search(r"Updated:\s*([A-Z][a-z]+ \d{1,2})", body)
    meta = {"url": url, "fetched_utc": stamp, "page_updated": upd.group(1) if upd else None,
            "tables": [len(t) for t in p.tables], "iframes": p.iframes[:20]}
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
