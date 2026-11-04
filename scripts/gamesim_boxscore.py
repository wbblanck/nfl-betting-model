"""One simulated game as a box score (illustration, not a test). Simulates the game 10,000 times with the frozen G3
simulator, prints run 1 as if it were the real game (quarter scores, team volume, player lines from the prop
player layer), the 10,000-run averages, and the real result.

Usage: python scripts/gamesim_boxscore.py <cache dir> <game_id> [run number]"""
from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.gamesim import engine as E, personnel as P, props as GP, run as R, teams as TM
from nflbet.gamesim.teams import FRANCHISE
from nflbet.props.sim import Simulator, inputs

SIMS = 10000


def main(d, gid, run_no=1):
    season = int(gid[:4])
    k = json.loads((config.ROOT / "data" / "backtests" / "gamesim_constants.json").read_text())
    T = json.loads((config.ROOT / "data" / "backtests" / "gamesim_league.json").read_text())
    tb = E.Tables(T)
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in range(2015, season + 1)], how="diagonal_relaxed")
    kicks, xps = R.kick_pools(pbp)
    fac = TM.factors(TM.game_stats(pbp, T), k["league"], k["h"], k["k"], k["r"])
    sched = pl.read_parquet(f"{d}/schedules.parquet")
    g = sched.filter(pl.col("game_id") == gid).row(0, named=True)
    qg = P.qb_games(pbp)
    qbd = P.qb_delta(sched.filter(pl.col("season") <= season), qg, P.QBRater(qg, k["personnel"]["replacement"]))
    inj = P.injury_loss(pl.read_parquet(f"{d}/injuries.parquet"), pl.read_parquet(f"{d}/snaps.parquet"),
                        pl.read_parquet(f"{d}/players.parquet"), sched.filter(pl.col("season") <= season))
    inp = P.inputs(qbd, inj, sched.filter(pl.col("season") <= season)).filter(pl.col("game_id") == gid)
    sh = P.shifts(inp, k["personnel"]["coefs"])
    home, away = FRANCHISE.get(g["home_team"], g["home_team"]), FRANCHISE.get(g["away_team"], g["away_team"])
    off = {f: np.zeros((SIMS, 2)) for f in E.FACTORS}
    dfn = {f: np.zeros((SIMS, 2)) for f in E.FACTORS}
    for side, t in ((0, home), (1, away)):
        row = fac.filter(pl.col("game_id") == gid, pl.col("team") == t).row(0, named=True)
        for f in E.FACTORS:
            off[f][:, side] = row["o" + f] + sh.get((gid, t), {}).get(f, 0.0)
            dfn[f][:, side] = row["d" + f]
    games = pl.DataFrame({"season": [season], "week": [g["week"]]})
    pools, pidx, xp = R.pools_for(games, kicks, xps)
    hfa = 0.0 if g["location"] == "Neutral" else k["hfa"]
    cnt = {}
    h, a = E.simulate(tb, off, dfn, (pools, np.zeros(SIMS, int)), np.full(SIMS, xp[0]), np.full(SIMS, season), hfa,
                      seed=2025, counts=cnt)
    i = run_no - 1
    q = cnt["qscore"][i]
    qs = [q[0], q[1] - q[0], q[2] - q[1], q[3] - q[2]]
    ot = (h[i], a[i]) != (q[3][0], q[3][1])
    L = [f"# Simulated box score: {g['away_team']} at {g['home_team']}, {season} week {g['week']} (run {run_no} of {SIMS:,})", "",
         "| Team | Q1 | Q2 | Q3 | Q4 |" + (" OT |" if ot else "") + " Final |", "|---|---|---|---|---|" + ("---|" if ot else "") + "---|"]
    for side, t in ((1, g["away_team"]), (0, g["home_team"])):
        fin = a[i] if side == 1 else h[i]
        L.append(f"| {t} | " + " | ".join(str(int(x[side])) for x in qs) + (f" | {int(fin - q[3][side])}" if ot else "") + f" | **{int(fin)}** |")
    L += ["", f"Team volume in this run: {g['away_team']} {int(cnt['att'][i, 1])} pass attempts, {int(cnt['car'][i, 1])} carries; "
          f"{g['home_team']} {int(cnt['att'][i, 0])} pass attempts, {int(cnt['car'][i, 0])} carries.", ""]
    # player lines for this run
    sim = Simulator(fit_season=2024, seasons=[season - 2, season - 1, season])
    rows = inputs(sim.pg, sim.sched, season, sim.pos_mean, sim.dfac).filter(pl.col("week") == g["week"],
                                                                          pl.col("team").is_in([g["home_team"], g["away_team"]]))
    names = sim.pg.select("player_id").unique()
    try:
        import nflreadpy as nfl
        names = nfl.load_players().select(pl.col("gsis_id").alias("player_id"), pl.col("display_name").alias("name"))
    except Exception:
        names = names.with_columns(pl.col("player_id").alias("name"))
    rows = rows.join(names, on="player_id", how="left")
    rng = np.random.default_rng(99)
    real = pl.read_parquet(f"{d}/pbp_{season}.parquet").filter(pl.col("game_id") == gid)
    for side, t in ((1, g["away_team"]), (0, g["home_team"])):
        tr = rows.filter(pl.col("team") == t).to_dicts()
        a1, c1 = cnt["att"][[i], side], cnt["car"][[i], side]
        lines = []
        for r in tr:
            s1 = GP.simulate_row_vol(r, a1.repeat(1), c1.repeat(1), sim.pools, rng)
            avg = GP.simulate_row_vol(r, cnt["att"][:, side], cnt["car"][:, side], sim.pools, rng)
            lines.append((r, s1, avg))
        qb = [x for x in lines if x[0]["pos"] == "QB"]
        qb = max(qb, key=lambda x: x[0]["att_share"] or 0) if qb else None
        L += [f"## {t}", ""]
        if qb:
            r, s1, avg = qb
            L += ["| Passing | Comp/Att | Yards |", "|---|---|---|",
                  f"| {r['name']} | {int(s1['pass_cmp'][0])}/{int(s1['pass_att'][0])} | {int(s1['pass_yds'][0])} |", ""]
        rush = sorted([x for x in lines if (x[0]["car_share"] or 0) > 0.03], key=lambda x: -x[1]["rush_att"][0])[:4]
        L += ["| Rushing | Carries | Yards | 10k-run avg yards |", "|---|---|---|---|"]
        L += [f"| {r['name']} | {int(s1['rush_att'][0])} | {int(s1['rush_yds'][0])} | {avg['rush_yds'].mean():.1f} |" for r, s1, avg in rush]
        rec = sorted([x for x in lines if (x[0]["tgt_share"] or 0) > 0.03], key=lambda x: -x[1]["rec_yds"][0])[:6]
        L += ["", "| Receiving | Targets | Catches | Yards | 10k-run avg yards |", "|---|---|---|---|---|"]
        L += [f"| {r['name']} | {int(s1['targets'][0])} | {int(s1['rec'][0])} | {int(s1['rec_yds'][0])} | {avg['rec_yds'].mean():.1f} |"
              for r, s1, avg in rec]
        L.append("")
    m = h - a
    L += ["## Across all 10,000 runs", "",
          f"- Average score: {g['away_team']} {a.mean():.1f}, {g['home_team']} {h.mean():.1f} (fair line: {g['home_team']} by {m.mean():+.1f}).",
          f"- {g['home_team']} won {np.mean(m > 0):.1%} of runs; ties {np.mean(m == 0):.1%}. Average total {(h + a).mean():.1f}.",
          f"- Market close: {g['home_team']} {('by ' + str(g['spread_line'])) if g['spread_line'] >= 0 else ('+' + str(-g['spread_line']))}, total {g['total_line']}.",
          f"- **Real result:** {g['away_team']} {g['away_score']}, {g['home_team']} {g['home_score']}."]
    rp = real.filter(pl.col("receiver_player_name").is_not_null()).group_by("posteam", "receiver_player_name").agg(
        pl.col("receiving_yards").sum()).sort("receiving_yards", descending=True).head(4)
    L.append("- Real top receivers: " + ", ".join(f"{n} ({t}) {int(y)} yds" for t, n, y in rp.iter_rows()) + ".")
    txt = "\n".join(L) + "\n"
    print(txt)
    return txt


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
