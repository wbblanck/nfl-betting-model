# Batch 5: joint scores, key-number margins, simulator totals, early-season ratings: Pre-registration (2026-11-06)

Requested by Will (2026-11-06, "Yes" to running master-list items 1-4 as one batch: M2/M3, M4/M5, D3, B4/M9/M10).
Committed before any batch 5 model is fit and before the simulator's totals are compared with any line. Code:
`src/nflbet/ats/batch5.py`, `scripts/batch5.py`, tests `tests/test_batch5.py`.

## Why these
- Batch 3's touchdown/field-goal model treated the two teams as independent and put 5.6% of margins on 3 against
  15.2% actual. S1 adds a shared component; K1 models the margin itself with key-number weights.
- The simulator has produced a total for every game but it has never been compared with a totals line (D3).
- Elo is weakest early in the season; R1 starts it from the market, R2 is a ridge least-squares rating (M9). Glicko
  (M10) is left out: the Kalman rating already tested that idea (batch 1 H5, failed).

## Samples
- **Score and totals tests (S1, K1, D3): test 2022-2025**, regular season weeks 2-18, games with an nflverse closing
  spread (S1, K1: the batch 3 sample, 1,023 games) or closing total with both prices (D3). Fit 2016-2020.
  These seasons have held other tests (E1-E7, batch 3, batch 4); none of these three models has been run on them, and
  the simulator's totals have never been compared with a line on any season.
- **Rating tests (R1, R2): test 2005-2015**, regular season weeks 2-6 (early season only). Fit 2016-2020 weeks 2-6.
  These seasons held batch 1; neither rating has been run on them.
- Elo, NB and touchdown/field-goal constants stay frozen (`elo_constants.json`, `batch3_constants.json`).
- nflverse sign: positive = home favored. Home covers when margin > `spread_line`. Over wins when total > `total_line`.

## Models
- **S1 bivariate touchdowns (M2):** home touchdowns = X_h + X_0, away = X_a + X_0, with X_0 ~ Poisson(λ_0) shared and
  X_h, X_a Poisson with means λ_T,home − λ_0 and λ_T,away − λ_0 (batch 3's means, so each team's own distribution of
  touchdowns is unchanged). λ_0 = c_0 · L, capped below the smaller mean. Field goals, conversions and safeties as in
  batch 3, independent. c_0 ≥ 0 fit by maximum likelihood of the joint touchdown counts on 2016-2020. If the fit
  gives c_0 = 0, S1 is batch 3's model and is reported as such. Expectation stated now: a shared component narrows
  the margin but cannot by itself put extra weight on 3, so S1 may well fail.
- **K1 key-number margin (M4 + M5):** P(margin = m) ∝ φ((m − μ)/σ) · w_|m| for m in −60..60, μ = Elo's fair margin.
  w_k for k = 0..40 is the ratio, on 2016-2020, of the actual share of games with |margin| = k to the share the plain
  discretized normal gives (w = 1 beyond 40). Fit: σ by maximum likelihood with all w = 1, then w from that fit, then
  σ refit once with w fixed. Frozen before the test.
- **D3 simulator totals:** G3 simulator as frozen (seed 101, 1,000 runs per game; its 2022-2025 margin MAE must
  reproduce 9.983 first). Total = mean simulated total.
- **R1 market start (B4):** Elo as frozen, except that before each season's week 1 games each team's rating is moved
  so that Elo's week-1 fair margin equals the nflverse week-1 closing spread: the gap is split equally, half to each
  team, converted to Elo points by the local slope of the fair margin in d. Nothing else changes.
- **R2 ridge least-squares rating (M9):** before each week, ratings r minimise Σ (margin − (r_h − r_a + h))² over this
  season's games so far + λ Σ (r_t − ρ·r_t,last season end)². h, λ, ρ fit on 2016-2020 weeks 2-6 by MAE over a grid
  (h 0-3 by 0.25, λ 1-16 doubling, ρ 0-1 by 0.25). Last season's end ratings come from the same model run on the full
  previous season with λ at its fitted value. Forecast = r_h − r_a + h (h = 0 at neutral sites).

## Tests (family of 5, Holm at 0.05; week-clustered bootstrap, 2,000 draws; one-sided)
- **S1:** per game d = log P_S1(observed margin) − log P_NB(observed margin), 2022-2025. Pass: interval above 0.
- **K1:** per game d = log P_K1(observed margin) − log P_NB(observed margin), 2022-2025. Pass: interval above 0.
- **D3:** where |simulated total − total_line| ≥ 1.5, bet the simulator's side at the listed nflverse price
  (`over_odds`/`under_odds`); pushes return 0. Pass: n ≥ 100 bets in ≥ 30 weeks and the ROI interval above 0.
- **R1:** paired d = |Elo − margin| − |R1 − margin|, 2005-2015 weeks 2-6. Pass: interval above 0.
- **R2:** paired d = |Elo − margin| − |R2 − margin|, 2005-2015 weeks 2-6. Pass: interval above 0.
Holm: order the five p values (share of draws ≤ 0); compare with 0.05/5, 0.05/4, …, stopping at the first failure.

## Power, stated in advance
- S1, K1: batch 3's per-game SD of a log-probability difference was 0.229, so the standard error at 1,023 games is
  about 0.007.
- D3: one bet's profit has SD about 0.95 units; at 500 bets the ROI standard error is about 4.2%, so only an edge near
  +10% would be detected reliably.
- R1, R2: about 800 games in weeks 2-6 of 2005-2015. If the paired SD is near 3 points, the standard error is about
  0.1 points, so gains under about 0.25 points will usually be missed.

## Known answers first (synthetic data, before any real output)
1. S1 with c_0 = 0 gives exactly batch 3's margin distribution; with c_0 > 0 its margin distribution matches a
   200,000-draw Monte Carlo within 0.003 at every margin, and each team's own points distribution is unchanged.
2. S1's fit recovers a planted c_0 within 25% on synthetic joint touchdown counts.
3. K1 sums to 1; on synthetic margins with a planted 3x weight on |m| = 3 the fitted w_3 is within 20% of 3, and on
   margins drawn from a plain normal every fitted w_k for k ≤ 20 is within 0.4 of 1.
4. R1 hand case: a week-1 gap of +3 points moves the home team up and the away team down by the same Elo amount, and
   Elo's week-1 fair margin then equals the close within 0.05 points.
5. R2 recovers planted team strengths (correlation ≥ 0.9 after 6 weeks of a synthetic league with low noise) and a
   week's forecasts do not change when later weeks are deleted.
6. D3 grading: total 45 vs line 44.5 is an over win; 44 vs 44 is a push.

Descriptive only: share of margins on 3, 7, 10, 14 under each model; K1 and S1 cover log loss against the close; the
simulator's total MAE next to the closing total's; R1 and R2 MAE by week; D3 at 0.5 / 1 / 2 / 3-point gaps.
