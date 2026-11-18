# Engine B B-1.0 on the tune seasons

Written by `scripts/engine_b_tune.py`. Fitted on 2018-2021 (yardage tail scales on 2022-2023); every Test S row
of 2022-2023 forecast with 4,000 runs. This is tuning, not Test S: no 2024-2025 outcome and no price was read.

CRPS is in the stat's own units, lower is better; the interval is a week-clustered bootstrap. Coverage in
brackets is what a forecast that was exactly right would show.

| Market | Rows | Baseline | Baseline CRPS | Engine B CRPS | B minus baseline (95% interval) | Central 50% covers (if right) | 80% | 90% |
|---|---|---|---|---|---|---|---|---|
| pass_att | 1,089 | B5 | 6.189 | 5.194 | -0.994 (-1.175 to -0.819) | 57.4% (54.2%) | 85.1% (82.3%) | 91.9% (91.4%) |
| pass_yds | 1,089 | B3 | 53.601 | 41.813 | -11.789 (-13.775 to -9.867) | 51.4% (51.1%) | 81.9% (80.5%) | 91.9% (90.2%) |
| rush_att | 2,029 | B4 | 3.125 | 2.844 | -0.281 (-0.323 to -0.238) | 56.0% (56.6%) | 84.0% (83.9%) | 92.7% (92.5%) |
| rush_yds | 2,029 | B3 | 18.554 | 17.000 | -1.554 (-1.781 to -1.309) | 53.8% (52.0%) | 83.1% (82.6%) | 91.8% (91.8%) |
| rec | 4,738 | B4 | 1.221 | 1.194 | -0.027 (-0.035 to -0.019) | 63.8% (64.9%) | 87.9% (88.4%) | 95.1% (95.2%) |
| rec_yds | 4,738 | B4 | 17.150 | 16.210 | -0.940 (-1.070 to -0.803) | 57.4% (54.9%) | 86.3% (85.7%) | 94.0% (93.9%) |

## Dependence layer (MODEL_SPECIFICATION 3.4)

The table above scores the joint runs: the copula, then the box reconciliation. Drawn each on its own, the
markets score as follows (the copula leaves each marginal exactly as it is; only the reconciliation can move
a market's score):

| Market | Each market on its own | Joint, reconciled (used) | Change | Joint with the quarterback caps (not used) | Change |
|---|---|---|---|---|---|
| pass_att | 5.202 | 5.194 | -0.008 | 5.194 | -0.008 |
| pass_yds | 41.921 | 41.813 | -0.109 | 41.813 | -0.109 |
| rush_att | 2.845 | 2.844 | -0.000 | 2.844 | -0.000 |
| rush_yds | 17.011 | 17.000 | -0.012 | 17.000 | -0.012 |
| rec | 1.194 | 1.194 | -0.000 | 1.204 | +0.009 |
| rec_yds | 16.214 | 16.210 | -0.004 | 16.505 | +0.291 |

Values changed out of 62,848,000 simulated values. Used (a player's yards need his own catch, carry or attempt): yards without volume 923,868. With the caps: yards without volume 976,188, receiving yards over passing 4,292,037, catches over attempts 793,086.

The caps are not used: they assume the forecast quarterback threw every pass. In 1,089 real 2022-2023
team-games with a forecast quarterback, the forecast receivers gained more yards than he threw for in 11.6% and caught more passes than he attempted in 7.4%
(another quarterback threw some), and the caps made the receiving scores worse. The spec's full reconciliation
needs a team passing total, which Engine B does not forecast.

Correlations of the normal scores (where each outcome fell in its own forecast), by pair kind, as fitted on
2018-2021 and as measured on 2022-2023. Kinds with at least 300 fit pairs:

| Pair kind | Fit 2018-2021 | Pairs | Tune 2022-2023 | Pairs |
|---|---|---|---|---|
| pass_att|pass_yds|same | +0.675 | 2,099 | +0.702 | 1,089 |
| pass_att|rec_yds|other | +0.187 | 9,711 | +0.175 | 4,774 |
| pass_att|rec|other | +0.253 | 9,711 | +0.249 | 4,774 |
| pass_att|rush_att_qb|same | +0.063 | 395 | +0.134 | 266 |
| pass_att|rush_att|other | -0.131 | 3,433 | -0.095 | 1,787 |
| pass_att|rush_yds_qb|same | +0.084 | 395 | +0.150 | 266 |
| pass_att|rush_yds|other | -0.172 | 3,433 | -0.132 | 1,787 |
| pass_yds|rec_yds|other | +0.298 | 9,711 | +0.293 | 4,774 |
| pass_yds|rec|other | +0.245 | 9,711 | +0.245 | 4,774 |
| pass_yds|rush_att_qb|same | +0.051 | 395 | +0.092 | 266 |
| pass_yds|rush_att|other | -0.058 | 3,433 | -0.041 | 1,787 |
| pass_yds|rush_yds_qb|same | +0.018 | 395 | +0.081 | 266 |
| pass_yds|rush_yds|other | -0.101 | 3,433 | -0.075 | 1,787 |
| rec_yds|rec_yds|other | -0.008 | 18,964 | -0.012 | 8,759 |
| rec_yds|rush_att_qb|other | -0.031 | 1,800 | -0.047 | 1,131 |
| rec_yds|rush_att|other | -0.031 | 14,181 | -0.026 | 6,937 |
| rec_yds|rush_att|same | +0.116 | 1,537 | +0.115 | 775 |
| rec_yds|rush_yds_qb|other | -0.026 | 1,800 | -0.021 | 1,131 |
| rec_yds|rush_yds|other | -0.048 | 14,181 | -0.036 | 6,937 |
| rec_yds|rush_yds|same | +0.077 | 1,537 | +0.050 | 775 |
| rec|rec_yds|other | +0.004 | 37,928 | +0.001 | 17,518 |
| rec|rec_yds|same | +0.792 | 9,598 | +0.785 | 4,738 |
| rec|rec|other | +0.021 | 18,964 | +0.026 | 8,759 |
| rec|rush_att_qb|other | -0.050 | 1,800 | -0.066 | 1,131 |
| rec|rush_att|other | -0.052 | 14,181 | -0.047 | 6,937 |
| rec|rush_att|same | +0.093 | 1,537 | +0.089 | 775 |
| rec|rush_yds_qb|other | -0.031 | 1,800 | -0.043 | 1,131 |
| rec|rush_yds|other | -0.076 | 14,181 | -0.057 | 6,937 |
| rec|rush_yds|same | +0.045 | 1,537 | +0.018 | 775 |
| rush_att_qb|rush_yds_qb|same | +0.739 | 401 | +0.691 | 271 |
| rush_att_qb|rush_yds|other | +0.085 | 662 | +0.037 | 447 |
| rush_att|rush_att_qb|other | +0.055 | 662 | +0.072 | 447 |
| rush_att|rush_att|other | -0.162 | 1,576 | -0.151 | 770 |
| rush_att|rush_yds_qb|other | -0.007 | 662 | +0.030 | 447 |
| rush_att|rush_yds|other | -0.078 | 3,152 | -0.073 | 1,540 |
| rush_att|rush_yds|same | +0.784 | 3,388 | +0.780 | 1,758 |
| rush_yds|rush_yds_qb|other | +0.018 | 662 | +0.024 | 447 |
| rush_yds|rush_yds|other | -0.010 | 1,576 | +0.021 | 770 |

## Family per market (chosen here, MODEL_SPECIFICATION 3.5)

| Market | Candidate | Engine B CRPS | Share of zeros, runs vs outcomes | Chosen |
|---|---|---|---|---|
| pass_att | nb | 5.413 | 0.2% vs 2.1% |  |
| pass_att | hurdle | 5.202 | 2.0% vs 2.1% | yes |
| rush_att | nb | 2.879 | 1.1% vs 3.6% |  |
| rush_att | hurdle | 2.845 | 3.0% vs 3.6% | yes |
| rec | nb | 1.199 | 7.8% vs 10.2% |  |
| rec | hurdle | 1.194 | 8.8% vs 10.2% | yes |
| pass_yds | quantile | 41.921 | 0.1% vs 3.1% | yes |
| pass_yds | quantile+zero | 42.150 | 2.5% vs 3.1% |  |
| rush_yds | quantile | 17.032 | 1.1% vs 4.3% |  |
| rush_yds | quantile+zero | 17.011 | 3.5% vs 4.3% | yes |
| rec_yds | quantile | 16.270 | 2.6% vs 10.6% |  |
| rec_yds | quantile+zero | 16.214 | 10.2% vs 10.6% | yes |

## Engine A on the same rows (reference, not a test)

| Market | Engine A CRPS | Engine B CRPS | B minus A |
|---|---|---|---|
| pass_att | 5.318 | 5.194 | -0.124 |
| pass_yds | 45.567 | 41.813 | -3.755 |
| rush_att | 2.897 | 2.844 | -0.052 |
| rush_yds | 17.420 | 17.000 | -0.421 |
| rec | 1.221 | 1.194 | -0.027 |
| rec_yds | 16.502 | 16.210 | -0.292 |

Engine A's figures are from its own tune run (`data/backtests/engine_a_v01.json`, 2,000 runs per game) on the
same Test S rows. No per-row comparison is made here; A versus B is reported, never a pass or fail.

## Fitted

- attempts: negative binomial on 2,099 fit rows (converged: True); size by position QB 19.1, RB 5.0, WR 5.0, TE 17.9; size multiplier per unit of role instability 0.02.
- carries: negative binomial on 3,789 fit rows (converged: True); size by position QB 8.9, RB 7.6, WR 4.7, TE 8.6; size multiplier per unit of role instability 0.18.
- targets: negative binomial on 9,598 fit rows (converged: True); size by position QB 5.0, RB 8.4, WR 13.7, TE 16.2; size multiplier per unit of role instability 0.13.
- Catches: beta-binomial, prior weight m = 160 targets, concentration kappa = 80; position catch rates QB 0.000, RB 0.769, WR 0.636, TE 0.674.
- pass_yds tails: upper scale 0.40 x (q95 - q75) from 43 rows above q95 (3.9%); lower width 0.67 x (q25 - q05) from 54 rows below q05 (5.0%).
- rush_yds tails: upper scale 0.56 x (q95 - q75) from 98 rows above q95 (4.8%); lower width 0.65 x (q25 - q05) from 111 rows below q05 (5.5%).
- rec_yds tails: upper scale 0.52 x (q95 - q75) from 215 rows above q95 (4.5%); lower width 0.48 x (q25 - q05) from 203 rows below q05 (4.3%).
- Quantile crossings before / after rearrangement: pass_yds 0 / 0, rush_yds 0 / 0, rec_yds 0 / 0.

Mean of the runs minus mean of the outcomes: pass_att +0.24, pass_yds +2.90, rush_att +0.12, rush_yds +0.89, rec +0.09, rec_yds +0.87.
Share of zeros, runs vs outcomes: pass_att 2.0% vs 2.1%, pass_yds 2.1% vs 3.1%, rush_att 3.0% vs 3.6%, rush_yds 5.3% vs 4.3%, rec 8.8% vs 10.2%, rec_yds 13.9% vs 10.6%.

## Reading (limits of this comparison)

- These are the tune seasons: the family per market, the yardage tree settings (five tried, the shallowest kept)
  and the yardage tail scales were all chosen on them, so the gaps flatter Engine B, as they flatter Engine A in
  its own tune report. Only Test S on 2024-2025, run once on a frozen version, counts.
- What Engine B is told: earlier games and the game-day active list (through the share of the team's recent
  volume held by active players). Each forecast is conditional on the player taking a snap, as a prop is.
  The rows of a team-game are exactly its active list: on 2018-2023 every player who played had roster status
  ACT that week except 0.03% of 2020 rows, so the row set does not reveal who played.
- The family per market is chosen on runs drawn market by market (which give the same marginals as the joint
  runs before reconciliation).
- The copula covers players of one team in the forecast set. Not modelled: the link between the two offenses
  of a game, backs with the game margin (Engine B has no margin variable), receivers outside the forecast set.
- Not in this version: random-effect terms (player and team effects come only through their trailing rates),
  touchdowns and interceptions (spec 3.3), pass_cmp and the combined markets.
- The hurdle's positive part is a negative binomial fitted on the positive rows, drawn with zeros redrawn; for
  these volumes a negative binomial puts almost no mass at zero, so the truncation changes little.
