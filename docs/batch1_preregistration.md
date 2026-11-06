# Batch 1: Elo at the opener, market-anchored blend, Elo + QB, Kalman rating: Pre-registration (2026-11-06)

Requested by Will (2026-11-06, "Do it", master list rows A1, M15, M14, B1 + B3, B2 + M8). Committed before any Elo,
Kalman or blend output exists for 2005-2015 and before the SBRO lines are joined to any model output for those
seasons. Code: `src/nflbet/ats/kalman.py`, `scripts/batch1.py`, tests `tests/test_kalman.py`.

## Samples
- **Fit: 2016-2021** regular season (SBRO lines where a parameter needs the opener). Elo's K, home field and score
  model stay frozen from `data/backtests/elo_constants.json`; only the parameters named below are fit, all on 2016-2021.
- **Test: 2005-2015** regular season weeks 2-17 for margin tests (H4, H5); **2007-2015** weeks 2-17 for tests that need
  SBRO openers (H1-H3). No Elo or Kalman output has been computed on these seasons in this repo (Elo ran through them
  only as warm-up history, never evaluated). Disclosed: the EPA rating used SBRO 2008-2015 for its own opener test
  (docs/ats_clv.md); these models never have.
- Ratings run forward from 1999 using only games before each forecast, so fitting on later seasons leaks nothing into
  pre-game ratings. Risk disclosed: parameters fit on 2016-2021 may suit 2005-2015 worse (scoring and rules changed).
- Spread sign: nflverse/SBRO, positive = home favored; "Elo" = the frozen Elo + NB score model's fair home margin.
  SBRO has no prices: bets graded at −110. Pushes are no bet.

## Models
- **Elo:** frozen (K 25, home 35, regression 1/2, b 0.0853).
- **Elo + QB (B1, B3 folded in):** d += q·(qb_delta_home − qb_delta_away) (the simulator's starting-QB input,
  EPA/dropback, replacement level from the frozen personnel constants). Refit on 2016-2020 by win-probability log loss
  over q ∈ {0, 50, …, 1000} × c ∈ {1/4, 1/3, 1/2, 2/3, 3/4, 1} (K, H fixed). b refit by Poisson ML with the chosen
  q, c. qb_delta needs nflverse play-by-play from 1999.
- **Kalman (B2 + M8):** each team's strength θ is a hidden value. Prediction: margin = θ_home − θ_away + h (h = 0 at
  neutral sites), observation variance σ²_m. Between weeks each θ's variance grows by τ²_w (teams on bye included);
  between seasons θ ← ρ·θ and its variance ← ρ²·var + τ²_s. Update after each game by the Kalman gain on the
  observed margin. Starting strength 0, variance 49. Parameters (h, σ_m, τ_w, ρ, τ_s) fit on 2016-2020 by maximum
  likelihood of the margins (normal), starting the filter in 1999. Fair margin = θ_home − θ_away + h.
- **Blend (M14):** f = open + w·(Elo − open), w fit on 2016-2021 by least squares of margin on that form.

## Tests (family of 5, Holm at 0.05 family-wise; week-clustered bootstrap, 2,000 draws; one-sided)
- **H1 (A1) Elo at the opener:** where |Elo − open| ≥ 1.5, Elo's side against the SBRO opener at −110, 2007-2015.
  Pass: n ≥ 100 in ≥ 30 weeks and the ROI interval is above 0.
- **H2 (M15) line movement:** OLS of (close − open) on (Elo − open), 2007-2015. Pass: coefficient interval above 0.
- **H3 (M14) blend beats the opener:** paired d = |open − margin| − |f − margin|, 2007-2015. Pass: interval above 0.
- **H4 (B1) Elo + QB beats Elo:** paired d = |Elo − margin| − |EloQB − margin|, 2005-2015. Pass: interval above 0.
- **H5 (B2) Kalman beats Elo:** paired d = |Elo − margin| − |Kalman − margin|, 2005-2015. Pass: interval above 0.
Holm: order the five one-sided bootstrap p-values (share of draws ≤ 0), compare the smallest with 0.05/5, the next
with 0.05/4, and so on, stopping at the first that fails. Reported intervals are at each test's own Holm level.

## Power, stated in advance
- Paired MAE differences: the per-game SD of such differences was about 3.2 points for Elo vs the simulator on
  2022-2025 (data/backtests/elo_confirm_games.csv). With about 2,600 games in 2005-2015 that gives a standard error of
  about 0.06 points, so differences under about 0.2 points will usually be missed. More similar models (H4, H5) have
  smaller SDs and more power.
- H1: at −110 one bet's profit has SD about 0.95 units. With n bets the ROI standard error is about 0.95/√n (n = 1,000
  → 3.0%), so only an ROI near +9% (about 57% covers) would be detected reliably. A fail on H1 says "no evidence".

## Known answers first (synthetic data, before any real output for 2005-2015)
1. Kalman hand case: one game, both teams θ 0 with variance 49, h 0, σ_m 13, margin +10 → home θ moves by
   10·49/(98 + 169) = 1.835, away by −1.835.
2. Kalman no look-ahead: deleting a week and every later week leaves earlier forecasts unchanged.
3. Kalman planted signal: a +7 team in a synthetic 32-team season ends top 8 in ≥ 90% of 200 seasons (Elo scored
   86.5% on the same check, point differential 93.5%); in an all-equal league, the correlation of end ratings with the
   next season's results is within ±0.1 of 0.
4. Blend: on synthetic data with a known w, the fit recovers it within 0.05.
5. Kalman maximum likelihood recovers a planted τ_w and σ_m within 25% on a synthetic league.

Descriptive only: margin MAE of open, close, Elo, Elo + QB, Kalman, blend by season; H1 at 0.5 / 1 / 2 / 3 point
thresholds; cover rate vs the close for H1's bets. "Nothing passes" is a valid result.
