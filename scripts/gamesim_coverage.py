"""Coverage layer (man vs zone) for the game simulator (docs/gamesim_coverage_preregistration.md).

Usage: python scripts/gamesim_coverage.py <cache dir> check|explore|confirm"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import ats_clv as C  # noqa: E402
_argv, sys.argv = sys.argv, sys.argv[:1]      # gamesim_confirm reads a run count from argv at import
import gamesim_confirm as GC  # noqa: E402
sys.argv = _argv
import gamesim_players as GPL  # noqa: E402

from nflbet import config  # noqa: E402
from nflbet.ats import rating as A  # noqa: E402
from nflbet.gamesim import coverage as CV, players as PL, run as R  # noqa: E402

K_COV = [100, 200, 400, 800]
K_REC = [10, 20, 40]
BT = config.ROOT / "data" / "backtests"
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s, flush=True)


def load(d):
    part = pl.read_parquet(f"{d}/participation_2022_2025.parquet")
    pbp = pl.concat([pl.read_parquet(f"{d}/pbp_{s}.parquet") for s in range(2022, 2026)], how="diagonal_relaxed")
    lab = CV.labeled(pbp, part)
    allb = pbp.filter(pl.col("season_type") == "REG")
    return lab, allb


# ------------------------------------------------------------------------------------------- checks

def synth(n_games, man_rate, comp_man, comp_zone, shuffle=False, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_games):
        for side, (off, dfn) in enumerate((("O", "D"), ("D", "O"))):
            n = 40
            man = rng.random(n) < (man_rate if dfn == "D" else 0.3)
            cp = np.where(man, rng.random(n) < comp_man, rng.random(n) < comp_zone) if off == "O" else rng.random(n) < 0.65
            if shuffle:
                man = rng.permutation(man)
            r = {"season": 2022, "week": g + 1, "game_id": f"g{g}", "posteam": off, "defteam": dfn}
            for c, v in (("cp", cp), ("natt", np.ones(n, bool)), ("it", np.zeros(n, bool)), ("att", np.ones(n, bool)),
                         ("sk", np.zeros(n, bool)), ("db", np.ones(n, bool)), ("cy", cp * 10.0)):
                r[c + "_m"], r[c + "_z"] = float(v[man].sum()), float(v[~man].sum())
            rows.append(r)
    return pl.DataFrame(rows)


def check(d):
    lab, allb = load(d)
    for s in range(2022, 2026):
        db = allb.filter(pl.col("season") == s, pl.col("qb_dropback").fill_null(0) == 1).height
        say(f"{s}: labeled dropbacks {lab.filter(pl.col('season') == s).height} of {db} dropback rows in play-by-play")
    tg = synth(30, 0.8, 1.0, 0.0)
    pg = CV.pregame(tg, [200])
    last = pg["split"][200][("g29", "O")]
    say(f"K1 planted offense (100% vs man, 0% vs zone): comp split man {last['comp_man']:+.2f}, zone {last['comp_zone']:+.2f} "
        f"-> {'PASS' if last['comp_man'] > 1 and last['comp_zone'] < -1 else 'FAIL'}")
    sh = CV.pregame(synth(30, 0.8, 1.0, 0.0, shuffle=True), [200])["split"][200][("g29", "O")]
    say(f"K1b same with labels shuffled: man {sh['comp_man']:+.2f}, zone {sh['comp_zone']:+.2f} -> "
        f"{'PASS' if abs(sh['comp_man']) < 0.3 and abs(sh['comp_zone']) < 0.3 else 'FAIL'}")
    # defense man rate: analytic value with the prior (8 games at the league rate to date)
    m = pg["man"][("g29", "D")]
    w = CV._w(np.zeros(29), np.arange(29)[::-1].astype(float))
    rows = tg.filter(pl.col("defteam") == "D").sort("week").to_dicts()[:29]
    num = sum(wi * r["db_m"] for wi, r in zip(w, rows))
    den = sum(wi * (r["db_m"] + r["db_z"]) for wi, r in zip(w, rows))
    allr = tg.filter(pl.col("week") < 30)
    lm = allr["db_m"].sum() / (allr["db_m"].sum() + allr["db_z"].sum())
    kn = CV.KG * np.mean((tg["db_m"] + tg["db_z"]).to_numpy())
    expect = (num + kn * lm) / (den + kn)
    say(f"K2 planted 80% man defense after 29 games: m {m:.3f}, by hand {expect:.3f}, raw weighted rate {num / den:.3f} -> "
        f"{'PASS' if abs(m - expect) < 1e-9 and 0.75 < num / den < 0.85 else 'FAIL'}")
    # engine: m = 1 and a +1.0 man completion split raises completion; zeros leave it unchanged
    S = GPL.setup(d, [2024])
    keep = set(S["games"].filter(pl.col("season") == 2024, pl.col("week") == 5)["game_id"].to_list())

    def comp_rate(cover):
        g, res, pairs, H, A_ = PL.simulate(S["games"].filter(pl.col("season") == 2024), S["fac"], S["tb"], S["kicks"], S["xps"],
                                           S["k"]["hfa"], S["ros"], 2000, 10.0, seed=9, shift=S["shift"], keep_games=keep,
                                           cover=cover)
        cmp = sum(r["cmp"].sum() for r in res)
        att = sum(r["tgt"].sum() for r in res)
        return cmp / att, res, g

    base, _, g = comp_rate(None)
    gids = g["game_id"].to_list()
    teams = list(zip(g["home_team"], g["away_team"]))

    def fake(mval, cm, cz):
        man = {(gid, t): mval for gid, (h, a) in zip(gids, teams) for t in (h, a)}
        z = {f"{f}_{c}": 0.0 for f in CV.SPLITS for c in ("man", "zone")}
        sp = {(gid, t): dict(z, comp_man=cm, comp_zone=cz) for gid, (h, a) in zip(gids, teams) for t in (h, a)}
        return ({"man": man, "split": {0: sp}}, 0)

    up, _, _ = comp_rate(fake(1.0, 1.0, 0.0))
    zero, _, _ = comp_rate(fake(0.5, 0.0, 0.0))
    say(f"K3 engine completion rate: no coverage {base:.4f}; all-zero splits {zero:.4f}; m = 1 with +1.0 man split {up:.4f} -> "
        f"{'PASS' if abs(zero - base) < 0.005 and up > base + 0.05 else 'FAIL'}")
    # receiver draw: slot 0 planted at double share against man; m = 1 vs m = 0
    ros2 = {}
    for kk, r in S["ros"].items():
        tm = np.ones((len(r["ts"]), 2))
        tm[0, 0] = 2.0
        ros2[kk] = dict(r, tmul=tm, ymul=np.ones((len(r["ts"]), 2)))
    S2 = dict(S, ros=ros2)
    tg_ = {}
    for mval in (1.0, 0.0):
        g, res, pairs, _, _ = PL.simulate(S2["games"].filter(pl.col("season") == 2024), S2["fac"], S2["tb"], S2["kicks"],
                                          S2["xps"], S2["k"]["hfa"], S2["ros"], 2000, np.inf, seed=9, shift=S2["shift"],
                                          keep_games=keep, cover=fake(mval, 0.0, 0.0))
        tg_[mval] = (np.mean([r["tgt"][:, 0, 0].mean() for r in res]), np.mean([p[0]["ts"][0] for p in pairs]))
    s0 = tg_[1.0][1]
    want = 2.0 / (1.0 + s0)
    got = tg_[1.0][0] / tg_[0.0][0]
    say(f"K4 receiver planted at double share against man: targets man-only / zone-only {got:.2f}, expected about "
        f"{want:.2f} (= 2 / (1 + share)) -> {'PASS' if abs(got - want) < 0.1 else 'FAIL'}")
    (config.ROOT / "docs" / "gamesim_coverage_checks.txt").write_text("\n".join(OUT) + "\n")


# ------------------------------------------------------------------------------------------- explore

def ll(p, y):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def explore(d):
    lab, _ = load(d)
    tg = CV.team_games(lab)
    pg = CV.pregame(tg, K_COV)
    oc = CV.overall_comp(tg)
    ex = lab.filter(pl.col("season").is_in([2022, 2023]), pl.col("natt"))
    keys = list(zip(ex["game_id"].to_list(), ex["posteam"].to_list()))
    man = ex["man"].to_numpy()
    y = ex["cp"].to_numpy().astype(float)
    base = np.array([oc[k] for k in keys])
    lo = np.log(base / (1 - base))
    res = {"n_attempts": int(len(y)), "ll_no_split": ll(base, y), "k_cov": {}}
    say(f"## Explore 2022-2023: completion on {len(y)} labeled attempts")
    say(f"No split (overall pre-game rate): log loss {res['ll_no_split']:.5f}")
    for k in K_COV:
        sp = pg["split"][k]
        dv = np.array([sp[kk]["comp_man"] if m else sp[kk]["comp_zone"] for kk, m in zip(keys, man)])
        res["k_cov"][k] = ll(1 / (1 + np.exp(-(lo + dv))), y)
        say(f"k_cov {k}: {res['k_cov'][k]:.5f}")
    kc = min(K_COV, key=lambda k: res["k_cov"][k])
    say(f"-> **k_cov = {kc}**")
    # receivers: which roster receiver was targeted
    rg = CV.receiver_games(lab)
    rs = CV.receiver_splits(rg, K_REC)
    t = lab.filter(pl.col("season").is_in([2022, 2023]), pl.col("att"), pl.col("receiver_player_id").is_not_null())
    # overall pre-game share from the same 16-game window (k = 0 multipliers are 1 by construction)
    share = _overall_share(rg)
    res["k_rec"] = {}
    by = {}
    for r in t.select("season", "week", "game_id", "posteam", "receiver_player_id", "man").iter_rows(named=True):
        by.setdefault((r["season"], r["week"], r["posteam"]), []).append((r["receiver_player_id"], r["man"]))
    for k in K_REC + [0]:
        tot, n = 0.0, 0
        for (s, w, team), plays in by.items():
            pool = share.get((s, w, team))
            if not pool:
                continue
            ids = list(pool)
            base_s = np.array([pool[i] for i in ids])
            for pid, m in plays:
                if pid not in pool:
                    continue
                mult = np.array([(rs[k].get((s, w, i), (1, 1, 1, 1))[0 if m else 1] if k else 1.0) for i in ids])
                p = base_s * mult
                p /= p.sum()
                tot -= np.log(max(p[ids.index(pid)], 1e-6))
                n += 1
        res["k_rec"][k] = tot / n
        say(f"k_rec {k if k else 'none (overall share)'}: target log loss {tot / n:.5f} on {n} targets")
    kr = min(K_REC, key=lambda k: res["k_rec"][k])
    say(f"-> **k_rec = {kr}**")
    res["chosen"] = {"k_cov": kc, "k_rec": kr}
    (BT / "gamesim_coverage_k.json").write_text(json.dumps(res, indent=1))
    # descriptive: G4 vs G3 margin MAE on 2022-2023
    S = GPL.setup(d, [2022, 2023])
    games = A.games([2022, 2023]).filter(pl.col("week") >= 2)
    o3, _ = R.simulate_games(games, S["fac"], S["tb"], S["kicks"], S["xps"], S["k"]["hfa"], sims=1000, seed=101, shift=S["shift"])
    o4, _ = R.simulate_games(games, S["fac"], S["tb"], S["kicks"], S["xps"], S["k"]["hfa"], sims=1000, seed=101, shift=S["shift"],
                             cover=(pg, kc))
    x3 = o3.select("game_id", "fair").join(games, on="game_id")
    x4 = o4.select("game_id", "fair").join(games, on="game_id")
    m3, m4 = (x3["fair"] - x3["result"]).abs().mean(), (x4["fair"] - x4["result"]).abs().mean()
    say(f"\nDescriptive 2022-2023 ({x3.height} games, weeks 2-18, 1,000 runs): margin MAE G3 {m3:.3f}, G4 {m4:.3f}, close "
        f"{(x3['spread_line'] - x3['result']).abs().mean():.3f}")
    (config.ROOT / "docs" / "gamesim_coverage_explore.txt").write_text("\n".join(OUT) + "\n")


def _overall_share(rg):
    """{(season, week, team): {player: overall labeled target share over his previous 16 games}} for players whose
    last earlier game was for that team."""
    out, hist, last_team = {}, {}, {}
    by_week = {}
    for r in rg.to_dicts():
        by_week.setdefault((r["season"], r["week"]), []).append(r)
    for sw in sorted(by_week):
        for pid, h in hist.items():
            h = h[-16:]
            tt = sum(x["tt_m"] + x["tt_z"] for x in h)
            if tt > 0:
                out.setdefault((*sw, last_team[pid]), {})[pid] = max(sum(x["t_m"] + x["t_z"] for x in h) / tt, 1e-4)
        for r in by_week[sw]:
            hist.setdefault(r["player_id"], []).append(r)
            last_team[r["player_id"]] = r["posteam"]
    return out


# ------------------------------------------------------------------------------------------- confirm

def confirm(d):
    ch = json.loads((BT / "gamesim_coverage_k.json").read_text())["chosen"]
    kc, kr = ch["k_cov"], ch["k_rec"]
    lab, _ = load(d)
    tg = CV.team_games(lab)
    pg = CV.pregame(tg, [kc])
    rs = CV.receiver_splits(CV.receiver_games(lab), [kr])[kr]
    S = GPL.setup(d, [2024, 2025])
    # C1 spreads
    games = A.games([2024, 2025]).filter(pl.col("week") >= 2)
    o3, _ = R.simulate_games(games, S["fac"], S["tb"], S["kicks"], S["xps"], S["k"]["hfa"], sims=1000, seed=303, shift=S["shift"])
    o4, _ = R.simulate_games(games, S["fac"], S["tb"], S["kicks"], S["xps"], S["k"]["hfa"], sims=1000, seed=303, shift=S["shift"],
                             cover=(pg, kc))
    x3 = o3.select("game_id", "fair").join(games, on="game_id").sort("game_id")
    x4 = o4.select("game_id", "fair").join(games, on="game_id").sort("game_id")
    e3, e4 = (x3["fair"] - x3["result"]).abs().to_numpy(), (x4["fair"] - x4["result"]).abs().to_numpy()
    diff = e4 - e3
    cl = (x4["season"] * 100 + x4["week"]).to_numpy()
    ci = C.boot(lambda ix: diff[ix].mean(), cl, 0.05 / 2 / 2)
    c1 = {"n": len(diff), "mae_g3": float(e3.mean()), "mae_g4": float(e4.mean()),
          "mae_close": float((x4["spread_line"] - x4["result"]).abs().mean()),
          "diff": float(diff.mean()), "ci": list(map(float, ci)), "better": bool(ci[1] < 0)}
    say(f"## Confirm 2024-2025, k_cov {kc}, k_rec {kr}")
    say(f"- **C1 spreads** ({c1['n']} games, weeks 2-18, 1,000 runs): margin MAE G4 {c1['mae_g4']:.3f} vs G3 {c1['mae_g3']:.3f} "
        f"(close {c1['mae_close']:.3f}); difference {c1['diff']:+.4f}, interval {ci[0]:+.4f} to {ci[1]:+.4f}: "
        f"**{'BETTER' if c1['better'] else 'NOT BETTER'}**")
    GC.ALPHA = 0.05 / 6
    desc = {"T1": GC.t1(x4), "T3": GC.t3(x4)}
    try:
        desc["T2"] = GC.t2(x4)
    except Exception as e:      # ASB file is personal and may be missing
        desc["T2"] = {"error": str(e)}
    say(f"- Descriptive G4: T1 coefficient {desc['T1']['coef']:+.3f}; T3 bets {desc['T3']['n']}, covers {desc['T3']['cover']:.1%}, "
        f"ROI {desc['T3']['roi']:+.1%}" + (f"; T2 coefficient {desc['T2']['coef']:+.3f} (2024 bet365, n {desc['T2']['n']})"
                                           if "coef" in desc["T2"] else ""))
    # C2 props
    ros_c = CV.attach_receivers(S["ros"], rs)
    L0, L1, cls, ys, mks = [], [], [], [], []
    cal = []
    for season in (2024, 2025):
        dk, team = GPL.dk_props(S, season)
        g0, r0, p0, _, _ = GPL.run(S, season, 2000, 10.0, seed=606)
        S1 = dict(S, ros=ros_c)
        g = S1["games"].filter(pl.col("season") == season)
        g1, r1, p1, _, _ = PL.simulate(g, S1["fac"], S1["tb"], S1["kicks"], S1["xps"], S1["k"]["hfa"], S1["ros"], 2000, 10.0,
                                       seed=606, shift=S1["shift"], cover=(pg, kc))
        a = GPL.player_probs(S, season, dk, team, g0, r0, p0)
        b = GPL.player_probs(S1, season, dk, team, g1, r1, p1)
        ok = ~np.isnan(a) & ~np.isnan(b)
        y = (dk["result"] == "over").cast(pl.Float64).to_numpy()[ok]
        L0.append(GPL.D.ll_each(a[ok], y))
        L1.append(GPL.D.ll_each(b[ok], y))
        cls.append(season * 100 + dk["week"].to_numpy()[ok])
        ys.append(y)
        mks.append(dk["market"].to_numpy()[ok])
        cal.append((b[ok], y))
    L0, L1, cl2, mk = np.concatenate(L0), np.concatenate(L1), np.concatenate(cls), np.concatenate(mks)
    d2 = L1 - L0
    ci2 = C.boot(lambda ix: d2[ix].mean(), cl2, 0.05 / 2 / 2)
    c2 = {"n": len(d2), "ll_with": float(L1.mean()), "ll_without": float(L0.mean()), "diff": float(d2.mean()),
          "ci": list(map(float, ci2)), "better": bool(ci2[1] < 0)}
    say(f"- **C2 props** ({c2['n']} DraftKings props, 2024-2025, 2,000 runs): log loss with coverage {c2['ll_with']:.4f} vs "
        f"without {c2['ll_without']:.4f}; difference {c2['diff']:+.4f}, interval {ci2[0]:+.4f} to {ci2[1]:+.4f}: "
        f"**{'BETTER' if c2['better'] else 'NOT BETTER'}**")
    say("\nBy market | n | with coverage | without")
    for m_ in GPL.MARKETS:
        m = mk == m_
        if m.any():
            say(f"{m_} | {m.sum()} | {L1[m].mean():.4f} | {L0[m].mean():.4f}")
    p = np.concatenate([c[0] for c in cal])
    y = np.concatenate([c[1] for c in cal])
    sp = np.maximum(p, 1 - p)
    hit = np.where(p >= 0.5, y == 1, y == 0)
    say("\nCalibration with coverage: band | n | said | hit")
    for lo in (0.5, 0.6, 0.7, 0.8, 0.9):
        m = (sp >= lo) & ((sp < lo + 0.1) if lo < 0.9 else (sp <= 1))
        if m.any():
            say(f"{lo:.0%}-{min(lo + .1, 1):.0%} | {m.sum()} | {sp[m].mean():.1%} | {hit[m].mean():.1%}")
    (BT / "gamesim_coverage.json").write_text(json.dumps({"k": ch, "C1": c1, "C2": c2, "desc": desc}, indent=1, default=str))
    with open(f"{d}/coverage_confirm.pkl", "wb") as f:
        pickle.dump((x3, x4), f)
    parts = [(config.ROOT / "docs" / n).read_text() for n in ("gamesim_coverage_checks.txt", "gamesim_coverage_explore.txt")]
    head = ["# Game simulator coverage layer (man vs zone)", "",
            "Pre-registration: docs/gamesim_coverage_preregistration.md. Two tests at 0.05 / 2.", "",
            "## Known-answer checks", "", parts[0], parts[1], ""]
    (config.ROOT / "docs" / "gamesim_coverage.md").write_text("\n".join(head + OUT) + "\n")


if __name__ == "__main__":
    {"check": check, "explore": explore, "confirm": confirm}[sys.argv[2]](sys.argv[1])
