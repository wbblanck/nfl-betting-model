# Engine B B-0.1 on the tune seasons

Written by `scripts/engine_b_tune.py`. Fitted on 2018-2021 (yardage tail scales on 2022-2023); every Test S row
of 2022-2023 forecast with 4,000 runs. This is tuning, not Test S: no 2024-2025 outcome and no price was read.

CRPS is in the stat's own units, lower is better; the interval is a week-clustered bootstrap. Coverage in
brackets is what a forecast that was exactly right would show.

| Market | Rows | Baseline | Baseline CRPS | Engine B CRPS | B minus baseline (95% interval) | Central 50% covers (if right) | 80% | 90% |
|---|---|---|---|---|---|---|---|---|
| pass_att | 1,089 | B5 | 6.189 | 5.200 | -0.988 (-1.169 to -0.813) | 56.9% (53.4%) | 85.2% (82.1%) | 92.1% (91.4%) |
| rush_att | 2,029 | B4 | 3.125 | 2.844 | -0.281 (-0.324 to -0.239) | 56.0% (56.6%) | 83.8% (84.1%) | 92.8% (92.5%) |
| rec | 4,738 | B4 | 1.221 | 1.194 | -0.027 (-0.035 to -0.019) | 63.7% (64.9%) | 87.9% (88.6%) | 95.0% (95.3%) |
| pass_yds | 1,089 | B3 | 53.601 | 41.911 | -11.690 (-13.692 to -9.774) | 50.5% (50.6%) | 81.5% (80.0%) | 91.1% (89.8%) |
| rush_yds | 2,029 | B3 | 18.554 | 17.004 | -1.550 (-1.778 to -1.301) | 52.6% (51.9%) | 82.8% (81.7%) | 91.6% (91.2%) |
| rec_yds | 4,738 | B4 | 17.150 | 16.213 | -0.937 (-1.066 to -0.802) | 55.0% (53.1%) | 85.0% (84.1%) | 93.4% (92.9%) |

## Family per market (chosen here, MODEL_SPECIFICATION 3.5)

| Market | Candidate | Engine B CRPS | Share of zeros, runs vs outcomes | Chosen |
|---|---|---|---|---|
| pass_att | nb | 5.411 | 0.2% vs 2.1% |  |
| pass_att | hurdle | 5.200 | 2.0% vs 2.1% | yes |
| rush_att | nb | 2.880 | 1.1% vs 3.6% |  |
| rush_att | hurdle | 2.844 | 3.0% vs 3.6% | yes |
| rec | nb | 1.199 | 7.8% vs 10.2% |  |
| rec | hurdle | 1.194 | 8.8% vs 10.2% | yes |
| pass_yds | quantile | 41.911 | 0.1% vs 3.1% | yes |
| pass_yds | quantile+zero | 42.145 | 2.5% vs 3.1% |  |
| rush_yds | quantile | 17.025 | 1.1% vs 4.3% |  |
| rush_yds | quantile+zero | 17.004 | 3.5% vs 4.3% | yes |
| rec_yds | quantile | 16.268 | 2.6% vs 10.6% |  |
| rec_yds | quantile+zero | 16.213 | 10.2% vs 10.6% | yes |

## Engine A on the same rows (reference, not a test)

| Market | Engine A CRPS | Engine B CRPS | B minus A |
|---|---|---|---|
| pass_att | 5.318 | 5.200 | -0.118 |
| rush_att | 2.897 | 2.844 | -0.053 |
| rec | 1.221 | 1.194 | -0.027 |
| pass_yds | 45.567 | 41.911 | -3.656 |
| rush_yds | 17.420 | 17.004 | -0.416 |
| rec_yds | 16.502 | 16.213 | -0.289 |

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

Mean of the runs minus mean of the outcomes: pass_att +0.25, rush_att +0.13, rec +0.09, pass_yds +3.62, rush_yds +0.99, rec_yds +1.15.
Share of zeros, runs vs outcomes: pass_att 2.0% vs 2.1%, rush_att 3.0% vs 3.6%, rec 8.8% vs 10.2%, pass_yds 0.1% vs 3.1%, rush_yds 3.5% vs 4.3%, rec_yds 10.2% vs 10.6%.

## Reading (limits of this comparison)

- These are the tune seasons: the family per market, the yardage tree settings (five tried, the shallowest kept)
  and the yardage tail scales were all chosen on them, so the gaps flatter Engine B, as they flatter Engine A in
  its own tune report. Only Test S on 2024-2025, run once on a frozen version, counts.
- What Engine B is told: earlier games and the game-day active list (through the share of the team's recent
  volume held by active players). Each forecast is conditional on the player taking a snap, as a prop is.
  The rows of a team-game are exactly its active list: on 2018-2023 every player who played had roster status
  ACT that week except 0.03% of 2020 rows, so the row set does not reveal who played.
- Not in this version: the dependence layer (Gaussian copula and box reconciliation, spec 3.4), random-effect
  terms (player and team effects come only through their trailing rates), touchdowns and interceptions
  (spec 3.3), pass_cmp and the combined markets. None of these changes a single market's forecast except
  the box reconciliation, which will be checked against this run when it is built.
- The hurdle's positive part is a negative binomial fitted on the positive rows, drawn with zeros redrawn; for
  these volumes a negative binomial puts almost no mass at zero, so the truncation changes little.
