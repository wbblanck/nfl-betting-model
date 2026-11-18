"""Seed re-check of the Engine A event layer, run once under the rule in docs/engine/seed_recheck.md (committed first).
Appends the result to that file and writes data/backtests/engine_a_seed_recheck.json; refuses to run twice."""
import json
import sys

import numpy as np
import polars as pl

import engine_a_events as X
import engine_a_tune as T
from nflbet.config import ROOT
from nflbet.engine.data import nflverse as N
from nflbet.engine.replication import events as EV

RUNS, GAMES, BASES = 20000, 40, (30, 40)
LINES = {"tds": 0.5, "passing_tds": 1.5, "passing_interceptions": 0.5, "long_rec": 19.5, "long_rush": 11.5, "long_cmp": 39.5,
         "pass_rush_yds": 250.5, "rush_rec_yds": 50.5}
DOC, OUT = ROOT / "docs" / "engine" / "seed_recheck.md", ROOT / "data" / "backtests" / "engine_a_seed_recheck.json"


def main() -> int:
    if OUT.exists():
        print("REFUSED: the re-check has already been run")
        return 1
    P, _, _ = T.fitted()
    fit, pbp = X.frame(T.FIT)
    yards, flags = EV.pools(pbp.filter(pl.col("season").is_in(T.FIT)), N.read("players"))
    sums, ptab = EV.tables(yards, flags, seed=0)
    h_fit = X.hist_table(T.FIT)
    EVp = EV.fit(fit.filter(pl.col("played")).join(h_fit, on=["player_id", "game_id"], how="left").fill_null(0), flags)
    tune, _ = X.frame(T.TUNE)
    h_tune = X.hist_table(T.TUNE)
    d, _, e1, _, _, _ = X.run(P, EVp, sums, ptab, tune, h_tune, RUNS, seed_base=BASES[0], games=GAMES)
    _, _, e2, _, _, _ = X.run(P, EVp, sums, ptab, tune, h_tune, RUNS, seed_base=BASES[1], games=GAMES)

    def var1(e):
        n = e["_n_play"]
        return np.where((n >= 50) & (n < RUNS), 1 / np.maximum(n, 1) + 1 / RUNS, 1 / RUNS)
    checked, beyond, by_market = 0, [], {}
    for c, line in LINES.items():
        p1, p2 = (e1[c] > line).mean(axis=1), (e2[c] > line).mean(axis=1)
        p = (p1 + p2) / 2
        se = np.sqrt(np.maximum(p * (1 - p), 1e-12) * (var1(e1) + var1(e2)))
        keep = (p > 0) & (p < 1)
        z = np.where(keep, np.abs(p1 - p2) / se, 0.0)
        checked += int(keep.sum())
        by_market[c] = {"checked": int(keep.sum()), "beyond_4": int((z > 4).sum()), "largest_z": float(z.max())}
        for i in np.flatnonzero(z > 4):
            beyond.append({"market": c, "player_id": d["player_id"][int(i)], "game_id": d["game_id"][int(i)], "z": float(z[i]),
                           "p1": float(p1[i]), "p2": float(p2[i]), "runs_played": float(e1["_n_play"][i])})
    verdict = "PASS" if not beyond else "FAIL"
    res = {"runs": RUNS, "games": GAMES, "seed_bases": BASES, "checked": checked, "beyond_4": beyond, "by_market": by_market, "verdict": verdict}
    OUT.write_text(json.dumps(res, indent=1) + "\n")
    L = ["", f"Run 2026-11-16: {checked:,} probabilities, {len(beyond)} beyond 4 standard errors. **{verdict}.**", "",
         "| Market | Probabilities | Beyond 4 | Largest gap (standard errors) |", "|---|---|---|---|"]
    L += [f"| {c} | {r['checked']:,} | {r['beyond_4']} | {r['largest_z']:.2f} |" for c, r in by_market.items()]
    if beyond:
        L += ["", "Beyond 4: " + "; ".join(f"{b['market']} {b['player_id']} {b['game_id']} z {b['z']:.2f}" for b in beyond) + "."]
    with DOC.open("a") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
