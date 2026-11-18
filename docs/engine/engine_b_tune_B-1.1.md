# Engine B B-1.1 on the tune seasons

Written by `scripts/engine_b_tune.py`. Fitted on 2018-2021 (yardage tail scales on 2022-2023); every Test S row
of 2022-2023 forecast with 4,000 runs. This is tuning, not Test S: no 2024-2025 outcome and no price was read.

CRPS is in the stat's own units, lower is better; the interval is a week-clustered bootstrap. Coverage in
brackets is what a forecast that was exactly right would show.

| Market | Rows | Baseline | Baseline CRPS | Engine B CRPS | B minus baseline (95% interval) | Central 50% covers (if right) | 80% | 90% |
|---|---|---|---|---|---|---|---|---|
| pass_att | 1,089 | B5 | 6.189 | 5.208 | -0.981 (-1.166 to -0.801) | 57.2% (54.1%) | 84.8% (82.4%) | 92.3% (91.4%) |
| pass_yds | 1,089 | B3 | 53.601 | 42.039 | -11.562 (-13.600 to -9.551) | 51.2% (51.2%) | 82.6% (80.5%) | 92.0% (90.3%) |
| rush_att | 2,029 | B4 | 3.125 | 2.845 | -0.280 (-0.323 to -0.238) | 56.0% (56.5%) | 84.0% (83.9%) | 92.8% (92.5%) |
| rush_yds | 2,029 | B3 | 18.554 | 17.009 | -1.545 (-1.768 to -1.300) | 54.0% (52.0%) | 83.3% (82.6%) | 91.9% (91.7%) |
| rec | 4,738 | B4 | 1.221 | 1.194 | -0.027 (-0.034 to -0.019) | 63.3% (64.6%) | 88.0% (88.4%) | 95.4% (95.3%) |
| rec_yds | 4,738 | B4 | 17.150 | 16.223 | -0.927 (-1.052 to -0.794) | 57.3% (54.8%) | 86.6% (85.8%) | 93.8% (93.9%) |

## Dependence layer (MODEL_SPECIFICATION 3.4)

The table above scores the joint runs: the copula, then the box reconciliation. Drawn each on its own, the
markets score as follows (the copula leaves each marginal exactly as it is; only the reconciliation can move
a market's score):

| Market | Each market on its own | Joint, reconciled (used) | Change | Joint with the quarterback caps (not used) | Change |
|---|---|---|---|---|---|
| pass_att | 5.215 | 5.208 | -0.007 | 5.208 | -0.007 |
| pass_yds | 42.155 | 42.039 | -0.116 | 42.039 | -0.116 |
| rush_att | 2.845 | 2.845 | -0.000 | 2.845 | -0.000 |
| rush_yds | 17.019 | 17.009 | -0.010 | 17.009 | -0.010 |
| rec | 1.195 | 1.194 | -0.000 | 1.204 | +0.009 |
| rec_yds | 16.228 | 16.223 | -0.005 | 16.511 | +0.283 |

Values changed out of 62,848,000 simulated values. Used (a player's yards need his own catch, carry or attempt): yards without volume 918,729. With the caps: yards without volume 971,448, receiving yards over passing 4,327,683, catches over attempts 803,218.

The caps are not used: they assume the forecast quarterback threw every pass. In 1,089 real 2022-2023
team-games with a forecast quarterback, the forecast receivers gained more yards than he threw for in 11.6% and caught more passes than he attempted in 7.4%
(another quarterback threw some), and the caps made the receiving scores worse. The spec's full reconciliation
needs a team passing total, which Engine B does not forecast.

Correlations of the normal scores (where each outcome fell in its own forecast), by pair kind, as fitted on
2018-2021 and as measured on 2022-2023. Kinds with at least 300 fit pairs:

| Pair kind | Fit 2018-2021 | Pairs | Tune 2022-2023 | Pairs |
|---|---|---|---|---|
| pass_att|pass_yds|same | +0.672 | 2,099 | +0.703 | 1,089 |
| pass_att|rec_yds|other | +0.186 | 9,711 | +0.174 | 4,774 |
| pass_att|rec|other | +0.252 | 9,711 | +0.248 | 4,774 |
| pass_att|rush_att_qb|same | +0.062 | 395 | +0.132 | 266 |
| pass_att|rush_att|other | -0.133 | 3,433 | -0.095 | 1,787 |
| pass_att|rush_yds_qb|same | +0.083 | 395 | +0.150 | 266 |
| pass_att|rush_yds|other | -0.173 | 3,433 | -0.133 | 1,787 |
| pass_yds|rec_yds|other | +0.296 | 9,711 | +0.291 | 4,774 |
| pass_yds|rec|other | +0.245 | 9,711 | +0.242 | 4,774 |
| pass_yds|rush_att_qb|same | +0.052 | 395 | +0.083 | 266 |
| pass_yds|rush_att|other | -0.060 | 3,433 | -0.046 | 1,787 |
| pass_yds|rush_yds_qb|same | +0.018 | 395 | +0.078 | 266 |
| pass_yds|rush_yds|other | -0.100 | 3,433 | -0.082 | 1,787 |
| rec_yds|rec_yds|other | -0.008 | 18,964 | -0.011 | 8,759 |
| rec_yds|rush_att_qb|other | -0.031 | 1,800 | -0.045 | 1,131 |
| rec_yds|rush_att|other | -0.030 | 14,181 | -0.025 | 6,937 |
| rec_yds|rush_att|same | +0.110 | 1,537 | +0.111 | 775 |
| rec_yds|rush_yds_qb|other | -0.028 | 1,800 | -0.020 | 1,131 |
| rec_yds|rush_yds|other | -0.047 | 14,181 | -0.034 | 6,937 |
| rec_yds|rush_yds|same | +0.071 | 1,537 | +0.047 | 775 |
| rec|rec_yds|other | +0.004 | 37,928 | +0.001 | 17,518 |
| rec|rec_yds|same | +0.793 | 9,598 | +0.786 | 4,738 |
| rec|rec|other | +0.023 | 18,964 | +0.027 | 8,759 |
| rec|rush_att_qb|other | -0.050 | 1,800 | -0.065 | 1,131 |
| rec|rush_att|other | -0.052 | 14,181 | -0.047 | 6,937 |
| rec|rush_att|same | +0.090 | 1,537 | +0.085 | 775 |
| rec|rush_yds_qb|other | -0.033 | 1,800 | -0.041 | 1,131 |
| rec|rush_yds|other | -0.076 | 14,181 | -0.056 | 6,937 |
| rec|rush_yds|same | +0.042 | 1,537 | +0.016 | 775 |
| rush_att_qb|rush_yds_qb|same | +0.739 | 401 | +0.692 | 271 |
| rush_att_qb|rush_yds|other | +0.085 | 662 | +0.035 | 447 |
| rush_att|rush_att_qb|other | +0.055 | 662 | +0.072 | 447 |
| rush_att|rush_att|other | -0.162 | 1,576 | -0.152 | 770 |
| rush_att|rush_yds_qb|other | -0.007 | 662 | +0.029 | 447 |
| rush_att|rush_yds|other | -0.078 | 3,152 | -0.074 | 1,540 |
| rush_att|rush_yds|same | +0.784 | 3,388 | +0.780 | 1,758 |
| rush_yds|rush_yds_qb|other | +0.018 | 662 | +0.023 | 447 |
| rush_yds|rush_yds|other | -0.010 | 1,576 | +0.020 | 770 |

## Family per market (chosen here, MODEL_SPECIFICATION 3.5)

| Market | Candidate | Engine B CRPS | Share of zeros, runs vs outcomes | Chosen |
|---|---|---|---|---|
| pass_att | nb | 5.442 | 0.2% vs 2.1% |  |
| pass_att | hurdle | 5.215 | 2.1% vs 2.1% | yes |
| rush_att | nb | 2.879 | 1.1% vs 3.6% |  |
| rush_att | hurdle | 2.845 | 2.9% vs 3.6% | yes |
| rec | nb | 1.199 | 7.8% vs 10.2% |  |
| rec | hurdle | 1.195 | 8.7% vs 10.2% | yes |
| pass_yds | quantile | 42.155 | 0.1% vs 3.1% | yes |
| pass_yds | quantile+zero | 42.193 | 2.5% vs 3.1% |  |
| rush_yds | quantile | 17.050 | 1.1% vs 4.3% |  |
| rush_yds | quantile+zero | 17.019 | 3.5% vs 4.3% | yes |
| rec_yds | quantile | 16.285 | 2.6% vs 10.6% |  |
| rec_yds | quantile+zero | 16.228 | 10.2% vs 10.6% | yes |

## Engine A on the same rows (reference, not a test)

| Market | Engine A CRPS | Engine B CRPS | B minus A |
|---|---|---|---|
| pass_att | 5.318 | 5.208 | -0.110 |
| pass_yds | 45.567 | 42.039 | -3.528 |
| rush_att | 2.897 | 2.845 | -0.052 |
| rush_yds | 17.420 | 17.009 | -0.411 |
| rec | 1.221 | 1.194 | -0.026 |
| rec_yds | 16.502 | 16.223 | -0.279 |

Engine A's figures are from its own tune run (`data/backtests/engine_a_v01.json`, 2,000 runs per game) on the
same Test S rows. No per-row comparison is made here; A versus B is reported, never a pass or fail.

## Fitted

- attempts: negative binomial on 2,099 fit rows (converged: True); size by position QB 18.8, RB 5.0, WR 5.0, TE 17.0; size multiplier per unit of role instability 0.02.
- carries: negative binomial on 3,789 fit rows (converged: True); size by position QB 8.9, RB 7.6, WR 4.7, TE 8.6; size multiplier per unit of role instability 0.18.
- targets: negative binomial on 9,598 fit rows (converged: True); size by position QB 5.0, RB 8.2, WR 13.5, TE 15.6; size multiplier per unit of role instability 0.13.
- Catches: beta-binomial, prior weight m = 160 targets, concentration kappa = 80; position catch rates QB 0.000, RB 0.769, WR 0.636, TE 0.674.
- pass_yds tails: upper scale 0.38 x (q95 - q75) from 45 rows above q95 (4.1%); lower width 0.72 x (q25 - q05) from 55 rows below q05 (5.1%).
- rush_yds tails: upper scale 0.57 x (q95 - q75) from 95 rows above q95 (4.7%); lower width 0.64 x (q25 - q05) from 110 rows below q05 (5.4%).
- rec_yds tails: upper scale 0.52 x (q95 - q75) from 217 rows above q95 (4.6%); lower width 0.48 x (q25 - q05) from 199 rows below q05 (4.2%).
- Quantile crossings before / after rearrangement: pass_yds 0 / 0, rush_yds 0 / 0, rec_yds 0 / 0.

Mean of the runs minus mean of the outcomes: pass_att +0.23, pass_yds +2.94, rush_att +0.12, rush_yds +0.90, rec +0.10, rec_yds +0.94.
Share of zeros, runs vs outcomes: pass_att 2.1% vs 2.1%, pass_yds 2.1% vs 3.1%, rush_att 3.0% vs 3.6%, rush_yds 5.3% vs 4.3%, rec 8.7% vs 10.2%, rec_yds 13.8% vs 10.6%.

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
