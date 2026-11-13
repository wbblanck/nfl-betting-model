"""Engine phase 3, step 1: fit the simple baselines on 2018-2021 and compare them on 2022-2023 (the tune seasons).
Chooses the best baseline per market by mean CRPS and freezes it in data/backtests/engine_baselines.json; writes
docs/engine/baselines.md. Reads no 2024-2025 outcome and no price."""
import json

import numpy as np
import polars as pl

from nflbet.config import ROOT
from nflbet.engine import baselines as BL, scoring as S
from nflbet.engine.data import nflverse as N, player_week as PW

FIT, TUNE = (2018, 2019, 2020, 2021), (2022, 2023)
KMAX = {"pass_att": 90, "pass_yds": 700, "rush_att": 60, "rush_yds": 350, "rec": 30, "rec_yds": 350}
OUT_MD, OUT_JSON = ROOT / "docs" / "engine" / "baselines.md", ROOT / "data" / "backtests" / "engine_baselines.json"


def table() -> pl.DataFrame:
    seasons = [*FIT, *TUNE]
    feats = pl.read_parquet(N.DIR / "features" / "player_game.parquet").filter(pl.col("season").is_in(seasons))
    pw, _ = PW.build(N.read("player_stats", seasons), N.read("snap_counts", seasons), N.read("players"))
    y = pw.select("player_id", "game_id", *sorted({v[0] for v in BL.MARKETS.values()} | {v[0] for v in BL.B4.values()}))
    return feats.join(y, on=["player_id", "game_id"], how="inner")


def main() -> None:
    df = table()
    assert df["season"].max() <= max(TUNE)
    res, L = {"fit_seasons": FIT, "tune_seasons": TUNE, "min_games_last3": BL.MIN_GAMES, "markets": {}}, [
        "# Baselines (engine phase 3, step 1)", "",
        "Written by `scripts/engine_baselines.py`. Fitted on 2018-2021, compared on 2022-2023 (the tune seasons, where",
        "choosing is allowed). No 2024-2025 outcome and no price was read. Lower CRPS is better; it is in the stat's own",
        "units (attempts, catches, yards).", "",
        "Rows: a player-game counts when the player had at least 2 of his last 3 games on record and, per game in them,",
        "at least 15 pass attempts (passing markets), 5 carries (rushing) or 3 targets (receiving). That filter was set",
        "in advance and is the Test S sample.", "",
        "B1 last season per game; B2 this season to date; B3 last 8 games; B4 share of team volume x team volume x",
        "position efficiency; B5 position and volume-band average. Each is a negative binomial around that mean.", ""]
    for market, (ycol, _, _) in BL.MARKETS.items():
        el = df.filter(BL.eligible(df, market))
        fit, tune = el.filter(pl.col("season").is_in(FIT)), el.filter(pl.col("season").is_in(TUNE))
        const = BL.fit(fit, market)
        mf, mt = BL.means(fit, market, const), BL.means(tune, market, const)
        yt, week = tune[ycol].to_numpy(), (tune["season"] * 100 + tune["week"]).to_numpy()
        rows, scores = {}, {}
        for b in BL.FALLBACK:
            r = S.fit_nb_size(mf[b], fit[ycol].to_numpy())
            cdf = S.nb_cdf(mt[b], r, KMAX[market])
            scores[b] = S.crps(cdf, yt)
            rows[b] = {"size": r, "crps": float(scores[b].mean()), "mae_of_mean": float(np.abs(mt[b] - yt).mean()),
                       **{f"cover{int(lv * 100)}": S.coverage(cdf, yt, lv) for lv in (0.5, 0.8, 0.9)}}
        best = min(rows, key=lambda b: rows[b]["crps"])
        for b in rows:
            if b != best:
                d, lo, hi = S.paired_bootstrap(scores[b] - scores[best], week)
                rows[b]["vs_best"] = [d, lo, hi]
        res["markets"][market] = {"n_fit": fit.height, "n_tune": tune.height, "weeks_tune": int(len(np.unique(week))),
                                  "chosen": best, "baselines": rows, "constants": const}
        L += [f"## {market}: {tune.height:,} tune rows ({fit.height:,} fit rows); chosen **{best}**", "",
              "| Baseline | NB size | CRPS | Worse than chosen by (95% interval) | Central 50% covers | 80% | 90% |", "|---|---|---|---|---|---|---|"]
        for b, v in rows.items():
            gap = "chosen" if b == best else f"{v['vs_best'][0]:+.3f} ({v['vs_best'][1]:+.3f} to {v['vs_best'][2]:+.3f})"
            L.append(f"| {b} | {v['size']:.1f} | {v['crps']:.3f} | {gap} | {v['cover50']:.1%} | {v['cover80']:.1%} | {v['cover90']:.1%} |")
        L.append("")
    L += ["## Reading", "",
          "- The chosen baseline per market is what each engine must beat on 2024-2025 (Test S).",
          "- Intervals are week-clustered bootstraps on the tune seasons and are descriptive: they say how clearly the chosen",
          "  baseline leads the others, not that it would lead on new seasons.",
          "- Coverage shows whether a single negative binomial is the right width. Discrete intervals cover slightly more",
          "  than their nominal level even when right."]
    OUT_JSON.write_text(json.dumps(res, indent=1) + "\n")
    OUT_MD.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
