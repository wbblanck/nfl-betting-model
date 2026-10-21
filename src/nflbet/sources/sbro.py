"""Sportsbook Review Online NFL odds archive (data/odds/sbro/, fetched by scripts/fetch/sbro_odds.py): opening and
closing point spreads and totals, 2007-08 to 2021-22.

Each game is two rows (visitor then home, or two neutral-site rows). In the Open and Close columns the favorite's row
carries the spread and the other row the total; "pk" is a spread of 0. Which book's opener the site shows is not
stated, so an opening number here may not have been bettable (CLAUDE.md, Action Network "Open" trap).
Games are matched to nflverse by date and teams; spreads are returned in nflverse's convention (positive = home
favored).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from nflbet import config

DIR = config.ROOT / "data" / "odds" / "sbro"
NAME = {"Arizona": ["ARI"], "Atlanta": ["ATL"], "Baltimore": ["BAL"], "Buffalo": ["BUF"], "BuffaloBills": ["BUF"],
        "Carolina": ["CAR"], "Chicago": ["CHI"], "Cincinnati": ["CIN"], "Cleveland": ["CLE"], "Dallas": ["DAL"],
        "Denver": ["DEN"], "Detroit": ["DET"], "GreenBay": ["GB"], "Houston": ["HOU"], "HoustonTexans": ["HOU"],
        "Indianapolis": ["IND"], "Jacksonville": ["JAX"], "KCChiefs": ["KC"], "Kansas": ["KC"], "KansasCity": ["KC"],
        "LAChargers": ["LAC"], "LARams": ["LA"], "LasVegas": ["LV"], "LVRaiders": ["LV"], "LosAngeles": ["LA", "LAC"],
        "Miami": ["MIA"], "Minnesota": ["MIN"], "NYGiants": ["NYG"], "NYJets": ["NYJ"], "NewYork": ["NYG", "NYJ"],
        "NewEngland": ["NE"], "NewOrleans": ["NO"], "Oakland": ["OAK", "LV"], "Philadelphia": ["PHI"],
        "Pittsburgh": ["PIT"], "SanDiego": ["SD", "LAC"], "SanFrancisco": ["SF"], "Seattle": ["SEA"],
        "St.Louis": ["STL", "LA"], "Tampa": ["TB"], "TampaBay": ["TB"], "Tennessee": ["TEN"], "Washington": ["WAS"],
        "Washingtom": ["WAS"]}


def _num(x: str) -> tuple[float | None, bool]:
    """(value, had_minus_sign). 'pk' = 0."""
    x = (x or "").strip().lower()
    if x in ("pk", "pick"):
        return 0.0, False
    try:
        v = float(x)
    except ValueError:
        return None, False
    return abs(v), v < 0


def _date(season: int, s: str) -> dt.date:
    s = s.strip()
    m, d = (int(s[:-2]), int(s[-2:]))
    return dt.date(season if m >= 8 else season + 1, m, d)


def pairs(season: int, path: Path | None = None) -> pl.DataFrame:
    """One row per listed game: date, first/second team names, open/close spread with the favorite's side, totals."""
    d = pl.read_csv(path or DIR / f"nfl_{season}.csv", infer_schema_length=0)
    rows = d.to_dicts()
    out = []
    for a, b in zip(rows[0::2], rows[1::2]):
        rec = {"season": season, "date": _date(season, a["Date"]), "team1": a["Team"], "team2": b["Team"],
               "vh1": a["VH"], "vh2": b["VH"], "score1": int(a["Final"]), "score2": int(b["Final"]), "sign_flag": False}
        for col in ("Open", "Close"):
            (x1, s1), (x2, s2) = _num(a[col]), _num(b[col])
            rec["sign_flag"] |= s1 or s2
            if x1 is None or x2 is None:
                rec[f"{col.lower()}_spread"], rec[f"{col.lower()}_fav"], rec[f"{col.lower()}_total"] = None, None, None
                continue
            fav1 = x1 <= x2
            rec[f"{col.lower()}_spread"] = min(x1, x2)
            rec[f"{col.lower()}_fav"] = 1 if fav1 else 2
            rec[f"{col.lower()}_total"] = max(x1, x2)
        out.append(rec)
    return pl.DataFrame(out)


def games(seasons: list[int]) -> pl.DataFrame:
    """SBRO lines matched to nflverse games (regular season and playoffs): game_id, nflverse home/away, home open and
    close spreads (positive = home favored), open/close totals, plus nflverse's closing spread for checking."""
    import nflreadpy as nfl

    sch = nfl.load_schedules(seasons=seasons).select("season", "game_id", "gameday", "game_type", "week", "home_team",
                                                     "away_team", "home_score", "away_score", "spread_line")
    by_day: dict = {}
    for r in sch.iter_rows(named=True):
        by_day.setdefault(r["gameday"], []).append(r)
    out, miss = [], 0
    for s in seasons:
        for p in pairs(s).iter_rows(named=True):
            c1, c2 = NAME.get(p["team1"], []), NAME.get(p["team2"], [])
            hit = None
            for day in (p["date"], p["date"] - dt.timedelta(days=1), p["date"] + dt.timedelta(days=1)):
                for g in by_day.get(day.isoformat(), []):
                    if {g["home_team"], g["away_team"]} & set(c1) and {g["home_team"], g["away_team"]} & set(c2) \
                            and g["home_team"] != g["away_team"]:
                        hit = g
                        break
                if hit:
                    break
            if hit is None:
                miss += 1
                continue
            first_is_home = hit["home_team"] in c1 and hit["away_team"] in c2 and not (hit["home_team"] in c2 and hit["away_team"] in c1)
            if p["vh1"] == "V":
                first_is_home = False
            elif p["vh1"] == "H":
                first_is_home = True
            rec = {"season": hit["season"], "game_id": hit["game_id"], "game_type": hit["game_type"], "week": hit["week"],
                   "home_team": hit["home_team"], "away_team": hit["away_team"], "nflverse_close": hit["spread_line"],
                   "sign_flag": p["sign_flag"],
                   "score_check": (p["score1"], p["score2"]) == ((hit["home_score"], hit["away_score"]) if first_is_home else (hit["away_score"], hit["home_score"]))}
            for col in ("open", "close"):
                sp, fav = p[f"{col}_spread"], p[f"{col}_fav"]
                if sp is None:
                    rec[f"home_{col}"] = None
                else:
                    home_fav = (fav == 1) == first_is_home
                    rec[f"home_{col}"] = sp if home_fav else -sp
                rec[f"total_{col}"] = p[f"{col}_total"]
            out.append(rec)
    d = pl.DataFrame(out)
    print(f"SBRO: {d.height} games matched to nflverse, {miss} listed pairs not matched")
    return d
