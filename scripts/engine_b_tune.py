"""Engine B on the tune seasons: fit on 2018-2021, forecast every Test S row of 2022-2023 and compare with the frozen
baselines (and, for reference, Engine A's tune-season scores). This is tuning (allowed on 2022-2023), not Test S: no
2024-2025 outcome and no price is read. Writes docs/engine/engine_b_tune.md and data/backtests/engine_b_tune.json."""
import json
import sys

import numpy as np
import polars as pl

from nflbet.config import ROOT
from nflbet.engine import baselines as BL, scoring as S
from nflbet.engine.challenger import model as M, yardage as Y
from nflbet.engine.data import nflverse as N, player_week as PW

FIT, TUNE, SIMS = (2018, 2019, 2020, 2021), (2022, 2023), 4000
KMAX = {"pass_att": 90, "pass_yds": 700, "rush_att": 60, "rush_yds": 350, "rec": 30, "rec_yds": 350}
OUT_MD, OUT_JSON = ROOT / "docs" / "engine" / "engine_b_tune.md", ROOT / "data" / "backtests" / "engine_b_tune.json"
OUTCOMES = ["attempts", "completions", "passing_yards", "carries", "rushing_yards", "targets", "receptions", "receiving_yards"]


def load(seasons) -> pl.DataFrame:
    """Feature rows of the seasons with that game's outcomes joined on (zeros for an active player who did not play)."""
    feats = pl.read_parquet(N.DIR / "features" / "player_game.parquet").filter(pl.col("season").is_in(list(seasons)))
    pw, _ = PW.build(N.read("player_stats", list(seasons)), N.read("snap_counts", list(seasons)), N.read("players"))
    df = feats.join(pw.select("player_id", "game_id", *OUTCOMES), on=["player_id", "game_id"], how="left")
    assert df.filter(pl.col("played"))[OUTCOMES[0]].null_count() == 0
    return df.with_columns([pl.col(c).fill_null(0) for c in OUTCOMES])


def fitted() -> dict:
    """Parameters fitted on the fit seasons, tail scales on the tune seasons."""
    P = M.fit(load(FIT))
    return M.fit_tails(P, load(TUNE))


CANDIDATES = {"pass_att": ("nb", "hurdle"), "rush_att": ("nb", "hurdle"), "rec": ("nb", "hurdle"),
              "pass_yds": ("quantile", "quantile+zero"), "rush_yds": ("quantile", "quantile+zero"), "rec_yds": ("quantile", "quantile+zero")}


def score(P: dict, frame: pl.DataFrame, base: dict, sims: int, level: float = 0.05, markets=None) -> dict:
    out = {}
    for i, (market, (ycol, _, _)) in enumerate(BL.MARKETS.items()):
        if markets is not None and market not in markets:
            continue
        m = BL.eligible(frame, market).to_numpy() & frame["played"].to_numpy()
        rows, y = frame.filter(pl.Series(m)), frame[ycol].to_numpy()[m]
        b = base["markets"][market]
        chosen = b["chosen"]
        bc = S.crps(S.nb_cdf(BL.means(rows, market, b["constants"])[chosen], b["baselines"][chosen]["size"], KMAX[market]), y)
        x = M.simulate(P, rows, market, sims, np.random.default_rng([1, i]))
        ec = S.crps_samples(x, y)
        week = (rows["season"] * 100 + rows["week"]).to_numpy()
        d, lo, hi = S.paired_bootstrap(ec - bc, week, level=level)
        pick = np.random.default_rng(1).integers(0, x.shape[1], (20, len(y)))
        qs = {q: np.quantile(x, q, axis=1, method="inverted_cdf") for q in (0.05, 0.25, 0.5, 0.75, 0.95)}
        out[market] = {"n": int(m.sum()), "weeks": int(len(np.unique(week))), "baseline": chosen, "baseline_crps": float(bc.mean()),
                       "engine_crps": float(ec.mean()), "diff": [d, lo, hi], "level": level,
                       "coverage": {str(lv): S.coverage_samples(x, y, lv) for lv in (0.5, 0.8, 0.9)},
                       "coverage_if_right": {str(lv): float(np.mean([S.coverage_samples(x, x[np.arange(len(y)), p], lv) for p in pick]))
                                             for lv in (0.5, 0.8, 0.9)},
                       "mean_bias": float(x.mean() - y.mean()), "share_zero": [float((x == 0).mean()), float((y == 0).mean())],
                       "pinball": {str(q): float(np.mean(np.where(y >= v, q * (y - v), (q - 1) * (y - v)))) for q, v in qs.items()}}
        if market in P["yards"]:
            out[market]["crossings_before_sort"] = Y.crossings(Y.raw(P["yards"][market], M._yard_inputs(P, rows, M.VOLUME[market])))
            out[market]["crossings_after_sort"] = Y.crossings(M.quantiles(P, rows, market))
    return out


def table(markets: dict, label: str) -> list[str]:
    L = [f"| Market | Rows | Baseline | Baseline CRPS | Engine B CRPS | B minus baseline ({label}) | Central 50% covers (if right) | 80% | 90% |",
         "|---|---|---|---|---|---|---|---|---|"]
    for market, r in markets.items():
        c, i = r["coverage"], r["coverage_if_right"]
        L.append(f"| {market} | {r['n']:,} | {r['baseline']} | {r['baseline_crps']:.3f} | {r['engine_crps']:.3f} | "
                 f"{r['diff'][0]:+.3f} ({r['diff'][1]:+.3f} to {r['diff'][2]:+.3f}) | {c['0.5']:.1%} ({i['0.5']:.1%}) | "
                 f"{c['0.8']:.1%} ({i['0.8']:.1%}) | {c['0.9']:.1%} ({i['0.9']:.1%}) |")
    return L


def main() -> int:
    P = fitted()
    df = load(TUNE)
    base = json.loads((ROOT / "data" / "backtests" / "engine_baselines.json").read_text())
    cand = {}
    for market, fams in CANDIDATES.items():          # spec 3.5: the family per market is chosen here, on 2022-2023
        for fam in fams:
            P["family"][market] = fam
            cand[(market, fam)] = score(P, df, base, SIMS, markets={market})[market]
        P["family"][market] = min(fams, key=lambda f: cand[(market, f)]["engine_crps"])
    assert P["family"] == M.FAMILY, f"update model.FAMILY to {P['family']}"
    markets = {m: cand[(m, P["family"][m])] for m in CANDIDATES}
    a = json.loads((ROOT / "data" / "backtests" / "engine_a_v01.json").read_text())["markets"]
    res = {"family": P["family"], "candidates": {f"{m}|{f}": r["engine_crps"] for (m, f), r in cand.items()}, "version": M.VERSION, "fit_seasons": FIT, "tune_seasons": TUNE, "sims": SIMS, "markets": markets,
           "count": {v: {k: c[k] for k in ("gamma", "delta", "converged", "n")} for v, c in P["count"].items()},
           "catch": {k: P["catch"][k] for k in ("m", "kappa", "prior")}, "tails": P["tails"], "yard_params": Y.PARAMS}
    L = [f"# Engine B {M.VERSION} on the tune seasons", "",
         "Written by `scripts/engine_b_tune.py`. Fitted on 2018-2021 (yardage tail scales on 2022-2023); every Test S row",
         f"of 2022-2023 forecast with {SIMS:,} runs. This is tuning, not Test S: no 2024-2025 outcome and no price was read.", "",
         "CRPS is in the stat's own units, lower is better; the interval is a week-clustered bootstrap. Coverage in",
         "brackets is what a forecast that was exactly right would show.", "",
         *table(markets, "95% interval"), "",
         "## Family per market (chosen here, MODEL_SPECIFICATION 3.5)", "",
         "| Market | Candidate | Engine B CRPS | Share of zeros, runs vs outcomes | Chosen |", "|---|---|---|---|---|",
         *[f"| {m} | {f} | {r['engine_crps']:.3f} | {r['share_zero'][0]:.1%} vs {r['share_zero'][1]:.1%} | {'yes' if P['family'][m] == f else ''} |"
           for (m, f), r in cand.items()], "",
         "## Engine A on the same rows (reference, not a test)", "",
         "| Market | Engine A CRPS | Engine B CRPS | B minus A |", "|---|---|---|---|"]
    for k, r in markets.items():
        ea = a[k]["engine_crps"] if a.get(k, {}).get("n") == r["n"] else None
        L.append(f"| {k} | {ea:.3f} | {r['engine_crps']:.3f} | {r['engine_crps'] - ea:+.3f} |" if ea is not None
                 else f"| {k} | rows differ | {r['engine_crps']:.3f} | |")
    L += ["", "Engine A's figures are from its own tune run (`data/backtests/engine_a_v01.json`, 2,000 runs per game) on the",
          "same Test S rows. No per-row comparison is made here; A versus B is reported, never a pass or fail.", "",
          "## Fitted", ""]
    for v, c in res["count"].items():
        L.append(f"- {v}: negative binomial on {c['n']:,} fit rows (converged: {c['converged']}); size by position "
                 + ", ".join(f"{p} {np.exp(g):.1f}" for p, g in c["gamma"].items())
                 + f"; size multiplier per unit of role instability {np.exp(c['delta']):.2f}.")
    L.append(f"- Catches: beta-binomial, prior weight m = {P['catch']['m']:g} targets, concentration kappa = {P['catch']['kappa']:g}; "
             "position catch rates " + ", ".join(f"{p} {x:.3f}" for p, x in P["catch"]["prior"].items()) + ".")
    for k, t in P["tails"].items():
        L.append(f"- {k} tails: upper scale {t['hi']:.2f} x (q95 - q75) from {t['n_hi']:,} rows above q95 ({t['share_hi']:.1%}); "
                 f"lower width {t['lo']:.2f} x (q25 - q05) from {t['n_lo']:,} rows below q05 ({t['share_lo']:.1%}).")
    L.append("- Quantile crossings before / after rearrangement: "
             + ", ".join(f"{k} {r['crossings_before_sort']} / {r['crossings_after_sort']}" for k, r in markets.items() if "crossings_after_sort" in r) + ".")
    L += ["", "Mean of the runs minus mean of the outcomes: " + ", ".join(f"{k} {r['mean_bias']:+.2f}" for k, r in markets.items()) + ".",
          "Share of zeros, runs vs outcomes: " + ", ".join(f"{k} {r['share_zero'][0]:.1%} vs {r['share_zero'][1]:.1%}" for k, r in markets.items()) + "."]
    L += ["", "## Reading (limits of this comparison)", "",
          "- These are the tune seasons: the family per market, the yardage tree settings (five tried, the shallowest kept)",
          "  and the yardage tail scales were all chosen on them, so the gaps flatter Engine B, as they flatter Engine A in",
          "  its own tune report. Only Test S on 2024-2025, run once on a frozen version, counts.",
          "- What Engine B is told: earlier games and the game-day active list (through the share of the team's recent",
          "  volume held by active players). Each forecast is conditional on the player taking a snap, as a prop is.",
          "  The rows of a team-game are exactly its active list: on 2018-2023 every player who played had roster status",
          "  ACT that week except 0.03% of 2020 rows, so the row set does not reveal who played.",
          "- Not in this version: the dependence layer (Gaussian copula and box reconciliation, spec 3.4), random-effect",
          "  terms (player and team effects come only through their trailing rates), touchdowns and interceptions",
          "  (spec 3.3), pass_cmp and the combined markets. None of these changes a single market's forecast except",
          "  the box reconciliation, which will be checked against this run when it is built.",
          "- The hurdle's positive part is a negative binomial fitted on the positive rows, drawn with zeros redrawn; for",
          "  these volumes a negative binomial puts almost no mass at zero, so the truncation changes little."]
    OUT_JSON.write_text(json.dumps(res, indent=1, default=float) + "\n")
    OUT_MD.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
