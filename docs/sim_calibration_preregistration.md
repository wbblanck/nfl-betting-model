# Simulator Calibration: Pre-registration (2026-10-09)

Requested by Will after docs/accuracy_eval.md found the simulator overconfident in every market (calibration
slope 0.37-0.79 in 2021-2023). Committed before the correction is fitted or scored (script:
`scripts/sim_calibration.py`, committed with this file). S1 and the live tracker are unchanged by this test; a
passing correction would still need its own decision before it touches any live record.

## Correction
Per market m: p' = sigmoid(a_m + b_m * logit(p)), p clipped to [0.01, 0.99]; (a_m, b_m) by maximum likelihood.

## Fit (2021-2023 only)
The rows of the accuracy test (docs/accuracy_preregistration.md: prop-type player-games, simulator P(over) at the
pseudo-line = previous-5-game average rounded down + 0.5). No 2024-2026 data is used to fit.

## Test (held out for the correction: 2024 and 2025)
Every screened DraftKings over/under in the nine S1 markets, final Action Network lines, pushes dropped, as
docs/sim_eval.txt: simulator P(over DK line) raw vs corrected, outcome = over. (2024 is the simulator's own fit
season but was not used for the correction.)
- **Primary:** log loss corrected minus raw, 2024 and 2025 pooled; player-clustered bootstrap (4,000 resamples,
  seed 7), two-sided 95%. **Pass** if the interval lies entirely below 0 **and** the 2025 point estimate is below 0.
- Reported, not tested: per season and per market; calibration by decile; DraftKings de-vigged log loss for
  reference; and, descriptively, what S1 would have done on 2024-25 with the corrected simulator in its simulator
  vote (n, win, ROI). That last item is exploration on seasons S1 was built on and decides nothing.

"The correction does not help" is a valid result.
