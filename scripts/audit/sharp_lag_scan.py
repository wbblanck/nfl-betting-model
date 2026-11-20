"""Sharp-lag scan: Pinnacle (recorded PinnRadar board) vs Novig (live public catalog), exact-line matches only.
Method and caveats: docs/sharp_lag_scan.md. Descriptive one-off snapshot, not a tested edge, not a tracked pick list.

  PYTHONPATH=src python scripts/audit/sharp_lag_scan.py [--out DIR] [--min-edge 0.03] [--min-depth 50]
  PYTHONPATH=src python scripts/audit/sharp_lag_scan.py --shop --week 11 --parlay <ParlayAPI snapshot .json.gz>
      line shopping: each matched side's best price across Novig, Kalshi, Polymarket US and DK/FanDuel (ParlayAPI)

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
from nflbet.sources.ids import TEAM_FIX, TEAMS, game_key, norm_name

R = Path("data/pinnacle/radar")
UNITS = {"Receptions": "RECEPTIONS", "Receiving Yards": "RECEIVING_YARDS", "Rushing Yards": "RUSHING_YARDS",
         "Rush Attempts": "RUSHING_ATTEMPTS", "Passing Yards": "PASSING_YARDS", "Pass Attempts": "PASSING_ATTEMPTS",
         "Pass Completions": "PASSING_COMPLETIONS", "Touchdown Passes": "PASSING_TOUCHDOWNS",
         "Interceptions": "INTERCEPTIONS_THROWN", "Touchdowns": "TOUCHDOWNS"}   # Pinnacle units -> Novig marketType
NV_SPREAD = re.compile(r"^([A-Z]{2,3}) ([+-]?\d+(?:\.\d+)?)$")
MIN_DEPTH = 50.0                # $ of payout an exchange price needs behind it to count
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


S1_KEY = {"Receptions": "rec", "Receiving Yards": "rec_yds", "Rushing Yards": "rush_yds", "Rush Attempts": "rush_att",
          "Passing Yards": "pass_yds", "Pass Attempts": "pass_att", "Pass Completions": "pass_cmp"}


def shop_quotes(week: int, parlay_path: str | None) -> tuple[dict, dict]:
    """(game, nkey, s1 market, line) -> {side: [(venue, cost, depth or None)]} for Kalshi, Polymarket US and DK/FD
    (ParlayAPI file), and the source times. Costs are all-in per $1 of payout (book vig in the price, exchange fees added)."""
    from nflbet.quant.odds import implied
    from nflbet.sources import parlay as P
    out: dict = collections.defaultdict(lambda: {"over": [], "under": []})
    times = {}
    now = dt.datetime.now(dt.timezone.utc)
    try:
        for k, q in V.ks_quotes(V.ks_markets()).items():
            if q["mult"] is None:
                continue
            for side in ("over", "under"):
                if q[side]:
                    c, sz = q[side]
                    out[k][side].append(("Kalshi", c + V.ks_fee(c, q["mult"]), sz))
        times["Kalshi"] = f"{now:%Y%m%dT%H%M%SZ}"
    except Exception as e:  # noqa: BLE001 - one venue failing leaves the others
        print(f"Kalshi unavailable: {e!r}"[:200])
    try:
        for k, q in V.pm_quotes(V.pm_markets(week, now, verbose=False)).items():
            for side in ("over", "under"):
                c = q[side]
                if 0 < c < 1:
                    out[k][side].append(("Polymarket US", c + V.pm_fee(c, q["fee"]), None))
        times["Polymarket US"] = f"{now:%Y%m%dT%H%M%SZ}"
    except Exception as e:  # noqa: BLE001
        print(f"Polymarket US unavailable: {e!r}"[:200])
    if parlay_path:
        rows = json.load(gzip.open(parlay_path))
        pa = P.parse(rows)
        for r in pa.iter_rows(named=True):
            name = {"dk": "DraftKings", "fd": "FanDuel"}.get(r["book"], r["book"])
            k = (r["game"], r["nkey"], r["market"], r["line"])
            out[k]["over"].append((name, implied(r["over"]), None))
            out[k]["under"].append((name, implied(r["under"]), None))
        times["DK/FD (ParlayAPI)"] = re.search(r"(\d{8}T\d{4}Z)", parlay_path).group(1) if re.search(r"(\d{8}T\d{4}Z)", parlay_path) else parlay_path
    return out, times


def scan(shop: dict | None = None) -> tuple[pl.DataFrame, str, str]:
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

    def add(kind, game, bet, pin_this, pin_other, m, i, p0, extra=()):
        c, depth = nv_cost(m, i) if m is not None else (None, 0.0)
        cands = ([("Novig", c, depth)] if c is not None else []) + list(extra)
        elig = [x for x in cands if x[1] is not None and (x[2] is None or x[2] >= MIN_DEPTH)]
        if not elig:
            return
        venue, c, depth = min(elig, key=lambda x: x[1])
        others = sorted([x[1] for x in elig if x[0] != venue] + [1 / pin_this])   # Pinnacle counts as a venue
        gap = (1 / c) / (1 / others[0]) - 1 if others and others[0] >= c else 0.0   # bestbook.app's "% better than next"
        pm, pp = devig_mult(pin_this, pin_other), devig_power(pin_this, pin_other)
        rows.append(dict(kind=kind, game=game, side=bet, venue=venue, gap_next=gap,
                         venues="; ".join(f"{v} {american(x)}" + ("" if d is None else f" (${d:,.0f})") for v, x, d in sorted(cands, key=lambda y: y[1])),
                         pin_price=pin_this, pin_other=pin_other,
                         pin_hold=1 / pin_this + 1 / pin_other - 1, fair_mult=pm, fair_power=pp, best_cost=c,
                         best_depth=depth if depth is not None else float("nan"), edge_mult=pm / c - 1, edge_power=pp / c - 1,
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
            ext = {"over": [], "under": []}
            if shop is not None and S1_KEY.get(e.get("special_units")):
                H, A = TEAMS.get(e.get("home")), TEAMS.get(e.get("away"))
                if H and A:
                    ext = shop.get((game_key(H, A), norm_name(player), S1_KEY[e["special_units"]], k), ext)
            if not m and not (ext["over"] or ext["under"]):
                continue
            p0 = None
            if ts.height:
                hist = ts.filter((pl.col("event_id") == str(e["event_id"])) & (pl.col("points") == str(pr["Over"]["points"]))).sort("t")
                if hist.height:
                    f = {r["outcome"]: float(r["price"]) for r in hist.filter(pl.col("t") == hist["t"][0]).iter_rows(named=True)}
                    if {"Over", "Under"} <= set(f):
                        p0 = devig_mult(f["Over"], f["Under"])
            for ov in (True, False):
                i = None
                if m:
                    i = next((j for j, o in enumerate(m["outcomes"]) if o["name"].startswith("Over") == ov), None)
                add(f"Prop {e['special_units']}", f"{e['away']} @ {e['home']}", f"{player} {'Over' if ov else 'Under'} {k:g}",
                    pr["Over" if ov else "Under"]["price"], pr["Under" if ov else "Over"]["price"],
                    m if i is not None else None, i if i is not None else 0,
                    None if p0 is None else (p0 if ov else 1 - p0), ext["over" if ov else "under"])
    return pl.DataFrame(rows, infer_schema_length=None), t_pin, t_nv


def american(p: float) -> str:
    return f"{-100 * p / (1 - p):+.0f}" if p >= 0.5 else f"+{100 * (1 - p) / p:.0f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/pinnacle/sharp_lag")
    ap.add_argument("--min-edge", type=float, default=0.03)
    ap.add_argument("--min-depth", type=float, default=50.0)
    ap.add_argument("--move-pp", type=float, default=0.3)
    ap.add_argument("--min-gap", type=float, default=0.0, help="best price at least this much better than the next best")
    ap.add_argument("--shop", action="store_true", help="best price across Novig, Kalshi, Polymarket US, DK/FD")
    ap.add_argument("--week", type=int, default=0, help="NFL week, for Polymarket US event lookup")
    ap.add_argument("--parlay", default=None, help="ParlayAPI snapshot (.json.gz) for DK/FanDuel prop prices")
    a = ap.parse_args()
    global MIN_DEPTH
    MIN_DEPTH = a.min_depth
    shop, times = shop_quotes(a.week, a.parlay) if a.shop else (None, {})
    df, t_pin, t_nv = scan(shop)
    for v, t in times.items():
        print(f"{v} as of {t}")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    out = Path(a.out) / f"sharp_lag_{t_nv}.csv"
    df.write_csv(out)
    q = df.filter((pl.col("edge_mult") >= a.min_edge) & (pl.col("edge_power") >= a.min_edge)
                  & (pl.col("gap_next") >= a.min_gap)).sort("edge_power", descending=True)
    print(f"Pinnacle as of {t_pin}, Novig {t_nv}: {df.height} matched sides, {q.height} qualify -> {out}\n")
    print("| Market | Game | Side | Pinnacle | Pinn fair | Best venue | Best price | Edge | Depth | Pinnacle move | All venues |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in q.iter_rows(named=True):
        mvp = r["move_pp"]
        d = "n/a" if mvp is None else "toward" if mvp >= a.move_pp else "away" if mvp <= -a.move_pp else "flat"
        dep = "n/a" if r["best_depth"] != r["best_depth"] else f"${r['best_depth']:,.0f}"
        mv = "" if mvp is None else f" ({mvp:+.2f}pp)"
        print(f"| {r['kind']} | {r['game']} | {r['side']} | {american(1 / r['pin_price'])} | {r['fair_power'] * 100:.1f}% | "
              f"{r['venue']} | {american(r['best_cost'])} | {min(r['edge_mult'], r['edge_power']) * 100:.1f}% | {dep} | "
              f"{d}{mv} | {r['venues']} |")


if __name__ == "__main__":
    main()
