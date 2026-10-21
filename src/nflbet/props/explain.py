"""Plain-language reasons for each S1 pick, built only from what the tracker recorded (docs/s1_live_rules.md).

For each pick: the four S1 signals as sentences (price, where DraftKings' line sat among the books at that run,
projection vs line, simulator vs market), then the player's recent games in that stat with how many cleared the
line. Nothing here is a new signal or changes a pick; it restates the numbers behind the rule.

Book lines come from the run's archived input: data/live/lines/<stamp>_w<week>.csv.gz for official S1 (Action
Network) and data/live/parlay/<stamp>_w<week>.json.gz for the ParlayAPI record. Recent games are nflverse player
stats from weeks before the pick's week (so a finished game never explains its own pick).
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import polars as pl

from nflbet.props import core as P

UNIT = {"rec": "receptions", "rec_yds": "receiving yards", "rush_att": "rush attempts", "rush_yds": "rushing yards",
        "rush_rec_yds": "rush + rec yards", "pass_att": "pass attempts", "pass_cmp": "completions",
        "pass_yds": "passing yards", "pass_rush_yds": "pass + rush yards"}
AN_NAME = {"DK NJ": "DraftKings", "FanDuel NJ": "FanDuel", "BetMGM NJ": "BetMGM", "BetRivers NJ": "BetRivers",
           "Caesars NV": "Caesars"}
N_RECENT = 5


def stamp(run_utc: str) -> str:
    """'2026-10-08T05:42:48Z' -> '20261008T0542Z' (the archive file prefix)."""
    return run_utc[:4] + run_utc[5:7] + run_utc[8:10] + "T" + run_utc[11:13] + run_utc[14:16] + "Z"


def book_lines(live: Path, r: dict, source: str) -> dict[str, float]:
    """{book: line} for this pick's player and market at the pick's run, two-sided quotes only."""
    key, mkt = P.norm_name(r["player"]), r["market"]
    st = stamp(r["run_utc"])
    try:
        if source == "parlay":
            from nflbet.sources import parlay as Pa

            f = live / "parlay" / f"{st}_w{r['week']}.json.gz"
            with gzip.open(f, "rt") as fh:
                d = Pa.parse(json.load(fh))
            d = d.filter(pl.col("nkey") == key, pl.col("market") == mkt)
            return {{"dk": "DraftKings", "fd": "FanDuel"}[b]: ln for b, ln in zip(d["book"], d["line"])}
        f = live / "lines" / f"{st}_w{r['week']}.csv.gz"
        d = pl.read_csv(f, infer_schema_length=0).filter(
            pl.col("market") == mkt, ~pl.col("book_id").is_in(list(P.NON_BOOKS)),
            pl.col("over_odds").fill_null("") != "", pl.col("under_odds").fill_null("") != "")
        d = d.filter(pl.col("player").map_elements(P.norm_name, return_dtype=pl.Utf8) == key)
        return {AN_NAME.get(b, b): float(ln) for b, ln in zip(d["book"], d["line"])}
    except (OSError, ValueError, KeyError, pl.exceptions.PolarsError):
        return {}


def recent_games(stats: pl.DataFrame, player_id: str, market: str, week: int, n: int = N_RECENT) -> list[tuple[int, str, float]]:
    """(week, opponent, value) for the player's last n games before `week` this season, oldest first.
    stats: props.load_stats output for the season."""
    if market not in stats.columns:
        return []
    x = stats.filter(pl.col("player_id") == player_id, pl.col("week") < week).sort("week").tail(n)
    out = []
    for w, t, g, v in zip(x["week"], x["team"], x["game_id"], x[market]):
        parts = (g or "").split("_")
        opp = (parts[3] if parts[2] == t else parts[2]) if len(parts) == 4 else "?"
        out.append((int(w), opp, float(v) if v is not None else 0.0))
    return out


def opponent_context(r: dict, opp: str, ctx: dict | None) -> str | None:
    """One sentence on the opposing defense this season to date (FTN charting via nflverse), or None.
    ctx: {"week": first week not included, "teams": {team: row}, "league": row} from teamstats.season_to_date."""
    if not ctx or opp not in ctx["teams"]:
        return None
    t, lg, w = ctx["teams"][opp], ctx["league"], ctx["week"]
    span = f"weeks 1-{w - 1}" if w > 2 else "week 1"
    if r["market"] in ("rush_att", "rush_yds"):
        return f"Opponent defense ({opp}, {span}, FTN charting): {t['def_box']:.1f} defenders in the box on dropbacks (league {lg['def_box']:.1f})."
    return (f"Opponent defense ({opp}, {span}, FTN charting): blitzes on {t['def_blitz_rate']:.0%} of dropbacks (league "
            f"{lg['def_blitz_rate']:.0%}), {t['def_pass_rushers']:.1f} pass rushers on average (league {lg['def_pass_rushers']:.1f}).")


def reasons(r: dict, books: dict[str, float], games: list[tuple[int, str, float]], opp_line: str | None = None) -> list[str]:
    """Sentences for one pick. r: a pick row with side, line, odds, market, p_mkt, p_model, proj (as floats or strings)."""
    side, line, odds = r["side"], float(r["line"]), float(r["odds"])
    under = side == "under"
    unit = UNIT.get(r["market"], r["market"])
    p_mkt, p_model = float(r["p_mkt"]), float(r["p_model"])
    out = [f"Price: DraftKings has the {side} at {odds:+.0f}, the favored side; with the vig removed the market gives "
           f"the {side} {p_mkt:.0%}."]
    others = {b: ln for b, ln in books.items() if b != "DraftKings"}
    if others:
        listed = ", ".join(f"{b} {ln:g}" for b, ln in sorted(others.items()))
        ext = "highest" if under else "lowest"
        tied = any(ln == line for ln in others.values())
        out.append(f"Books: DraftKings' {line:g} {'ties for' if tied else 'is'} the {ext} line on the board ({listed}), "
                   f"so the {side} gets {'as much room there as anywhere' if tied else 'the most room there'}.")
    else:
        out.append(f"Books: DraftKings' {line:g} was the {'highest' if under else 'lowest'} line among the books at the run.")
    proj = r.get("proj")
    if proj not in (None, ""):
        proj = float(proj)
        gap = abs(line - proj) / max(abs(line), 1)
        out.append(f"Projection: {proj:.1f} {unit}, {gap:.0%} {'below' if under else 'above'} the {line:g} line.")
    out.append(f"Simulator: {p_model:.0%} for the {side}, {100 * (p_model - p_mkt):+.0f} points against the market's {p_mkt:.0%}.")
    if games:
        hit = sum(1 for _, _, v in games if (v < line if under else v > line))
        vals = ", ".join(f"{v:g} vs {o}" for _, o, v in games)
        avg = sum(v for _, _, v in games) / len(games)
        out.append(f"Recent games: {vals}. {side.capitalize()} {line:g} in {hit} of {len(games)}; "
                   f"average {avg:.1f} {unit}.")
    else:
        out.append("Recent games: none this season before this week.")
    if opp_line:
        out.append(opp_line)
    return out
