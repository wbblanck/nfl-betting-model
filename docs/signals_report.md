# Signals A-D: confirm 2022-2023

Pre-registration: docs/five_signals_preregistration.md. Train 2019-2021. Interval: week-clustered, two-sided 0.05/11.

- Snap-count rows 145,337, matched to a gsis id 145,231.

| Signal: market | k (train) | Rows tested | Current: mean (actual − proj) | MAE current | MAE adjusted | Diff (interval) | Verdict |
|---|---|---|---|---|---|---|---|
| A_qb_change:rec | -0.1 | 668 | -0.24 | 1.73 | 1.68 | -0.052 (-0.091 to -0.010) | **PASS** |
| A_qb_change:rec_yds | -0.1 | 675 | -2.53 | 23.96 | 23.22 | -0.739 (-1.151 to -0.331) | **PASS** |
| A_qb_change:pass_yds | +0.05 | 77 | +1.94 | 75.19 | 76.44 | +1.244 (-1.654 to +3.829) | **FAIL** |
| B_snap_trend:rec | +0.25 | 4,740 | -0.17 | 1.74 | 1.73 | -0.006 (-0.013 to -0.000) | **PASS** |
| B_snap_trend:rec_yds | +0.25 | 4,733 | -2.60 | 24.20 | 24.11 | -0.091 (-0.172 to -0.005) | **PASS** |
| B_snap_trend:rush_att | +0.5 | 1,584 | -0.40 | 4.55 | 4.44 | -0.113 (-0.201 to -0.028) | **PASS** |
| B_snap_trend:rush_yds | +0.25 | 1,584 | -2.94 | 26.67 | 26.43 | -0.237 (-0.443 to -0.057) | **PASS** |
| C_ngs:rush_yds | -0.05 | 1,582 | -3.09 | 26.84 | 26.62 | -0.215 (-0.337 to -0.091) | **PASS** |
| C_ngs:rec_yds | -0 | 3,917 | -2.28 | 25.25 | 25.25 | +0.000 (+0.000 to +0.000) | **FAIL** |
| D_wind:pass_yds | -0.02 | 153 | -16.53 | 66.31 | 64.61 | -1.695 (-6.861 to +5.536) | **FAIL** |
| D_wind:rec_yds | -0.025 | 674 | -4.00 | 22.38 | 21.81 | -0.573 (-1.192 to +0.625) | **FAIL** |

## Reading
Seven of eleven market-tests pass as pre-registered. A check run after the result (`scripts/signals_diag.py`,
**not pre-registered**, so it qualifies the passes but does not change the verdicts) shows only some are real signals:

- **A, QB change (rec, rec_yds pass): mostly not about the QB.** k = −0.1 is a flat 10% cut on every
  QB-change row, and the same cut on rows *without* a QB change helps almost as much (rec_yds MAE 24.26 → 23.61
  there, vs 23.96 → 23.22 with a change). The projection simply runs high in 2022-2023 (mean actual − projection
  about −2.5 yards on most rows), and lowering it helps everywhere. The QB-specific part is under 0.1 yards.
- **B, snap trend (all 4 pass): a real signal, small.** Its mean is about 0, so a level-only factor does
  nothing (rush_att MAE 4.545), while the signal gives 4.436 and lowers squared error too (32.86 → 31.31). A player
  whose snap share just rose gets more volume than his average says. Gains: 0.4% (rec) to 2.5% (rush_att).
- **C, NGS rush yards over expected (rush_yds passes): partly level.** Prior RYOE runs above 0 (mean +0.26),
  so k = −0.05 also lowers the average; level-only gets 26.84 → 26.69, the signal 26.62. A higher prior RYOE
  predicts slightly *fewer* yards than usage says: past efficiency regresses. The specific part is about 0.07 yards.
- **C (rec_yds, separation) and D (wind) fail.** Wind's MAE gains come with higher squared error, and the same
  factor on calm games makes passing yards worse.

None of this touches the prop rules. Snap trend is the one candidate worth carrying into a betting test, and that
needs its own pre-registration on a season not yet used for props (2027). The projection's general over-shoot
in 2022-2023 is a new observation (a hypothesis, not a result).
