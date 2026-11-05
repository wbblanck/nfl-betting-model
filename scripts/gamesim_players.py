"""Players on every play of the game simulator (docs/gamesim_players_preregistration.md).

Usage: python scripts/gamesim_players.py <cache dir> check|grid|test
  check: known-answer checks (box scores add up, team totals unchanged, planted double share, same seed)
  grid:  choose the Dirichlet concentration c on 2024 (2,000 runs per game)
  test:  2025 at 10,000 runs per game vs the negative binomial version; writes docs/gamesim_players.md"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import ats_clv as C  # noqa: E402
import gamesim_props_dist as D  # noqa: E402

from nflbet import config  # noqa: E402
from nflbet.gamesim import engine as E, personnel as P, players as PL, run as R, teams as TM  # noqa: E402
from nflbet.gamesim.teams import FRANCHISE  # noqa: E402
from nflbet.props import confirm as PCF, core as PC  # noqa: E402
from nflbet.props.sim import Simulator, inputs  # noqa: E402

GRID = [5, 10, 20, 40, 80]
MARKETS = D.MARKETS
NB_SIZE = None   # read from data/backtests/gamesim_props_dist.json
OUT = []
BT = config.ROOT / "data" / "backtests"


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s, flush=True)


def setup(d, seasons):
    k = json.loads((BT / "gamesim_constants.json").read_text())
    tb = E.Tables(json.loads((BT / "gamesim_league.json").read_text()))
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in range(2015, max(seasons) + 1)], how="diagonal_relaxed")
    kicks, xps = R.kick_pools(pbp)
    T = json.loads((BT / "gamesim_league.json").read_text())
    fac = TM.factors(TM.game_stats(pbp, T), k["league"], k["h"], k["k"], k["r"])
    sched = pl.read_parquet(f"{d}/schedules.parquet")
    qg = P.qb_games(pbp)
    qbd = P.qb_delta(sched, qg, P.QBRater(qg, k["personnel"]["replacement"]))
    inj = P.injury_loss(pl.read_parquet(f"{d}/injuries.parquet"), pl.read_parquet(f"{d}/snaps.parquet"),
                        pl.read_parquet(f"{d}/players.parquet"), sched)
    games = sched.filter(pl.col("game_type") == "REG", pl.col("season").is_in(seasons)).select(
        "season", "week", "game_id", "home_team", "away_team", (pl.col("location") == "Neutral").alias("neutral"))
    inp = P.inputs(qbd, inj, sched).filter(pl.col("game_id").is_in(games["game_id"].implode()))
    shift = P.shifts(inp, k["personnel"]["coefs"])
    f_scr = PL.scramble_share(pbp.filter(pl.col("season").is_between(2016, 2020)))
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    rows = pl.concat([inputs(sim.pg, sim.sched, s, sim.pos_mean, sim.dfac) for s in seasons], how="diagonal_relaxed")
    ros = PL.rosters(rows, f_scr)
    return dict(k=k, tb=tb, kicks=kicks, xps=xps, fac=fac, games=games, shift=shift, f_scr=f_scr, ros=ros, sim=sim,
                rows=rows, sched=sched)


def run(S, season, sims, c, seed=404, keep_games=None):
    g = S["games"].filter(pl.col("season") == season)
    return PL.simulate(g, S["fac"], S["tb"], S["kicks"], S["xps"], S["k"]["hfa"], S["ros"], sims, c, seed=seed,
                       shift=S["shift"], keep_games=keep_games)


# ------------------------------------------------------------------------------------------- checks

def check(d):
    S = setup(d, [2024])
    say(f"Scramble share of rush attempts, 2016-2020: {S['f_scr']:.4f}")
    wk = S["games"].filter(pl.col("season") == 2024, pl.col("week") == 5)
    keep = set(wk["game_id"].to_list())
    sims = 2000
    g, res, pairs, H, A = run(S, 2024, sims, 20.0, keep_games=keep)
    say(f"Checks on 2024 week 5: {g.height} games x {sims} runs")
    # 1. box scores add up
    bad = 0
    for rg in res:
        ryd, rec, tgt = rg["ryd"].astype(int).sum(2), rg["rec"].astype(int).sum(2), rg["tgt"].astype(int).sum(2)
        bad += int((ryd != rg["pyd"]).sum() + (rec != rg["cmp"]).sum())
    say(f"K1 box scores add up (QB yards = receivers' yards, completions = catches): mismatches {bad} -> {'PASS' if bad == 0 else 'FAIL'}")
    # 2. team totals unchanged vs the engine without players (same games, other random numbers)
    gg, pools, pidx, xp = R.prep(g.select("season", "week", "game_id", "home_team", "away_team", "neutral"),
                                 S["fac"], S["kicks"], S["xps"])
    off, dfn = R.chunk_inputs(gg, sims, S["shift"])
    cnt = {}
    h0, a0 = R._sim_hfa(S["tb"], off, dfn, (pools, np.repeat(pidx, sims)), np.repeat(xp, sims),
                        np.repeat(gg["season"].to_numpy(), sims), np.where(np.repeat(gg["neutral"].to_numpy(), sims), 0.0, S["k"]["hfa"]),
                        77, cnt)
    att_p = np.mean([rg["tgt"].sum(2).mean() for rg in res])
    car_p = np.mean([rg["car"].sum(2).mean() for rg in res])
    pyd_p = np.mean([rg["pyd"].mean() for rg in res])
    pts_p, pts_0 = (H.mean() + A.mean()) / 2, (h0.mean() + a0.mean()) / 2
    say(f"K2 team totals per team-game, with players vs without: pass attempts {att_p:.2f} vs {cnt['att'].mean():.2f}; "
        f"carries incl. kneels {car_p:.2f} vs {cnt['car'].mean():.2f} (without kneels); points {pts_p:.2f} vs {pts_0:.2f}")
    # 3. planted double share: two receivers on one team set to shares 0.2 and 0.1, c = infinity and c = 20
    key = next(iter(S["ros"]))
    for (s, w, h, a), pr in zip(g.select("season", "week", "home_team", "away_team").iter_rows(), pairs):
        key = (s, w, h)
        break
    base = S["ros"][key]
    pl_ = dict(base)
    ts = np.full(len(base["ts"]), 0.7 / max(len(base["ts"]) - 2, 1))
    ts[0], ts[1] = 0.2, 0.1
    pl_["ts"] = ts / ts.sum()
    pl_["cshift"] = np.zeros(len(ts))
    pl_["yscale"] = np.ones(len(ts))
    ros2 = dict(S["ros"])
    ros2[key] = pl_
    for c in (np.inf, 20.0):
        S2 = dict(S, ros=ros2)
        g2, r2, p2, _, _ = run(S2, 2024, sims, c, keep_games={g["game_id"][0]})
        t = r2[0]["tgt"][:, 0]
        ratio = t[:, 0].mean() / t[:, 1].mean()
        say(f"K3 planted shares 0.2 vs 0.1 (c={c}): mean targets {t[:, 0].mean():.2f} vs {t[:, 1].mean():.2f}, ratio {ratio:.2f} "
            f"-> {'PASS' if 1.85 < ratio < 2.15 else 'FAIL'}")
    # 4. same seed reproduces
    g3, r3, *_ = run(S, 2024, 200, 20.0, keep_games={g["game_id"][0]})
    g4, r4, *_ = run(S, 2024, 200, 20.0, keep_games={g["game_id"][0]})
    same = all(np.array_equal(r3[0][k], r4[0][k]) for k in PL.STATS)
    say(f"K4 same seed reproduces: {'PASS' if same else 'FAIL'}")
    # share of rosters with normalized target / carry share sums (disclosure)
    sums = S["rows"].group_by("season", "week", "team").agg(pl.col("tgt_share").sum().alias("t"), pl.col("car_share").sum().alias("c"))
    say(f"Roster share sums before normalizing (2024): targets median {sums['t'].median():.3f} (min {sums['t'].min():.3f}, "
        f"max {sums['t'].max():.3f}); carries median {sums['c'].median():.3f}")
    (config.ROOT / "docs" / "gamesim_players_checks.txt").write_text("\n".join(OUT) + "\n")


# ------------------------------------------------------------------------------------------- evaluation

def dk_props(S, season):
    g = PC.graded(PC.join(PC.load_lines(season), PC.load_stats(season), PC.load_snaps(season)))
    dk = PCF.screened(g).filter(pl.col("book") == "DK NJ", pl.col("result") != "push", pl.col("market").is_in(MARKETS)) \
        .unique(subset=PCF.KEY)
    rows = S["rows"].filter(pl.col("season") == season)
    team = {(r["player_id"], r["week"]): FRANCHISE.get(r["team"], r["team"]) for r in rows.select("player_id", "week", "team").iter_rows(named=True)}
    return dk, team


def player_probs(S, season, dk, team, g, res, pairs):
    idx = {}
    for i, (w, h, a) in enumerate(zip(g["week"], g["home_team"], g["away_team"])):
        idx[(w, h)], idx[(w, a)] = (i, 0), (i, 1)
    cache, p = {}, []
    for r in dk.iter_rows(named=True):
        key = (r["player_id"], r["week"])
        t = team.get(key)
        gi = idx.get((r["week"], t)) if t else None
        if gi is None:
            p.append(np.nan)
            continue
        if key not in cache:
            cache[key] = PL.player_samples(res[gi[0]], pairs[gi[0]], gi[1], r["player_id"])
        smp = cache[key].get(r["market"])
        v = D.GP.p_over(smp, r["line"]) if smp is not None else None
        p.append(np.nan if v is None else v)
    return np.array(p, float)


def grid(d):
    S = setup(d, [2024])
    dk, team = dk_props(S, 2024)
    y = (dk["result"] == "over").cast(pl.Float64).to_numpy()
    lls = {}
    ps = {}
    for c in GRID:
        g, res, pairs, H, A = run(S, 2024, 2000, float(c), seed=404)
        ps[c] = player_probs(S, 2024, dk, team, g, res, pairs)
        say(f"c={c}: simulated {g.height} games")
    ok = np.all([~np.isnan(ps[c]) for c in GRID], axis=0)
    for c in GRID:
        lls[c] = float(D.ll_each(ps[c][ok], y[ok]).mean())
    best = min(GRID, key=lambda c: lls[c])
    say("## Concentration c chosen on 2024 (2,000 runs per game), log loss on " + f"{ok.sum()} DraftKings props")
    say(", ".join(f"c={c}: {lls[c]:.4f}" for c in GRID) + f" -> **c = {best}**")
    (BT / "gamesim_players_c.json").write_text(json.dumps({"ll": lls, "chosen": best, "n": int(ok.sum())}, indent=1))
    (config.ROOT / "docs" / "gamesim_players_grid.txt").write_text("\n".join(OUT) + "\n")


def test(d):
    c = json.loads((BT / "gamesim_players_c.json").read_text())["chosen"]
    nb = json.loads((BT / "gamesim_props_dist.json").read_text())["chosen"]
    S = setup(d, [2025])
    dk, team = dk_props(S, 2025)
    g, res, pairs, H, A = run(S, 2025, 10000, float(c), seed=505)
    with open(f"{d}/gamesim_players_2025.pkl", "wb") as f:
        pickle.dump((g, res, pairs), f, protocol=4)
    pv = player_probs(S, 2025, dk, team, g, res, pairs)
    # negative binomial version on the same props (docs/gamesim_props_dist.md), recomputed
    out, att, car = D.volumes(d)
    idx = {}
    for i, (s, w, h, a) in enumerate(zip(out["season"], out["week"], out["home_team"], out["away_team"])):
        idx[(s, w, h)], idx[(s, w, a)] = (i, 0), (i, 1)
    sim = S["sim"]
    keep = set(zip(dk["player_id"].to_list(), dk["week"].to_list()))
    rows_in = {(r["player_id"], r["week"]): r for r in inputs(sim.pg, sim.sched, 2025, sim.pos_mean, sim.dfac).iter_rows(named=True)
               if (r["player_id"], r["week"]) in keep}
    ok = np.array([(k in rows_in) and ((2025, k[1], FRANCHISE.get(rows_in[k]["team"], rows_in[k]["team"])) in idx)
                   for k in zip(dk["player_id"].to_list(), dk["week"].to_list())])
    pnb = np.full(dk.height, np.nan)
    pnb[ok] = D.probs(2025, dk.filter(pl.Series(ok)), rows_in, idx, att, car, sim.pools, "nb", nb)
    good = ~np.isnan(pv) & ~np.isnan(pnb)
    y = (dk["result"] == "over").cast(pl.Float64).to_numpy()[good]
    cl = dk["week"].to_numpy()[good]
    mk = dk["market"].to_numpy()[good]
    pdk = dk["p_over"].to_numpy()[good]
    oo, uo = dk["over_odds"].to_numpy()[good].astype(float), dk["under_odds"].to_numpy()[good].astype(float)
    pv, pnb = pv[good], pnb[good]
    Lp, Ln, Ld = D.ll_each(pv, y), D.ll_each(pnb, y), D.ll_each(pdk, y)
    diff = Lp - Ln
    ci = C.boot(lambda ix: diff[ix].mean(), cl, 0.05 / 2)
    better = bool(ci[1] < 0)
    say(f"## 2025 test: {len(y)} DraftKings props ({dk.height - len(y)} dropped: player not on a simulated roster or no "
        f"line for him in one version), c = {c}, 10,000 runs per game")
    say(f"Log loss: players-on-every-play {Lp.mean():.4f} | negative binomial {Ln.mean():.4f} | DK de-vigged {Ld.mean():.4f} | coin 0.6931")
    say(f"- **Players minus negative binomial:** {diff.mean():+.4f}, interval {ci[0]:+.4f} to {ci[1]:+.4f}: "
        f"**{'BETTER' if better else 'NOT BETTER'}**")
    say("\nBy market (log loss) | n | players | neg. binomial | DK")
    for m_ in MARKETS:
        m = mk == m_
        if m.any():
            say(f"{m_} | {m.sum()} | {Lp[m].mean():.4f} | {Ln[m].mean():.4f} | {Ld[m].mean():.4f}")
    say("\nCalibration: favored side's probability band | version | n | said | hit")
    cal = {}
    for name, p in (("players", pv), ("NB", pnb)):
        sp = np.maximum(p, 1 - p)
        hit = np.where(p >= 0.5, y == 1, y == 0)
        cal[name] = []
        for lo in (0.5, 0.6, 0.7, 0.8, 0.9):
            m = (sp >= lo) & ((sp < lo + 0.1) if lo < 0.9 else (sp <= 1))
            if m.any():
                cal[name].append([lo, int(m.sum()), float(sp[m].mean()), float(hit[m].mean())])
                say(f"{lo:.0%}-{min(lo + .1, 1):.0%} | {name} | {m.sum()} | {sp[m].mean():.1%} | {hit[m].mean():.1%}")
        m75 = sp >= 0.75
        odds = np.where(p >= 0.5, oo, uo)
        pnl = PC.profit(odds[m75], hit[m75].astype(float)) if m75.any() else np.array([])
        say(f"75%+ | {name} | {m75.sum()} | hit {hit[m75].mean() if m75.any() else float('nan'):.1%} | "
            f"ROI {pnl.mean() if len(pnl) else float('nan'):+.1%}")
        cal[name].append({"ge75_n": int(m75.sum()), "hit": float(hit[m75].mean()) if m75.any() else None,
                          "roi": float(pnl.mean()) if len(pnl) else None})
    res_j = {"c": c, "nb_size": nb, "n": int(len(y)), "ll": {"players": float(Lp.mean()), "nb": float(Ln.mean()), "dk": float(Ld.mean())},
             "diff": {"mean": float(diff.mean()), "ci": list(map(float, ci)), "better": better}, "calibration": cal}
    (BT / "gamesim_players.json").write_text(json.dumps(res_j, indent=1))
    grid_txt = (config.ROOT / "docs" / "gamesim_players_grid.txt").read_text()
    checks = (config.ROOT / "docs" / "gamesim_players_checks.txt").read_text()
    head = ["# Game simulator with players on every play", "",
            "Pre-registration: docs/gamesim_players_preregistration.md. Every throw goes to a receiver and every designed run "
            "to a rusher inside the game engine, so a simulated QB's line is the sum of his receivers' lines.", "",
            "## Known-answer checks (2024 week 5)", "", checks, grid_txt, ""]
    (config.ROOT / "docs" / "gamesim_players.md").write_text("\n".join(head + OUT) + "\n")


def box(d, gid="2025_17_CHI_SF", run_no=1):
    """One run of one 2025 game from the test output, printed as a box score (illustration, not a test)."""
    with open(f"{d}/gamesim_players_2025.pkl", "rb") as f:
        g, res, pairs = pickle.load(f)
    i = g["game_id"].to_list().index(gid)
    rg, pr = res[i], pairs[i]
    sched = pl.read_parquet(f"{d}/schedules.parquet").filter(pl.col("game_id") == gid).row(0, named=True)
    names = dict(pl.read_parquet(f"{d}/players.parquet").select("gsis_id", "display_name").iter_rows())
    j = run_no - 1
    q = rg["qscore"][j].astype(int)
    qs = [q[0], q[1] - q[0], q[2] - q[1], q[3] - q[2]]
    sims = rg["tgt"].shape[0]
    L = [f"# Simulated box score with players on every play: {sched['away_team']} at {sched['home_team']}, 2025 week "
         f"{sched['week']} (run {run_no} of {sims:,})", "",
         "Every throw in this run went to one receiver and every run to one rusher, so the QB line is the sum of his "
         "receivers' lines.", "", "| Team | Q1 | Q2 | Q3 | Q4 | Final |", "|---|---|---|---|---|---|"]
    fin = {}
    for side, t in ((1, sched["away_team"]), (0, sched["home_team"])):
        tot = sum(x[side] for x in qs)
        fin[side] = tot
        L.append(f"| {t} | " + " | ".join(str(x[side]) for x in qs) + f" | **{tot}** |")
    L.append("")
    for side, t in ((1, sched["away_team"]), (0, sched["home_team"])):
        r = pr[side]
        tg, rc, ry = rg["tgt"][:, side], rg["rec"][:, side], rg["ryd"][:, side]
        ca, uy = rg["car"][:, side], rg["uyd"][:, side]
        L += [f"## {t}", "", "| Passing | Comp/Att | Yards | 10k-run avg yards |", "|---|---|---|---|",
              f"| {names.get(r['qb'], r['qb'])} | {rg['cmp'][j, side]}/{tg[j].sum()} | {rg['pyd'][j, side]} | "
              f"{rg['pyd'][:, side].mean():.1f} |", "",
              "| Rushing | Carries | Yards | 10k-run avg carries | 10k-run avg yards |", "|---|---|---|---|---|"]
        order = sorted(range(len(r["rus_ids"])), key=lambda k: -ca[j, k])
        L += [f"| {names.get(r['rus_ids'][k], r['rus_ids'][k])} | {ca[j, k]} | {uy[j, k]} | {ca[:, k].mean():.1f} | {uy[:, k].mean():.1f} |"
              for k in order if ca[j, k] > 0 or ca[:, k].mean() >= 1]
        L += ["", "| Receiving | Targets | Catches | Yards | 10k-run avg targets | 10k-run avg yards |", "|---|---|---|---|---|---|"]
        order = sorted(range(len(r["rec_ids"])), key=lambda k: -ry[j, k])
        L += [f"| {names.get(r['rec_ids'][k], r['rec_ids'][k])} | {tg[j, k]} | {rc[j, k]} | {ry[j, k]} | {tg[:, k].mean():.1f} | {ry[:, k].mean():.1f} |"
              for k in order if tg[j, k] > 0 or tg[:, k].mean() >= 1]
        L += ["", f"Check: receivers' yards {ry[j].sum()} = passing yards {rg['pyd'][j, side]}; catches {rc[j].sum()} = "
              f"completions {rg['cmp'][j, side]}.", ""]
    L += [f"**Real result:** {sched['away_team']} {sched['away_score']}, {sched['home_team']} {sched['home_score']}.", ""]
    txt = "\n".join(L) + "\n"
    print(txt)
    return txt


if __name__ == "__main__":
    {"check": check, "grid": grid, "test": test, "box": box}[sys.argv[2]](sys.argv[1], *sys.argv[3:4])
