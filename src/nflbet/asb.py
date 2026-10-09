"""Australia Sports Betting NFL file (data/odds/asb/nfl.xlsx, supplied by Will 2026-10-09; personal use only per
its terms, do not republish): every game from 2006 with opening, minimum, maximum and closing point spread and
spread prices, moneylines and totals. Sources per the file: Pinnacle 2014 to February 2018, bet365 September 2018 to
February 2025, betr from September 2025; footballlocks.com before 2014.

Prices in the file are decimal; returned as American. Spreads are returned in nflverse's convention (positive = home
favored); the file's "Home Line" is a handicap (negative = home favored).
"""
from __future__ import annotations

import datetime as dt

import polars as pl

from nflbet import config
from nflbet.parlay import TEAMS

PATH = config.ROOT / "data" / "odds" / "asb" / "nfl.xlsx"
OLD = {"San Diego Chargers": "LAC", "St. Louis Rams": "LA", "Oakland Raiders": "LV", "Washington Redskins": "WAS",
       "Washington Football Team": "WAS", "Washington": "WAS"}
NFLVERSE_OLD = {"SD": "LAC", "STL": "LA", "OAK": "LV"}


def american(d):
    d = _f(d)
    if d is None:
        return None
    if d <= 1:
        return None
    return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))


def raw() -> list[dict]:
    """Data sheet rows as dicts (cells mix numbers and text, so no typed frame here)."""
    import openpyxl

    ws = openpyxl.load_workbook(PATH, read_only=True, data_only=True)["Data"]
    rows = list(ws.iter_rows(values_only=True))
    head = [str(h) for h in rows[0]]
    return [dict(zip(head, r)) for r in rows[1:] if isinstance(r[0], (dt.datetime, dt.date))]


def _f(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def games() -> pl.DataFrame:
    """ASB rows matched to nflverse games: game_id, season, week, game_type, home/away (nflverse), home open / close
    spread (nflverse sign), open / close spread prices (American) for each side, moneylines, totals, nflverse close."""
    import nflreadpy as nfl

    d = raw()
    seasons = sorted({(r["Date"].year if r["Date"].month >= 8 else r["Date"].year - 1) for r in d})
    sch = nfl.load_schedules(seasons=seasons).select("season", "game_id", "gameday", "game_type", "week", "home_team",
                                                     "away_team", "home_score", "away_score", "spread_line")
    by_day: dict = {}
    for r in sch.iter_rows(named=True):
        key = frozenset({NFLVERSE_OLD.get(r["home_team"], r["home_team"]), NFLVERSE_OLD.get(r["away_team"], r["away_team"])})
        by_day.setdefault((r["gameday"], key), r)
    out, miss = [], []
    for r in d:
        h, a = TEAMS.get(r["Home Team"]) or OLD.get(r["Home Team"]), TEAMS.get(r["Away Team"]) or OLD.get(r["Away Team"])
        date = r["Date"].date() if isinstance(r["Date"], dt.datetime) else r["Date"]
        g = None
        for dd in (date, date - dt.timedelta(days=1), date + dt.timedelta(days=1)):
            g = by_day.get((dd.isoformat(), frozenset({h, a})))
            if g:
                break
        if g is None:
            miss.append((date, r["Home Team"], r["Away Team"]))
            continue
        flip = NFLVERSE_OLD.get(g["home_team"], g["home_team"]) != h      # ASB home differs from nflverse home (neutral sites)
        def line(col):
            v = _f(r[col])
            return None if v is None else (v if flip else -v)
        def px(home_col, away_col):
            return (american(r[away_col]), american(r[home_col])) if flip else (american(r[home_col]), american(r[away_col]))
        ho, ao = px("Home Line Odds Open", "Away Line Odds Open")
        hc, ac = px("Home Line Odds Close", "Away Line Odds Close")
        out.append({"game_id": g["game_id"], "season": g["season"], "week": g["week"], "game_type": g["game_type"],
                    "home_team": g["home_team"], "away_team": g["away_team"],
                    "home_open": line("Home Line Open"), "home_close": line("Home Line Close"),
                    "home_open_odds": ho, "away_open_odds": ao, "home_close_odds": hc, "away_close_odds": ac,
                    "total_open": _f(r["Total Score Open"]), "total_close": _f(r["Total Score Close"]),
                    "nflverse_close": g["spread_line"],
                    "score_check": ({_f(r["Home Score"]), _f(r["Away Score"])} == {_f(g["home_score"]), _f(g["away_score"])})})
    res = pl.DataFrame(out)
    print(f"ASB: {res.height} games matched to nflverse, {len(miss)} not matched (e.g. {miss[:3]})")
    return res
