"""Sharp-lag scan: Pinnacle (recorded PinnRadar board) vs Novig (live public catalog), exact-line matches only.
Method and caveats: docs/sharp_lag_scan.md. Descriptive one-off snapshot, not a tested edge, not a tracked pick list.

  PYTHONPATH=src python scripts/audit/sharp_lag_scan.py [--out DIR] [--min-edge 0.03] [--min-depth 50]

Reads data/pinnacle/radar/ (run scripts/fetch/pinnradar_tidy.py first for the move column). Fetches Novig's NFL
catalog (keyless, read-only). Writes <out>/sharp_lag_<UTC stamp>.csv (every matched side) and prints the qualifying
rows as a Markdown table.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import gzip
import json
import re
from pathlib import Path

import polars as pl

from nflbet.sources import venues as V
from nflbet.sources.ids import TEAM_FIX, TEAMS, norm_name

R = Path("data/pinnacle/radar")
UNITS = {"Receptions": "RECEPTIONS", "Receiving Yards": "RECEIVING_YARDS", "Rushing Yards": "RUSHING_YARDS",
         "Rush Attempts": "RUSHING_ATTEMPTS", "Passing Yards": "PASSING_YARDS", "Pass Attempts": "PASSING_ATTEMPTS",
         "Pass Completions": "PASSING_COMPLETIONS", "Touchdown Passes": "PASSING_TOUCHDOWNS",
         "Interceptions": "INTERCEPTIONS_THROWN", "Touchdowns": "TOUCHDOWNS"}   # Pinnacle units -> Novig marketType
NV_SPREAD = re.compile(r"^([A-Z]{2,3}) ([+-]?\d+(?:\.\d+)?)$")
NV_PROP = re.compile(r"^(.+?) (\d+(?:\.\d+)?) ([A-Z_]+)$")


def devig_mult(a: float, b: float) -> float:
    """Proportional no-vig probability of side a from decimal prices a, b."""
    return (1 / a) / (1 / a + 1 / b)


def devig_power(a: float, b: float) -> float:
    """Power no-vig: k with (1/a)^k + (1/b)^k = 1; less generous to longshots than proportional."""
    lo, hi = 1.0, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        lo, hi = (lo, k) if (1 / a) ** k + (1 / b) ** k < 1 else (k, hi)
    return (1 / a) ** k


def pinnacle_state() -> tuple[dict, str]:
    """Current prematch board: newest full board, then every later delta (a delta event replaces the stored one)."""
    fulls = sorted(glob.glob(str(R / "2*" / "full_*.json.gz")), key=lambda p: re.search(r"full_(\S+)\.json", p).group(1))
    if not fulls:
        raise SystemExit("no PinnRadar full board under data/pinnacle/radar")
    tf = re.search(r"full_(\S+)\.json", fulls[-1]).group(1)
    state = {e["event_id"]: e for e in json.load(gzip.open(fulls[-1]))["events"]}
    tmax = tf
    for p in sorted(glob.glob(str(R / "2*" / "prematch_deltas.jsonl.gz"))):
        for ln in gzip.open(p, "rt"):
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r["t"] > tf:
                for e in r["events"]:
                    state[e["event_id"]] = e
                tmax = max(tmax, r["t"])
    return state, tmax


def novig_now() -> tuple[dict, list, str]:
    now = dt.datetime.now(dt.timezone.utc)
    lo, hi = int((now - dt.timedelta(hours=6)).timestamp() * 1000), int((now + dt.timedelta(days=8)).timestamp() * 1000)
    ev = {e["eventId"]: e for e in V.nv_get("/v3/public/catalog/events", league="NFL", startsAfter=lo, startsBefore=hi,
                                            limit=500).get("items", [])}
    ms, after = [], None
    for _ in range(20):
        q = dict(league="NFL", startsAfter=lo, startsBefore=hi, limit=5000) | ({"after": after} if after else {})
        b = V.nv_get("/v3/public/catalog/markets", **q)
        ms += b.get("items", [])
        after = b.get("next")
        if not after:
            break
    return ev, ms, f"{now:%Y%m%dT%H%M%SZ}"


def nv_cost(m: dict, i: int) -> tuple[float | None, float]:
    """Cost per $1 payout to take outcome i = 1 - best resting bid on the other outcome; depth in $ of payout.
    Pregame fee is zero on Novig NFL markets (fee charged WHEN_LIVE); a market charged ALWAYS adds venues.nv_fee."""
    outs = m.get("outcomes") or []
    bid = outs[1 - i].get("bid") or {}
    if not bid.get("price"):
        return None, 0.0
    c = 1 - float(bid["price"])
    if not 0 < c < 1:
        return None, 0.0
    return c + V.nv_fee(m, c), float(bid.get("qty") or 0) / 100


def first_fair(tidy: pl.DataFrame, **match) -> float | None:
    q = tidy
    for k, v in match.items():
        q = q.filter(pl.col(k).is_null()) if v is None else q.filter(pl.col(k) == v)
    if q.height == 0:
        return None
    f = q.sort("t").row(0, named=True)
    return devig_mult(f["price_a"], f["price_b"])


def scan() -> tuple[pl.DataFrame, str, str]:
    state, t_pin = pinnacle_state()
    nev, nms, t_nv = novig_now()
    tg = pl.read_csv(R / "tidy" / "game_lines.csv.gz").filter(pl.col("board") == "prematch") \
        if (R / "tidy" / "game_lines.csv.gz").exists() else pl.DataFrame()
    ts = pl.read_csv(R / "tidy" / "specials.csv.gz", infer_schema_length=0).filter(pl.col("board") == "prematch") \
        if (R / "tidy" / "specials.csv.gz").exists() else pl.DataFrame()
    nv_game = collections.defaultdict(list)
    nv_prop = {}
    for m in nms:
        ev = nev.get(m["eventId"])
        if not ev or m.get("status") != "OPEN" or ev.get("status") != "OPEN_PREGAME" or len(m.get("outcomes") or []) != 2:
            continue
        if " @ " in (ev.get("description") or ""):
            a, h = (x.strip() for x in ev["description"].split(" @ "))
            nv_game[(TEAMS.get(h), TEAMS.get(a))].append(m)
        d = NV_PROP.match(m.get("description") or "")
        if d and d.group(3) == m["marketType"]:
            nv_prop[(norm_name(d.group(1)), m["marketType"], float(m["strike"]))] = m
    rows = []

    def add(kind, game, bet, pin_this, pin_other, m, i, p0):
        c, depth = nv_cost(m, i)
        if c is None:
            return
        pm, pp = devig_mult(pin_this, pin_other), devig_power(pin_this, pin_other)
        rows.append(dict(kind=kind, game=game, side=bet, pin_price=pin_this, pin_other=pin_other,
                         pin_hold=1 / pin_this + 1 / pin_other - 1, fair_mult=pm, fair_power=pp, novig_cost=c,
                         novig_depth=depth, edge_mult=pm / c - 1, edge_power=pp / c - 1,
                         move_pp=None if p0 is None else (pm - p0) * 100))

    for eid, g in state.items():
        if g.get("league_name") != "NFL" or g.get("parent_id") or not g.get("periods"):
            continue
        h, a = g["home"], g["away"]
        H, A = TEAMS.get(h), TEAMS.get(a)
        per = g["periods"].get("num_0") or {}
        game = f"{a} @ {h}"
        mv = (lambda mk, line, side_a: (lambda p: None if p is None else (p if side_a else 1 - p))(
            first_fair(tg, event_id=eid, period=0, market=mk, line=line)) if tg.height else None)
        for m in nv_game.get((H, A), []):
            t, outs = m["marketType"], m["outcomes"]
            if t == "MONEY" and (per.get("money_line") or {}).get("home"):
                ml = per["money_line"]
                for i, o in enumerate(outs):
                    tm = TEAM_FIX.get(o["name"], o["name"])
                    if tm in (H, A):
                        hs = tm == H
                        add("Moneyline", game, f"{tm} ML", ml["home"] if hs else ml["away"], ml["away"] if hs else ml["home"],
                            m, i, mv("money_line", None, hs))
            elif t == "SPREAD":
                for i, o in enumerate(outs):
                    x = NV_SPREAD.match(o.get("name") or "")
                    if not x:
                        continue
                    tm, hv = TEAM_FIX.get(x.group(1), x.group(1)), float(x.group(2))
                    if tm not in (H, A):
                        continue
                    hdp = hv if tm == H else -hv           # Pinnacle keys spreads by the home handicap
                    v = next((v for v in (per.get("spreads") or {}).values() if float(v["hdp"]) == hdp), None)
                    if v:
                        hs = tm == H
                        add("Spread", game, o["name"], v["home"] if hs else v["away"], v["away"] if hs else v["home"],
                            m, i, mv("spreads", hdp, hs))
            elif t in ("TOTAL", "TEAM_TOTAL"):
                k = float(m["strike"])
                if t == "TOTAL":
                    ladder, label, mk = per.get("totals") or {}, "Total", "totals"
                else:
                    team = m["description"].rsplit(" ", 2)[0]
                    side = "home" if team == h else "away" if team == a else None
                    if not side:
                        continue
                    ladder, label, mk = ((per.get("team_totals") or {}).get(side) or {}), f"Team total {team}", f"team_total_{side}"
                v = next((v for v in ladder.values() if float(v["points"]) == k), None)
                if v:
                    for i, o in enumerate(outs):
                        ov = o["name"].startswith("Over")
                        add(label.split(" ")[0] if t == "TOTAL" else "Team total", game, f"{label} {o['name']}",
                            v["over"] if ov else v["under"], v["under"] if ov else v["over"], m, i, mv(mk, k, ov))
    for e in state.values():
        u = UNITS.get(e.get("special_units"))
        if e.get("league_name") != "NFL" or e.get("special_category") != "Player Props" or not u:
            continue
        player = re.sub(r" Total .*$", "", e["special"])
        for mk in (e.get("special_markets") or {}).get("num_0", []):
            pr = {p["name"]: p for p in mk.get("prices") or []}
            if set(pr) != {"Over", "Under"}:
                continue
            k = float(pr["Over"]["points"])
            m = nv_prop.get((norm_name(player), u, k))
            if not m:
                continue
            p0 = None
            if ts.height:
                hist = ts.filter((pl.col("event_id") == str(e["event_id"])) & (pl.col("points") == str(pr["Over"]["points"]))).sort("t")
                if hist.height:
                    f = {r["outcome"]: float(r["price"]) for r in hist.filter(pl.col("t") == hist["t"][0]).iter_rows(named=True)}
                    if {"Over", "Under"} <= set(f):
                        p0 = devig_mult(f["Over"], f["Under"])
            for i, o in enumerate(m["outcomes"]):
                ov = o["name"].startswith("Over")
                add(f"Prop {e['special_units']}", f"{e['away']} @ {e['home']}", f"{player} {o['name']}",
                    pr["Over" if ov else "Under"]["price"], pr["Under" if ov else "Over"]["price"], m, i,
                    None if p0 is None else (p0 if ov else 1 - p0))
    return pl.DataFrame(rows, infer_schema_length=None), t_pin, t_nv


def american(p: float) -> str:
    return f"{-100 * p / (1 - p):+.0f}" if p >= 0.5 else f"+{100 * (1 - p) / p:.0f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/pinnacle/sharp_lag")
    ap.add_argument("--min-edge", type=float, default=0.03)
    ap.add_argument("--min-depth", type=float, default=50.0)
    ap.add_argument("--move-pp", type=float, default=0.3)
    a = ap.parse_args()
    df, t_pin, t_nv = scan()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    out = Path(a.out) / f"sharp_lag_{t_nv}.csv"
    df.write_csv(out)
    q = df.filter((pl.col("edge_mult") >= a.min_edge) & (pl.col("edge_power") >= a.min_edge)
                  & (pl.col("novig_depth") >= a.min_depth)).sort("edge_power", descending=True)
    print(f"Pinnacle as of {t_pin}, Novig {t_nv}: {df.height} matched sides, {q.height} qualify -> {out}\n")
    print("| Market | Game | Side | Pinnacle | Pinn fair | Novig | Edge | Novig depth | Pinnacle move |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in q.iter_rows(named=True):
        mvp = r["move_pp"]
        d = "n/a" if mvp is None else "toward" if mvp >= a.move_pp else "away" if mvp <= -a.move_pp else "flat"
        print(f"| {r['kind']} | {r['game']} | {r['side']} | {american(1 / r['pin_price'])} | {r['fair_power'] * 100:.1f}% | "
              f"{american(r['novig_cost'])} | {min(r['edge_mult'], r['edge_power']) * 100:.1f}% | ${r['novig_depth']:,.0f} | "
              f"{d}{'' if mvp is None else f' ({mvp:+.2f}pp)'} |")


if __name__ == "__main__":
    main()
