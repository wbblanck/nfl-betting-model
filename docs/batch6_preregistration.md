# Batch 6: key-number margins around the market line: Pre-registration (2026-11-08)

Requested by Will (2026-11-08, "Sure" to writing up the market-centered key-number test that batch 5 named as a new
hypothesis). Committed before the weights are fit and before any 2007-2015 or 2021 margin is compared with any model
in this batch. Code: `src/nflbet/ats/batch6.py`, `scripts/batch6.py`, tests `tests/test_batch6.py`.

## Why
Batch 5's K1 put key-number weights on Elo's margin and got the clumps right (14.3% on 3 against 15.2% actual), but
Elo's mean made its cover calls worse than a coin flip. The practical use is different: centered on the market's own
number, do the weights price a line that is **not** the market's (a pool line, a stale opener, a bought half point)
and the chance of a push better than a smooth curve does? Both models below share the market's center, so any gain
comes only from the weights.

## Samples
- **Two eras, split by the 2015 extra-point change** (margins of 1, 2, 8 and so on changed with it, so weights are
  fit within an era):
  - Older: **fit 1999-2006, test 2007-2014.**
  - Newer: **fit 2016-2020, test 2015 and 2021.**
- 2022-2025 are not used: batch 5's margin table on those seasons is where this idea came from.
- Disclosed: 2007-2015 held batch 1's tests (Elo and the opener) and 2021 the ATS rating's exploration (2016-2021).
  **These seasons are not fresh for this idea:** NFL_ATS's `keynum` estimator (its docs/keynumber_preregistration.md
  and keynumber_report.md), a market-centered key-number model with weights on |margin| 0-20, was tested
  walk-forward on 2007-2021 against SBRO openers and failed its rule against NFL_ATS's "shifted empirical"
  estimator (log loss 0.6879 vs 0.6862, 3,722 games). This test differs (the comparison is a smooth normal with the
  same center, weights only at 3, 6, 7, 10, 14, and a separate push test), but its result is a second look at
  seasons that already held a close relative, not a fresh confirmation. Will chose this sample after that was
  pointed out (2026-11-09). The sample was chosen (Will, 2026-11-08)
  after a power check on synthetic data showed 2015 and 2021 alone would catch an effect of batch 5's size only
  about 20% of the time; no real data was read for that choice.
- Lines: center c = nflverse `spread_line` (closing), regular season, all weeks. Off-market line L = SBRO opening
  spread (`home_open` in `data/odds/sbro_nfl_games.csv`, same sign), games with `sign_flag` false only. SBRO does not
  say which book its opener is from; here it stands for "a number a little away from the market", which is all the
  test needs.
- Sign: positive = home favored. Home covers L when margin > L, pushes when margin = L.

## Models
- **N (smooth):** P(margin = m) ∝ φ((m − c)/σ_N) for m in −60..60. σ_N by maximum likelihood on the era's fit
  seasons.
- **K2 (key numbers):** P(margin = m) ∝ φ((m − c)/σ) · w_|m|, the batch 5 K1 form with the close as center, but
  with weights only at the named key numbers **3, 6, 7, 10 and 14** (all others 1). The power check showed that
  K1's 41 free weights add enough noise to cost most of the power. w_k = actual share of |margin| = k over the
  share N gives, then σ refit once with the weights fixed. Frozen per era in `data/backtests/batch6_constants.json`
  before the test runs.

## Tests (family of 2, Holm at 0.05; week-clustered bootstrap over season-weeks, 2,000 draws; one-sided)
- **P1, a line away from the market:** test games where the SBRO opener differs from the close. Outcome against the
  opener: home covers, push (only possible at a whole number), or away covers. Per game
  d = log P_K2(outcome) − log P_N(outcome). Pass: interval above 0.
- **P2, a push at the market's number:** test games whose close is a whole number. Outcome: push or not. d as in
  P1. Pass: interval above 0.
- Holm: order the two p values (share of draws ≤ 0); compare with 0.05/2, then 0.05, stopping at the first failure.
  The interval reported for each test is at its Holm level.

## Power, stated in advance
Synthetic check (planted weights 2.5 on 3 and 1.8 on 7, centers shaped like real closes, weights fit on 1,300
games): about 2,700 test games catch P1 about 65% of the time and P2 about 50%. Two seasons alone: about 20%. The
fit file reports the per-game SD of d on the fit seasons before the test runs. A failure would not show the weights
are useless, only that this sample cannot show it.

## Known answers first (synthetic data, before any real output)
1. Hand case: center 3, σ 13, only w_3 = 2 (all else 1): P(push at 3) and P(home covers 3.5) equal a direct sum
   over the pmf, and the three outcome probabilities at a whole-number line sum to 1.
2. At a half-point line both models give P(push) = 0, and K2 with all w = 1 gives exactly N.
3. Planted signal: margins drawn from K2 with w_3 = 2.5 and w_7 = 1.8; the fit recovers w_3 within 25% and leaves
   w_5 at 1; on 2,700 games P1 passes in at least 10 of 20 runs and P2 in at least 6 of 20.
4. Null: margins drawn from N; P2 passes in at most 6 of 60 runs at the 0.025 level (weights fit on separate
   synthetic games).

## Descriptive only
Actual push rate at whole-number closes against N and K2 (overall and at 3, 7); the share of P1 games whose opener
and close sit on opposite sides of 3 or 7; under K2, the cover probability at 2.5, 3 and 3.5 around a close of 3,
and the break-even price for buying a half point off 3 and off 7, both at the newer era's weights; P1 and P2 by era.
