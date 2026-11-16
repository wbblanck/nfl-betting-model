"""Test S for Engine B (docs/engine_preregistration.md): distribution accuracy on 2024-2025, once per frozen version.

  python scripts/engine_test_s_b.py --freeze      write the frozen record for the current version (no 2024-2025 data read)
  python scripts/engine_test_s_b.py --dry-run     run the whole test machinery on the TUNE seasons; writes nothing
  python scripts/engine_test_s_b.py --run-once    the test itself; refuses if this version already has a result, if
                                                  the frozen record does not match the code's parameters, or if the
                                                  working tree has uncommitted changes

Same procedure as Engine A's (scripts/engine_test_s.py): the frozen baselines, the Test S sample, 4,000 runs (here the
joint runs: copula and the box rule, as used), and per market the week-clustered bootstrap interval of (engine CRPS
- baseline CRPS) at two-sided level 0.05 / 6 / (versions of Engine B run so far, this one included). PASS when the
interval lies entirely below 0. No price is read.
"""
import hashlib
import json
import subprocess
import sys

import numpy as np
import polars as pl

import engine_b_tune as T
from nflbet.config import ROOT
from nflbet.engine.challenger import joint as J, model as M
from nflbet.engine.data import nflverse as N
from nflbet.engine.features import build as B

TEST, SIMS, MARKETS, SEED = (2024, 2025), 4000, 6, 7
FROZEN = ROOT / "data" / "backtests" / "engine_b_frozen.json"
RESULT = ROOT / "data" / "backtests" / f"engine_test_s_{M.VERSION}.json"
REPORT = ROOT / "docs" / "engine" / f"test_s_engine_{M.VERSION}.md"


def _round(x):
    """Floats to 10 significant digits: the copula's sums run over groups in no fixed order, which moves the last
    bits (about 1e-15) from one fit to the next."""
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_round(v) for v in x]
    if isinstance(x, float):
        return float(f"{x:.10g}")
    return x


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(_round(json.loads(json.dumps(obj, default=float))), sort_keys=True).encode()).hexdigest()


def fingerprint() -> tuple[dict, dict]:
    P = T.fitted()
    plain = {"scaler": {k: v.to_dict() for k, v in P["scaler"].items()}, "count": P["count"], "hurdle": P["hurdle"],
             "zero": P["zero"], "catch": P["catch"], "tails": P["tails"], "tails_nz": P["tails_nz"], "rho": P["rho"],
             "family": P["family"]}
    boosters = {f"{k}|{m}": hashlib.sha256(bytes(b.save_raw("json"))).hexdigest()
                for k in ("yards", "yards_nz") for m, b in sorted(P[k].items())}
    fp = {"version": M.VERSION, "fit_seasons": list(T.FIT), "tune_seasons": list(T.TUNE), "sims": SIMS, "seed": SEED,
          "params_sha256": digest(plain), "boosters_sha256": digest(boosters),
          "baselines_sha256": hashlib.sha256((ROOT / "data" / "backtests" / "engine_baselines.json").read_bytes()).hexdigest()}
    return fp, P


def versions_run() -> int:
    return len(list((ROOT / "data" / "backtests").glob("engine_test_s_B-*.json")))


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("--freeze", "--dry-run", "--run-once"):
        print(__doc__)
        return 2
    fp, P = fingerprint()
    if mode == "--freeze":
        fp["features_sha256_fit_tune"] = B.snapshot_hash(pl.read_parquet(N.DIR / "features" / "player_game.parquet")
                                                       .filter(pl.col("season").is_in([*T.FIT, *T.TUNE])))
        FROZEN.write_text(json.dumps(fp, indent=1) + "\n")
        print(json.dumps(fp, indent=1))
        return 0
    frozen = json.loads(FROZEN.read_text())
    same = all(frozen[k] == fp[k] for k in fp)
    seasons = T.TUNE if mode == "--dry-run" else TEST
    k = versions_run() + (0 if mode == "--dry-run" else 1)
    level = 0.05 / MARKETS / max(k, 1)
    if mode == "--run-once":
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        if RESULT.exists() or not same or dirty:
            print(f"REFUSED: result exists={RESULT.exists()}, frozen record matches={same}, uncommitted changes={bool(dirty)}")
            return 1
    df = T.load(seasons)
    base = json.loads((ROOT / "data" / "backtests" / "engine_baselines.json").read_text())
    runs, fixes = J.simulate(P, P["rho"], df, T.masks(df), SIMS, np.random.default_rng(SEED))
    markets = T.score(P, df, base, SIMS, level, runs=runs)
    for r in markets.values():
        r["verdict"] = "PASS" if r["diff"][2] < 0 else ("WORSE" if r["diff"][1] > 0 else "FAIL")
    label = f"{100 * (1 - level):.2f}% interval"
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    L = [f"# Test S: Engine {M.VERSION} on {seasons[0]}-{seasons[-1]}" + (" (DRY RUN on the tune seasons)" if mode == "--dry-run" else ""), "",
         "Pre-registration: docs/engine_preregistration.md. Written by `scripts/engine_test_s_b.py`.",
         f"Code at commit `{head[:10]}`; frozen record `data/backtests/engine_b_frozen.json` matches: {same}.",
         f"Fitted on {T.FIT[0]}-{T.FIT[-1]}, settings and tail scales chosen on {T.TUNE[0]}-{T.TUNE[-1]}; {SIMS:,} joint runs per team-game. No price was read.",
         "Box rule (a player's yards need his own catch, carry or attempt) changed "
         + ", ".join(f"{v:,} values ({k.replace('_', ' ')})" for k, v in fixes.items() if v) + ".",
         f"Versions of Engine B tested so far, this one included: {k}. Level per market: 0.05 / {MARKETS} / {max(k, 1)} = {level:.5f}.", "",
         *T.table(markets, label), "",
         "| Market | Verdict | Weeks | Pinball loss at 0.05 / 0.25 / 0.50 / 0.75 / 0.95 |", "|---|---|---|---|"]
    L += [f"| {m} | **{r['verdict']}** | {r['weeks']} | " + " / ".join(f"{r['pinball'][q]:.3f}" for q in ("0.05", "0.25", "0.5", "0.75", "0.95")) + " |"
          for m, r in markets.items()]
    L += ["", "PASS: the interval is entirely below 0 (the engine is better than the frozen baseline). FAIL: it is not.",
          "WORSE: the interval is entirely above 0. Coverage in brackets is what a forecast that was exactly right would show.",
          f"Passed {sum(r['verdict'] == 'PASS' for r in markets.values())} of {len(markets)} markets."]
    print("\n".join(L))
    if mode == "--run-once":
        RESULT.write_text(json.dumps({"fingerprint": fp, "commit": head, "seasons": list(seasons), "level": level, "versions_run": k,
                                      "box_rule_changes": fixes, "markets": markets}, indent=1, default=float) + "\n")
        REPORT.write_text("\n".join(L) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
