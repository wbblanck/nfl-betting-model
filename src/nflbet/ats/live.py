"""Live ATS tracker (docs/ats_live_rules.md): each run records, for every game of the week not yet started, the
frozen rating's fair line, every book's spread and price (Action Network scoreboard), the exchanges' spread
(OpenMarkets), the best number for the rating's side, expected CLV, the key-number flag (rule K1) and a label.

Descriptive tracker, unvalidated (CLAUDE.md second exception). The rating does not beat closing spreads
(docs/ats_confirm.md); it does predict open-to-close movement (docs/ats_clv.md, docs/ats_clv2.md), which is what
expected CLV here estimates.
"""
from __future__ import annotations

import datetime as dt
import json
import statistics
import time
import urllib.request

import polars as pl

from nflbet import config
from nflbet.ats import rating as A
from nflbet.execution.records import before_kickoff
from nflbet.quant.odds import american_to_decimal
from nflbet.sources.http import BROWSER_UA as UA
from nflbet.sources.ids import TEAM_FIX, game_key

AN = "https://api.actionnetwork.com/web/v2/scoreboard/nfl?season={s}&week={w}&periods=event"
BOOKS = {68: "DraftKings", 69: "FanDuel", 71: "BetRivers", 75: "BetMGM", 49: "Caesars"}
CONSENSUS = 15                       # Action Network consensus, a reference, not a book; 30 ("Open") is ignored
CLV_PER_POINT = 0.235                # line moves this share of (fair - line) by the close: bet365 2022-24, docs/ats_clv2.md
RUNS = config.ROOT / "data" / "live" / "ats_runs_2026.csv"
RECORD = config.ROOT / "data" / "live" / "ats_record_2026.csv"


def fetch_an(season: int, week: int) -> dict:
    headers = {"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.actionnetwork.com/",
               "Origin": "https://www.actionnetwork.com"}
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(AN.format(s=season, w=week), headers=headers), timeout=60) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001 - retried
            time.sleep(2 ** (i + 1))
    raise RuntimeError("Action Network scoreboard unavailable")


def parse_an(sb: dict) -> pl.DataFrame:
    """One row per game and book: game (team key), start_time, home, away, book, home_line (positive = home favored),
    home_odds, away_odds. Consensus rows carry book 'consensus'."""
    out = []
    for g in sb.get("games", []):
        teams = {t["id"]: TEAM_FIX.get(t.get("abbr"), t.get("abbr")) for t in g.get("teams", [])}
        h, a = teams.get(g.get("home_team_id")), teams.get(g.get("away_team_id"))
        if not (h and a):
            continue
        for bid, mk in (g.get("markets") or {}).items():
            bid = int(bid)
            name = BOOKS.get(bid) or ("consensus" if bid == CONSENSUS else None)
            if not name:
                continue
            sp = {s["side"]: s for s in (mk.get("event") or {}).get("spread", []) if s.get("period", "event") == "event"}
            if "home" not in sp or "away" not in sp or sp["home"].get("value") is None:
                continue
            out.append({"game": game_key(h, a), "start_time": g.get("start_time"), "home": h, "away": a, "book": name,
                        "home_line": -float(sp["home"]["value"]), "home_odds": sp["home"].get("odds"),
                        "away_odds": sp["away"].get("odds")})
    return pl.DataFrame(out, schema={"game": pl.Utf8, "start_time": pl.Utf8, "home": pl.Utf8, "away": pl.Utf8, "book": pl.Utf8,
                                     "home_line": pl.Float64, "home_odds": pl.Float64, "away_odds": pl.Float64})


def fair_lines(season: int, week: int) -> pl.DataFrame:
    """Frozen rating's fair home margin for this week's scheduled games: game_id, game, home, away, neutral, fair."""
    import nflreadpy as nfl

    k = json.loads((config.ROOT / "data" / "backtests" / "ats_constants.json").read_text())
    tg = A.team_games([season - 1, season]).filter((pl.col("season") < season) | (pl.col("week") < week))
    st = A.current_state(tg, k["h"], k["k"], k["r"])
    sch = nfl.load_schedules(seasons=[season]).filter(pl.col("game_type") == "REG", pl.col("week") == week)
    rows = []
    for r in sch.iter_rows(named=True):
        neutral = r["location"] == "Neutral"
        fair = k["c"] * (st.get(r["home_team"], 0.0) - st.get(r["away_team"], 0.0)) + (0.0 if neutral else k["hfa"])
        rows.append({"game_id": r["game_id"], "game": game_key(r["home_team"], r["away_team"]), "home": r["home_team"],
                     "away": r["away_team"], "neutral": neutral, "fair": fair})
    return pl.DataFrame(rows)


def evaluate(fair: pl.DataFrame, books: pl.DataFrame, exch: pl.DataFrame | None, qb_flags: dict[str, str] | None = None) -> pl.DataFrame:
    """One row per game: fair, consensus, exchange line, the rating's side, best number and book, gap, key flag,
    expected CLV, whether the number is at least as good as the sharp reference, QB note and label."""
    qb_flags = qb_flags or {}
    out = []
    for f in fair.iter_rows(named=True):
        b = books.filter(pl.col("game") == f["game"])
        real = b.filter(pl.col("book") != "consensus")
        if not real.height:
            continue
        cons = b.filter(pl.col("book") == "consensus")
        cons_line = float(cons["home_line"][0]) if cons.height else float(statistics.median(real["home_line"].to_list()))
        ex = exch.filter(pl.col("game") == f["game"]) if exch is not None and exch.height else None
        ex_line = float(statistics.median(ex["home_line"].to_list())) if ex is not None and ex.height else None
        ref = ex_line if ex_line is not None else cons_line
        home = f["fair"] > cons_line
        # best number for the side: home wants the smallest home_line, away the largest; ties -> better price
        price_col = "home_odds" if home else "away_odds"
        best = real.sort(["home_line", price_col], descending=[not home, True]).row(0, named=True)
        line, odds = best["home_line"], best[price_col]
        gap = (f["fair"] - line) if home else (line - f["fair"])
        key = A.crosses_key(line, f["fair"], home)
        beats = (line <= ref) if home else (line >= ref)
        side_team = f["home"] if home else f["away"]
        qb = "; ".join(v for t, v in qb_flags.items() if t in (f["home"], f["away"]))
        if gap >= 1 and key and beats:
            label = "Wait" if qb else "Bet Now"
        elif gap >= 1.5 or (gap >= 1 and key):
            label = "Monitor"
        else:
            label = "No Value"
        out.append({"game_id": f["game_id"], "game": f["game"], "start_time": best["start_time"], "home": f["home"], "away": f["away"],
                    "fair": round(f["fair"], 2), "consensus": cons_line, "exchange": ex_line, "n_exchanges": 0 if ex is None else ex.height,
                    "side": side_team, "side_is_home": home, "best_book": best["book"], "best_line": line, "best_odds": odds,
                    "gap": round(gap, 2), "key": key, "exp_clv": round(CLV_PER_POINT * max(gap, 0.0), 2), "beats_ref": beats,
                    "qb_note": qb, "label": label,
                    **{f"{bk.lower()}_line": (float(real.filter(pl.col("book") == bk)["home_line"][0]) if real.filter(pl.col("book") == bk).height else None)
                       for bk in BOOKS.values()}})
    return pl.DataFrame(out)


def qb_flags(season: int, week: int) -> dict[str, str]:
    """{team: note} when a team's recent starting QB (most attempts in its last 3 weeks) is listed Questionable or
    worse on ESPN right now (src/nflbet/sources/injuries.py, src/nflbet/sources/depth.py)."""
    from nflbet.sources import depth as D
    from nflbet.sources import injuries as Inj

    inj = Inj.parse(Inj.fetch())
    ids = Inj.espn_ids()
    st = inj.join(ids, on="espn_id").filter(pl.col("status").is_in(list(Inj.SHOWN)))
    status = dict(zip(st["player_id"].to_list(), st["status"].to_list()))
    names = dict(zip(st["player_id"].to_list(), st["name"].to_list()))
    u = D.recent_usage(season, week).filter(pl.col("pos") == "QB").sort("n", descending=True).group_by("team", maintain_order=True).first()
    return {r["team"]: f"{r['team']} QB {names[r['player_id']]}: {status[r['player_id']]}"
            for r in u.iter_rows(named=True) if r["player_id"] in status}


def official(runs: pl.DataFrame) -> pl.DataFrame:
    """The last run before each game's kickoff."""
    r = before_kickoff(runs)
    last = r.group_by("game_id").agg(pl.col("run_utc").max())
    return r.join(last, on=["game_id", "run_utc"])


def grade(runs: pl.DataFrame, season: int) -> pl.DataFrame:
    """Official rows graded once final: CLV (points the closing spread moved toward the side from the recorded
    number; nflverse closing spread_line) and the ATS result at the recorded number and price (Bet Now / Wait /
    Monitor rows only; No Value rows keep CLV for reference)."""
    import nflreadpy as nfl

    off = official(runs).with_columns(pl.col("best_line").cast(pl.Float64), pl.col("best_odds").cast(pl.Float64),
                                      (pl.col("side_is_home").cast(pl.Utf8) == "true").alias("home_side"))
    sch = nfl.load_schedules(seasons=[season]).select("game_id", "result", "spread_line")
    d = off.join(sch, on="game_id", how="left")
    res, units, clv = [], [], []
    for r in d.iter_rows(named=True):
        if r["result"] is None:
            res.append("pending"); units.append(0.0); clv.append(None); continue
        h = r["home_side"]
        clv.append(((r["spread_line"] - r["best_line"]) if h else (r["best_line"] - r["spread_line"])) if r["spread_line"] is not None else None)
        m, ln = r["result"], r["best_line"]
        if m == ln:
            res.append("P"); units.append(0.0); continue
        won = (m > ln) if h else (m < ln)
        res.append("W" if won else "L")
        units.append((american_to_decimal(r["best_odds"]) - 1) if won else -1.0)
    return d.with_columns(pl.Series("result_ats", res), pl.Series("units", units), pl.Series("clv", clv, dtype=pl.Float64))
