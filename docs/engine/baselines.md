# Baselines (engine phase 3, step 1)

Written by `scripts/engine_baselines.py`. Fitted on 2018-2021, compared on 2022-2023 (the tune seasons, where
choosing is allowed). No 2024-2025 outcome and no price was read. Lower CRPS is better; it is in the stat's own
units (attempts, catches, yards).

Rows: a player-game counts when the player had at least 2 of his last 3 games on record and, per game in them,
at least 15 pass attempts (passing markets), 5 carries (rushing) or 3 targets (receiving). That filter was set
in advance and is the Test S sample.

B1 last season per game; B2 this season to date; B3 last 8 games; B4 share of team volume x team volume x
position efficiency; B5 position and volume-band average. Each is a negative binomial around that mean.

## pass_att: 1,089 tune rows (2,099 fit rows); chosen **B5**

| Baseline | NB size | CRPS | Worse than chosen by (95% interval) | Central 50% covers | 80% | 90% |
|---|---|---|---|---|---|---|
| B1 | 1.6 | 8.523 | +2.334 (+2.063 to +2.604) | 75.8% | 88.3% | 90.7% |
| B2 | 4.9 | 6.369 | +0.180 (-0.003 to +0.364) | 72.5% | 89.0% | 92.1% |
| B3 | 6.0 | 6.289 | +0.100 (-0.070 to +0.277) | 68.0% | 85.8% | 90.7% |
| B4 | 6.0 | 6.347 | +0.158 (-0.025 to +0.351) | 68.0% | 85.4% | 90.3% |
| B5 | 6.6 | 6.189 | chosen | 67.3% | 87.5% | 91.3% |

## pass_yds: 1,089 tune rows (2,099 fit rows); chosen **B3**

| Baseline | NB size | CRPS | Worse than chosen by (95% interval) | Central 50% covers | 80% | 90% |
|---|---|---|---|---|---|---|
| B1 | 0.2 | 111.815 | +58.214 (+55.326 to +61.004) | 36.6% | 95.8% | 96.8% |
| B2 | 0.9 | 67.433 | +13.832 (+12.177 to +15.572) | 78.3% | 93.4% | 95.7% |
| B3 | 2.7 | 53.601 | chosen | 65.7% | 87.1% | 91.0% |
| B4 | 2.7 | 54.502 | +0.901 (+0.028 to +1.815) | 67.4% | 86.9% | 91.8% |
| B5 | 2.7 | 53.740 | +0.139 (-1.305 to +1.539) | 70.2% | 89.8% | 92.4% |

## rush_att: 2,029 tune rows (3,789 fit rows); chosen **B4**

| Baseline | NB size | CRPS | Worse than chosen by (95% interval) | Central 50% covers | 80% | 90% |
|---|---|---|---|---|---|---|
| B1 | 2.2 | 3.642 | +0.517 (+0.408 to +0.630) | 59.9% | 83.9% | 90.8% |
| B2 | 3.6 | 3.129 | +0.004 (-0.048 to +0.054) | 61.2% | 85.7% | 92.5% |
| B3 | 3.6 | 3.126 | +0.001 (-0.015 to +0.016) | 60.2% | 85.6% | 92.6% |
| B4 | 3.6 | 3.125 | chosen | 60.4% | 85.5% | 92.3% |
| B5 | 4.0 | 3.159 | +0.034 (-0.033 to +0.104) | 58.1% | 83.8% | 91.3% |

## rush_yds: 2,029 tune rows (3,789 fit rows); chosen **B3**

| Baseline | NB size | CRPS | Worse than chosen by (95% interval) | Central 50% covers | 80% | 90% |
|---|---|---|---|---|---|---|
| B1 | 0.5 | 21.803 | +3.249 (+2.808 to +3.694) | 63.5% | 89.1% | 94.1% |
| B2 | 1.1 | 18.833 | +0.280 (+0.057 to +0.555) | 58.5% | 85.1% | 91.2% |
| B3 | 1.2 | 18.554 | chosen | 57.8% | 84.0% | 90.3% |
| B4 | 1.2 | 18.652 | +0.098 (-0.096 to +0.288) | 57.6% | 83.3% | 90.2% |
| B5 | 1.2 | 18.710 | +0.157 (-0.171 to +0.483) | 55.8% | 83.8% | 90.5% |

## rec: 4,738 tune rows (9,598 fit rows); chosen **B4**

| Baseline | NB size | CRPS | Worse than chosen by (95% interval) | Central 50% covers | 80% | 90% |
|---|---|---|---|---|---|---|
| B1 | 4.0 | 1.298 | +0.077 (+0.057 to +0.098) | 65.1% | 87.4% | 94.2% |
| B2 | 6.0 | 1.254 | +0.033 (+0.009 to +0.064) | 64.5% | 87.4% | 94.8% |
| B3 | 7.3 | 1.224 | +0.003 (-0.005 to +0.011) | 64.1% | 87.9% | 95.0% |
| B4 | 6.6 | 1.221 | chosen | 64.4% | 87.8% | 95.6% |
| B5 | 6.0 | 1.271 | +0.050 (+0.039 to +0.062) | 61.8% | 88.3% | 95.0% |

## rec_yds: 4,738 tune rows (9,598 fit rows); chosen **B4**

| Baseline | NB size | CRPS | Worse than chosen by (95% interval) | Central 50% covers | 80% | 90% |
|---|---|---|---|---|---|---|
| B1 | 0.4 | 20.162 | +3.012 (+2.752 to +3.258) | 58.0% | 92.1% | 96.0% |
| B2 | 0.7 | 18.193 | +1.043 (+0.780 to +1.352) | 59.2% | 85.6% | 95.2% |
| B3 | 0.9 | 17.293 | +0.143 (+0.033 to +0.261) | 56.9% | 81.9% | 90.6% |
| B4 | 1.0 | 17.150 | chosen | 56.0% | 81.0% | 88.7% |
| B5 | 0.9 | 17.704 | +0.554 (+0.433 to +0.676) | 55.8% | 81.1% | 89.0% |

## Reading

- The chosen baseline per market is what each engine must beat on 2024-2025 (Test S).
- Intervals are week-clustered bootstraps on the tune seasons and are descriptive: they say how clearly the chosen
  baseline leads the others, not that it would lead on new seasons.
- Coverage shows whether a single negative binomial is the right width. Discrete intervals cover slightly more
  than their nominal level even when right.
