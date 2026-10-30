"""S1 live tracker (docs/s1_live_rules.md).

  python scripts/live_s1.py run     # fetch this week's lines, record S1 picks for games not yet started
  python scripts/live_s1.py grade   # settle official picks, write docs/s1_live.md and the season record
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import shutil
import subprocess
import sys

import polars as pl

from nflbet import config
from nflbet.ats import live as AL
from nflbet.ats import your_venues as AY
from nflbet.props import bestprice as Bp
from nflbet.sources import depth as D
from nflbet.sources import injuries as Inj
from nflbet.props import live as Lv
from nflbet.sources import openmarkets as Om
from nflbet.sources import parlay as Pa
from nflbet.sources import venues as V
from nflbet.props import core as P
from nflbet.props import your_venues as SY

SEASON = 2026
PICKS = Lv.LIVE / f"s1_picks_{SEASON}.csv"
RUNS = Lv.LIVE / f"s1_runs_{SEASON}.csv"
PARLAY_CMP = Lv.LIVE / f"parlay_compare_{SEASON}.csv"
BEST = Lv.LIVE / f"s1_bestprice_{SEASON}.csv"
# "S1 on ParlayAPI": the same rule scored on ParlayAPI's DK and FanDuel lines (books-disagree vote = DK vs FanDuel
# only). A separate record, never pooled with the official S1 record above.
PA_PICKS = Lv.LIVE / f"s1pa_picks_{SEASON}.csv"
PA_RUNS = Lv.LIVE / f"s1pa_runs_{SEASON}.csv"
PA_RECORD = Lv.LIVE / f"s1pa_record_{SEASON}.csv"
OM_CMP = Lv.LIVE / f"openmarkets_compare_{SEASON}.csv"
_OM_ROWS: list = []
_PA_ROWS: list = []                                                 # raw ParlayAPI rows: pick'em quotes for the your-venues record


def do_run() -> None:
    week = Lv.current_week(SEASON)
    if week is None:
        print("season over"); return
    tmp = Lv.LIVE / "tmp" / "an_props_live.csv"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(config.ROOT / "scripts" / "fetch" / "an_props.py"), "--season", str(SEASON),
                    "--weeks", f"{week}-{week}", "--out", str(tmp)], check=True)
    with open(tmp) as f:
        n_rows = sum(1 for _ in f) - 1                                  # header excluded
    when = Lv.now_utc()
    pa = parlay_record(week, when, tmp if n_rows > 0 else None)
    om = openmarkets_record(week, when, pa, tmp if n_rows > 0 else None)
    scored = []                                                          # (label, picks, log, picks file, runs file)
    if n_rows > 0:
        arch = Lv.LIVE / "lines" / f"{when.strftime('%Y%m%dT%H%MZ')}_w{week}.csv.gz"   # saved first: a failed run leaves its input
        arch.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "rb") as f, gzip.open(arch, "wb") as g:
            shutil.copyfileobj(f, g)
        picks, log = Lv.run(SEASON, tmp, when)
        scored.append(("S1 (Action Network)", Om.attach(Pa.attach(picks, pa), om), log, PICKS, RUNS))
    else:                                                                # books have not posted this week's props yet
        print(f"week {week}: Action Network has no player props posted yet; official S1 has nothing to score (not an error)")
    if pa is not None and pa.height:
        try:
            pa_csv = Lv.LIVE / "tmp" / "pa_props_live.csv"
            n = Pa.to_an_csv(pa, SEASON, week, pa_csv)
            if n:
                picks, log = Lv.run(SEASON, pa_csv, when)
                scored.append(("S1 on ParlayAPI (DK + FanDuel)", Om.attach(picks, om), log, PA_PICKS, PA_RUNS))
        except Exception as e:  # noqa: BLE001 - the second record never stops the official one
            print(f"S1 on ParlayAPI unavailable: {type(e).__name__}: {e}")
    ats_record(week, when)
    if n_rows > 0:                                                      # scored[0] is official S1
        bestprice_record(scored[0][1], tmp, pa, week, when)
    if not scored:
        return
    flagged = with_news([x[1] for x in scored], week, when)
    for (label, _, log, pf, rf), picks in zip(scored, flagged):
        Lv.append(picks, pf)
        Lv.append(log, rf)
        print(f"{label}, week {week}: {log.height} games not yet started, {int(log['props_scored'].sum())} props scored, "
              f"{picks.height} picks")
        for r in picks.sort("start_time").iter_rows(named=True):
            print(f"  {r['away']}@{r['home']}  {r['player']:24s} {r['market']:12s} {r['side']:5s} {r['line']:6} {r['odds']:+.0f}"
                  f"  {'INJURY NEWS AGAINST ' if r['inj_against'] else ''}{r['inj_self'] or ''} {r['inj_teammates'] or ''}"
                  f"  {'DEPTH CHART AGAINST ' if r['depth_against'] else ''}{r['depth_note'] or ''}")


def bestprice_record(picks: pl.DataFrame, an_path, pa: pl.DataFrame | None, week: int, when: dt.datetime) -> None:
    """Best available price per official S1 pick at its line and side, all-in (src/nflbet/props/bestprice.py), appended to
    data/live/s1_bestprice_2026.csv. Record only: S1 is still graded at its DraftKings price. A failure never stops
    the run."""
    try:
        quotes = Bp.fetch_quotes(picks, week, when)
        yv_s1_record(picks, quotes, when)
        rows = Bp.record(picks, an_path, pa, week, when, quotes=quotes)
        if rows is None or not rows.height:
            return
        Lv.append(rows, BEST)
        for r in rows.iter_rows(named=True):
            best = f"{r['best_venue']} {r['best_odds']:+.0f} ({r['edge_cents']:+.1f}c vs DK)" if r["best_venue"] else "no venue at this line"
            print(f"  best price: {r['player']:24s} {r['market']:12s} {r['side']:5s} {r['line']:6} DK {r['dk_odds']:+.0f} -> "
                  f"{best}, {r['n_venues']} venues")
    except Exception as e:  # noqa: BLE001
        print(f"best price record unavailable: {type(e).__name__}: {e}")


def yv_s1_record(picks: pl.DataFrame, quotes: dict, when: dt.datetime) -> None:
    """S1 on Will's venues (src/nflbet/props/your_venues.py, docs/your_venues_rules.md): each official pick priced at the
    cheapest of his venues at a line at least as good as DK's, appended to data/live/s1_yv_2026.csv. Descriptive; a
    failure never stops the run."""
    try:
        if picks is None or not picks.height:
            return
        pickem = Pa.parse_pickem(_PA_ROWS) if _PA_ROWS else None
        qs = [SY.exchange_quotes(p, quotes["pmq"], quotes["pm_size"], quotes["nv_idx"], quotes["nv_books"], quotes["ksq"])
              + SY.pickem_quotes(p, pickem) for p in picks.iter_rows(named=True)]
        rows = SY.rows(picks, qs, when.strftime("%Y-%m-%dT%H:%M:%SZ"))
        Lv.append(rows, SY.ROWS)
        for r in rows.iter_rows(named=True):
            at = f"{r['yv_venue']} {r['yv_line']:g} ({r['yv_odds']:+.0f})" if r["yv_venue"] else r["label"]
            print(f"  your venues: {r['player']:24s} {r['market']:12s} {r['side']:5s} DK {r['dk_line']:g} -> {at}, {r['n_quotes']} quotes")
    except Exception as e:  # noqa: BLE001
        print(f"your-venues S1 record unavailable: {type(e).__name__}: {e}")


def yv_ats_record(fair: pl.DataFrame, ev: pl.DataFrame, week: int, when: dt.datetime) -> None:
    """ATS on Will's venues (src/nflbet/ats/your_venues.py): the official rules at the best number among Kalshi and
    Polymarket US (OpenMarkets, fees added) and Novig (its public catalog), appended to data/live/ats_yv_runs_2026.csv. Descriptive; a failure never
    stops the run."""
    try:
        frames = [AY.exchange_quotes(Om.spread_quotes(_OM_ROWS))]                      # Kalshi, Polymarket US (fees added)
        try:
            nv = V.nv_spread_quotes(*V.nv_spread_markets(when))
            frames.append(pl.DataFrame(nv, schema=AY.QUOTE_SCHEMA))
        except Exception as e:  # noqa: BLE001 - one venue down never stops the record
            print(f"your-venues ATS: Novig spreads unavailable: {type(e).__name__}: {e}")
        quotes = pl.concat(frames)
        yv = AY.evaluate(fair, ev, quotes)
        if not yv.height:
            return
        yv = yv.with_columns(pl.lit(when.strftime("%Y-%m-%dT%H:%M:%SZ")).alias("run_utc"), pl.lit(week).alias("week"))
        Lv.append(yv, AY.RUNS)
        for r in yv.sort("start_time").iter_rows(named=True):
            at = (f"{r['side']} {r['yv_line']:+g} at {r['yv_venue']} (cost {r['yv_cost']:.3f}), gap {r['gap']:+.2f}"
                  if r["yv_venue"] else "no eligible quote")
            print(f"ATS your venues {r['away']}@{r['home']}: {at}: {r['label']}")
    except Exception as e:  # noqa: BLE001
        print(f"your-venues ATS record unavailable: {type(e).__name__}: {e}")


def ats_record(week: int, when: dt.datetime) -> None:
    """Live ATS tracker (src/nflbet/ats/live.py, docs/ats_live_rules.md): every game not yet started, appended to
    data/live/ats_runs_2026.csv. Descriptive; a failure never stops the S1 run."""
    try:
        books = AL.parse_an(AL.fetch_an(SEASON, week))
        fair = AL.fair_lines(SEASON, week)
        exch = Om.spreads(_OM_ROWS) if _OM_ROWS else None
        try:
            qb = AL.qb_flags(SEASON, week)
        except Exception as e:  # noqa: BLE001
            print(f"ATS QB check unavailable: {type(e).__name__}: {e}")
            qb = {}
        ev = AL.evaluate(fair, books, exch, qb)
        if not ev.height:
            print("ATS: no game spreads posted"); return
        ev = ev.filter(pl.col("start_time").map_elements(lambda t: Lv.parse_ts(t) > when, return_dtype=pl.Boolean))
        ev = ev.with_columns(pl.lit(when.strftime("%Y-%m-%dT%H:%M:%SZ")).alias("run_utc"), pl.lit(week).alias("week"))
        Lv.append(ev, AL.RUNS)
        yv_ats_record(fair, ev, week, when)
        for r in ev.sort("start_time").iter_rows(named=True):
            print(f"ATS {r['away']}@{r['home']}: fair {r['fair']:+.1f}, consensus {r['consensus']:+.1f}, exchange {r['exchange']}, "
                  f"{r['side']} at {r['best_book']} {r['best_line']:+.1f} ({r['best_odds']:+.0f}), gap {r['gap']:+.2f}, "
                  f"key {r['key']}, exp CLV {r['exp_clv']:+.2f}: {r['label']} {r['qb_note']}")
    except Exception as e:  # noqa: BLE001
        print(f"ATS tracker unavailable: {type(e).__name__}: {e}")


def openmarkets_record(week: int, when: dt.datetime, pa: pl.DataFrame | None, an_path) -> pl.DataFrame | None:
    """Third price record (src/nflbet/sources/openmarkets.py): Kalshi, ProphetX and BettorEdge player-prop quotes, archived in
    data/live/openmarkets/, compared per venue with DraftKings at DraftKings' line (ParlayAPI's DK if available, else
    Action Network's) in data/live/openmarkets_compare_2026.csv. Skipped without OPENMARKETS_API_KEY; a failure
    never stops the run."""
    if not os.environ.get("OPENMARKETS_API_KEY"):
        print("OpenMarkets record skipped: OPENMARKETS_API_KEY not set")
        return None
    try:
        rows = Om.fetch(now=when)
        _OM_ROWS[:] = rows                                              # game spreads, reused by the ATS tracker
        om = Om.parse(rows)
        arch = Lv.LIVE / "openmarkets" / f"{when.strftime('%Y%m%dT%H%MZ')}_w{week}.csv.gz"   # parsed quotes only (raw ~1 MB/run)
        arch.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(arch, "wb") as f:
            om.write_csv(f)
        dk = pa.filter(pl.col("book") == "dk") if pa is not None and pa.height else (
            Pa.an_lines(an_path).filter(pl.col("book") == "dk") if an_path is not None else Pa.parse([]))
        cmp = pl.DataFrame([{"run_utc": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "week": week, **c} for c in Om.compare(om, dk)])
        Lv.append(cmp, OM_CMP)
        for c in cmp.iter_rows(named=True):
            print(f"OpenMarkets {c['venue']}: {c['n_both']} of {c['n_dk']} DK props quoted two-sided at DK's line, "
                  f"mean no-vig gap {c['mean_gap_pts']} pts, median ${c['median_avail']} on the thinner side")
        return om
    except Exception as e:  # noqa: BLE001
        print(f"OpenMarkets record unavailable: {type(e).__name__}: {e}")
        return None


def parlay_record(week: int, when: dt.datetime, an_path) -> pl.DataFrame | None:
    """Second price record (src/nflbet/sources/parlay.py): ParlayAPI's DK and FanDuel lines, archived in data/live/parlay/,
    and per book how they compare with Action Network's at this run (data/live/parlay_compare_2026.csv). Descriptive;
    S1 still runs on Action Network. Skipped without PARLAY_API_KEY; a failure never stops the run."""
    if not os.environ.get("PARLAY_API_KEY"):
        print("ParlayAPI record skipped: PARLAY_API_KEY not set")
        return None
    try:
        rows, hdr = Pa.fetch()
        _PA_ROWS[:] = rows
        _archive(rows, "parlay", week, when)
        pa = Pa.parse(rows)
        an = Pa.an_lines(an_path) if an_path is not None else Pa.parse([])
        if an_path is not None:                                         # games already started carry in-play lines
            started = {Pa.game_key(P.TEAM_FIX.get(h, h), P.TEAM_FIX.get(a, a))
                       for h, a, t in pl.read_csv(an_path, infer_schema_length=0).select("home", "away", "start_time").unique().iter_rows()
                       if Lv.parse_ts(t) <= when}
            an = an.filter(~pl.col("game").is_in(list(started)))
            pa = pa.filter(~pl.col("game").is_in(list(started)))
        stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
        cmp = pl.DataFrame([{"run_utc": stamp, "week": week, **c, "credits_left": hdr.get("x-requests-remaining")}
                            for c in Pa.compare(pa, an)])
        Lv.append(cmp, PARLAY_CMP)
        for c in cmp.iter_rows(named=True):
            print(f"ParlayAPI {c['book']}: {c['n_parlay']} props, Action Network {c['n_an']}, both {c['n_both']}, "
                  f"same line {c['same_line']}, mean P(over) gap at same line {c['mean_p_gap_pts']} pts")
        print(f"ParlayAPI credits left: {hdr.get('x-requests-remaining')}")
        return pa
    except Exception as e:  # noqa: BLE001
        print(f"ParlayAPI record unavailable: {type(e).__name__}: {e}")
        return None


def _archive(body, kind: str, week: int, when: dt.datetime) -> None:
    arch = Lv.LIVE / kind / f"{when.strftime('%Y%m%dT%H%MZ')}_w{week}.json.gz"
    arch.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(arch, "wt") as f:
        json.dump(body, f)


def with_news(frames: list[pl.DataFrame], week: int, when: dt.datetime) -> list[pl.DataFrame]:
    """Descriptive flags (src/nflbet/sources/injuries.py, src/nflbet/sources/depth.py) from ESPN at run time, fetched once and applied
    to every record's picks; responses are archived. A failed fetch leaves that flag empty and never stops the run."""
    inj = None
    try:
        body = Inj.fetch()
        _archive(body, "injuries", week, when)
        inj = Inj.parse(body)
        ids, recent = Inj.espn_ids(), Inj.recent_players(SEASON, week)
        frames = [Inj.flag(f, inj, ids, recent) for f in frames]
    except Exception as e:  # noqa: BLE001
        print(f"injury flag unavailable: {type(e).__name__}: {e}")
        frames = [f.with_columns(pl.lit("fetch failed").alias("inj_self"), pl.lit(None, pl.Utf8).alias("inj_teammates"),
                                 pl.lit(None, pl.Boolean).alias("inj_against")) for f in frames]
    try:
        if inj is None:
            raise RuntimeError("needs the injury list")
        charts = D.fetch(SEASON)
        _archive(charts, "depth", week, when)
        ch = D.changes(D.parse(charts), inj, D.players_table(), D.recent_usage(SEASON, week))
        print("depth-chart changes:", [f"{r['team']} {r['pos']}: {r['starter_name']} over {r['leader_name']}" for r in ch.iter_rows(named=True)])
        frames = [D.flag(f, ch) for f in frames]
    except Exception as e:  # noqa: BLE001
        print(f"depth flag unavailable: {type(e).__name__}: {e}")
        frames = [f.with_columns(pl.lit("fetch failed").alias("depth_note"), pl.lit(None, pl.Boolean).alias("depth_against"))
                  for f in frames]
    return frames


def news(r: dict) -> str:
    """One cell: injury and depth-chart news recorded at the pick's run (string fields as read back from the CSV)."""
    if r["inj_against"] is None:
        inj = f"injuries {r['inj_self'] or 'not checked'}"
    else:
        inj = "; ".join(x for x in (f"self: {r['inj_self']}" if r["inj_self"] else "", r["inj_teammates"] or "") if x)
        inj = ("**Injury against** — " + inj) if r["inj_against"] == "true" else inj
    if r["depth_against"] is None:
        dep = f"depth chart {r['depth_note'] or 'not checked'}"
    else:
        dep = ("**Depth chart against** — " + (r["depth_note"] or "")) if r["depth_against"] == "true" else (r["depth_note"] or "")
    return "; ".join(x for x in (inj, dep) if x)


def settle_record(picks_path, runs_path, out_path, coverage_guard: float | None = None) -> pl.DataFrame | None:
    """Official picks (last run before kickoff) settled against nflverse; written to out_path."""
    import nflreadpy as nfl

    if not picks_path.exists() or not picks_path.stat().st_size:
        return None
    picks = pl.read_csv(picks_path, infer_schema_length=0)
    runs = pl.read_csv(runs_path, infer_schema_length=0)
    off = Lv.official(picks, runs, coverage_guard)
    sched = nfl.load_schedules(seasons=[SEASON]).filter(pl.col("game_type") == "REG")
    fix = lambda c: pl.col(c).replace(P.TEAM_FIX)  # noqa: E731
    final = sched.filter(pl.col("result").is_not_null()).select("week", "home_team", "away_team")
    g = runs.select("an_game_id", pl.col("week").cast(pl.Int32), fix("home").alias("home_team"), fix("away").alias("away_team")).unique()
    st = P.load_stats(SEASON)
    final_games = Lv.gradable(g, final, set(zip(st["week"].cast(pl.Int32).to_list(), st["team"].to_list())))
    long = st.unpivot(index=["player_id", "week"], on=list(P.STAT), variable_name="market", value_name="actual") \
        .with_columns(pl.col("week").cast(pl.Int64), pl.col("actual").cast(pl.Float64))
    sn = P.load_snaps(SEASON)
    snap_keys = {(w, t, P.norm_name(n)) for w, t, n in zip(sn["week"], sn["team"], sn["player"])}
    played = {(r["player_id"], int(r["week"])) for r in off.iter_rows(named=True)
              if (int(r["week"]), P.TEAM_FIX.get(r["team"], r["team"]), P.norm_name(r["player"])) in snap_keys}
    d = Lv.settle(off, long, played, final_games).sort("start_time", "player")
    d.write_csv(out_path)
    return d


def do_grade() -> None:
    if AL.RUNS.exists() and AL.RUNS.stat().st_size:
        try:
            g = AL.grade(pl.read_csv(AL.RUNS, infer_schema_length=0), SEASON)
            g.write_csv(AL.RECORD)
            bn = g.filter(pl.col("label") == "Bet Now", pl.col("result_ats").is_in(["W", "L", "P"]))
            print(f"ATS tracker: {g.height} official games; Bet Now graded {bn.height}")
        except Exception as e:  # noqa: BLE001
            print(f"ATS grading unavailable: {type(e).__name__}: {e}")
    if AY.RUNS.exists() and AY.RUNS.stat().st_size:
        try:
            g = AY.grade(pl.read_csv(AY.RUNS, infer_schema_length=0), SEASON)
            g.write_csv(AY.RECORD)
            print(f"ATS your venues: {g.height} official games, {int(g['result_ats'].is_in(['W', 'L', 'P']).sum())} graded")
        except Exception as e:  # noqa: BLE001
            print(f"your-venues ATS grading unavailable: {type(e).__name__}: {e}")
    pa = settle_record(PA_PICKS, PA_RUNS, PA_RECORD, coverage_guard=0.5)   # ParlayAPI's DK feed thins out overnight
    if pa is not None:
        t = Lv.record(pa)
        print(f"S1 on ParlayAPI: {t['W']}-{t['L']}-{t['P']}, {t['units']:+.2f} units (pending {t['pending']}, void {t['void']})")
    d = settle_record(PICKS, RUNS, Lv.LIVE / f"s1_record_{SEASON}.csv")
    if d is None:
        print("no picks yet"); return
    if SY.ROWS.exists() and SY.ROWS.stat().st_size:
        try:
            g = SY.grade(pl.read_csv(SY.ROWS, infer_schema_length=0), d)
            g.write_csv(SY.RECORD)
            print(f"S1 your venues: {g.height} official picks, {int(g['result'].is_in(['W', 'L', 'P']).sum())} graded, "
                  f"{int((g['result'] == 'no line').sum())} with no line")
        except Exception as e:  # noqa: BLE001
            print(f"your-venues S1 grading unavailable: {type(e).__name__}: {e}")
    tot = Lv.record(d)
    lines = [f"# S1 live tracker, {SEASON}", "",
             "Rule S1: bet only props where all four signals agree (docs/simulator_confirm.md). NOT validated: in 2025 it",
             "went 38-23 (+5.2%) on 61 bets, an interval of -16% to +27%. Official pick = the last run before kickoff.",
             f"Updated {Lv.now_utc().strftime('%Y-%m-%d %H:%M')} UTC.", "",
             f"**Season: {tot['W']}-{tot['L']}" + (f"-{tot['P']}" if tot["P"] else "") +
             (f", {tot['win_pct']:.1%} wins, {tot['units']:+.2f} units, ROI {tot['roi']:+.1%}" if tot["win_pct"] is not None else "") +
             f"** (pending {tot['pending']}, void {tot['void']})", "",
             "| Week | W-L-P | Win % | Units | ROI |", "|---|---|---|---|---|"]
    for (wk,), x in sorted(d.group_by(["week"]), key=lambda kv: int(kv[0][0])):
        r = Lv.record(x)
        if r["W"] + r["L"] + r["P"]:
            lines.append(f"| {wk} | {r['W']}-{r['L']}-{r['P']} | {r['win_pct']:.1%} | {r['units']:+.2f} | {r['roi']:+.1%} |"
                         if r["win_pct"] is not None else f"| {wk} | {r['W']}-{r['L']}-{r['P']} | | | |")
    for c in Inj.FLAG_COLS + D.FLAG_COLS:
        if c not in d.columns:
            d = d.with_columns(pl.lit(None, pl.Utf8).alias(c))
    lines += ["", "News flags (descriptive; S1 unchanged), from ESPN at the pick's run. **Injury against** = an under whose "
              "teammate at the same position is Out / Doubtful / IR, or an over whose player is himself listed (from "
              "2026-10-03). **Depth chart against** = the team's listed QB / RB starter differs from its recent usage "
              "leader, and the pick is an under on the new starter or an over on the old leader (from 2026-10-03)."]
    for lab, x in (("Injury against", d.filter(pl.col("inj_against") == "true")),
                   ("Depth chart against", d.filter(pl.col("depth_against") == "true")),
                   ("Neither flag against", d.filter(pl.col("inj_against") == "false", pl.col("depth_against") == "false"))):
        r = Lv.record(x)
        lines.append(f"- {lab}: {r['W']}-{r['L']}-{r['P']}" + (f", {r['units']:+.2f} units" if r["W"] + r["L"] else "")
                     + f" (pending {r['pending']})")
    lines += ["", "## Picks", "", "| Week | Game | Player | Prop | Side | Line | Odds | News at pick | Result |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in d.sort("week", "start_time", "player", descending=[True, False, False]).iter_rows(named=True):
        lines.append(f"| {r['week']} | {r['away']}@{r['home']} | {r['player']} | {r['market']} | {r['side']} | {r['line']} | "
                     f"{int(r['odds']):+d} | {news(r)} | {r['result']} |")
    (config.ROOT / "docs" / "s1_live.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))


if __name__ == "__main__":
    {"run": do_run, "grade": do_grade}[sys.argv[1]]()
