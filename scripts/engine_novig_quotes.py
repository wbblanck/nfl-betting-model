"""Phase 6: executable Novig quotes from every recorded snapshot that has books (engine.quotes). Market data only: no
prediction, probability or expected value is read or written, so this is not a priced-sides list (CLAUDE.md).

Writes, per snapshot with books, data/live/novig_quotes/<stamp>/quotes.csv.gz (one row per contract, side and size),
unmatched.json (counts by reason) and rosters.json.gz (the roster rows used to resolve players, so every row can be
re-derived from committed files). Then re-derives every quote row from the saved files (the phase 6 gate) and writes
docs/engine/novig_quotes.md: what the books would have cost, by market type, at $10 and $100 of payout (Test E is
descriptive until Will authorizes more).
"""
import collections
import datetime as dt
import gzip
import json
import statistics as st
import sys

import polars as pl

from nflbet.config import ROOT
from nflbet.engine import quotes as Q
from nflbet.sources import ids

SNAPS, OUT, DOC = ROOT / "data" / "live" / "novig_books", ROOT / "data" / "live" / "novig_quotes", ROOT / "docs" / "engine" / "novig_quotes.md"
SKILL = ("QB", "RB", "WR", "TE")


def fix(t: str) -> str:
    return ids.TEAM_FIX.get(t, t)


def rosters_for(snap: dict, season: int) -> tuple[dict, dict]:
    """(game key -> roster rows, game key -> roster week used). The week is the scheduled game's; if nflverse has no
    roster for that week yet, the latest earlier week is used and the week used is recorded."""
    import nflreadpy as nr
    sched = nr.load_schedules([season])
    sched = sched.filter(pl.col("game_type") == "REG")
    ros = nr.load_rosters_weekly([season])
    ros = ros.filter(pl.col("position").is_in(SKILL) & pl.col("gsis_id").is_not_null())
    have = sorted(set(ros["week"].to_list()))
    out, used = {}, {}
    for e in snap["events"]:
        parts = (e.get("description") or "").split(" @ ")
        if len(parts) != 2 or not all(ids.TEAMS.get(p.strip()) for p in parts):
            continue
        away, home = (ids.TEAMS[p.strip()] for p in parts)
        day = dt.datetime.fromtimestamp(e["startsTs"] / 1000, dt.timezone.utc).date()
        g = sched.filter((pl.col("home_team").map_elements(fix, return_dtype=pl.Utf8) == home)
                         & (pl.col("away_team").map_elements(fix, return_dtype=pl.Utf8) == away))
        g = g.with_columns((pl.col("gameday").str.to_date() - pl.lit(day)).dt.total_days().abs().alias("gap")).sort("gap")
        if g.height == 0 or g["gap"][0] > 3:
            continue
        week = int(g["week"][0])
        wk = max([w for w in have if w <= week], default=None)
        if wk is None:
            continue
        sub = ros.filter((pl.col("week") == wk) & pl.col("team").map_elements(fix, return_dtype=pl.Utf8).is_in([home, away]))
        key = ids.game_key(away, home)
        out[key] = [{"player_id": a, "name": b, "team": fix(c), "position": d}
                    for a, b, c, d in zip(sub["gsis_id"].to_list(), sub["full_name"].to_list(), sub["team"].to_list(), sub["position"].to_list())]
        used[key] = {"game_week": week, "roster_week": wk}
    return out, used


def med(x):
    x = [v for v in x if v is not None]
    return st.median(x) if x else None


def main() -> int:
    stamps = sorted(p.name for p in SNAPS.iterdir() if p.is_dir() and json.loads((p / "summary.json").read_text()).get("books_saved", 0) > 0)
    all_rows, report, checked, mismatched, lost = [], [], 0, 0, collections.Counter()
    for stamp in stamps:
        snap = Q.load(SNAPS / stamp)
        season = dt.datetime.fromisoformat(snap["summary"]["run_utc"]).year
        d = OUT / stamp
        if (d / "rosters.json.gz").exists():              # re-derive from the rosters saved the first time
            saved = json.load(gzip.open(d / "rosters.json.gz", "rt"))
            ros, used = saved["rosters"], saved["weeks"]
        else:
            ros, used = rosters_for(snap, season)
        rows, un = Q.quotes(snap, ros)
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / "rosters.json.gz", "wt") as f:
            json.dump({"rosters": ros, "weeks": used}, f, sort_keys=True)
        pl.DataFrame(rows, infer_schema_length=None).write_csv(d / "quotes.csv") if rows else None
        if rows:
            with open(d / "quotes.csv", "rb") as src, gzip.open(d / "quotes.csv.gz", "wb") as dst:
                dst.write(src.read())
            (d / "quotes.csv").unlink()
        reasons = collections.Counter(u["reason"] for u in un)
        lost.update(f'{u["description"].rsplit(" ", 2)[0]} ({u["reason"].removeprefix("player: ")})' for u in un if u["reason"].startswith("player"))
        (d / "unmatched.json").write_text(json.dumps(dict(reasons.most_common()), indent=1) + "\n")
        for r in rows:                                     # the gate: every row re-derived from the saved files
            checked += 1
            mismatched += not Q.rederive(r, snap, ros)
        n_contracts = len({r["market_id"] for r in rows})
        report.append((stamp, snap["summary"]["books_saved"], n_contracts, reasons))
        all_rows += rows
    by_type = collections.defaultdict(list)
    for r in all_rows:
        by_type[r["market_type"]].append(r)
    L = ["# Novig executable quotes from the recorded books (phase 6)", "",
         "Written by `scripts/engine_novig_quotes.py` from `data/live/novig_books/`. Market data only: no model probability,",
         "expected value or side is read or written. One contract pays 1 cent; sizes are $10 (1,000 contracts) and $100",
         "(10,000 contracts) of payout. Costs are dollars per $1 of payout; buying Over takes the resting orders on Under.",
         "Fees are pregame (`WHEN_LIVE` charges nothing before the start). These are snapshots, not fills.", "",
         f"Re-derivation gate: {checked:,} quote rows recomputed from the saved files, {mismatched} differ."
         + (" **PASS.**" if mismatched == 0 else " **FAIL.**"), "",
         "## Snapshots with books", "", "| Snapshot (UTC) | Books saved | Contracts quoted | Not quoted, by reason |", "|---|---|---|---|"]
    for stamp, nb, nc, reasons in report:
        L.append(f"| {stamp} | {nb:,} | {nc:,} | " + "; ".join(f"{k} {v:,}" for k, v in reasons.most_common()) + " |")
    L += ["", "## By market type (all snapshots)", "",
          "A contract seen in several snapshots is counted once per snapshot.", "",
          "| Market type | Contracts | Fully filled at $10, both sides | At $100, both sides | Median two-side cost at $10 (1 = no margin) | At $100 | Median minutes before start |",
          "|---|---|---|---|---|---|---|"]
    for t, rs in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        byc = collections.defaultdict(dict)
        for r in rs:
            byc[(r["stamp"], r["market_id"])][(r["side"], r["size"])] = r
        def both(size):
            full = [c for c in byc.values() if all(c[(s, size)]["unfilled"] == 0 for s in ("Over", "Under"))]
            cost = [c[("Over", size)]["all_in"] + c[("Under", size)]["all_in"] for c in full]
            return len(full) / len(byc), med(cost)
        f10, c10 = both(1000)
        f100, c100 = both(10000)
        mins = med([c[("Over", 1000)]["minutes_before_start"] for c in byc.values()])
        L.append(f"| {t} | {len(byc):,} | {f10:.0%} | {f100:.0%} | {c10:.3f} | " + (f"{c100:.3f}" if c100 else "n/a") + f" | {mins:.0f} |")
    L += ["", "## Reading", "",
          "- 'Two-side cost' adds what it costs to buy Over and to buy Under at that size: above 1 is the margin a taker",
          "  pays across the pair at that moment; it is not the margin on any one side.",
          "- A contract counts only if it matched exactly (engine/contracts.py), its player resolved to one player on the",
          "  game's two rosters, and its book was fetched before the start and within",
          f"  {Q.FRESH_MINUTES} minutes of the catalog read. 'No book saved' means the recorder did not pull that market's",
          "  book (its game was not within the recorder's window), not that the market was empty.",
          "- Rosters: nflverse weekly rosters for the game's week, or the latest earlier week if that week was not out yet",
          "  (saved with each snapshot's quotes). Players not resolved (markets across snapshots, left unquoted, not guessed): "
          + "; ".join(f"{k} {v}" for k, v in lost.most_common()) + ".",
          "- Novig's overtime and FMV void rules remain unconfirmed (NOVIG_INTEGRATION.md)."]
    DOC.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0 if mismatched == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
