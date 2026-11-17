"""Props closing-line value record (docs/props_clv_rules.md). Record only, unvalidated; never feeds a pick.

Pinnacle prices come from PinnRadar (https://pinnradar.com, a reseller of Pinnacle's board; free key, 100 requests a day,
secret PINN_API). One call to /kit/v1/prematch/fixtures?sport_id=5&include_specials=1 returns every NFL game and its
player props with prices (probe: docs/evidence/pinnradar/20261117T035156Z). DraftKings and FanDuel come from ParlayAPI
(src/nflbet/sources/parlay.py).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import polars as pl
from scipy.stats import norm

from nflbet.quant.odds import implied
from nflbet.sources.ids import TEAMS, game_key, norm_name

PINN_URL = "https://pinnradar.com/kit/v1/prematch/fixtures"
PINN_SPORT = 5                         # API sport id 5 = Football (Pinnacle 15), docs "Sport IDs"
UNITS = {"Passing Yards": "pass_yds", "Rushing Yards": "rush_yds", "Receiving Yards": "rec_yds", "Receptions": "rec",
         "Touchdown Passes": "pass_td", "Passing Attempts": "pass_att", "Pass Attempts": "pass_att",
         "Completions": "pass_cmp", "Pass Completions": "pass_cmp", "Rushing Attempts": "rush_att",
         "Carries": "rush_att"}    # probe saw the first five; the rest are guesses that only add rows if the title fits
PINN_SCHEMA = {"game": pl.Utf8, "home": pl.Utf8, "away": pl.Utf8, "starts": pl.Utf8, "nkey": pl.Utf8, "player": pl.Utf8,
               "market": pl.Utf8, "line": pl.Float64, "over_dec": pl.Float64, "under_dec": pl.Float64,
               "max_risk": pl.Float64}
MAX_HOLD = 0.10
CLOSE_MAX_MIN = 30.0                   # a close must be taken 30 minutes or less before kickoff
SMALL = {"rec", "pass_att", "pass_cmp", "rush_att", "pass_td"}


# ------------------------------------------------------------------------------------------ Pinnacle

def fetch_pinnacle(key: str | None = None) -> tuple[dict, dict]:
    """(board, rate headers). The key is sent only as a header and never returned or archived."""
    key = (key or os.environ["PINN_API"]).strip()
    q = urllib.parse.urlencode({"sport_id": PINN_SPORT, "include_specials": 1})
    req = urllib.request.Request(f"{PINN_URL}?{q}", headers={"x-portal-apikey": key, "Accept": "application/json",
                                                             "User-Agent": "nfl-betting-model/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        hdr = {k: v for k, v in r.headers.items() if k.lower().startswith(("x-rate", "retry"))}
        return json.loads(r.read()), hdr


def parse_pinnacle(board: dict) -> pl.DataFrame:
    """NFL player-prop totals: one row per game, player and market (main line, decimal prices, max_risk)."""
    out = []
    for e in board.get("events") or []:
        if "nfl" not in str(e.get("league_name", "")).lower() or not e.get("parent_id"):
            continue
        if e.get("special_category") != "Player Props":
            continue
        m = UNITS.get(str(e.get("special_units")))
        h, a = TEAMS.get(e.get("home")), TEAMS.get(e.get("away"))
        title = str(e.get("special") or "")
        mt = re.match(r"^(.*?)\s+Total\s+" + re.escape(str(e.get("special_units"))) + r"\s*$", title)
        if not (m and h and a and mt):
            continue
        for mk in ((e.get("special_markets") or {}).get("num_0") or []):
            if mk.get("type") != "total":
                continue
            px = {str(p.get("name")).lower(): p for p in mk.get("prices") or []}
            o, u = px.get("over"), px.get("under")
            if not (o and u) or o.get("points") is None or o.get("points") != u.get("points"):
                continue
            out.append({"game": game_key(h, a), "home": h, "away": a, "starts": e.get("starts"), "nkey": norm_name(mt.group(1)),
                        "player": mt.group(1), "market": m, "line": float(o["points"]), "over_dec": float(o["price"]),
                        "under_dec": float(u["price"]), "max_risk": float(mk["max_risk"]) if mk.get("max_risk") is not None else None})
    return pl.DataFrame(out, schema=PINN_SCHEMA).unique(["game", "nkey", "market"], keep="first", maintain_order=True)


# ------------------------------------------------------------------------------------------ quotes

def american_to_dec(a: float) -> float:
    return 1 + (a / 100 if a > 0 else 100 / -a)


def fair_over(over_dec: float, under_dec: float) -> tuple[float, float] | None:
    """(de-vigged P(over), hold) from two decimal prices, or None if a side is missing or the hold is 10%+."""
    if not over_dec or not under_dec or over_dec <= 1 or under_dec <= 1:
        return None
    io, iu = 1 / over_dec, 1 / under_dec
    hold = io + iu - 1
    if hold >= MAX_HOLD or hold < -0.02:
        return None
    return io / (io + iu), hold


# ------------------------------------------------------------------------------------------ line moves

def sigma(market: str, line: float, s: float) -> float:
    return s * math.sqrt(max(line, 0.5))


def p_over_at(line_q: float, q: float, line_to: float, market: str, s: float) -> float:
    """P(over line_to) from a quote (line_q, fair P(over) q) under Normal(mu, s*sqrt(line)) (docs/props_clv_rules.md)."""
    if line_q == line_to:
        return q
    q = min(max(q, 1e-4), 1 - 1e-4)
    mu = line_q + sigma(market, line_q, s) * norm.ppf(q)
    sd = sigma(market, (line_q + line_to) / 2, s)
    return float(norm.cdf((mu - line_to) / sd))


def fit_s(pairs: pl.DataFrame, market: str) -> float | None:
    """Least-squares s for one market on pairs (line_a, q_a, line_b, q_b): predict q_b from (line_a, q_a)."""
    d = pairs.filter(pl.col("market") == market)
    if not d.height:
        return None
    grid = np.arange(0.05, 3.0001, 0.01) if market in SMALL else np.arange(0.5, 15.0001, 0.05)
    la, qa, lb, qb = (d[c].to_numpy() for c in ("line_a", "q_a", "line_b", "q_b"))
    best, err = None, math.inf
    for s in grid:
        pred = np.array([p_over_at(x, y, z, market, s) for x, y, z in zip(la, qa, lb)])
        e = float(np.mean((pred - qb) ** 2))
        if e < err:
            best, err = float(s), e
    return best


def mae(pairs: pl.DataFrame, market: str, s: float | None) -> tuple[float, float, int]:
    """(model MAE, baseline MAE = ignore the line difference, n) on one market's pairs."""
    d = pairs.filter(pl.col("market") == market)
    la, qa, lb, qb = (d[c].to_numpy() for c in ("line_a", "q_a", "line_b", "q_b"))
    base = float(np.mean(np.abs(qa - qb))) if d.height else math.nan
    if s is None or not d.height:
        return math.nan, base, d.height
    pred = np.array([p_over_at(x, y, z, market, s) for x, y, z in zip(la, qa, lb)])
    return float(np.mean(np.abs(pred - qb))), base, d.height


# ------------------------------------------------------------------------------------------ CLV

def last_close(rows: pl.DataFrame) -> pl.DataFrame:
    """Per source, game, player and market: the last snapshot before kickoff, kept only if 30 minutes or less before."""
    d = rows.filter((pl.col("lead_min") > 0) & (pl.col("lead_min") <= CLOSE_MAX_MIN))
    return d.sort("snap_utc").group_by(["source", "game", "nkey", "market"], maintain_order=True).last()


def pick_clv(picks: pl.DataFrame, closes: pl.DataFrame, s_by_market: dict) -> pl.DataFrame:
    """One row per official pick and close source. picks need: game, nkey, market, side, line, odds (American),
    p_over_dk (the pick run's DK no-vig P(over)), best_cost (optional). closes: last_close() output with
    line, fair_over. s_by_market: market -> s for converted line moves (missing = no conversion)."""
    out = []
    cl = {(r["source"], r["game"], r["nkey"], r["market"]): r for r in closes.iter_rows(named=True)}
    sources = sorted({k[0] for k in cl}) or ["pinnacle", "dk", "fd"]
    for p in picks.iter_rows(named=True):
        side, lp = p["side"], float(p["line"])
        d = american_to_dec(float(p["odds"]))
        pov = float(p["p_over_dk"]) if p.get("p_over_dk") not in (None, "") else None
        p_pick = None if pov is None else (pov if side == "over" else 1 - pov)
        for src in sources:
            c = cl.get((src, p["game"], p["nkey"], p["market"]))
            row = {**{k: p.get(k) for k in ("run_utc", "week", "an_game_id", "start_time", "home", "away", "player",
                                             "player_id", "market", "side", "line", "odds", "result")},
                   "source": src, "close_line": None, "close_fair_over": None, "close_lead_min": None, "line_move": None,
                   "converted": None, "p_close": None, "clv_ev": None, "clv_ev_best": None, "novig_move": None}
            if c is not None:
                lc, q = float(c["line"]), float(c["fair_over"])
                move = (lc - lp) if side == "over" else (lp - lc)
                row.update(close_line=lc, close_fair_over=q, close_lead_min=c["lead_min"], line_move=move)
                s = s_by_market.get(p["market"])
                pc_over = q if lc == lp else (p_over_at(lc, q, lp, p["market"], s) if s else None)
                if pc_over is not None:
                    pc = pc_over if side == "over" else 1 - pc_over
                    row.update(converted=lc != lp, p_close=pc, clv_ev=pc * d - 1,
                               novig_move=None if p_pick is None else pc - p_pick)
                    bc = p.get("best_cost")
                    if bc not in (None, "") and float(bc) > 0:
                        row["clv_ev_best"] = pc / float(bc) - 1
            out.append(row)
    return pl.DataFrame(out, infer_schema_length=None)


def summary(clv: pl.DataFrame) -> pl.DataFrame:
    """By source: picks, picks with a close, with a CLV number, mean CLV (EV at close), share CLV > 0, mean line move."""
    if not clv.height:
        return pl.DataFrame()
    return clv.group_by("source").agg(
        pl.len().alias("picks"), pl.col("close_line").is_not_null().sum().alias("with_close"),
        pl.col("clv_ev").is_not_null().sum().alias("with_clv"), pl.col("clv_ev").mean().alias("mean_clv"),
        (pl.col("clv_ev") > 0).mean().alias("share_pos"), pl.col("clv_ev_best").mean().alias("mean_clv_best"),
        pl.col("line_move").mean().alias("mean_line_move")).sort("source")


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def implied_cost(american: float) -> float:
    return implied(american)
