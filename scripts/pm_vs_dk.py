"""Polymarket US vs DraftKings prop prices, 2026 weeks 5-8 (docs/pm_vs_dk_plan.md). Descriptive; no picks.

  python scripts/pm_vs_dk.py fetch   # match props, read Polymarket price history -> data/backtests/pm_vs_dk_2026.csv
  python scripts/pm_vs_dk.py report  # grade and compare -> docs/pm_vs_dk.md
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import sys
import time
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
from nflbet import config  # noqa: E402
from nflbet.props import core as P  # noqa: E402
from nflbet.quant.odds import implied, no_vig_over  # noqa: E402
from nflbet.sources import parlay as Pa, venues as V  # noqa: E402
from nflbet.sources.ids import game_key, norm_name  # noqa: E402

SEASON, WEEKS = 2026, (5, 6, 7, 8)
MARKETS = ["rec", "rec_yds", "rush_att", "rush_yds", "pass_att", "pass_cmp", "pass_yds"]
OUT = config.ROOT / "data" / "backtests" / "pm_vs_dk_2026.csv"
SNAPS = config.ROOT / "data" / "live" / "parlay"
EMPTY_HI, EMPTY_LO = 0.97, 0.03


def snap_time(p: Path) -> dt.datetime:
    return dt.datetime.strptime(p.name.split("_")[0], "%Y%m%dT%H%MZ").replace(tzinfo=dt.timezone.utc)


def schedule() -> dict:
    import nflreadpy as nfl
    g = nfl.load_schedules(seasons=[SEASON]).filter(pl.col("game_type") == "REG", pl.col("week").is_in(WEEKS))
    out = {}
    for r in g.iter_rows(named=True):
        t = dt.datetime.fromisoformat(f"{r['gameday']}T{r['gametime']}").replace(tzinfo=ZoneInfo("America/New_York"))
        out[(r["week"], game_key(r["home_team"], r["away_team"]))] = {
            "home": r["home_team"], "away": r["away_team"], "kick": t.astimezone(dt.timezone.utc), "gameday": r["gameday"]}
    return out


def dk_rows(sched: dict) -> pl.DataFrame:
    """Per game: DraftKings rows of the last snapshot before kickoff, screened."""
    rows = []
    for wk in WEEKS:
        snaps = sorted(SNAPS.glob(f"*_w{wk}.json.gz"), key=snap_time)
        parsed = []
        for s in snaps:
            with gzip.open(s, "rt") as f:
                parsed.append((s, snap_time(s), Pa.parse(json.load(f)).filter(pl.col("book") == "dk", pl.col("market").is_in(MARKETS))))
        for (w, g), info in sched.items():
            if w != wk:
                continue
            before = [(s, t, d.filter(pl.col("game") == g)) for s, t, d in parsed if t < info["kick"]]
            before = [x for x in before if x[2].height]
            if not before:
                continue
            s, t, d = before[-1]
            for r in d.iter_rows(named=True):
                po = no_vig_over(r["over"], r["under"])
                hold = implied(r["over"]) + implied(r["under"]) - 1
                if not (0.35 <= po <= 0.65 and hold < 0.10):
                    continue
                rows.append({"week": wk, "game": g, **{k: info[k] for k in ("home", "away", "gameday")},
                             "kick": info["kick"].isoformat(), "snapshot": s.name, "snap_utc": t.isoformat(),
                             "player": r["player"], "nkey": r["nkey"], "market": r["market"], "line": r["line"],
                             "dk_over": r["over"], "dk_under": r["under"], "p_over_dk": po})
    return pl.DataFrame(rows)


def pm_event_markets(info: dict) -> dict:
    """(nkey, market, line) -> market slug for one game's Polymarket US event."""
    a, h = (V.SLUG_CODE.get(x, x.lower()) for x in (info["away"], info["home"]))
    slug = f"nfl-{a}-{h}-{info['gameday']}"
    try:
        b = V.pm_get(f"/v1/events/slug/{slug}")
    except Exception as e:  # noqa: BLE001
        print(f"  {slug}: {type(e).__name__}"); return {}
    e = b.get("event", b) if isinstance(b, dict) else {}
    out = {}
    for m in e.get("markets") or []:
        x = V.PM_PAT.match(m.get("question") or "")
        if x and x.group(3) in V.PM_MAP:
            out[(norm_name(x.group(1)), V.PM_MAP[x.group(3)], float(x.group(2)) - 0.5)] = m.get("slug")
    print(f"  {slug}: {len(out)} threshold markets")
    return out


def price_at(slug: str, t: dt.datetime) -> tuple | None:
    end = int(t.timestamp())
    q = urllib.parse.urlencode({"symbol": slug, "timestamp.startTimestamp": end - 86400, "timestamp.endTimestamp": end, "fidelity": 1})
    for k in range(3):
        try:
            h = V.pm_get(f"/v1/price-history?{q}").get("history") or []
            break
        except Exception:  # noqa: BLE001
            time.sleep(2 * (k + 1))
    else:
        return None
    h = [x for x in h if int(x["timestamp"]) <= end]
    if not h:
        return None
    x = max(h, key=lambda z: int(z["timestamp"]))
    return float(x["longPrice"]), float(x["shortPrice"]), int(x["timestamp"])


def fetch() -> None:
    sched = schedule()
    dk = dk_rows(sched)
    print(f"DraftKings screened props: {dk.height} in {dk['game'].n_unique()} games")
    rows = []
    for (wk, g), grp in dk.group_by("week", "game", maintain_order=True):
        idx = pm_event_markets(sched[(wk, g)])
        for r in grp.iter_rows(named=True):
            slug = idx.get((r["nkey"], r["market"], float(r["line"])))
            pr = price_at(slug, dt.datetime.fromisoformat(r["snap_utc"])) if slug else None
            time.sleep(0.1)
            rows.append({**r, "pm_slug": slug, "pm_yes": pr[0] if pr else None, "pm_no": pr[1] if pr else None,
                         "pm_ts": pr[2] if pr else None})
    pl.DataFrame(rows).write_csv(OUT)
    print(f"wrote {OUT} ({len(rows)} rows, {sum(r['pm_slug'] is not None for r in rows)} with a Polymarket market)")


def boot(pnl, cl, n=4000, seed=0):
    W = np.unique(cl); rng = np.random.default_rng(seed); out = []
    for _ in range(n):
        s = rng.choice(W, len(W)); ix = np.concatenate([np.flatnonzero(cl == w) for w in s]); out.append(pnl[ix].mean())
    return np.percentile(out, [2.5, 97.5])


def report() -> None:
    d = pl.read_csv(OUT)
    st = P.load_stats(SEASON).with_columns(pl.col("player_display_name").map_elements(norm_name, return_dtype=pl.Utf8).alias("nkey"))
    sn = P.load_snaps(SEASON)
    snap_keys = {(w, P.TEAM_FIX.get(t, t), norm_name(n)) for w, t, n in zip(sn["week"], sn["team"], sn["player"])}
    long = st.unpivot(index=["nkey", "week", "team"], on=MARKETS, variable_name="market", value_name="actual")
    sides = []
    for r in d.iter_rows(named=True):
        teams = {r["home"], r["away"]}
        a = long.filter(pl.col("nkey") == r["nkey"], pl.col("week") == r["week"], pl.col("market") == r["market"],
                        pl.col("team").is_in(list(teams)))
        if a.height == 1:
            act = float(a["actual"][0] or 0)
        elif a.height == 0 and any((r["week"], t, r["nkey"]) in snap_keys for t in teams):
            act = 0.0
        else:
            continue                                   # void or ambiguous
        if act == r["line"]:
            continue                                   # push (cannot happen on .5 lines)
        for side, dk_odds, pm in (("over", r["dk_over"], r["pm_yes"]), ("under", r["dk_under"], r["pm_no"])):
            won = (act > r["line"]) == (side == "over")
            pm_ok = pm is not None and EMPTY_LO < pm < EMPTY_HI
            pm_cost = pm + V.pm_fee(pm) if pm_ok else None
            sides.append({"week": r["week"], "market": r["market"], "side": side, "won": won, "dk_cost": implied(dk_odds),
                          "pm_cost": pm_cost, "has_pm_market": r["pm_slug"] is not None})
    s = pl.DataFrame(sides)
    q = s.filter(pl.col("pm_cost").is_not_null())
    L = [f"# Polymarket US vs DraftKings prop prices, {SEASON} weeks 5-8", "",
         "Plan: docs/pm_vs_dk_plan.md. Descriptive; no picks. Polymarket price = last one-minute quote at or before the "
         "DraftKings snapshot time, plus its taker fee; no size is known, so fills are not guaranteed.", "",
         f"- DraftKings screened props graded: {s.height // 2} ({s.height} sides) in {d['game'].n_unique()} games.",
         f"- With a Polymarket US market at the same line: {s.filter('has_pm_market').height // 2} props.",
         f"- Sides with a usable Polymarket quote (not an empty book): {q.height}.", ""]
    if q.height:
        diff = (q["pm_cost"] - q["dk_cost"]).to_numpy() * 100
        L += [f"**Price:** Polymarket cheaper on {np.mean(diff < 0):.1%} of sides; mean Polymarket minus DraftKings "
              f"{diff.mean():+.2f} cents per $1 of payout (median {np.median(diff):+.2f}).", "",
              "Stat | sides | PM cheaper | mean PM - DK (cents)", "---|---|---|---"]
        for (m,), g in q.group_by("market", maintain_order=True):
            dd = (g["pm_cost"] - g["dk_cost"]).to_numpy() * 100
            L.append(f"{m} | {g.height} | {np.mean(dd < 0):.0%} | {dd.mean():+.2f}")
        for sd in ("over", "under"):
            g = q.filter(pl.col("side") == sd); dd = (g["pm_cost"] - g["dk_cost"]).to_numpy() * 100
            L.append(f"all {sd}s | {g.height} | {np.mean(dd < 0):.0%} | {dd.mean():+.2f}")
        won, cl = q["won"].to_numpy(), q["week"].to_numpy()
        best = np.minimum(q["pm_cost"].to_numpy(), q["dk_cost"].to_numpy())
        L += ["", "**Buying every quoted side (one unit of stake each), graded** (known answer: should lose about the hold):", "",
              "Price | sides | ROI | interval (weeks)", "---|---|---|---"]
        for name, c in (("DraftKings", q["dk_cost"].to_numpy()), ("Polymarket US", q["pm_cost"].to_numpy()), ("cheaper of the two", best)):
            pnl = np.where(won, 1 / c - 1, -1.0); lo, hi = boot(pnl, cl)
            L.append(f"{name} | {len(pnl)} | {pnl.mean():+.1%} | {lo:+.1%} to {hi:+.1%}")
    text = "\n".join(L) + "\n"
    (config.ROOT / "docs" / "pm_vs_dk.md").write_text(text)
    print(text)


if __name__ == "__main__":
    {"fetch": fetch, "report": report}[sys.argv[1]]()
