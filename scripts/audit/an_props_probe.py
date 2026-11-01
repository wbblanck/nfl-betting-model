"""Why does Action Network return 0 prop rows since 2026 week 5? (evidence only)

Fetches the books list, the week-8 scoreboard, and the props of two week-8 games plus one week-4 game whose props the
live fetch parsed (data/live/lines/20261005T0117Z_w4.csv.gz). For each props response records its top-level keys, the
player_props market keys with entry counts, the books and periods seen in the lines, and one sample line, so the shape
can be compared with what scripts/fetch/an_props.py expects. Keyless public API, same headers as the fetch.

Writes docs/evidence/an_props_probe/<UTC stamp>/summary.json plus each raw response as <name>.json.gz.
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fetch"))
import an_props as F  # noqa: E402

SEASON = 2026


def shape(props) -> dict:
    if not isinstance(props, dict):
        return {"type": type(props).__name__, "head": str(props)[:400]}
    pp = props.get("player_props")
    s = {"top_keys": sorted(props.keys()), "player_props_type": type(pp).__name__}
    if isinstance(pp, dict):
        s["markets"] = {k: len(v or []) for k, v in sorted(pp.items())}
        s["known_markets_present"] = sorted(k for k in F.MARKETS if k in pp)
        books, periods, sides, alt = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
        sample = None
        for k, entries in pp.items():
            for e in entries or []:
                if not isinstance(e, dict):
                    continue
                lines = e.get("lines")
                if sample is None:
                    sample = {"market": k, "entry_keys": sorted(e.keys()), "lines_type": type(lines).__name__,
                              "lines_head": json.dumps(lines)[:800] if lines is not None else None,
                              "entry_head": json.dumps(e)[:800]}
                if isinstance(lines, dict):
                    for b, ls in lines.items():
                        for ln in ls or []:
                            books[str(b)] += 1
                            periods[str(ln.get("period"))] += 1
                            sides[str(ln.get("side"))] += 1
                            alt[str(ln.get("is_alt_market"))] += 1
        s.update({"books": books.most_common(), "periods": periods.most_common(), "sides": sides.most_common(),
                  "is_alt_market": alt.most_common(), "sample": sample})
    s["players_type"] = type(props.get("players")).__name__
    return s


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/an_props_probe") / stamp
    out.mkdir(parents=True, exist_ok=True)
    s: dict = {"stamp": stamp}

    def save(name, body):
        with gzip.open(out / f"{name}.json.gz", "wt") as fh:
            json.dump(body, fh)

    bd = F.get(F.AN + "/web/v1/books", 1.0)
    save("books", bd)
    s["books"] = {str(b.get("id")): b.get("display_name") or b.get("name") for b in ((bd or {}).get("books") or [])}

    picks = {}
    for week in (8, 4):
        sb = F.get(f"{F.AN}/web/v2/scoreboard/nfl?season={SEASON}&week={week}&periods=event", 1.0)
        save(f"scoreboard_w{week}", sb)
        games = (sb or {}).get("games") or []
        s[f"scoreboard_w{week}"] = [{"id": g.get("id"), "start_time": g.get("start_time"), "status": g.get("status")}
                                    for g in games]
        games = sorted(games, key=lambda g: str(g.get("start_time")), reverse=True)
        picks[week] = [g for g in games if g.get("status") not in ("complete", "closed")][:2] if week == 8 else games[:1]

    s["props"] = {}
    for week, games in picks.items():
        for g in games:
            props = F.get(f"{F.AN}/web/v2/games/{g['id']}/props", 1.0)
            save(f"props_w{week}_{g['id']}", props)
            sh = shape(props)
            sh["parsed_rows"] = len(F.rows_for_game(props, g, SEASON, week, {})) if isinstance(props, dict) else None
            s["props"][f"w{week}_{g['id']}"] = sh
            print(week, g["id"], sh.get("top_keys"), sh.get("known_markets_present"), sh.get("parsed_rows"), flush=True)

    (out / "summary.json").write_text(json.dumps(s, indent=1, default=str))
    print("wrote", out)


if __name__ == "__main__":
    main()
