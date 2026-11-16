# Engine A event layer: seed re-check (rule fixed 2026-11-16, before the run)

Why: the two-seed gate in `docs/engine/engine_a_events.md` found 1 of 4,948 probabilities beyond 4 Monte Carlo
standard errors (largest 4.29) at 2,000 runs. Will agreed (2026-11-16) to one re-check with the rule written down
and committed before it runs. The first result stands as reported; both are reported.

Rule (committed before the run, not changed after it):
- Same 40 games (the first 40 of 2022-2023 in the script's order), same Engine A-1.0 and event-layer fit.
- Two new seed pairs not used before (bases 30 and 40), 20,000 runs each.
- Same probabilities at the same fixed lines (tds 0.5, passing_tds 1.5, passing_interceptions 0.5, long_rec 19.5,
  long_rush 11.5, long_cmp 39.5, pass_rush_yds 250.5, rush_rec_yds 50.5), probabilities strictly between 0 and 1.
- Same standard-error formula: per seed p(1 - p)(1/n + 1/runs) for a player resampled from the n runs he plays in
  (50 <= n < runs), p(1 - p)/runs otherwise.
- Same gate: PASS if every probability is within 4 standard errors; FAIL otherwise. No other threshold is applied.
- If FAIL with several probabilities beyond 4, look for a defect, starting with the resampling error formula.
- Run once: `python scripts/engine_a_seed_recheck.py`. Its result is appended below.

## Result
