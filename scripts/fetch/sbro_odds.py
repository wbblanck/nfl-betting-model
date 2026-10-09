"""Fetch Sportsbook Review Online's NFL odds archive (2007-08 to 2021-22): one raw CSV per season with every table
row as published (date, rotation, V/H/N, team, quarter scores, final, open, close, moneyline, 2H). Parsing into
games and lines is done by nflbet.sbro, so this script only saves what the site shows.
Writes data/odds/sbro/nfl_<start year>.csv."""
from __future__ import annotations

import csv
import html
import re
import time
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
URL = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nfl-odds-{a}-{b:02d}"
OUT = Path("data/odds/sbro")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for a in range(2007, 2022):
        time.sleep(2)
        req = urllib.request.Request(URL.format(a=a, b=(a + 1) % 100), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            t = r.read().decode("utf-8", "replace")
        table = re.search(r"<table.*?</table>", t, re.S | re.I).group(0)
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", table, re.S | re.I):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
            if cells:
                rows.append(cells)
        with open(OUT / f"nfl_{a}.csv", "w", newline="") as f:
            csv.writer(f).writerows(rows)
        print(a, len(rows) - 1, "rows", rows[0], flush=True)


if __name__ == "__main__":
    main()
