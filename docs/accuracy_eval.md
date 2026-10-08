# Model accuracy without lines

Pre-registration: docs/accuracy_preregistration.md. Intervals: week-clustered, two-sided 0.05/9 (Bonferroni over 9 markets).

## 2021-2023

| Market | n | MAE projection | MAE recent avg | Diff (interval) | Projection better | Log loss sim | Log loss recent freq | Diff (interval) | Sim better | Calib. slope | In 50% / 80% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rec | 7283 | 1.72 | 1.78 | -0.07 (-0.08 to -0.05) | yes | 0.6546 | 0.6637 | -0.0091 (-0.0170 to -0.0019) | yes | 0.66 | 0.68 / 0.91 |
| rec_yds | 6942 | 24.18 | 25.43 | -1.25 (-1.49 to -1.02) | yes | 0.6475 | 0.6644 | -0.0170 (-0.0244 to -0.0093) | yes | 0.79 | 0.55 / 0.87 |
| rush_att | 2560 | 4.46 | 4.66 | -0.20 (-0.27 to -0.12) | yes | 0.7005 | 0.6889 | +0.0115 (-0.0107 to +0.0333) | no | 0.38 | 0.47 / 0.72 |
| rush_yds | 2637 | 25.91 | 27.35 | -1.45 (-1.88 to -1.01) | yes | 0.6721 | 0.6773 | -0.0052 (-0.0221 to +0.0110) | no | 0.50 | 0.42 / 0.72 |
| rush_rec_yds | 7339 | 28.57 | 30.01 | -1.43 (-1.73 to -1.14) | yes | 0.6583 | 0.6713 | -0.0130 (-0.0233 to -0.0030) | yes | 0.70 | 0.49 / 0.80 |
| pass_att | 1467 | 7.50 | 7.80 | -0.30 (-0.50 to -0.09) | yes | 0.7236 | 0.6933 | +0.0303 (-0.0129 to +0.0689) | no | 0.38 | 0.47 / 0.73 |
| pass_cmp | 1479 | 5.28 | 5.55 | -0.27 (-0.41 to -0.13) | yes | 0.7231 | 0.6821 | +0.0410 (+0.0034 to +0.0778) | no | 0.37 | 0.49 / 0.74 |
| pass_yds | 1435 | 63.61 | 66.41 | -2.80 (-4.29 to -1.31) | yes | 0.6887 | 0.6768 | +0.0119 (-0.0220 to +0.0441) | no | 0.57 | 0.49 / 0.76 |
| pass_rush_yds | 1450 | 65.59 | 68.51 | -2.92 (-4.40 to -1.43) | yes | 0.6888 | 0.6804 | +0.0084 (-0.0226 to +0.0381) | no | 0.59 | 0.48 / 0.77 |
| all | 32592 | 20.71 | 21.73 | -1.01 (-1.22 to -0.81) | yes | 0.6682 | 0.6721 | -0.0040 (-0.0123 to +0.0043) | no | 0.57 | 0.54 / 0.82 |

Simulator calibration, all markets (decile of P(over pseudo-line): n, mean P, actual over rate):

- [0.01, 0.23] n 3253: P 0.175, over 0.286
- [0.23, 0.27] n 3265: P 0.251, over 0.318
- [0.27, 0.31] n 3258: P 0.292, over 0.314
- [0.31, 0.34] n 3242: P 0.327, over 0.345
- [0.34, 0.38] n 3249: P 0.361, over 0.385
- [0.38, 0.41] n 3280: P 0.395, over 0.406
- [0.41, 0.45] n 3254: P 0.432, over 0.446
- [0.45, 0.51] n 3269: P 0.479, over 0.456
- [0.51, 0.58] n 3261: P 0.542, over 0.532
- [0.58, 0.95] n 3261: P 0.673, over 0.578

## 2025

| Market | n | MAE projection | MAE recent avg | Diff (interval) | Projection better | Log loss sim | Log loss recent freq | Diff (interval) | Sim better | Calib. slope | In 50% / 80% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rec | 2316 | 1.67 | 1.75 | -0.08 (-0.11 to -0.05) | yes | 0.6414 | 0.6628 | -0.0214 (-0.0362 to -0.0051) | yes | 0.89 | 0.71 / 0.93 |
| rec_yds | 2204 | 23.45 | 24.59 | -1.14 (-1.43 to -0.82) | yes | 0.6388 | 0.6632 | -0.0244 (-0.0361 to -0.0094) | yes | 0.89 | 0.57 / 0.87 |
| rush_att | 833 | 4.04 | 4.13 | -0.09 (-0.21 to +0.06) | no | 0.6859 | 0.6956 | -0.0097 (-0.0364 to +0.0152) | no | 0.41 | 0.52 / 0.77 |
| rush_yds | 921 | 24.93 | 25.85 | -0.91 (-1.63 to -0.21) | yes | 0.6560 | 0.6748 | -0.0188 (-0.0345 to -0.0051) | yes | 0.54 | 0.47 / 0.75 |
| rush_rec_yds | 2415 | 27.16 | 28.48 | -1.32 (-1.75 to -0.95) | yes | 0.6476 | 0.6673 | -0.0197 (-0.0301 to -0.0069) | yes | 0.71 | 0.53 / 0.82 |
| pass_att | 503 | 7.70 | 8.29 | -0.59 (-0.89 to -0.29) | yes | 0.6648 | 0.6799 | -0.0152 (-0.0637 to +0.0410) | no | 0.58 | 0.49 / 0.73 |
| pass_cmp | 511 | 5.31 | 5.77 | -0.46 (-0.66 to -0.25) | yes | 0.6553 | 0.6752 | -0.0199 (-0.0699 to +0.0325) | no | 0.68 | 0.51 / 0.76 |
| pass_yds | 486 | 65.01 | 69.49 | -4.48 (-7.17 to -1.57) | yes | 0.6465 | 0.6546 | -0.0082 (-0.0504 to +0.0337) | no | 0.93 | 0.50 / 0.76 |
| pass_rush_yds | 493 | 66.08 | 70.68 | -4.59 (-7.37 to -1.63) | yes | 0.6485 | 0.6622 | -0.0137 (-0.0586 to +0.0296) | no | 0.90 | 0.50 / 0.77 |
| all | 10682 | 20.43 | 21.53 | -1.10 (-1.39 to -0.82) | yes | 0.6493 | 0.6685 | -0.0192 (-0.0291 to -0.0080) | yes | 0.74 | 0.57 / 0.83 |

Simulator calibration, all markets (decile of P(over pseudo-line): n, mean P, actual over rate):

- [0.00, 0.25] n 1064: P 0.195, over 0.239
- [0.25, 0.30] n 1073: P 0.275, over 0.262
- [0.30, 0.34] n 1065: P 0.319, over 0.304
- [0.34, 0.37] n 1071: P 0.356, over 0.346
- [0.37, 0.41] n 1061: P 0.391, over 0.344
- [0.41, 0.45] n 1074: P 0.429, over 0.393
- [0.45, 0.49] n 1069: P 0.465, over 0.451
- [0.49, 0.53] n 1064: P 0.508, over 0.448
- [0.53, 0.61] n 1069: P 0.567, over 0.511
- [0.61, 0.96] n 1072: P 0.685, over 0.591

## Result
- **Projection:** better than the recent average in all 9 markets in 2021-2023 (pooled mean absolute error 20.71 vs
  21.73, about 5% smaller) and in 8 of 9 in 2025 (rush attempts not distinguishable).
- **Simulator:** better than the recent-game frequency in 3 of 9 markets in 2021-2023 (receptions, receiving yards,
  rush + rec yards) and 4 of 9 in 2025; pooled 2021-2023 not distinguishable (−0.0040, interval −0.0123 to +0.0043).
  It is **overconfident** in every market (calibration slope 0.37-0.79 in 2021-2023, 0.41-0.93 in 2025): its lowest
  decile says 18% and 29% happened, its highest says 67% and 58% happened. Worst on rush attempts and the passing
  markets (slope near 0.4). Same pattern as against the books' lines in 2024-25 (docs/sim_eval.txt).
- What this does not show: whether either model beats the books. The books' lines were closer to the actual than
  the simulator in 2024-25.
