"""What does OddsPapi return for Hard Rock Bet's NFL spreads and player props? (evidence only)

Five requests of the free tier's 250 a month: sports (to find American football), its tournaments (to find the NFL),
the bookmaker list (to confirm the `hardrockbet` slug and which of Will's other venues OddsPapi carries), the market
list (to name the numeric market ids), then Hard Rock's odds for the NFL tournament. The key is read from
ODDSPAPI_API_KEY and never written: URLs are saved with it redacted.

Writes docs/evidence/oddspapi_probe/<UTC stamp>/summary.json plus each raw response as <name>.json.gz.
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = "https://api.oddspapi.io/v4"
VENUES = ["hardrockbet", "kalshi", "polymarket", "novig", "prizepicks", "underdog", "sleeper"]


def get(path: str, **params):
    key = os.environ["ODDSPAPI_API_KEY"]
    url = f"{ROOT}{path}?" + urllib.parse.urlencode({**params, "apiKey": key})
    shown = url.replace(key, "REDACTED")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nfl-betting-model/1.0 (read-only research)",
                                                   "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            hdr = {k: v for k, v in r.headers.items()
                   if any(s in k.lower() for s in ("remain", "used", "credit", "limit", "quota", "request"))}
            return shown, r.status, hdr, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return shown, e.code, {}, e.read()[:800].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - record and continue
        return shown, str(e)[:160], {}, None


def save(out: Path, name: str, body) -> None:
    if body is not None:
        with gzip.open(out / f"{name}.json.gz", "wt") as fh:
            json.dump(body, fh)


def rows(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("data", "results", "items"):
            if isinstance(body.get(k), list):
                return body[k]
    return []


def main() -> None:
    if not os.environ.get("ODDSPAPI_API_KEY"):
        raise SystemExit("ODDSPAPI_API_KEY not set (repo Settings -> Secrets and variables -> Actions)")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/oddspapi_probe") / stamp
    out.mkdir(parents=True, exist_ok=True)
    s: dict = {"stamp": stamp}

    url, st, hdr, body = get("/sports")
    save(out, "sports", body)
    sports = rows(body)
    af = [x for x in sports if isinstance(x, dict) and "football" in json.dumps(x).lower()
          and "soccer" not in json.dumps(x).lower()]
    s["sports"] = {"url": url, "status": st, "headers": hdr, "n": len(sports), "american_football_candidates": af[:5],
                   "error": body if isinstance(body, str) else None}
    print("sports", st, hdr, af[:3], flush=True)
    sport_id = next((x.get("sportId") or x.get("id") for x in af if "american" in json.dumps(x).lower()), None)

    url, st, hdr, body = get("/tournaments", sportId=sport_id) if sport_id is not None else (None, "no sport id", {}, None)
    save(out, "tournaments", body)
    tours = rows(body)
    nfl = [t for t in tours if isinstance(t, dict) and ("nfl" in json.dumps(t).lower())]
    s["tournaments"] = {"url": url, "status": st, "headers": hdr, "n": len(tours), "nfl_candidates": nfl[:5],
                        "error": body if isinstance(body, str) else None}
    print("tournaments", st, nfl[:3], flush=True)
    nfl_id = next((t.get("tournamentId") for t in nfl if str(t.get("tournamentSlug", "")).lower() == "nfl"),
                  nfl[0].get("tournamentId") if nfl else None)

    url, st, hdr, body = get("/bookmakers")
    save(out, "bookmakers", body)
    text = json.dumps(body).lower() if body is not None else ""
    s["bookmakers"] = {"url": url, "status": st, "headers": hdr, "slugs_present": {v: (f'"{v}' in text) for v in VENUES},
                       "error": body if isinstance(body, str) else None}
    print("bookmakers", st, s["bookmakers"]["slugs_present"], flush=True)

    url, st, hdr, body = get("/markets", sportId=sport_id) if sport_id is not None else (None, "no sport id", {}, None)
    save(out, "markets", body)
    s["markets"] = {"url": url, "status": st, "headers": hdr, "n": len(rows(body)), "head": rows(body)[:40],
                    "error": body if isinstance(body, str) else None}
    print("markets", st, len(rows(body)), flush=True)

    if nfl_id is None:
        s["odds"] = {"skipped": "no NFL tournament id"}
    else:
        url, st, hdr, body = get("/odds-by-tournaments", bookmaker="hardrockbet", tournamentIds=nfl_id, oddsFormat="american")
        save(out, "odds_hardrockbet_nfl", body)
        fx = rows(body)
        mk = collections.Counter()
        players = 0
        sample = None
        for f in fx:
            hr = ((f.get("bookmakerOdds") or {}).get("hardrockbet") or {}) if isinstance(f, dict) else {}
            for mid, m in (hr.get("markets") or {}).items():
                mk[mid] += 1
                for oc in (m.get("outcomes") or {}).values():
                    for pid, p in (oc.get("players") or {}).items():
                        if pid != "0" or (p or {}).get("playerName"):
                            players += 1
                if sample is None:
                    sample = {"fixture": {k: f.get(k) for k in ("fixtureId", "participant1Id", "participant2Id", "startTime")},
                              "market_id": mid, "market": m}
        s["odds"] = {"url": url, "status": st, "headers": hdr, "fixtures": len(fx), "markets_by_id": mk.most_common(60),
                     "player_outcomes": players, "sample": sample, "error": body if isinstance(body, str) else None}
        print("odds", st, hdr, len(fx), mk.most_common(10), players, flush=True)

    (out / "summary.json").write_text(json.dumps(s, indent=1, default=str))
    print("wrote", out)


if __name__ == "__main__":
    main()
