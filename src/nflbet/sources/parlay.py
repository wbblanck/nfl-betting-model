"""ParlayAPI DraftKings and FanDuel prices as a second record next to Action Network (docs/s1_live_rules.md).

Descriptive only: rule S1 and its picks are unchanged and still come from Action Network, whose book set (DK, FanDuel,
BetMGM, BetRivers, Caesars) the "books disagree" vote was locked on. ParlayAPI carries DK and FanDuel but not BetMGM,
BetRivers or Caesars, so it cannot replace Action Network without changing the rule. It adds: two-sided DK prices
with an update time even when Action Network has none posted yet, and a check that both sources agree.

Probe (docs/evidence/parlay on branch claude/espn-props-full, 2026-10-08): an unfiltered call stops at its 10,000-row
cap, mostly correct-score and milestone markets, so the fetch asks for DK and FanDuel and the S1 market keys only:
751 two-sided full-game rows, all 15 week-5 games, one line per book, player and market. Each book files the same
market under its own key (DK player_receiving_yards, FanDuel player_rec_yds). One call = 3 credits of 1,000 a month.
"""
from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request

import polars as pl

from nflbet.quant.odds import implied, no_vig_over
from nflbet.sources.ids import TEAMS, TEAM_FIX, game_key, norm_name  # noqa: F401 - TEAMS kept as parlay.TEAMS for scripts

URL = "https://parlay-api.com/v1/sports/americanfootball_nfl/props"
BOOKS = {"draftkings": "dk", "fanduel": "fd"}
KEYS = {   # book's market key -> S1 market (keys as seen in the probe; FanDuel attempts/completions keys are guesses)
    "player_passing_yards": "pass_yds", "player_pass_yds": "pass_yds",
    "player_passing_attempts": "pass_att", "player_pass_attempts": "pass_att",
    "player_passing_completions": "pass_cmp", "player_pass_completions": "pass_cmp",
    "player_rushing_yards": "rush_yds", "player_rush_yds": "rush_yds",
    "player_rushing_attempts": "rush_att", "player_rush_attempts": "rush_att",
    "player_receiving_yards": "rec_yds", "player_rec_yds": "rec_yds",
    "player_receptions": "rec",
    "player_passing_+_rushing_yards": "pass_rush_yds",
    "player_rushing_+_receiving_yards": "rush_rec_yds", "player_rush_reception_yds": "rush_rec_yds",
}
# Pick'em apps (docs/your_venues_rules.md): each files S1's markets under its own keys (2026-10-08 probe,
# docs/evidence/parlay/20261008T050251Z); two-player "combo" markets are not mapped.
PICKEM_BOOKS = {"prizepicks": "PrizePicks", "underdog": "Underdog", "sleeper": "Sleeper"}
PICKEM_KEYS = {
    "prizepicks": {"player_pass_yds": "pass_yds", "player_pass_attempts": "pass_att", "player_pass_completions": "pass_cmp",
                   "player_rush_yards": "rush_yds", "player_rush_attempts": "rush_att", "player_receiving_yards": "rec_yds",
                   "player_receptions": "rec", "player_pass_plus_rush_yds": "pass_rush_yds", "player_rush_plus_rec_yds": "rush_rec_yds"},
    "underdog": {"player_pass_yds": "pass_yds", "player_pass_attempts": "pass_att", "player_completions": "pass_cmp",
                 "player_rush_yards": "rush_yds", "player_rush_attempts": "rush_att", "player_rec_yds": "rec_yds",
                 "player_receptions": "rec", "player_pass___rush_yards": "pass_rush_yds", "player_rush___rec_yards": "rush_rec_yds"},
    "sleeper": {"player_passing_yards": "pass_yds", "player_passing_attempts": "pass_att", "player_pass_completions": "pass_cmp",
                "player_rushing_yards": "rush_yds", "player_rushing_attempts": "rush_att", "player_receiving_yards": "rec_yds",
                "player_receptions": "rec", "player_passing_and_rushing_yards": "pass_rush_yds",
                "player_rushing_and_receiving_yards": "rush_rec_yds"},
}
PRIZEPICKS_POWER2 = 3.0          # 2-pick Power payout on standard lines
UNDERDOG_POWER2 = 3.5            # Underdog's 2-pick base, as ParlayAPI's per-pick decimals imply
UNDERDOG_TOL = 0.04              # reported per-pick decimal vs sqrt(3.5) x multiplier (S1 markets: max 0.034 on the probe)
PICKEM_SCHEMA = {"venue": pl.Utf8, "game": pl.Utf8, "nkey": pl.Utf8, "player": pl.Utf8, "market": pl.Utf8,
                 "line": pl.Float64, "side": pl.Utf8, "cost": pl.Float64, "last_update": pl.Utf8}
AN_BOOKS = {"DK NJ": "dk", "FanDuel NJ": "fd"}
SCHEMA = {"book": pl.Utf8, "game": pl.Utf8, "nkey": pl.Utf8, "player": pl.Utf8, "market": pl.Utf8, "line": pl.Float64,
          "over": pl.Float64, "under": pl.Float64, "last_update": pl.Utf8}
PICK_COLS = ["pa_dk_line", "pa_dk_odds", "pa_fd_line", "pa_fd_odds"]


def fetch(key: str | None = None) -> tuple[list, dict]:
    """(rows, credit headers). The key comes from PARLAY_API_KEY and is never returned or archived."""
    key = key or os.environ["PARLAY_API_KEY"]
    keys = sorted(set(KEYS) | {k for m in PICKEM_KEYS.values() for k in m})
    q = {"apiKey": key, "bookmakers": ",".join([*BOOKS, *PICKEM_BOOKS]), "markets": ",".join(keys), "limit": 10000,
         "oddsFormat": "american"}
    req = urllib.request.Request(f"{URL}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "nfl-betting-model/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        hdr = {k: v for k, v in r.headers.items() if k.lower().startswith("x-requests")}
        return json.loads(r.read()), hdr


def parse(rows: list) -> pl.DataFrame:
    """Two-sided full-game rows in S1 markets: book (dk / fd), game, nkey (normalized name), market, line, prices."""
    out = []
    for r in rows:
        b, m = BOOKS.get(r.get("bookmaker")), KEYS.get(r.get("market_key"))
        h, a = TEAMS.get(r.get("home_team")), TEAMS.get(r.get("away_team"))
        if not (b and m and h and a) or (r.get("period") or "FULL") != "FULL" or r.get("line") is None \
                or r.get("over_price") is None or r.get("under_price") is None or not r.get("player"):
            continue
        out.append({"book": b, "game": game_key(h, a), "nkey": norm_name(r["player"]), "player": r["player"], "market": m,
                    "line": float(r["line"]), "over": float(r["over_price"]), "under": float(r["under_price"]),
                    "last_update": r.get("last_update") or ""})
    d = pl.DataFrame(out, schema=SCHEMA)
    return d.sort("last_update", descending=True).unique(["book", "game", "nkey", "market"], keep="first", maintain_order=True)


def pickem_cost(r: dict, side: str) -> float | None:
    """Per-pick all-in cost of a 2-pick Power entry's leg (docs/your_venues_rules.md), or None if not priceable.
    A 2-pick entry paying X wins only if both legs win; each leg is priced at 1/sqrt(X), so two legs at costs c1, c2
    have positive expected value exactly when p1 * p2 > c1 * c2."""
    b = r.get("bookmaker")
    if b == "prizepicks":
        return 1 / math.sqrt(PRIZEPICKS_POWER2) if (r.get("odds_type") or "standard") == "standard" else None
    if b == "underdog":
        sel = ((r.get("selection_by_side") or {}).get(side) or {}).get("payout_multiplier")
        dec = ((((r.get("product_quotes") or {}).get(side) or {}).get("products") or {}).get("fantasy") or {}).get("decimal")
        if not sel:
            return None
        per = math.sqrt(UNDERDOG_POWER2) * float(sel)
        if dec is not None and abs(float(dec) - per) > UNDERDOG_TOL:
            return None
        return 1 / per
    if b == "sleeper":
        price = r.get(f"{side}_price")
        return implied(float(price)) if price is not None else None
    return None


def parse_pickem(rows: list) -> pl.DataFrame:
    """Pick'em sides in S1 markets, full game: venue, game, nkey, player, market, line, side, per-pick cost.
    Only sides the app offers (`available_sides` when present) and that pickem_cost can price."""
    out = []
    for r in rows:
        b = r.get("bookmaker")
        m = PICKEM_KEYS.get(b, {}).get(r.get("market_key"))
        h, a = TEAMS.get(r.get("home_team")), TEAMS.get(r.get("away_team"))
        if not (m and h and a) or (r.get("period") or "FULL") != "FULL" or r.get("line") is None or not r.get("player"):
            continue
        for side in r.get("available_sides") or ("over", "under"):
            c = pickem_cost(r, side)
            if c is not None:
                out.append({"venue": PICKEM_BOOKS[b], "game": game_key(h, a), "nkey": norm_name(r["player"]), "player": r["player"],
                            "market": m, "line": float(r["line"]), "side": side, "cost": c, "last_update": r.get("last_update") or ""})
    d = pl.DataFrame(out, schema=PICKEM_SCHEMA)
    return d.sort("last_update", descending=True).unique(["venue", "game", "nkey", "market", "line", "side"], keep="first",
                                                          maintain_order=True)


def an_lines(path) -> pl.DataFrame:
    """Action Network's DK and FanDuel two-sided rows from a fetched lines file, in parse()'s shape."""
    d = pl.read_csv(path, infer_schema_length=0).filter(pl.col("book").is_in(list(AN_BOOKS)),
                                                        pl.col("over_odds").fill_null("") != "",
                                                        pl.col("under_odds").fill_null("") != "")
    if not d.height:
        return pl.DataFrame(schema=SCHEMA)
    fix = lambda c: pl.col(c).replace(TEAM_FIX)  # noqa: E731
    return d.select(pl.col("book").replace_strict(AN_BOOKS).alias("book"),
                    pl.struct(fix("home").alias("h"), fix("away").alias("a")).map_elements(
                        lambda s: game_key(s["h"], s["a"]), return_dtype=pl.Utf8).alias("game"),
                    pl.col("player").map_elements(norm_name, return_dtype=pl.Utf8).alias("nkey"), "player", "market",
                    pl.col("line").cast(pl.Float64), pl.col("over_odds").cast(pl.Float64).alias("over"),
                    pl.col("under_odds").cast(pl.Float64).alias("under"), pl.lit("").alias("last_update")) \
        .unique(["book", "game", "nkey", "market"], keep="first", maintain_order=True)


def to_an_csv(pa: pl.DataFrame, season: int, week: int, path) -> int:
    """Write ParlayAPI's DK and FanDuel rows in Action Network's lines-file format so live.run scores them with
    rule S1's own code (the "S1 on ParlayAPI" record, docs/s1_live_rules.md). Only games on the nflverse schedule
    for `week` are kept; home / away and kickoff come from the schedule (ParlayAPI lists some games under two
    kickoff times), an_game_id is "pa_" + the nflverse game_id. Returns the number of rows written."""
    import datetime as dt
    from zoneinfo import ZoneInfo

    import nflreadpy as nfl

    g = nfl.load_schedules(seasons=[season]).filter(pl.col("game_type") == "REG", pl.col("week") == week)
    games = {}
    for r in g.iter_rows(named=True):
        t = dt.datetime.fromisoformat(f"{r['gameday']}T{r['gametime']}").replace(tzinfo=ZoneInfo("America/New_York"))
        games[game_key(r["home_team"], r["away_team"])] = (f"pa_{r['game_id']}", r["home_team"], r["away_team"],
                                                           t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    book = {"dk": ("68", "DK NJ"), "fd": ("69", "FanDuel NJ")}
    rows = []
    for r in pa.iter_rows(named=True):
        if r["game"] not in games:
            continue
        gid, h, a, t = games[r["game"]]
        rows.append({"season": str(season), "week": str(week), "an_game_id": gid, "start_time": t, "home": h, "away": a,
                     "market": r["market"], "an_player_id": r["nkey"], "player": r["player"], "player_team": "",
                     "book_id": book[r["book"]][0], "book": book[r["book"]][1], "line": f"{r['line']:g}",
                     "over_odds": f"{r['over']:g}", "under_odds": f"{r['under']:g}", "yes_odds": ""})
    cols = ["season", "week", "an_game_id", "start_time", "home", "away", "market", "an_player_id", "player",
            "player_team", "book_id", "book", "line", "over_odds", "under_odds", "yes_odds"]
    pl.DataFrame(rows, schema={c: pl.Utf8 for c in cols}).write_csv(path)
    return len(rows)


def compare(pa: pl.DataFrame, an: pl.DataFrame) -> list[dict]:
    """Per book: props at each source, props at both, share at the same line, and at the same line the mean absolute
    gap in de-vigged P(over) (points)."""
    res = []
    for b in BOOKS.values():
        x, y = pa.filter(pl.col("book") == b), an.filter(pl.col("book") == b)
        j = x.join(y, on=["game", "nkey", "market"], how="inner", suffix="_an")
        same = j.filter(pl.col("line") == pl.col("line_an"))
        gap = [abs(no_vig_over(r["over"], r["under"]) - no_vig_over(r["over_an"], r["under_an"])) * 100 for r in same.iter_rows(named=True)]
        res.append({"book": b, "n_parlay": x.height, "n_an": y.height, "n_both": j.height,
                    "same_line": same.height, "mean_p_gap_pts": round(sum(gap) / len(gap), 2) if gap else None})
    return res


def attach(picks: pl.DataFrame, pa: pl.DataFrame | None) -> pl.DataFrame:
    """Add ParlayAPI's DK and FanDuel line and price on the pick's side (null when absent)."""
    if pa is None:
        return picks.with_columns(*(pl.lit(None, pl.Float64).alias(c) for c in PICK_COLS))
    idx = {(r["book"], r["game"], r["nkey"], r["market"]): r for r in pa.iter_rows(named=True)}
    cols = {c: [] for c in PICK_COLS}
    for p in picks.iter_rows(named=True):
        g = game_key(TEAM_FIX.get(p["home"], p["home"]), TEAM_FIX.get(p["away"], p["away"]))
        for b in BOOKS.values():
            r = idx.get((b, g, norm_name(p["player"]), p["market"]))
            cols[f"pa_{b}_line"].append(r["line"] if r else None)
            cols[f"pa_{b}_odds"].append((r["under"] if p["side"] == "under" else r["over"]) if r else None)
    return picks.with_columns(*(pl.Series(c, v, dtype=pl.Float64) for c, v in cols.items()))
