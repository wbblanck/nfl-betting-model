# M20: anytime-valid e-value readouts for the live trackers: Pre-registration (2026-11-06)

Requested by Will (2026-11-06, batch 2 of the master list). Committed before 2026 week 10. **Descriptive readout
only:** it never replaces or changes a tracker's own registered verdict (S1, D1/D2, wind unders, props mix, ATS
tracker). Those are still judged by their own rules at season's end. Code: `src/nflbet/execution/evalues.py`,
`scripts/evalues.py`, tests `tests/test_evalues.py`.

## Why
Every weekly look at a tracker's running record is a peek. Ordinary p-values computed every week find a "significant"
streak far more often than 5% of the time. An e-process can be read after every game: the chance it ever reaches 20
when there is no edge is at most 5%, however often it is checked.

## Method
- For each graded bet i, in order of kickoff, u_i = profit per unit staked (the record's `units` column: win pays the
  price, loss −1, push or void 0). The null hypothesis is "no edge": each bet's expected profit, given everything
  before it, is ≤ 0.
- Betting e-process with a fixed mixture: E_t = mean over λ ∈ {0.025, 0.05, 0.1, 0.2} of Π_{i ≤ t} (1 + λ·u_i).
  Because u_i ≥ −1 and λ ≤ 0.2, every factor is positive. Each product is a nonnegative supermartingale under the
  null, so their average is too (Ville's inequality: P(sup E_t ≥ 1/α) ≤ α).
- Readout per tracker, refreshed with each grading run: bets so far, E_t, and the running maximum.
- Thresholds: E ≥ 20 is evidence at the 5% level for that tracker alone. Across the k trackers read together,
  Bonferroni: E ≥ 20·k.
- Trackers covered from week 10 (bets graded from week 10 onward start the product at 1): `ats_record_2026.csv`,
  `ats_yv_record_2026.csv`, `s1_record_2026.csv`, `s1pa_record_2026.csv`, `s1_yv_record_2026.csv`,
  `mix_record_2026.csv`, and the wind-unders record. Earlier weeks are shown as a separate, descriptive run.

## Known answers first
1. Hand case: bets +0.909 and −1 with λ = 0.1 give (1.0909)(0.9) = 0.98181.
2. Under the null (fair −110 coin, 52.38% wins, expected profit 0), the share of 2,000 simulated 500-bet sequences
   whose E ever reaches 20 is at most 5%.
3. With a planted 58% win rate at −110 (expected profit about +10.7%), E reaches 20 within 500 bets in most sequences.

## What it cannot do
It has little power on the sample sizes here (one season's bets). It detects only large edges quickly. A low E is
"no evidence yet", not "no edge".

## Addendum after the known-answer checks (2026-11-06, before any live readout)
Check 2 passed (1.95% of null sequences reached 20). Check 3 missed its bar: with a planted 58% at −110, E reached 20
within 500 bets in 50.0% of 300 sequences, not "most". The method is unchanged; this is its power, and it confirms
that a low readout this season means "no evidence yet".
