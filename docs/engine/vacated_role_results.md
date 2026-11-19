# Vacated-role study: results

Pre-registration: `docs/engine/vacated_role_study.md` (commit 6885ad3, before the run). Written by
`scripts/engine_vacated_role.py` from `data/backtests/vacated_role.json`. Engine A-1.0 frozen parameters, 2,000 runs per game,
2022-2023 regular season (1,086 team-games, 13,316 played player-games). No price read. Hand cases passed before the run.

## 1. How often

- RB events (lead back with 50%+ of RB carries, first game out): 18 in 2022, 28 in 2023.
- Target events (lead target 25%+, first game out): 13 in 2022, 11 in 2023.

## 2. How much error (Engine A)

| Market | Beneficiary rows | Their mean CRPS | Other rows' mean CRPS | Their share of all CRPS | Next man: engine mean | actual mean | signed error (95%) | above engine p90 |
|---|---|---|---|---|---|---|---|---|
| rush_att | 129 | 2.80 | 2.13 | 3.5% | 9.8 | 10.6 | -0.82 (-2.37 to +0.72) | 13.3% |
| rush_yds | 129 | 14.17 | 8.90 | 3.1% | 43.0 | 44.2 | -1.24 (-10.64 to +7.79) | 13.3% |
| rec | 112 | 0.81 | 1.05 | 0.9% | 3.4 | 3.2 | +0.21 (-0.46 to +0.86) | 8.3% |
| rec_yds | 112 | 11.48 | 10.43 | 1.0% | 42.5 | 39.5 | +3.01 (-6.62 to +12.04) | 4.2% |

'Other rows' are played rows outside events where the engine's mean is at least 1. A calibrated engine has 10% above its p90.

## 3. Fake edges

Not countable (no 2022-2023 prop prices in the repo). Proxy: next men above the engine's 90th percentile, table above.

## 4. Team style (RB events)

Next man's actual share of team RB carries: mean 0.531, n 46.

| Predictor | MAE of share |
|---|---|
| P0 | 0.3034 |
| P1 | 0.3032 |
| P2 | 0.2900 |

- P1 minus P0: -0.00 (-0.07 to +0.07) (97.5% interval)
- P2 minus P0: -0.01 (-0.05 to +0.03) (97.5% interval)

## Verdict (pre-registered rule)

- Problem is real: **no** (next-man rush_att error interval must be below 0 and 20%+ above p90).
- Team style helps: **no**.
- Recommendation: nothing to fix at scale.

Power is low: 46 RB events in two seasons. The study cannot rule out a modest effect; it rules out a large, systematic one.
The 2026 week 10 Emmett Johnson case (7.5 projected, 22 actual) looks like a tail case rather than the typical outcome.
