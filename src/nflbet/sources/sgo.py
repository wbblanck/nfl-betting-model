"""SportsGameOdds (api.sportsgameodds.com/v2): per-book open and close prices for finished NFL games.

Record only (docs/sgo_closes.md). The key comes from SPORTSGAMEODDS and is never returned or archived. The free tier
(probe 2026-11-19, docs/evidence/sgo_probe/README.md) allows 10 requests a minute and 2,500 objects a month; each
event returned is one object with every market in it. Close = the book's price at the event's start time (SGO docs).
/account/usage returns the account email: only numeric fields are read from it here, and nothing from it is saved.
"""
from __future__ import annotations

import os
import urllib.parse

import polars as pl

from nflbet.sources.http import RESEARCH_UA, get_json
from nflbet.sources.ids import TEAMS, game_key, norm_name

BASE = "https://api.sportsgameodds.com/v2/"
PACE = 6.5                       # seconds between requests: 10 a minute on the free tier
# SGO statID -> our market names (nflbet.sources.parlay.KEYS); other stats are kept with market = null
MARKETS = {"passing_yards": "pass_yds", "passing_attempts": "pass_att", "passing_completions": "pass_cmp",
           "rushing_yards": "rush_yds", "rushing_attempts": "rush_att", "receiving_yards": "rec_yds",
           "receiving_receptions": "rec", "passing+rushing_yards": "pass_rush_yds",
           "rushing+receiving_yards": "rush_rec_yds"}
SCHEMA = {"event_id": pl.Utf8, "starts_at": pl.Utf8, "season_week": pl.Utf8, "game": pl.Utf8, "home": pl.Utf8,
          "away": pl.Utf8, "odd_id": pl.Utf8, "stat_id": pl.Utf8, "entity": pl.Utf8, "player": pl.Utf8,
          "nkey": pl.Utf8, "market": pl.Utf8, "bet_type": pl.Utf8, "side": pl.Utf8, "book": pl.Utf8,
          "open_odds": pl.Float64, "open_line": pl.Float64, "close_odds": pl.Float64, "close_line": pl.Float64,
          "last_odds": pl.Float64, "last_line": pl.Float64, "last_update": pl.Utf8, "score": pl.Float64}


def _key() -> str:
    k = os.environ.get("SPORTSGAMEODDS", "")
    if not k:
        raise RuntimeError("SPORTSGAMEODDS not set")
    return k


def _get(path: str, params: dict | None = None) -> dict:
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    return get_json(url, {"x-api-key": _key(), "user-agent": RESEARCH_UA, "accept": "application/json"},
                    timeout=120, pace=PACE, retries_429=3, backoff=20)


def objects_left() -> int | None:
    """Objects left this month (None if unlimited or unreadable). Reads numbers only; the answer also holds the email."""
    m = ((_get("account/usage").get("data") or {}).get("rateLimits") or {}).get("per-month") or {}
    mx, cur = m.get("max-entities"), m.get("current-entities", 0)
    return mx - (cur or 0) if isinstance(mx, int) else None


def finalized_events(starts_after: str, starts_before: str, max_events: int) -> list[dict]:
    """Finalized NFL events starting in [after, before), with per-book open/close; at most max_events objects."""
    out: list[dict] = []
    cursor = None
    while len(out) < max_events:
        p = {"leagueID": "NFL", "finalized": "true", "startsAfter": starts_after, "startsBefore": starts_before,
             "includeOpenCloseOdds": "true", "limit": min(10, max_events - len(out))}
        if cursor:
            p["cursor"] = cursor
        body = _get("events", p)
        out += body.get("data") or []
        cursor = body.get("nextCursor")
        if not cursor or not body.get("data"):
            break
    return out


def _num(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(str(x).replace("+", ""))
    except ValueError:
        return None


def _team(t: dict) -> str | None:
    return TEAMS.get(((t or {}).get("names") or {}).get("long", ""))


def parse_event(ev: dict) -> pl.DataFrame:
    """One row per (full-game market side, book). Lines: spread for sp, over/under for ou, none otherwise."""
    st = ev.get("status") or {}
    home, away = _team((ev.get("teams") or {}).get("home")), _team((ev.get("teams") or {}).get("away"))
    players = ev.get("players") or {}
    rows = []
    for oid, o in (ev.get("odds") or {}).items():
        if o.get("periodID") != "game":
            continue
        ent, bt = o.get("statEntityID", ""), o.get("betTypeID")
        is_player = ent not in ("home", "away", "all")
        name = (players.get(ent) or {}).get("name") if is_player else None
        lk = {"sp": "spread", "ou": "overUnder"}.get(bt)
        for book, q in (o.get("byBookmaker") or {}).items():
            rows.append({
                "event_id": ev.get("eventID"), "starts_at": st.get("startsAt"),
                "season_week": str((ev.get("info") or {}).get("seasonWeek") or ""),
                "game": game_key(home, away) if home and away else None, "home": home, "away": away,
                "odd_id": oid, "stat_id": o.get("statID"), "entity": ent, "player": name,
                "nkey": norm_name(name) if name else None,
                "market": MARKETS.get(o.get("statID")) if is_player and bt == "ou" else None,
                "bet_type": bt, "side": o.get("sideID"), "book": book,
                "open_odds": _num(q.get("openOdds")), "close_odds": _num(q.get("closeOdds")),
                "last_odds": _num(q.get("odds")), "last_update": q.get("lastUpdatedAt"),
                "open_line": _num(q.get("open" + lk[0].upper() + lk[1:])) if lk else None,
                "close_line": _num(q.get("close" + lk[0].upper() + lk[1:])) if lk else None,
                "last_line": _num(q.get(lk)) if lk else None, "score": _num(o.get("score"))})
    return pl.DataFrame(rows, schema=SCHEMA)
