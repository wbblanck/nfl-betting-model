"""Evidence only: since 2026 week 5 `web/v2/games/{id}/props` answers with empty dicts for every game (even week 1).
Try candidate Action Network endpoints for one 2026 and one 2025 game and record status, size and top-level keys
to docs/evidence/an_endpoints/<UTC stamp>.json."""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fetch"))
from an_props import AN, UA  # noqa: E402

HDR = {"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.actionnetwork.com/",
       "Origin": "https://www.actionnetwork.com"}


def hit(url: str) -> dict:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=60) as r:
            body = r.read().decode("utf-8", "replace")
            st = r.status
    except urllib.error.HTTPError as e:
        return {"url": url, "status": e.code, "body": e.read().decode("utf-8", "replace")[:300]}
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": str(e)[:300]}
    out = {"url": url, "status": st, "bytes": len(body), "head": body[:400]}
    try:
        j = json.loads(body)
        out["keys"] = sorted(j)[:30] if isinstance(j, dict) else type(j).__name__
        if isinstance(j, dict):
            out["sizes"] = {k: (len(v) if isinstance(v, (list, dict)) else None) for k, v in j.items()}
    except Exception:  # noqa: BLE001
        pass
    return out


def main() -> None:
    res = []
    books = json.loads(urllib.request.urlopen(urllib.request.Request(AN + "/web/v1/books", headers=HDR), timeout=60).read())
    ids = ",".join(str(b["id"]) for b in books.get("books", [])[:40])
    for season, week in ((2026, 9), (2025, 9)):
        sb = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"{AN}/web/v2/scoreboard/nfl?season={season}&week={week}&periods=event", headers=HDR), timeout=60).read())
        g = (sb.get("games") or [{}])[0]
        gid, day = g.get("id"), str(g.get("start_time", ""))[:10].replace("-", "")
        res.append({"season": season, "week": week, "game": gid, "start": g.get("start_time"), "game_keys": sorted(g)[:40]})
        for u in (f"/web/v2/games/{gid}/props", f"/web/v2/games/{gid}/props?bookIds={ids}", f"/web/v1/games/{gid}/props",
                  f"/web/v2/games/{gid}", f"/web/v2/games/{gid}/props?periods=event",
                  f"/web/v1/leagues/1/props/core_bet_type_16_receiving_yards?date={day}",
                  f"/web/v2/leagues/1/props/core_bet_type_16_receiving_yards?date={day}",
                  f"/web/v1/leagues/1/props/core_bet_type_16_receiving_yards?date={day}&bookIds={ids}",
                  f"/web/v2/scoreboard/nfl?season={season}&week={week}&periods=event&bookIds={ids}"):
            res.append(hit(AN + u))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/an_endpoints") / f"{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    for r in res:
        print(json.dumps({k: r.get(k) for k in ("url", "status", "bytes", "sizes", "error", "game", "season")})[:600])


if __name__ == "__main__":
    main()
