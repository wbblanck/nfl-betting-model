"""Engine A event layer (phase 5) on the tune seasons: touchdowns, interceptions, longest play and combined yards.

Fit on 2018-2021 (Engine A-1.0's frozen parameters plus the event layer's rates); every offense-game of 2022-2023
simulated; scored against simple baselines. These markets are reported, not tested (docs/engine_preregistration.md:
only the six Test S markets are tested), and no 2024-2025 outcome or price is read. Gates checked here: every box
agrees with its events on every run; the six A-1.0 markets are bit-identical with and without the layer; two seeds
agree within 4 Monte Carlo standard errors. Writes docs/engine/engine_a_events.md and data/backtests/engine_a_events.json.
"""
import json
import sys

import numpy as np
import polars as pl
from scipy import stats

import engine_a_tune as T
from nflbet.config import ROOT
from nflbet.engine import baselines as BL, scoring as S
from nflbet.engine.data import nflverse as N, player_week as PW
from nflbet.engine.replication import environment as V, events as EV, model as M

SIMS, SEED_CHECK_GAMES = 2000, 40
OUT_MD, OUT_JSON = ROOT / "docs" / "engine" / "engine_a_events.md", ROOT / "data" / "backtests" / "engine_a_events.json"
EXTRA = ["passing_tds", "passing_interceptions", "rushing_tds", "receiving_tds", "special_teams_tds", "fumble_recovery_tds"]


def longest(pbp: pl.DataFrame) -> pl.DataFrame:
    """Longest catch and longest carry per player per game (regular season, no two-point tries); absent = 0."""
    reg = pbp.filter((pl.col("season_type") == "REG") & (pl.col("two_point_attempt") == 0))
    r = (reg.filter((pl.col("complete_pass") == 1) & pl.col("receiving_yards").is_not_null())
         .group_by("game_id", pl.col("receiver_player_id").alias("player_id")).agg(pl.col("receiving_yards").max().alias("y_long_rec")))
    u = (reg.filter((pl.col("rush_attempt") == 1) & pl.col("rushing_yards").is_not_null())
         .group_by("game_id", pl.col("rusher_player_id").alias("player_id")).agg(pl.col("rushing_yards").max().alias("y_long_rush")))
    return r.join(u, on=["game_id", "player_id"], how="full", coalesce=True)


def frame(seasons) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(feature rows with every outcome this script scores, play-by-play)."""
    df, _, pbp = T.load(list(seasons))
    pw, _ = PW.build(N.read("player_stats", list(seasons)), N.read("snap_counts", list(seasons)), N.read("players"))
    df = df.join(pw.select("player_id", "game_id", *EXTRA), on=["player_id", "game_id"], how="left").join(longest(pbp), on=["game_id", "player_id"], how="left")
    df = df.with_columns([pl.col(c).fill_null(0) for c in EXTRA + ["y_long_rec", "y_long_rush"]])
    return df.with_columns((pl.col("rushing_tds") + pl.col("receiving_tds") + pl.col("special_teams_tds") + pl.col("fumble_recovery_tds")).alias("y_tds")), pbp


def hist_table(seasons) -> pl.DataFrame:
    """events.history over the seasons and the one before (last-season sums need it)."""
    all_s = list(range(min(seasons) - 1, max(seasons) + 1))
    feats = pl.read_parquet(N.DIR / "features" / "player_game.parquet").filter(pl.col("season").is_in(all_s))
    pw, _ = PW.build(N.read("player_stats", all_s), N.read("snap_counts", all_s), N.read("players"))
    return EV.history(feats, pw)


def run(P, EVp, sums, ptab, df, hist, sims, seed_base=0, games=None):
    """Simulate every game in df; returns (frame sorted as the runs, samples, event samples, event violations, n)."""
    df = df.sort("game_id", "team", "player_id")
    gids = df["game_id"].unique(maintain_order=True).to_list()
    if games is not None:
        gids = gids[:games]
        df = df.filter(pl.col("game_id").is_in(gids))
    keys = ["attempts", "passing_yards", "carries", "rushing_yards", "receptions", "receiving_yards"]
    out = {c: np.zeros((df.height, sims), dtype=np.int32) for c in keys}
    evk = ["tds", "passing_tds", "passing_interceptions", "long_rec", "long_rush", "long_cmp", "pass_rush_yds", "rush_rec_yds"]
    ev_out = {c: np.zeros((df.height, sims), dtype=np.int32) for c in evk}
    ev_out["_n_play"] = np.zeros(df.height)
    broke, same, at, n = {}, True, 0, 0
    for gi, ((gid,), game) in enumerate(df.group_by(["game_id"], maintain_order=True)):
        sides = [rows for _, rows in game.group_by(["team"], maintain_order=True)]
        seed = int.from_bytes(str(gid).encode(), "little") % (2 ** 32)
        rng, ev_rng = np.random.default_rng([seed_base, seed]), np.random.default_rng([seed_base + 1, seed])
        index = V.draw_index(P["env"], sims, rng)
        res = [EV.simulate(P, EVp, sums, ptab, rows, hist, sims, rng, ev_rng, index, side) for side, rows in enumerate(sides[:2])]
        if gi < 20 and seed_base == 0:                    # the six A-1.0 markets must not move: same seed, no event layer
            plain = M.simulate_game(P, sums, sides, sims, np.random.default_rng([0, seed]))
            same &= all((a[1][c] == b[1][c]).all() for a, b in zip(res, plain) for c in keys)
        for rows, (box, s, e) in zip(sides, res):
            for k, v in EV.violations(e["box"]).items():
                broke[k] = broke.get(k, 0) + v
            for c in keys:
                out[c][at:at + rows.height] = s[c]
            for c in evk:
                ev_out[c][at:at + rows.height] = e["samples"][c]
            ev_out["_n_play"][at:at + rows.height] = e["n_play"]
            at, n = at + rows.height, n + 1
    return df, out, ev_out, broke, same, n


def poisson_cdf(lam, kmax):
    from scipy import stats
    return stats.poisson.cdf(np.arange(kmax + 1)[None, :], np.asarray(lam)[:, None])


def main() -> int:
    P, _, _ = T.fitted()                                   # Engine A-1.0, frozen
    fit, pbp_fit = frame(T.FIT)
    yards, flags = EV.pools(pbp_fit.filter(pl.col("season").is_in(T.FIT)), N.read("players"))
    ref = T.pools(pbp_fit.filter(pl.col("season").is_in(T.FIT)))
    assert all(np.array_equal(ref[k][p], yards[k][p]) for k in ref for p in ref[k]), "event pools differ from Engine A's"
    sums, ptab = EV.tables(yards, flags, seed=0)
    mt = M.tables(ref, seed=0)
    assert all(np.array_equal(mt[k][p], sums[k][p]) for k in mt for p in mt[k]), "event tables differ from Engine A's"
    h_fit = hist_table(T.FIT)
    fp = fit.filter(pl.col("played")).join(h_fit, on=["player_id", "game_id"], how="left").fill_null(0)
    EVp = EV.fit(fp, flags)
    tune, _ = frame(T.TUNE)
    h_tune = hist_table(T.TUNE)
    df, runs, ev, broke, same, n_games = run(P, EVp, sums, ptab, tune, h_tune, SIMS)
    df = df.join(h_tune, on=["player_id", "game_id"], how="left").fill_null(0)
    fitj = fit.join(h_fit, on=["player_id", "game_id"], how="left").fill_null(0)
    played = df["played"].to_numpy()
    week = (df["season"] * 100 + df["week"]).to_numpy()
    elig = {m: BL.eligible(df, m).to_numpy() & played for m in BL.MARKETS}
    felig = {m: BL.eligible(fitj, m).to_numpy() & fitj["played"].to_numpy() for m in BL.MARKETS}
    games_h = lambda d: (d["p_n_std"] + d["p_n_prev"]).to_numpy().astype(float)
    res = {}

    def shrunk_rate(d, num, m_fit, c=4.0):                 # per game: (his count + c x fit-season mean) / (his games + c)
        return (d[num].to_numpy() + c * m_fit) / (games_h(d) + c)

    # Anytime touchdown: rows in the receiving or rushing sample, not quarterbacks.
    def td_rows(d, e):
        return (e["rec"] | e["rush_att"]) & (d["position"] != "QB").to_numpy()
    m, fm = td_rows(df, elig), td_rows(fitj, felig)
    hist_tds = lambda d: d.with_columns((pl.col("h_receiving_tds") + pl.col("h_rushing_tds")).alias("h_tds"))
    mu_fit = float(fitj.filter(pl.Series(fm))["y_tds"].mean())
    lam = shrunk_rate(hist_tds(df.filter(pl.Series(m))), "h_tds", mu_fit)
    pb = 1 - np.exp(-lam)
    pe = np.clip((ev["tds"][m] > 0).mean(axis=1), 1e-4, 1 - 1e-4)
    y = (df["y_tds"].to_numpy()[m] > 0).astype(float)
    ll = lambda p: -(y * np.log(p) + (1 - y) * np.log(1 - p))
    d, lo, hi = S.paired_bootstrap(ll(pe) - ll(pb), week[m])
    res["anytime_td"] = {"n": int(m.sum()), "engine": float(ll(pe).mean()), "baseline": float(ll(pb).mean()), "diff": [d, lo, hi],
                         "mean_p": float(pe.mean()), "mean_p_baseline": float(pb.mean()), "hit": float(y.mean()), "unit": "log loss"}
    # Counts and yardage by CRPS against a simple baseline.
    specs = {   # market -> (rows, outcome, runs, baseline (kind, ...), grid)
        "pass_td": ("pass_att", "passing_tds", ev["passing_tds"], ("poisson", "h_passing_tds_unused"), 10),
        "pass_int": ("pass_att", "passing_interceptions", ev["passing_interceptions"], ("poisson", "h_passing_interceptions"), 10),
        "long_rec": ("rec", "y_long_rec", ev["long_rec"], None, None),
        "long_rush": ("rush_att", "y_long_rush", ev["long_rush"], None, None),
        "pass_rush_yds": ("pass_att", None, ev["pass_rush_yds"], ("nb", ["passing_yards", "rushing_yards"]), 800),
        "rush_rec_yds": (None, None, ev["rush_rec_yds"], ("nb", ["rushing_yards", "receiving_yards"]), 400),
    }
    for market, (sample, ycol, x_all, base, kmax) in specs.items():
        if market == "rush_rec_yds":
            m, fm = td_rows(df, elig), td_rows(fitj, felig)
            yv = (df["rushing_yards"] + df["receiving_yards"]).to_numpy()
        elif market == "pass_rush_yds":
            m, fm = elig[sample], felig[sample]
            yv = (df["passing_yards"] + df["rushing_yards"]).to_numpy()
        else:
            m, fm = elig[sample], felig[sample]
            yv = df[ycol].to_numpy()
        x, yy = x_all[m], yv[m]
        ec = S.crps_samples(x, yy)
        r = {"n": int(m.sum()), "engine": float(ec.mean()), "unit": "CRPS", "mean_bias": float(x.mean() - yy.mean()),
             "coverage": {str(lv): S.coverage_samples(x, yy, lv) for lv in (0.5, 0.8, 0.9)}}
        if base is not None and base[0] == "poisson":
            col = "passing_tds" if market == "pass_td" else "passing_interceptions"
            mu_f = float(fitj.filter(pl.Series(fm))[col].mean())
            sub = df.filter(pl.Series(m))
            if market == "pass_td":                         # passing touchdowns this season and last are not in the history
                hcol = (sub["p_passing_yards_std"] + sub["p_passing_yards_prev"]).to_numpy() / 155.0   # ~1 TD per 155 yards (fit)
                lam = (hcol + 4 * mu_f) / (games_h(sub) + 4)
            else:
                lam = shrunk_rate(sub, base[1], mu_f)
            bc = S.crps(poisson_cdf(lam, kmax), yy)
        elif base is not None:
            cols = base[1]
            def mean_w8(d):
                return sum(np.where(d["p_n_w8"].to_numpy() > 0, d[f"p_{c}_w8"].to_numpy() / np.maximum(d["p_n_w8"].to_numpy(), 1), np.nan) for c in cols)
            fsub = fitj.filter(pl.Series(fm))
            fmean = mean_w8(fsub)
            ok = ~np.isnan(fmean)
            size = S.fit_nb_size(fmean[ok], sum(fsub[c].to_numpy() for c in cols)[ok])
            mean = mean_w8(df.filter(pl.Series(m)))
            mean = np.where(np.isnan(mean), np.nanmean(mean), mean)
            bc = S.crps(S.nb_cdf(mean, size, kmax), yy)
            r["baseline_size"] = size
        else:
            bc = None
        if bc is not None:
            d, lo, hi = S.paired_bootstrap(ec - bc, week[m])
            r.update({"baseline": float(bc.mean()), "diff": [d, lo, hi]})
        res[market] = r
    # Seed stability: two seeds, the first games of the tune seasons, each reported probability within 4 standard errors.
    _, _, e1, _, _, _ = run(P, EVp, sums, ptab, tune, h_tune, SIMS, seed_base=10, games=SEED_CHECK_GAMES)
    d2, _, e2, _, _, _ = run(P, EVp, sums, ptab, tune, h_tune, SIMS, seed_base=20, games=SEED_CHECK_GAMES)
    lines = {"tds": 0.5, "passing_tds": 1.5, "passing_interceptions": 0.5, "long_rec": 19.5, "long_rush": 11.5, "long_cmp": 39.5,
             "pass_rush_yds": 250.5, "rush_rec_yds": 50.5}
    checked = failed = 0
    worst = 0.0
    for c, line in lines.items():
        p1, p2 = (e1[c] > line).mean(axis=1), (e2[c] > line).mean(axis=1)
        p = (p1 + p2) / 2
        # A player's forecast is resampled from the runs he plays in (n of them); below SIMS that resampling adds its
        # own error, so each seed's variance is p(1 - p) (1/n + 1/SIMS) there and p(1 - p) / SIMS otherwise.
        def var1(e):
            n = e["_n_play"]
            return np.where((n >= 50) & (n < SIMS), 1 / np.maximum(n, 1) + 1 / SIMS, 1 / SIMS)   # under 50: all runs used
        se = np.sqrt(np.maximum(p * (1 - p), 1e-12) * (var1(e1) + var1(e2)))
        keep = (p > 0) & (p < 1)
        z = np.abs(p1 - p2)[keep] / se[keep]
        checked += int(keep.sum())
        failed += int((z > 4).sum())
        worst = max(worst, float(z.max()) if keep.any() else 0.0)
    out = {"version": EV.VERSION, "engine_a": M.VERSION, "fit_seasons": T.FIT, "tune_seasons": T.TUNE, "sims": SIMS, "team_games": n_games,
           "event_violations": broke, "six_markets_unchanged": bool(same), "params": EVp,
           "seed_check": {"probabilities": checked, "beyond_4_se": failed, "largest_z": worst, "games": SEED_CHECK_GAMES}, "markets": res}
    L = [f"# Engine A event layer ({EV.VERSION}) on the tune seasons", "",
         "Written by `scripts/engine_a_events.py`. Engine A-1.0 as frozen, plus the event layer fitted on 2018-2021; every",
         f"offense-game of 2022-2023 simulated {SIMS:,} times ({n_games:,} offense-games). Shadow and combined markets: reported,",
         "not tested. No 2024-2025 outcome and no price was read.", "",
         "## Gates", "",
         f"- Every box agrees with its events (plays add up to yards, touchdowns within plays, passing touchdowns within the",
         f"  receiving touchdowns credited, longest equal to the yards on a single catch): "
         + ("**yes**, every run." if not broke else "**NO** " + json.dumps(broke)),
         f"- The six A-1.0 markets with the layer on are bit-identical to A-1.0 without it (first 20 games checked): **{'yes' if same else 'NO'}**.",
         f"- Two seeds on the first {SEED_CHECK_GAMES} games: {checked:,} probabilities at fixed lines, {failed} beyond 4 Monte Carlo",
         f"  standard errors (largest {worst:.2f})." + (" **Pass.**" if failed == 0 else " **Fail** (the gate is every probability within 4)."),
         f"  If the errors are right, {checked:,} checks put {checked * 2 * stats.norm.sf(4):.2f} beyond 4 on average, and one as far out",
         f"  as {worst:.2f} or more turns up with probability {1 - np.exp(-checked * 2 * stats.norm.sf(worst)):.2f}. The threshold is not changed after the fact.", "",
         "## Scores on 2022-2023 (lower is better; interval: week-clustered bootstrap, 95%)", "",
         "| Market | Rows | Score | Engine | Baseline | Engine minus baseline | Central 50% / 80% / 90% covers |", "|---|---|---|---|---|---|---|"]
    for k, r in res.items():
        cov = " / ".join(f"{r['coverage'][lv]:.1%}" for lv in ("0.5", "0.8", "0.9")) if "coverage" in r else ""
        bl = f"{r['baseline']:.4f}" if "baseline" in r else "none"
        df_ = f"{r['diff'][0]:+.4f} ({r['diff'][1]:+.4f} to {r['diff'][2]:+.4f})" if "diff" in r else ""
        L.append(f"| {k} | {r['n']:,} | {r['unit']} | {r['engine']:.4f} | {bl} | {df_} | {cov} |")
    a = res["anytime_td"]
    L += ["", f"Anytime touchdown: engine's average probability {a['mean_p']:.1%}, baseline's {a['mean_p_baseline']:.1%}, actual {a['hit']:.1%}.",
          "Mean of the runs minus mean of the outcomes: " + ", ".join(f"{k} {r['mean_bias']:+.2f}" for k, r in res.items() if "mean_bias" in r) + ".", "",
          "## Fitted on 2018-2021", "",
          "- Touchdown share of plays in the pools: catches " + ", ".join(f"{p} {v:.3f}" for p, v in EVp["td_rate"]["rec"].items())
          + "; carries " + ", ".join(f"{p} {v:.3f}" for p, v in EVp["td_rate"]["rush"].items()) + ".",
          f"- Touchdown factor prior strength: {EVp['c']['rec']:g} catches, {EVp['c']['rush']:g} carries. Interception rate "
          f"{EVp['int_rate']:.4f} per attempt, prior strength {EVp['c']['int']:g} attempts.", "",
          "## Baselines and limits", "",
          "- Anytime touchdown: Poisson with the player's touchdowns per game this season and last, shrunk with 4 games of the",
          "  fit-season average (rows in the receiving or rushing sample, quarterbacks left out). The outcome counts special",
          "  teams and fumble-return touchdowns, as books grade it; the engine does not model them.",
          "- Interceptions: the same Poisson from interceptions per game. Passing touchdowns: no per-player passing-touchdown",
          "  history is kept, so the baseline uses passing yards this season and last at one touchdown per 155 yards: a weak",
          "  baseline, and the comparison says little.",
          "- Combined yards: negative binomial around the player's last-8-game average of the sum, size fitted on 2018-2021.",
          "- Longest catch and carry: no baseline; coverage only. A player with no catch (or carry) in a run has 0 for it.",
          "- Not built: first touchdown scorer (needs the order of scores), defensive and special-teams touchdowns.",
          "- Touchdowns depend on the play's yards (pool plays carry their own flags) and on the player's own touchdown rate;",
          "  field position and the red zone are not simulated."]
    OUT_JSON.write_text(json.dumps(out, indent=1, default=float) + "\n")
    OUT_MD.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0 if (not broke and same and failed == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
