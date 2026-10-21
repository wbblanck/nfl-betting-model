"""ESPN injury statuses for the S1 live tracker's injury flag (docs/s1_live_rules.md).

Descriptive only: rule S1 and its picks are unchanged; the flag says whether injury news known at run time works
against a pick, which the model cannot see (it projects from each player's past usage only).

One request to ESPN's site API returns every team's current statuses (Active / Questionable / Doubtful / Out /
Injured Reserve) with the athlete's ESPN id in his player-card link; nflverse's players table maps ESPN ids to
gsis ids. Format checked on a runner snapshot (docs/evidence/espn_injuries/20261003T032301Z): Breece Hall "Out"
since 2026-10-02 15:26 UTC, 2.5 h before the week-4 run that picked Braelon Allen's rush attempts under.
"""
from __future__ import annotations

import re

import polars as pl

from nflbet.sources.http import BROWSER_UA as UA, get_json

SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
ABSENT = {"Out", "Doubtful", "Injured Reserve", "Suspension", "Physically Unable to Perform"}
SHOWN = ABSENT | {"Questionable"}
GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "REC", "TE": "REC"}
RECENT_WEEKS = 3          # a teammate counts if he played for the team in its last 3 weeks (else the model's usage
                          # history already reflects his absence)
FLAG_COLS = ["inj_self", "inj_teammates", "inj_against"]


def fetch() -> dict:
    return get_json(SITE, {"User-Agent": UA, "Accept": "application/json"}, timeout=45)


def parse(body: dict) -> pl.DataFrame:
    rows = []
    for team in body.get("injuries", []):
        for it in team.get("injuries", []):
            a = it.get("athlete") or {}
            m = next((re.search(r"/id/(\d+)", l.get("href", "")) for l in a.get("links", [])
                      if re.search(r"/id/(\d+)", l.get("href", ""))), None)
            rows.append({"espn_id": m.group(1) if m else None, "name": a.get("displayName"),
                         "espn_pos": (a.get("position") or {}).get("abbreviation"),
                         "status": it.get("status"), "date": it.get("date")})
    schema = {"espn_id": pl.Utf8, "name": pl.Utf8, "espn_pos": pl.Utf8, "status": pl.Utf8, "date": pl.Utf8}
    return pl.DataFrame(rows, schema=schema).filter(pl.col("espn_id").is_not_null())


def flag(picks: pl.DataFrame, inj: pl.DataFrame, ids: pl.DataFrame, recent: pl.DataFrame) -> pl.DataFrame:
    """Add inj_self (the player's own status, if not Active), inj_teammates (same team and position group, played
    recently, status Questionable or worse) and inj_against (an under with a teammate Out / Doubtful / IR, or an
    over whose player is himself Questionable or worse).
    ids: espn_id -> player_id (gsis). recent: player_id, team, position of players who played in the last weeks."""
    st = inj.join(ids, on="espn_id", how="inner").filter(pl.col("status").is_in(list(SHOWN))) \
        .unique("player_id", keep="first")
    status = dict(zip(st["player_id"].to_list(), st["status"].to_list()))
    names = dict(zip(st["player_id"].to_list(), st["name"].to_list()))
    rec = recent.with_columns(pl.col("position").replace_strict(GROUP, default=None).alias("g")) \
        .filter(pl.col("g").is_not_null()).unique(["player_id", "team"], maintain_order=True)
    by_team: dict[tuple, list] = {}
    for r in rec.iter_rows(named=True):
        if r["player_id"] in status:
            by_team.setdefault((r["team"], r["g"]), []).append(r)
    group = dict(zip(rec["player_id"].to_list(), rec["g"].to_list()))
    s_out, t_out, against = [], [], []
    for r in picks.iter_rows(named=True):
        me = status.get(r["player_id"])
        mates = [m for m in by_team.get((r["team"], group.get(r["player_id"])), []) if m["player_id"] != r["player_id"]]
        s_out.append(me or "")
        t_out.append("; ".join(f"{m['position']} {names[m['player_id']]}: {status[m['player_id']]}" for m in mates))
        against.append(bool((r["side"] == "under" and any(status[m["player_id"]] in ABSENT for m in mates))
                            or (r["side"] == "over" and me is not None)))
    return picks.with_columns(pl.Series("inj_self", s_out, dtype=pl.Utf8), pl.Series("inj_teammates", t_out, dtype=pl.Utf8),
                              pl.Series("inj_against", against, dtype=pl.Boolean))


def espn_ids() -> pl.DataFrame:
    import nflreadpy as nfl

    return nfl.load_players().select(pl.col("espn_id").cast(pl.Utf8), pl.col("gsis_id").alias("player_id")) \
        .filter(pl.col("espn_id").is_not_null(), pl.col("player_id").is_not_null()).unique("espn_id")


def recent_players(season: int, week: int) -> pl.DataFrame:
    import nflreadpy as nfl

    st = nfl.load_player_stats(seasons=[season]).filter(pl.col("season_type") == "REG",
                                                         pl.col("week") >= week - RECENT_WEEKS, pl.col("week") < week)
    return st.select("player_id", "team", "position").unique()
