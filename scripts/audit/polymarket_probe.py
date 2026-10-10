"""Does Polymarket list NFL player props (evidence only)? Polymarket's public Gamma API (keyless) and the
Polymarket US site. Writes docs/evidence/polymarket/<stamp>/summary.json."""
from __future__ import annotations

import collections
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
PROP = re.compile(r"(passing|rushing|receiving) yards|receptions|completions|yds|\bTD\b|touchdown", re.I)


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=60) as r:
            b = r.read()
            try:
                return r.status, json.loads(b)
            except ValueError:
                return r.status, b[:3000].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return str(e)[:150], None


def main():
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/polymarket") / stamp
    out.mkdir(parents=True, exist_ok=True)
    s = {}
    st, tags = get("https://gamma-api.polymarket.com/tags?limit=500")
    nfl_tags = [t for t in (tags or []) if isinstance(t, dict) and "nfl" in json.dumps(t).lower()] if isinstance(tags, list) else []
    s["tags"] = {"status": st, "nfl": nfl_tags[:20]}
    events = []
    for t in nfl_tags[:6]:
        for off in (0, 100, 200):
            st2, ev = get("https://gamma-api.polymarket.com/events?" + urllib.parse.urlencode(
                {"tag_id": t.get("id"), "closed": "false", "limit": 100, "offset": off}))
            if isinstance(ev, list):
                events += ev
            if not ev:
                break
    for q in ("Jalen Hurts passing yards", "Josh Downs receptions", "Aaron Jones receptions", "Bears Packers",
              "Eagles Jaguars", "NFL player props week 5", "Lamar Jackson"):
        st3, sr = get("https://gamma-api.polymarket.com/public-search?" + urllib.parse.urlencode({"q": q, "limit_per_type": 20}))
        evs = (sr or {}).get("events", []) if isinstance(sr, dict) else []
        s[f"search_{q}"] = {"status": st3, "n_events": len(evs),
                            "events": [{"title": e.get("title"), "end": e.get("endDate"), "closed": e.get("closed"),
                                        "markets": [m.get("question") for m in (e.get("markets") or [])][:12]} for e in evs[:8]]}
    seen, titles = set(), []
    markets = collections.Counter()
    for e in events:
        if e.get("id") in seen:
            continue
        seen.add(e.get("id"))
        titles.append(e.get("title"))
        for m in e.get("markets") or []:
            q = m.get("question") or ""
            markets["player prop" if PROP.search(q) else "other"] += 1
    props = [m.get("question") for e in events for m in (e.get("markets") or []) if PROP.search(m.get("question") or "")]
    s["events"] = {"n": len(seen), "titles_sample": titles[:40], "market_kinds": markets, "prop_questions_sample": props[:40]}
    for u in ("https://polymarket.us", "https://www.polymarket.us", "https://api.polymarket.us/v1/markets?limit=5"):
        st4, b = get(u)
        s[u] = {"status": st4, "head": (json.dumps(b)[:800] if isinstance(b, (dict, list)) else (b or "")[:800])}
    (out / "summary.json").write_text(json.dumps(s, indent=1, default=str))
    print(json.dumps(s, indent=1, default=str)[:8000])


if __name__ == "__main__":
    main()
