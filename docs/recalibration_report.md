# Projection recalibration: confirm 2017-2018

Pre-registration: docs/recalibration_preregistration.md. Train 2014-2016. Interval: week-clustered, two-sided 0.05/5. Criterion: squared error.

| Market | c (train) | Train bias | Rows | Bias current → adjusted | MSE current | MSE diff (interval) | MAE current | MAE diff (interval) | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| rec | 0.95 | -0.15 | 4,368 | -0.13 → +0.06 | 4.7 | -0.03 (-0.07 to +0.02) | 1.71 | -0.023 (-0.031 to -0.015) | **FAIL** |
| rec_yds | 0.93 | -2.17 | 4,541 | -1.52 → +1.47 | 990.3 | -4.95 (-15.68 to +4.46) | 24.38 | -0.485 (-0.638 to -0.346) | **FAIL** |
| rush_att | 0.96 | -0.33 | 1,506 | -0.54 → -0.06 | 33.7 | -0.43 (-0.97 to +0.06) | 4.62 | -0.057 (-0.099 to -0.021) | **FAIL** |
| rush_yds | 0.94 | -2.23 | 1,493 | -3.34 → -0.25 | 1201.6 | -18.08 (-39.56 to +0.51) | 26.88 | -0.579 (-0.852 to -0.340) | **FAIL** |
| pass_yds | 0.98 | -4.45 | 927 | -4.35 → +0.48 | 7109.7 | -29.21 (-102.46 to +43.83) | 67.35 | -0.126 (-0.555 to +0.284) | **FAIL** |

## Reading
Fails in all five markets on the pre-registered criterion. The over-shoot itself is real and shows up on these
fresh seasons too: the current projection runs high on prop-type players in every market (2017-2018: −0.13
receptions, −1.52 receiving yards, −3.34 rushing yards, −4.35 passing yards), and a 2-7% cut fitted on 2014-2016
lowers squared error in every market. But none of those reductions clears its interval, so it is not shown to
matter. MAE improves clearly, but that is expected from any downward shift on right-skewed stats (the median sits
below the mean), so it is not evidence. Nothing changes in the live model.
