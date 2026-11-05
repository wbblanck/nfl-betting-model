"""Props-mix live tracker (docs/mix_live_rules.md). Unvalidated; tracker records, not recommendations.

Scores DraftKings props from the newest saved ParlayAPI snapshot with the M1 mix of docs/gamesim_calibration.md:
G3 game simulator volumes (10,000 runs per game) -> negative binomial player layer -> P_sim, then
P = logistic(a_g + b_g logit(P_DK) + c_g logit(P_sim)) with the frozen 2024 weights. A pick is a side at 55%+.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
from pathlib import Path

import numpy as np
import polars as pl

from nflbet import config
from nflbet.gamesim import engine as E, personnel as PE, props as GP, run as R, teams as TM
from nflbet.gamesim.teams import FRANCHISE
from nflbet.props import confirm as C, core as P, live as Lv
from nflbet.props.sim import inputs
from nflbet.sources import parlay as Pa

SEASON = 2026
SIMS = 10000
THRESH = 0.55
JUDGE_WEEKS = (10, 18)
MARKETS = ["rec", "rec_yds", "rush_att", "rush_yds", "pass_att", "pass_cmp", "pass_yds"]
GROUPS = {"rec": "receiving", "rec_yds": "receiving", "rush_att": "rushing", "rush_yds": "rushing",
          "pass_att": "passing", "pass_cmp": "passing", "pass_yds": "passing"}
BT = config.ROOT / "data" / "backtests"
PROPS = Lv.LIVE / f"mix_props_{SEASON}.csv"        # every scored prop at every run
RUNS = Lv.LIVE / f"mix_runs_{SEASON}.csv"
RECORD = Lv.LIVE / f"mix_record_{SEASON}.csv"        # official picks, graded
BEST = Lv.LIVE / f"mix_bestprice_{SEASON}.csv"       # best all-in price per pick per run (record only, rules amendment)
PROP_COLS = ["run_utc", "season", "week", "an_game_id", "start_time", "home", "away", "player", "player_id", "team",
             "market", "line", "over_odds", "under_odds", "p_over_dk", "p_sim", "p_mix", "snapshot"]
PICK_COLS = ["run_utc", "season", "week", "an_game_id", "start_time", "home", "away", "player", "player_id", "team",
             "market", "side", "line", "odds", "p_over_dk", "p_sim", "p_mix", "p_side", "edge", "snapshot"]


def coefs() -> dict:
    return json.loads((BT / "gamesim_calibration_m1.json").read_text())["coefs"]


def nb_size() -> dict:
    return json.loads((BT / "gamesim_props_dist.json").read_text())["chosen"]


def _lg(p):
    p = np.clip(np.asarray(p, float), 0.02, 0.98)
    return np.log(p / (1 - p))


def mix(market, p_dk, p_sim, cf: dict | None = None) -> np.ndarray:
    """Frozen M1 mix probability of the over (same clip as the fit: 0.02-0.98)."""
    cf = cf or coefs()
    a, b, c = (np.array([cf[GROUPS[m]][i] for m in market]) for i in range(3))
    return 1 / (1 + np.exp(-(a + b * _lg(p_dk) + c * _lg(p_sim))))


def break_even(odds: float) -> float:
    return 1 / P.american_to_decimal(odds)


def picks_from(props: pl.DataFrame) -> pl.DataFrame:
    """Sides at THRESH or more, with the price's break-even and the edge (shown, not part of the rule)."""
    if not props.height:
        return pl.DataFrame(schema={c: pl.Utf8 for c in PICK_COLS})
    d = props.with_columns(pl.when(pl.col("p_mix") >= 0.5).then(pl.lit("over")).otherwise(pl.lit("under")).alias("side"))
    d = d.with_columns(pl.when(pl.col("side") == "over").then(pl.col("over_odds")).otherwise(pl.col("under_odds")).alias("odds"),
                       pl.when(pl.col("side") == "over").then(pl.col("p_mix")).otherwise(1 - pl.col("p_mix")).alias("p_side"))
    d = d.filter(pl.col("p_side") >= THRESH)
    be = d["odds"].map_elements(break_even, return_dtype=pl.Float64)
    return d.with_columns((pl.col("p_side") - be).alias("edge")).sort("edge", descending=True).select(PICK_COLS)


# ----------------------------------------------------------------------------------------- lines

def latest_snapshot(live: Path | None = None) -> Path | None:
    files = sorted((live or Lv.LIVE).joinpath("parlay").glob("*.json.gz"))
    return files[-1] if files else None


def lines_file(snap: Path, season: int, week: int, out: Path) -> int:
    """DraftKings rows of a saved ParlayAPI snapshot in Action Network's lines format (games on this week's schedule)."""
    with gzip.open(snap, "rt") as f:
        rows = json.load(f)
    pa = Pa.parse(rows).filter(pl.col("book") == "dk")
    out.parent.mkdir(parents=True, exist_ok=True)
    return Pa.to_an_csv(pa, season, week, out)


def snapshot_books(snap: Path) -> pl.DataFrame:
    """Every book's two-sided rows (DraftKings and FanDuel) of a saved ParlayAPI snapshot, for the best-price record."""
    with gzip.open(snap, "rt") as f:
        return Pa.parse(json.load(f))


def with_best(rec: pl.DataFrame, best: pl.DataFrame | None) -> pl.DataFrame:
    """Graded official picks plus the cheapest all-in price recorded at the pick's own run, line and side
    (src/nflbet/props/bestprice.py), and the units at that price. Record only: `units` stays at DraftKings' price.
    A pick with no priced venue keeps DraftKings' price as its best."""
    keys = ["run_utc", "an_game_id", "player_id", "market", "side"]
    d = rec
    if best is not None and best.height:
        b = best.select(*keys, "best_venue", pl.col("best_cost").cast(pl.Float64), pl.col("best_odds").cast(pl.Float64)) \
            .unique(keys, keep="last", maintain_order=True)
        d = d.join(b, on=keys, how="left")
    else:
        d = d.with_columns(pl.lit(None, pl.Utf8).alias("best_venue"), pl.lit(None, pl.Float64).alias("best_cost"),
                           pl.lit(None, pl.Float64).alias("best_odds"))
    dk = pl.col("odds").cast(pl.Float64)
    dk_cost = pl.when(dk > 0).then(100 / (dk + 100)).otherwise(-dk / (-dk + 100))
    d = d.with_columns(pl.col("best_venue").fill_null("DraftKings"),
                       pl.coalesce(pl.col("best_cost"), dk_cost).alias("best_cost"),
                       pl.coalesce(pl.col("best_odds"), dk).alias("best_odds"))
    return d.with_columns(pl.when(pl.col("result") == "W").then(1 / pl.col("best_cost") - 1)
                          .when(pl.col("result") == "L").then(-1.0).otherwise(0.0).alias("units_best"))


# ------------------------------------------------------------------------------------ simulation

PBP_FIRST = 2015


def _load_inputs(season: int) -> dict:
    import nflreadpy as nfl

    seasons = list(range(PBP_FIRST, season + 1))
    pbp = pl.concat([nfl.load_pbp(seasons=[s]) for s in seasons], how="diagonal_relaxed")
    sched = nfl.load_schedules(seasons=list(range(PBP_FIRST, season + 1)))
    inj = nfl.load_injuries(seasons=list(range(2016, season + 1)))
    snaps = nfl.load_snap_counts(seasons=list(range(2016, season + 1)))
    players = nfl.load_players()
    return {"pbp": pbp, "sched": sched, "inj": inj, "snaps": snaps, "players": players}


def game_volumes(season: int, week: int, data: dict | None = None, sims: int = SIMS, seed: int = 202):
    """G3 simulator for the week's games: (games frame, att, car) with att / car arrays (G, sims, 2)."""
    data = data or _load_inputs(season)
    k = json.loads((BT / "gamesim_constants.json").read_text())
    T = json.loads((BT / "gamesim_league.json").read_text())
    tb = E.Tables(T)
    pbp, sched = data["pbp"], data["sched"]
    kicks, xps = R.kick_pools(pbp)
    fac = _with_upcoming_factors(pbp, T, k, sched, season, week)
    qg = PE.qb_games(pbp)
    qbd = PE.qb_delta(sched, qg, PE.QBRater(qg, k["personnel"]["replacement"]))
    inj = PE.injury_loss(data["inj"], data["snaps"], data["players"], sched)
    games = sched.filter(pl.col("game_type") == "REG", pl.col("season") == season, pl.col("week") == week).select(
        "season", "week", "game_id", "home_team", "away_team", (pl.col("location") == "Neutral").alias("neutral"))
    inp = PE.inputs(qbd, inj, sched).filter(pl.col("game_id").is_in(games["game_id"].implode()))
    out, _, att, car = R.simulate_games(games, fac, tb, kicks, xps, k["hfa"], sims=sims, seed=seed,
                                        shift=PE.shifts(inp, k["personnel"]["coefs"]), want_counts=True)
    return out, att, car


def _with_upcoming_factors(pbp, T, k, sched, season, week):
    """Team factors need a row for each team in the upcoming week: add placeholder zero-count rows for those games so
    `factors` emits their pre-game values (the zero-count row itself never enters any later estimate: it is last)."""
    gs = TM.game_stats(pbp, T)
    g = sched.filter(pl.col("game_type") == "REG", pl.col("season") == season, pl.col("week") == week)
    have = set(gs["game_id"].unique().to_list())
    extra = []
    for r in g.iter_rows(named=True):
        if r["game_id"] in have:
            continue
        for t, o in ((r["home_team"], r["away_team"]), (r["away_team"], r["home_team"])):
            extra.append({"season": season, "week": week, "game_id": r["game_id"], "team": FRANCHISE.get(t, t),
                          "opp": FRANCHISE.get(o, o)})
    if extra:
        z = pl.DataFrame(extra)
        num = [c for c in gs.columns if c not in z.columns]
        z = z.with_columns([pl.lit(0).cast(gs[c].dtype).alias(c) for c in num]).select(gs.columns)
        gs = pl.concat([gs, z.with_columns([pl.col(c).cast(gs[c].dtype) for c in gs.columns])]).sort(TM.KEYS)
    return TM.factors(gs, k["league"], k["h"], k["k"], k["r"])


def score(season: int, lines_path: Path, when: dt.datetime, snapshot: str, data: dict | None = None,
          sims: int = SIMS) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Every screened DraftKings prop for games not started at `when`, with P_DK, P_sim and the mix. Returns (props, log)."""
    raw = pl.read_csv(lines_path, infer_schema_length=0)
    week = int(raw["week"].cast(pl.Int64).max())
    not_started = pl.col("start_time").map_elements(lambda s: Lv.parse_ts(s) > when, return_dtype=pl.Boolean)
    lines = P.load_lines(season, path=lines_path, where=not_started).filter(pl.col("week") == week)
    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    games = lines.select("an_game_id", "start_time", "home", "away").unique()
    up = Lv.upcoming_rows(season, week)
    stats = P.load_stats(season)
    ident = up.select("player_id", "player_display_name", "position", "week", "team", "game_id")
    joined = P.join(lines, pl.concat([stats, ident], how="diagonal_relaxed"))
    s = C.screened(Lv.priced(joined)).filter(pl.col("market").is_in(MARKETS), pl.col("book") == "DK NJ",
                                                     pl.col("player_id").is_not_null()) \
        .unique(["an_game_id", "player_id", "market"], keep="first", maintain_order=True)
    sim = Lv._sim_with_upcoming(season, up)
    rows = {(r["player_id"], r["week"]): r for r in inputs(sim.pg, sim.sched, season, sim.pos_mean, sim.dfac)
            .filter(pl.col("week") == week).iter_rows(named=True)}
    out, att, car = game_volumes(season, week, data, sims)
    idx = {}
    for i, (h, a) in enumerate(zip(out["home_team"], out["away_team"])):
        idx[h], idx[a] = (i, 0), (i, 1)
    rng = np.random.default_rng(31)
    size = nb_size()
    cache, psim, teams = {}, [], []
    for r in s.iter_rows(named=True):
        key = (r["player_id"], week)
        pr = rows.get(key)
        gi = idx.get(FRANCHISE.get(pr["team"], pr["team"])) if pr else None
        teams.append(pr["team"] if pr else (r["team"] or ""))
        if gi is None:
            psim.append(None)
            continue
        if key not in cache:
            cache[key] = GP.simulate_row_vol(pr, att[gi[0], :, gi[1]], car[gi[0], :, gi[1]], sim.pools, rng, "nb", size)
        psim.append(GP.p_over(cache[key][r["market"]], r["line"]) if r["market"] in cache[key] else None)
    s = s.with_columns(pl.Series("p_sim", psim, dtype=pl.Float64), pl.Series("team", teams, dtype=pl.Utf8)).filter(pl.col("p_sim").is_not_null())
    props = s.with_columns(pl.Series("p_mix", mix(s["market"].to_list(), s["p_over"].to_numpy(), s["p_sim"].to_numpy())),
                           pl.lit(stamp).alias("run_utc"), pl.lit(season).alias("season"), pl.lit(snapshot).alias("snapshot"),
                           pl.col("p_over").alias("p_over_dk")).select(PROP_COLS)
    n = props.group_by("an_game_id").len().rename({"len": "props_scored"})
    log = games.join(n, on="an_game_id", how="left").with_columns(
        pl.lit(stamp).alias("run_utc"), pl.lit(season).alias("season"), pl.lit(week).alias("week"),
        pl.col("props_scored").fill_null(0), pl.lit(snapshot).alias("snapshot"))
    return props, log.select("run_utc", "season", "week", "an_game_id", "start_time", "home", "away", "props_scored", "snapshot")


# ---------------------------------------------------------------------------------------- grading

def official_props(props: pl.DataFrame, runs: pl.DataFrame) -> pl.DataFrame:
    """Props from the last run before each game's kickoff that scored at least half of that game's best earlier run."""
    return Lv.official(props, runs, coverage_guard=0.5)


def grade(props: pl.DataFrame, runs: pl.DataFrame, season: int = SEASON) -> pl.DataFrame:
    """Official picks settled against nflverse (same rules as S1). Also carries every official prop's outcome."""
    import nflreadpy as nfl

    off = official_props(props, runs)
    sched = nfl.load_schedules(seasons=[season]).filter(pl.col("game_type") == "REG")
    fix = lambda c: pl.col(c).replace(P.TEAM_FIX)  # noqa: E731
    final = sched.filter(pl.col("result").is_not_null()).select("week", "home_team", "away_team")
    g = runs.select("an_game_id", pl.col("week").cast(pl.Int32), fix("home").alias("home_team"), fix("away").alias("away_team")).unique()
    st = P.load_stats(season)
    final_games = Lv.gradable(g, final, set(zip(st["week"].cast(pl.Int32).to_list(), st["team"].to_list())))
    long = st.unpivot(index=["player_id", "week"], on=list(P.STAT), variable_name="market", value_name="actual") \
        .with_columns(pl.col("week").cast(pl.Int64), pl.col("actual").cast(pl.Float64))
    sn = P.load_snaps(season)
    snap_keys = {(w, t, P.norm_name(n)) for w, t, n in zip(sn["week"], sn["team"], sn["player"])}
    typed = off.with_columns(*[pl.col(c).cast(pl.Float64) for c in ("line", "over_odds", "under_odds", "p_over_dk", "p_sim", "p_mix")])
    pk = picks_from(typed)
    played = {(r["player_id"], int(r["week"])) for r in pk.iter_rows(named=True)
              if (int(r["week"]), P.TEAM_FIX.get(r["team"] or "", r["team"] or ""), P.norm_name(r["player"])) in snap_keys}
    return Lv.settle(pk, long, played, final_games).sort("start_time", "player")


def judge(props: pl.DataFrame, runs: pl.DataFrame, season: int = SEASON) -> dict:
    """Running log loss of the mix vs DraftKings on official props of games already final (descriptive until week 18)."""
    off = official_props(props, runs).with_columns(pl.col("week").cast(pl.Int64), pl.col("line").cast(pl.Float64),
                                                     pl.col("p_over_dk").cast(pl.Float64), pl.col("p_mix").cast(pl.Float64))
    st = P.load_stats(season)
    long = st.unpivot(index=["player_id", "week"], on=list(P.STAT), variable_name="market", value_name="actual") \
        .with_columns(pl.col("week").cast(pl.Int64), pl.col("actual").cast(pl.Float64))
    d = off.join(long, on=["player_id", "week", "market"], how="inner").filter(pl.col("actual") != pl.col("line"),
                                                                         pl.col("week").is_between(*JUDGE_WEEKS))
    if not d.height:
        return {"n": 0}
    y = (d["actual"] > d["line"]).cast(pl.Float64).to_numpy()

    def ll(p):
        p = np.clip(p, 0.02, 0.98)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    return {"n": int(d.height), "weeks": int(d["week"].n_unique()), "ll_mix": ll(d["p_mix"].to_numpy()),
            "ll_dk": ll(d["p_over_dk"].to_numpy())}
