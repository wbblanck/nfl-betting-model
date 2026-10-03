"""ESPN depth charts for the S1 live tracker's role-change flag (docs/s1_live_rules.md). QB and RB only.

Descriptive only: rule S1 and its picks are unchanged. The model projects from past usage, so when a team changes
its starter it keeps projecting the old roles for a while. The flag compares each team's depth-chart starter (the
highest-ranked QB / RB who is not Out, Doubtful or on IR at run time) with the player who led the team in attempts
(QB) or carries (RB) over its last 3 weeks. When they differ (and the leader is healthy; an injured leader is the
injury flag's case), a pick is marked against if it is an under on the listed starter or an over on the old leader,
in that position's own markets; receiving picks on a team whose QB changed get a note only.

Probe (docs/evidence/espn_depth/20261003T033746Z): all 32 charts load from a runner, 99.8% of players map to
nflverse ids, no last-updated time is given. The charts do not track injuries (9 listed offensive starters were Out
on ESPN's own injury list), mostly repeat recent usage (listed #1 = weeks 1-3 leader for 91% of QBs, 88% of RBs),
and TE order is often blocking roles, so TEs and WRs are left out.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

import polars as pl

from nflbet.injuries import ABSENT, RECENT_WEEKS, UA

CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_TEAM = {"WSH": "WAS", "LAR": "LA"}            # ESPN abbreviations that differ from nflverse
USAGE = {"QB": "attempts", "RB": "carries"}
ROLE_MARKETS = {"QB": {"pass_att", "pass_cmp", "pass_yds", "pass_rush_yds"}, "RB": {"rush_att", "rush_yds", "rush_rec_yds"}}
RECEIVING = {"rec", "rec_yds"}
FLAG_COLS = ["depth_note", "depth_against"]


def _get(url: str):
    req = urllib.request.Request(url.replace("http://", "https://"), headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def fetch(season: int) -> dict:
    """{ESPN team abbreviation: core depth chart body} for every team."""
    teams = _get(f"{SITE}/teams")["sports"][0]["leagues"][0]["teams"]
    out = {}
    for t in teams:
        time.sleep(0.3)
        out[t["team"]["abbreviation"]] = {"id": t["team"]["id"],
                                         "body": _get(f"{CORE}/seasons/{season}/teams/{t['team']['id']}/depthcharts")}
    return out


def parse(charts: dict) -> pl.DataFrame:
    """team (nflverse abbreviation), pos (QB / RB), rank, espn_id from each team's offensive formation."""
    rows = []
    for ab, c in charts.items():
        for it in (c.get("body") or {}).get("items", []):
            for p in (it.get("positions") or {}).values():
                pos = ((p.get("position") or {}).get("abbreviation") or "").upper()
                if pos not in USAGE:
                    continue
                for a in p.get("athletes", []):
                    m = re.search(r"athletes/(\d+)", (a.get("athlete") or {}).get("$ref", ""))
                    if m:
                        rows.append({"team": ESPN_TEAM.get(ab, ab), "pos": pos, "rank": a.get("rank"), "espn_id": m.group(1)})
    schema = {"team": pl.Utf8, "pos": pl.Utf8, "rank": pl.Int64, "espn_id": pl.Utf8}
    return pl.DataFrame(rows, schema=schema).unique(["team", "pos", "espn_id"], keep="first", maintain_order=True)


def changes(dc: pl.DataFrame, inj: pl.DataFrame, players: pl.DataFrame, usage: pl.DataFrame) -> pl.DataFrame:
    """Teams whose depth-chart starter at QB / RB differs from the healthy recent usage leader.
    players: espn_id, player_id, name. usage: player_id, team, pos, n (attempts or carries, last weeks)."""
    absent = set(inj.filter(pl.col("status").is_in(list(ABSENT))).join(players, on="espn_id")["player_id"].to_list())
    d = dc.join(players, on="espn_id", how="inner").filter(~pl.col("player_id").is_in(list(absent))) \
        .sort("team", "pos", "rank").group_by("team", "pos", maintain_order=True).first() \
        .select("team", "pos", pl.col("player_id").alias("starter_id"), pl.col("name").alias("starter_name"))
    lead = usage.sort("n", descending=True).group_by("team", "pos", maintain_order=True).first() \
        .join(players.select("player_id", "name"), on="player_id", how="left") \
        .select("team", "pos", pl.col("player_id").alias("leader_id"), pl.col("name").alias("leader_name"),
                pl.col("n").alias("leader_n"))
    n = usage.select(pl.col("player_id").alias("starter_id"), "team", "pos", pl.col("n").alias("starter_n"))
    return d.join(lead, on=["team", "pos"], how="inner").filter(pl.col("starter_id") != pl.col("leader_id"),
                                                                ~pl.col("leader_id").is_in(list(absent))) \
        .join(n, on=["starter_id", "team", "pos"], how="left").with_columns(pl.col("starter_n").fill_null(0))


def flag(picks: pl.DataFrame, ch: pl.DataFrame) -> pl.DataFrame:
    """Add depth_note and depth_against (see module docstring)."""
    by = {(r["team"], r["pos"]): r for r in ch.iter_rows(named=True)}
    notes, against = [], []
    for p in picks.iter_rows(named=True):
        note, bad = [], False
        for pos in USAGE:
            c = by.get((p["team"], pos))
            if c is None:
                continue
            what = (f"{pos} change: chart lists {c['starter_name']} ({c['starter_n']} {USAGE[pos]} last {RECENT_WEEKS} wks) "
                    f"over {c['leader_name']} ({c['leader_n']})")
            if p["player_id"] in (c["starter_id"], c["leader_id"]) and p["market"] in ROLE_MARKETS[pos]:
                note.append(what)
                bad |= (p["player_id"] == c["starter_id"] and p["side"] == "under") or \
                       (p["player_id"] == c["leader_id"] and p["side"] == "over")
            elif pos == "QB" and p["market"] in RECEIVING:
                note.append("team " + what)
        notes.append("; ".join(note))
        against.append(bad)
    return picks.with_columns(pl.Series("depth_note", notes, dtype=pl.Utf8), pl.Series("depth_against", against, dtype=pl.Boolean))


def players_table() -> pl.DataFrame:
    import nflreadpy as nfl

    return nfl.load_players().select(pl.col("espn_id").cast(pl.Utf8), pl.col("gsis_id").alias("player_id"),
                                     pl.col("display_name").alias("name")) \
        .filter(pl.col("espn_id").is_not_null(), pl.col("player_id").is_not_null()).unique("espn_id")


def recent_usage(season: int, week: int) -> pl.DataFrame:
    import nflreadpy as nfl

    st = nfl.load_player_stats(seasons=[season]).filter(pl.col("season_type") == "REG", pl.col("position").is_in(list(USAGE)),
                                                         pl.col("week") >= week - RECENT_WEEKS, pl.col("week") < week)
    st = st.with_columns(pl.when(pl.col("position") == "QB").then(pl.col("attempts")).otherwise(pl.col("carries")).alias("n"))
    return st.group_by("player_id", "team", pl.col("position").alias("pos")).agg(pl.col("n").sum())
