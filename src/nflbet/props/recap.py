"""Weekly recap of the S1 tracker's official picks: why each one landed where it did (docs/recaps/week_N.md).

Every pick's stat is split into the same parts, each compared with what that player usually does:
  receptions    = team pass attempts x targets per team attempt x catch rate      (volume x role x efficiency)
  rush attempts = team carries x share of team carries                            (volume x role)
  completions   = his pass attempts x completion rate                             (volume x efficiency)
Baseline = the player's own games this season before the week (in games he played; if fewer than 2, padded with his
last 2025 games), catch / completion rates shrunk toward the league rate. The gap between the result and the line is
then  (baseline expectation - line) + volume + role + efficiency, with the three parts from a Shapley split so the
order of the factors does not matter and the pieces add up exactly. "Efficiency" is the part closest to luck.

Context columns (game script, pass rate over expected, weather, separation, box counts, opponent coverage mix, injury
news at pick time) are descriptive. They are read from files and nflverse; nothing is carried from memory.
This recap is a hypothesis generator: with about 15 picks a week it cannot establish a cause (CLAUDE.md standing rules).
"""
from __future__ import annotations

from itertools import permutations
from pathlib import Path

import polars as pl

from nflbet import config
from nflbet.props import live as Lv

FIX = {"JAC": "JAX", "LAR": "LA", "WSH": "WAS"}
K_CATCH, K_COMP = 20.0, 50.0                  # pseudo-attempts pulling a rate toward the league rate
MARKETS = {"rec": ("pass_att", "share", "rate"), "rush_att": ("rush_att", "share"), "pass_cmp": ("own_att", "rate")}
LABEL = {"A": "volume", "S": "role", "R": "efficiency"}


def shapley(base: dict, act: dict) -> dict:
    """Split product(act) - product(base) into one piece per factor, averaged over every order of switching the
    factors from baseline to actual. The pieces sum to the total change exactly."""
    keys = list(base)
    out = {k: 0.0 for k in keys}
    perms = list(permutations(keys))
    for order in perms:
        cur = dict(base)
        prod = 1.0
        for v in cur.values():
            prod *= v
        for k in order:
            before = prod
            cur[k] = act[k]
            prod = 1.0
            for v in cur.values():
                prod *= v
            out[k] += (prod - before) / len(perms)
    return out


def _prod(d: dict) -> float:
    p = 1.0
    for v in d.values():
        p *= v
    return p


def pick_parts(market: str, base_rows: pl.DataFrame, team_week: dict, league: dict, act: dict) -> dict | None:
    """Baseline and actual factors for one pick.
    base_rows: the player's prior games (player_id rows) with columns team_att, team_car, targets, rec, carries, att, cmp.
    act: week-4 actuals {team_att, team_car, targets, rec, carries, att, cmp}."""
    if base_rows.height == 0:
        return None
    n = base_rows.height
    s = {c: float(base_rows[c].sum()) for c in ("team_att", "team_car", "targets", "rec", "carries", "att", "cmp")}
    if market == "rec":
        base = {"A": s["team_att"] / n, "S": s["targets"] / max(s["team_att"], 1.0),
                "R": (s["rec"] + K_CATCH * league["catch"]) / (s["targets"] + K_CATCH)}
        actual = {"A": act["team_att"], "S": act["targets"] / max(act["team_att"], 1.0),
                  "R": (act["rec"] / act["targets"]) if act["targets"] else base["R"]}
        if act["targets"] == 0:                       # no target: all of it is role, efficiency stays at baseline
            actual["R"] = base["R"]
        actual_stat = act["rec"]
        # a real catch rate for the week (not the baseline) is what "efficiency" measures; with zero targets it is moot
    elif market == "rush_att":
        base = {"A": s["team_car"] / n, "S": s["carries"] / max(s["team_car"], 1.0)}
        actual = {"A": act["team_car"], "S": act["carries"] / max(act["team_car"], 1.0)}
        actual_stat = act["carries"]
    elif market == "pass_cmp":
        base = {"A": s["att"] / n, "R": (s["cmp"] + K_COMP * league["comp"]) / (s["att"] + K_COMP)}
        actual = {"A": act["att"], "R": (act["cmp"] / act["att"]) if act["att"] else base["R"]}
        actual_stat = act["cmp"]
    else:
        return None
    expected = _prod(base)
    parts = shapley(base, actual)
    # the product of the actual factors equals the real stat by construction (except zero-target weeks, handled above)
    return {"base": base, "actual": actual, "expected": expected, "parts": parts, "n_base": n,
            "actual_stat": float(actual_stat), "check": _prod(actual)}


def in_favor(parts: dict, side: str) -> dict:
    """Signed so that + means the part pushed the result toward the pick's side (an under likes a smaller number)."""
    sgn = -1.0 if side == "under" else 1.0
    return {k: sgn * v for k, v in parts.items()}


def driver(parts: dict, side: str) -> tuple[str, float]:
    f = in_favor(parts, side)
    k = max(f, key=lambda x: abs(f[x]))
    return LABEL[k], f[k]


# ----------------------------------------------------------------------------------------------- data assembly

def load_week_inputs(season: int, week: int) -> dict:
    import nflreadpy as nfl

    st = nfl.load_player_stats(seasons=[season - 1, season]).filter(pl.col("season_type") == "REG")
    team_w = st.group_by("season", "week", "team").agg(pl.col("attempts").sum().alias("team_att"), pl.col("carries").sum().alias("team_car"))
    st = st.join(team_w, on=["season", "week", "team"]).with_columns(
        pl.col("receptions").alias("rec"), pl.col("attempts").alias("att"), pl.col("completions").alias("cmp"))
    return {
        "st": st,
        "pbp": nfl.load_pbp(seasons=[season]).filter(pl.col("week") == week),
        "sched": nfl.load_schedules(seasons=[season]).filter(pl.col("week") == week),
        "ngs_rec": nfl.load_nextgen_stats(stat_type="receiving", seasons=[season]).filter(pl.col("season_type") == "REG"),
        "ngs_rush": nfl.load_nextgen_stats(stat_type="rushing", seasons=[season]).filter(pl.col("season_type") == "REG"),
        "ngs_pass": nfl.load_nextgen_stats(stat_type="passing", seasons=[season]).filter(pl.col("season_type") == "REG"),
    }


def league_rates(st: pl.DataFrame, season: int, week: int) -> dict:
    x = st.filter(pl.col("season") == season, pl.col("week") < week)
    t = float(x["targets"].sum()); a = float(x["att"].sum())
    return {"catch": float(x["rec"].sum()) / t if t else 0.65, "comp": float(x["cmp"].sum()) / a if a else 0.65}


def baseline_rows(st: pl.DataFrame, pid: str, season: int, week: int) -> pl.DataFrame:
    cur = st.filter(pl.col("player_id") == pid, pl.col("season") == season, pl.col("week") < week)
    if cur.height >= 2:
        return cur
    prev = st.filter(pl.col("player_id") == pid, pl.col("season") == season - 1).sort("week").tail(4 - cur.height)
    return pl.concat([prev, cur], how="diagonal_relaxed")


def game_context(pbp: pl.DataFrame, sched: pl.DataFrame, team: str) -> dict:
    p = pbp.filter(pl.col("posteam") == team, (pl.col("pass") == 1) | (pl.col("rush") == 1))
    g = sched.filter((pl.col("home_team") == team) | (pl.col("away_team") == team))
    out = {"plays": p.height, "pass_rate": float(p["pass"].mean()) if p.height else None,
           "proe": float(p["pass_oe"].mean()) if p.height else None,
           "led_share": float((p["score_differential"] > 0).mean()) if p.height else None}
    if g.height:
        r = g.row(0, named=True)
        home = r["home_team"] == team
        out.update({"margin": (r["home_score"] - r["away_score"]) * (1 if home else -1) if r["home_score"] is not None else None,
                    "roof": r.get("roof"), "temp": r.get("temp"), "wind": r.get("wind"),
                    "opp": r["away_team"] if home else r["home_team"]})
    return out


def ngs_delta(ngs: pl.DataFrame, pid: str, week: int, cols: list[str], weight: str) -> dict:
    x = ngs.filter(pl.col("player_gsis_id") == pid, pl.col("week") > 0)
    cur, prior = x.filter(pl.col("week") == week), x.filter(pl.col("week") < week)
    out = {}
    for c in cols:
        if cur.height and cur[c][0] is not None:
            out[c] = float(cur[c][0])
            w = prior[weight].cast(pl.Float64) if prior.height else None
            out[c + "_prior"] = float((prior[c].cast(pl.Float64) * w).sum() / w.sum()) if prior.height and float(w.sum()) > 0 else None
    return out


def coverage_for(opp: str, path: Path | None = None) -> dict:
    p = path or config.ROOT / "data" / "external" / "coverage_fantasypoints_2026_w1-4.csv"
    if not p.exists():
        return {}
    d = pl.read_csv(p).filter(pl.col("team") == opp)
    a = d.filter(pl.col("table") == "all_plays")
    e = d.filter(pl.col("table") == "expected_pass_situations")
    return {"man": float(a["man_total"][0]) if a.height else None, "cov3": float(a["cov3"][0]) if a.height else None,
            "epa_db": float(a["epa_per_db"][0]) if a.height else None,
            "man_exp_pass": float(e["man_total"][0]) if e.height else None}


def build_rows(rec: pl.DataFrame, inputs: dict, season: int, week: int) -> list[dict]:
    st, lg = inputs["st"], league_rates(inputs["st"], season, week)
    rows = []
    for r in rec.iter_rows(named=True):
        market, pid = r["market"], r["player_id"]
        team = FIX.get(r["team"], r["team"])
        wk = st.filter(pl.col("player_id") == pid, pl.col("season") == season, pl.col("week") == week)
        row = {"player": r["player"], "team": team, "game": f"{r['away']}@{r['home']}", "market": market, "side": r["side"],
               "line": float(r["line"]), "odds": float(r["odds"]), "result": r["result"], "units": float(r["units"]),
               "proj": float(r["proj"]), "actual": float(r["actual"]) if r["actual"] not in (None, "") else None,
               "inj_news": "; ".join(x for x in (r.get("inj_self") or "", r.get("inj_teammates") or "") if x),
               "depth_note": r.get("depth_note") or ""}
        ctx = game_context(inputs["pbp"], inputs["sched"], team)
        row.update({f"ctx_{k}": v for k, v in ctx.items()})
        if ctx.get("opp"):
            row.update({f"opp_{k}": v for k, v in coverage_for(ctx["opp"]).items()})
        if wk.height and market in MARKETS:
            act = {c: float(wk[c][0] or 0) for c in ("team_att", "team_car", "targets", "rec", "carries", "att", "cmp")}
            parts = pick_parts(market, baseline_rows(st, pid, season, week), {}, lg, act)
            if parts:
                f = in_favor(parts["parts"], r["side"])
                name, val = driver(parts["parts"], r["side"])
                row.update({"expected": parts["expected"], "n_base": parts["n_base"], "driver": name, "driver_in_favor": val,
                            **{f"base_{k}": v for k, v in parts["base"].items()}, **{f"act_{k}": v for k, v in parts["actual"].items()},
                            **{f"d_{LABEL[k]}": v for k, v in parts["parts"].items()},
                            **{f"fav_{LABEL[k]}": v for k, v in f.items()}})
        if market == "rec":
            row.update({f"ngs_{k}": v for k, v in ngs_delta(inputs["ngs_rec"], pid, week, ["avg_separation", "avg_cushion"], "targets").items()})
        elif market == "rush_att":
            row.update({f"ngs_{k}": v for k, v in ngs_delta(inputs["ngs_rush"], pid, week, ["percent_attempts_gte_eight_defenders", "rush_yards_over_expected_per_att"], "rush_attempts").items()})
        elif market == "pass_cmp":
            row.update({f"ngs_{k}": v for k, v in ngs_delta(inputs["ngs_pass"], pid, week, ["completion_percentage_above_expectation", "avg_time_to_throw"], "attempts").items()})
        rows.append(row)
    return rows


# ----------------------------------------------------------------------------------------------- output

STAT = {"rec": "receptions", "rush_att": "rush attempts", "pass_cmp": "completions"}


def _f(x, d=1, sign=False):
    return "–" if x is None else f"{x:{'+' if sign else ''}.{d}f}"


def card(r: dict) -> str:
    head = (f"### {r['player']} ({r['team']}): {STAT.get(r['market'], r['market'])} {r['side']} {r['line']:g} at {r['odds']:+.0f}, "
            f"{r['result']}" + (f", actual {r['actual']:g}" if r["actual"] is not None else ""))
    out = [head, ""]
    if r.get("expected") is None:
        out += ["No baseline (no prior games found), so the split is not shown.", ""]
    else:
        b, a = r, r
        lines = []
        if r["market"] == "rec":
            lines += [f"- Team pass attempts: usual {r['base_A']:.1f}, this week {r['act_A']:.0f} ({_f(r['fav_volume'], 2, True)} toward the pick)",
                      f"- Targets per team attempt: usual {r['base_S']:.3f}, this week {r['act_S']:.3f} ({_f(r['fav_role'], 2, True)})",
                      f"- Catch rate: usual {r['base_R']:.2f}, this week {r['act_R']:.2f} ({_f(r['fav_efficiency'], 2, True)})"]
        elif r["market"] == "rush_att":
            lines += [f"- Team carries: usual {r['base_A']:.1f}, this week {r['act_A']:.0f} ({_f(r['fav_volume'], 2, True)} toward the pick)",
                      f"- Share of team carries: usual {r['base_S']:.3f}, this week {r['act_S']:.3f} ({_f(r['fav_role'], 2, True)})"]
        else:
            lines += [f"- His pass attempts: usual {r['base_A']:.1f}, this week {r['act_A']:.0f} ({_f(r['fav_volume'], 2, True)} toward the pick)",
                      f"- Completion rate: usual {r['base_R']:.2f}, this week {r['act_R']:.2f} ({_f(r['fav_efficiency'], 2, True)})"]
        gap = (r["actual"] - r["line"]) if r["actual"] is not None else None
        lines.append(f"- Line {r['line']:g}; model projected {r['proj']:.1f}; usage baseline {r['expected']:.1f} (from {r['n_base']} prior games); "
                     f"actual {_f(r['actual'], 0)}" + (f", {_f(gap, 1, True)} against the line" if gap is not None else ""))
        lines.append(f"- Largest part: **{r['driver']}** ({_f(r['driver_in_favor'], 2, True)} toward the pick, in {STAT.get(r['market'])})"
                     + (" · decided by half a count or less" if gap is not None and abs(gap) <= 0.5 else ""))
        out += lines
    ctx = []
    if r.get("ctx_margin") is not None:
        ctx.append(f"team {'won' if r['ctx_margin'] > 0 else 'lost'} by {abs(r['ctx_margin']):.0f}")
    if r.get("ctx_led_share") is not None:
        ctx.append(f"led on {r['ctx_led_share']:.0%} of its plays")
    if r.get("ctx_pass_rate") is not None:
        ctx.append(f"pass rate {r['ctx_pass_rate']:.0%} ({_f(r.get('ctx_proe'), 1, True)} pts vs expected)")
    if r.get("ctx_roof"):
        w = [f"{r['ctx_roof']}"] + ([f"{r['ctx_temp']:.0f}°F"] if r.get("ctx_temp") is not None else []) + ([f"wind {r['ctx_wind']:.0f} mph"] if r.get("ctx_wind") is not None else [])
        ctx.append(", ".join(w))
    out.append("- Game: " + "; ".join(ctx))
    n = []
    for k, lab in (("ngs_avg_separation", "separation"), ("ngs_avg_cushion", "cushion")):
        if r.get(k) is not None:
            n.append(f"{lab} {r[k]:.2f} yds (weeks 1-3: {_f(r.get(k + '_prior'), 2)})")
    if r.get("ngs_percent_attempts_gte_eight_defenders") is not None:
        n.append(f"carries against 8+ defenders {r['ngs_percent_attempts_gte_eight_defenders']:.0f}% (weeks 1-3: {_f(r.get('ngs_percent_attempts_gte_eight_defenders_prior'), 0)}%), "
                 f"rush yards over expected {_f(r.get('ngs_rush_yards_over_expected_per_att'), 2, True)} per carry")
    if r.get("ngs_completion_percentage_above_expectation") is not None:
        n.append(f"completion rate above expected {_f(r['ngs_completion_percentage_above_expectation'], 1, True)} (weeks 1-3: {_f(r.get('ngs_completion_percentage_above_expectation_prior'), 1, True)}), "
                 f"time to throw {_f(r.get('ngs_avg_time_to_throw'), 2)} s")
    if n:
        out.append("- Next Gen Stats: " + "; ".join(n))
    if r.get("opp_man") is not None:
        out.append(f"- Opponent defense, weeks 1-4 (includes this game): man {r['opp_man']:.0f}% of plays, Cover 3 {r['opp_cov3']:.0f}%, EPA per DB {_f(r['opp_epa_db'], 2, True)}")
    if r["inj_news"] or r["depth_note"]:
        out.append("- News at pick time: " + "; ".join(x for x in (r["inj_news"], r["depth_note"]) if x))
    out.append("")
    return "\n".join(out)


def render(rows: list[dict], week: int) -> str:
    w, l = sum(r["result"] == "W" for r in rows), sum(r["result"] == "L" for r in rows)
    units = sum(r["units"] for r in rows)
    lines = [f"# Week {week} recap: S1 tracker", "",
             f"Official picks: {len(rows)} ({w}-{l}), {units:+.2f} units. Written from the committed tracker files and nflverse. "
             "The split is descriptive: with this few picks it can suggest causes, not establish them, and nothing here changes rule S1.", "",
             "How to read it: each result is compared with what the player usually does (usage baseline). 'Toward the pick' means the part "
             "moved the stat in the direction the pick needed (smaller for an under, larger for an over), in units of the stat. "
             "Efficiency (catch or completion rate) is the part closest to luck.", "",
             "| Pick | Result | Actual vs line | Model | Usage baseline | Volume | Role | Efficiency | Largest part |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["result"] != "L", r["player"])):
        lines.append(f"| {r['player']} {STAT.get(r['market'], r['market'])} {r['side']} {r['line']:g} | {r['result']} | "
                     f"{_f(r['actual'], 0)} vs {r['line']:g} | {r['proj']:.1f} | {_f(r.get('expected'))} | "
                     f"{_f(r.get('fav_volume'), 2, True)} | {_f(r.get('fav_role'), 2, True)} | {_f(r.get('fav_efficiency'), 2, True)} | {r.get('driver', '–')} |")
    have = [r for r in rows if r.get("expected") is not None]
    if have:
        lines += ["", "## Across the week", "", "Average part per pick, relative to the line (toward-the-pick is +):", "",
                  "| Group | Picks | Volume | Role | Efficiency | Model minus baseline |", "|---|---|---|---|---|---|"]
        for lab, grp in (("Won", [r for r in have if r["result"] == "W"]), ("Lost", [r for r in have if r["result"] == "L"]), ("All", have)):
            if grp:
                m = lambda k: sum(r.get(k, 0.0) / max(r["line"], 1.0) for r in grp) / len(grp)  # noqa: E731
                gap = sum(((r["proj"] - r["expected"]) * (-1 if r["side"] == "under" else 1)) / max(r["line"], 1.0) for r in grp) / len(grp)
                lines.append(f"| {lab} | {len(grp)} | {m('fav_volume'):+.2f} | {m('fav_role'):+.2f} | {m('fav_efficiency'):+.2f} | {gap:+.2f} |")
        cnt = {}
        for r in have:
            cnt[r["driver"]] = cnt.get(r["driver"], 0) + 1
        lines += ["", "Largest part by pick: " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])) + ".",
                  "'Model minus baseline' is how far the model's projection sat from the usage baseline, toward the pick: a positive number "
                  "means the model was leaning into the pick more than the player's own recent usage did."]
    lines += ["", "## Picks", ""]
    lines += [card(r) for r in sorted(rows, key=lambda r: (r["result"] != "L", r["player"]))]
    lines += ["## Limits", "",
              "- Baseline is the player's own games this season before the week (in games he played; padded with 2025 games when fewer than 2). "
              "Catch and completion rates are shrunk toward the league rate. A different baseline would move the split.",
              "- Coverage numbers come from a hand-transcribed weeks 1-4 table (`data/external/`), include this game, and omit some coverage types.",
              "- Not measured: man or zone coverage faced by this player, routes run, personnel, and anything in the game's film.", ""]
    return "\n".join(lines)


def write(week: int, season: int = 2026, record_path: Path | None = None) -> tuple[Path, Path]:
    rec = pl.read_csv(record_path or Lv.LIVE / f"s1_record_{season}.csv", infer_schema_length=0).filter(
        pl.col("week") == str(week), pl.col("result").is_in(["W", "L", "P"]))
    rows = build_rows(rec, load_week_inputs(season, week), season, week)
    md = config.ROOT / "docs" / "recaps" / f"week_{week}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(render(rows, week))
    ledger = Lv.LIVE / f"recap_ledger_{season}.csv"
    new = pl.DataFrame(rows, infer_schema_length=None).with_columns(pl.lit(week).alias("week"))
    if ledger.exists():
        old = pl.read_csv(ledger, infer_schema_length=0).filter(pl.col("week") != str(week))
        new = pl.concat([old, new.select([pl.col(c).cast(pl.Utf8) for c in new.columns])], how="diagonal_relaxed")
    new.write_csv(ledger)
    return md, ledger
