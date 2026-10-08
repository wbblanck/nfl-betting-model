"""Full dump of ESPN core propBets for one week (evidence only; no outcomes read).

Question: the 2026-10-08 probe found DraftKings (provider 100) propBets answering for 2026 week 5 (1,620 items in
one game), but its samples are cut to 3 items. Which markets, which fields (prices or only lines?), which update
times, and how many players per game? A 2025 week-6 game (ESPN BET, 58) is dumped alongside for comparison.

Writes docs/evidence/espn_props/<UTC stamp>/summary.json and props_<season>w<week>.jsonl.gz (every item, flattened).
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from espn_probe import CORE, get  # noqa: E402

TARGETS = [(2026, 5, None), (2025, 6, 1)]          # (season, week, max games or None for all)


def paths(o, pre=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from paths(v, f"{pre}.{k}" if pre else k)
    elif isinstance(o, list):
        for v in o:
            yield from paths(v, pre + "[]")
    else:
        yield pre


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("docs/evidence/espn_props") / stamp
    out.mkdir(parents=True, exist_ok=True)
    summary = {"stamp": stamp, "weeks": []}
    for season, week, cap in TARGETS:
        st, ev, _ = get(f"{CORE}/seasons/{season}/types/2/weeks/{week}/events?limit=50")
        ids = [re.search(r"events/(\d+)", r["$ref"]).group(1) for r in (ev or {}).get("items", [])][:cap]
        wk = {"season": season, "week": week, "events_status": st, "n_events": len(ids), "games": []}
        types, kp, upd, rows = collections.Counter(), collections.Counter(), [], []
        samples = {}
        for eid in ids:
            st, odds, _ = get(f"{CORE}/events/{eid}/competitions/{eid}/odds?limit=100")
            provs = [((it.get("provider") or {}).get("id"), (it.get("provider") or {}).get("name"))
                     for it in (odds or {}).get("items", [])]
            for pid, pname in provs:
                items, page, pages, status = [], 1, 1, None
                while page <= pages:
                    status, body, _ = get(f"{CORE}/events/{eid}/competitions/{eid}/odds/{pid}/propBets?limit=1000&page={page}")
                    if not isinstance(body, dict):
                        break
                    items += body.get("items", [])
                    pages = body.get("pageCount", 1)
                    page += 1
                aths = set()
                for it in items:
                    t = (it.get("type") or {}).get("name")
                    types[t] += 1
                    kp.update(set(paths(it)))
                    if it.get("lastUpdated"):
                        upd.append(it["lastUpdated"])
                    a = re.search(r"athletes/(\d+)", (it.get("athlete") or {}).get("$ref", ""))
                    aths.add(a.group(1) if a else None)
                    samples.setdefault(t, it)
                    rows.append({"event": eid, "provider": pid, **{p: v for p, v in flat(it)}})
                wk["games"].append({"event": eid, "odds_status": st, "provider": pid, "provider_name": pname,
                                    "props_status": status, "n_items": len(items), "n_athletes": len(aths)})
                print(season, week, eid, pid, pname, status, len(items), len(aths), flush=True)
        wk["types"] = types.most_common()
        wk["key_paths"] = kp.most_common()
        wk["last_updated_min"], wk["last_updated_max"] = (min(upd), max(upd)) if upd else (None, None)
        wk["last_updated_by_day"] = sorted(collections.Counter(u[:10] for u in upd).items())
        wk["sample_per_type"] = samples
        summary["weeks"].append(wk)
        with gzip.open(out / f"props_{season}w{week}.jsonl.gz", "wt") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))


def flat(o, pre=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flat(v, f"{pre}.{k}" if pre else k)
    else:
        yield pre, o


if __name__ == "__main__":
    main()
