"""OpenMarkets prediction-market prices (Kalshi, ProphetX, BettorEdge) as a third record next to Action Network and
ParlayAPI (docs/s1_live_rules.md).

Descriptive only: S1 still picks from Action Network. Each run archives the S1-market player props of this week's
NFL games, compares each venue with DraftKings at DraftKings' exact line, and stores the venues' price on each
pick's side. Read-only API calls; no orders, no account linking.

Probe (docs/evidence/openmarkets_props/, 2026-10-09): player props come from Kalshi, ProphetX and BettorEdge only;
Kalshi and BettorEdge quote full two-sided ladders. At DraftKings' line the no-vig P(over) differed by 1.3-1.7
points on average; median fillable amount $76-$200. One call per game per run (about 15), plus 2 for the catalog.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import urllib.parse
import urllib.request

import polars as pl

from nflbet.parlay import TEAMS, game_key
from nflbet.props import TEAM_FIX, norm_name

BASE = "https://api.openmarkets.ai/flow/v1"
MARKETS = {"player_receptions": "rec", "player_receiving_yards": "rec_yds", "player_rushing_yards": "rush_yds",
           "player_rushing_attempts": "rush_att", "player_passing_yards": "pass_yds", "player_passing_attempts": "pass_att",
           "player_passing_completions": "pass_cmp"}
VENUES = {"Kalshi": "kalshi", "ProphetX": "prophetx", "BettorEdge": "bettoredge"}
PICK_COLS = [f"om_{v}_odds" for v in VENUES.values()] + [f"om_{v}_avail" for v in VENUES.values()]
SCHEMA = {"venue": pl.Utf8, "game": pl.Utf8, "nkey": pl.Utf8, "player": pl.Utf8, "market": pl.Utf8, "line": pl.Float64,
          "p_over": pl.Float64, "p_under": pl.Float64, "avail_over": pl.Float64, "avail_under": pl.Float64}


def _get(path: str, key: str, **q):
    url = f"{BASE}{path}" + (("?" + urllib.parse.urlencode(q)) if q else "")
    time.sleep(1.0)
    req = urllib.request.Request(url, headers={"X-API-Key": key, "Accept": "application/json", "User-Agent": "nfl-betting-model/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def fetch(key: str | None = None, now: dt.datetime | None = None, days: int = 8, spreads: bool = True) -> list[dict]:
    """S1-market player-prop positions (and, with `spreads`, game spread positions for the ATS tracker) of NFL games
    starting within `days`, each tagged with its contest title."""
    key = key or os.environ["OPENMARKETS_API_KEY"]
    now = now or dt.datetime.now(dt.timezone.utc)
    nfl = next(x for x in _get("/leagues", key)["data"] if x.get("name") == "NFL")
    contests, cursor = [], None
    for _ in range(10):
        q = {"league_id": nfl["id"], "limit": 200}
        if cursor:
            q["cursor"] = cursor
        c = _get("/contests", key, **q)
        contests += c.get("data", [])
        pg = c.get("pagination") or {}
        if not pg.get("has_more"):
            break
        cursor = pg.get("next_cursor")
    out = []
    for x in contests:
        try:
            t = dt.datetime.fromisoformat(x["starts_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError, AttributeError):
            continue
        if x.get("type") == "tournament" or not (now <= t <= now + dt.timedelta(days=days)):
            continue
        for p in _get(f"/contests/{x['id']}/liquidity", key).get("data", []):
            if p.get("market_key") in MARKETS or (spreads and p.get("market_key") == "spread"):
                out.append({"contest_title": x.get("title"), "starts_at": x["starts_at"], **p})
    return out


def _teams(title: str) -> str | None:
    m = re.match(r"NFL:\s*(.+?)\s+vs\.?\s+(.+)$", title or "")
    if not m:
        return None
    a, b = TEAMS.get(m.group(1).strip()), TEAMS.get(m.group(2).strip())
    return game_key(a, b) if a and b else None


def parse(rows: list[dict]) -> pl.DataFrame:
    """Two-sided quotes per venue: game, player, S1 market, line, prices as probabilities, fillable USD per side."""
    sides: dict = {}
    for r in rows:
        g, mk = _teams(r.get("contest_title")), MARKETS.get(r.get("market_key"))
        if not (g and mk) or r.get("side_key") not in ("over", "under") or r.get("variable") in (None, ""):
            continue
        name = re.split(r"\s+(?:over|under)\s+", r.get("title") or "")[0].strip()
        for v in r.get("partner_liquidities") or []:
            ven = VENUES.get(v.get("partner_name"))
            if ven and v.get("actionable") and v.get("price"):
                k = (ven, g, norm_name(name), mk, float(r["variable"]))
                sides.setdefault(k, {"player": name})[r["side_key"]] = (float(v["price"]), float(v.get("available") or 0))
    out = [{"venue": k[0], "game": k[1], "nkey": k[2], "player": s["player"], "market": k[3], "line": k[4],
            "p_over": s["over"][0], "p_under": s["under"][0], "avail_over": s["over"][1], "avail_under": s["under"][1]}
           for k, s in sides.items() if "over" in s and "under" in s]
    return pl.DataFrame(out, schema=SCHEMA)


def american(p: float) -> float:
    """Price as a probability (cost of a share paying 1) -> American odds."""
    return -100 * p / (1 - p) if p >= 0.5 else 100 * (1 - p) / p


def _nv(o: float, u: float) -> float:
    io = -o / (-o + 100) if o < 0 else 100 / (o + 100)
    iu = -u / (-u + 100) if u < 0 else 100 / (u + 100)
    return io / (io + iu)


def compare(om: pl.DataFrame, dk: pl.DataFrame) -> list[dict]:
    """Per venue against DraftKings at DK's exact line. dk: parlay.parse/an_lines shape filtered to book 'dk'.
    n_both = DK props with a two-sided venue quote at that line; gap = mean |no-vig P(over) difference| in points;
    median_avail = median fillable USD on the thinner side at those lines."""
    res = []
    for ven in VENUES.values():
        j = dk.join(om.filter(pl.col("venue") == ven), on=["game", "nkey", "market", "line"], how="inner")
        gaps, depth = [], []
        for r in j.iter_rows(named=True):
            pv = r["p_over"] / (r["p_over"] + r["p_under"])
            gaps.append(abs(_nv(r["over"], r["under"]) - pv) * 100)
            depth.append(min(r["avail_over"], r["avail_under"]))
        res.append({"venue": ven, "n_dk": dk.height, "n_both": j.height,
                    "mean_gap_pts": round(sum(gaps) / len(gaps), 2) if gaps else None,
                    "median_avail": sorted(depth)[len(depth) // 2] if depth else None})
    return res


def attach(picks: pl.DataFrame, om: pl.DataFrame | None) -> pl.DataFrame:
    """Each venue's American price and fillable USD on the pick's side at the pick's line (null when not quoted)."""
    if om is None:
        return picks.with_columns(*(pl.lit(None, pl.Float64).alias(c) for c in PICK_COLS))
    idx = {(r["venue"], r["game"], r["nkey"], r["market"], r["line"]): r for r in om.iter_rows(named=True)}
    cols = {c: [] for c in PICK_COLS}
    for p in picks.iter_rows(named=True):
        g = game_key(TEAM_FIX.get(p["home"], p["home"]), TEAM_FIX.get(p["away"], p["away"]))
        for ven in VENUES.values():
            r = idx.get((ven, g, norm_name(p["player"]), p["market"], float(p["line"])))
            side = "under" if p["side"] == "under" else "over"
            cols[f"om_{ven}_odds"].append(american(r[f"p_{side}"]) if r else None)
            cols[f"om_{ven}_avail"].append(r[f"avail_{side}"] if r else None)
    return picks.with_columns(*(pl.Series(c, v, dtype=pl.Float64) for c, v in cols.items()))


SPREAD_VENUES = {"Kalshi", "Polymarket", "PolymarketUS", "ProphetX", "4Casters", "BettorEdge", "SX Bet", "BetOpenly"}


def spreads(rows: list[dict]) -> pl.DataFrame:
    """Each exchange's main game spread: game, venue, home_line (nflverse sign: positive = home favored), home and
    away price (probabilities). Main line = the two-sided line whose prices are closest to even."""
    sides: dict = {}
    for r in rows:
        g = _teams(r.get("contest_title"))
        if r.get("market_key") != "spread" or not g or r.get("side_key") not in ("home", "away") or r.get("variable") in (None, ""):
            continue
        v = float(r["variable"])
        home_line = -v if r["side_key"] == "home" else v          # the home side's handicap -3.5 = home favored by 3.5
        for q in r.get("partner_liquidities") or []:
            if q.get("actionable") and q.get("price") and q.get("partner_name") in SPREAD_VENUES:
                sides.setdefault((g, q["partner_name"], home_line), {})[r["side_key"]] = float(q["price"])
    best: dict = {}
    for (g, ven, hl), sd in sides.items():
        if "home" in sd and "away" in sd:
            dev = abs(sd["home"] / (sd["home"] + sd["away"]) - 0.5)
            if (g, ven) not in best or dev < best[(g, ven)][0]:
                best[(g, ven)] = (dev, hl, sd["home"], sd["away"])
    out = [{"game": g, "venue": ven, "home_line": hl, "p_home": ph, "p_away": pa} for (g, ven), (_, hl, ph, pa) in best.items()]
    return pl.DataFrame(out, schema={"game": pl.Utf8, "venue": pl.Utf8, "home_line": pl.Float64, "p_home": pl.Float64, "p_away": pl.Float64})
