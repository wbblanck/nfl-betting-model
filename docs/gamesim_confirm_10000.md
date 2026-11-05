# Game simulator: confirm 2022-2025 (descriptive rerun at 10000 simulations per game; the registered result is docs/gamesim_confirm.md)

Pre-registration: docs/gamesim_preregistration.md; constants: data/backtests/gamesim_constants.json (frozen before this ran). Regular season weeks 2-18, 10000 simulations per game. Each test at 0.05 / 6.

## G2 (step 2: team factors)

- MAE vs actual margin (1023 games): simulator 10.088, closing spread 9.537.
- **T1** information beyond the close: coefficient on (fair − close) -0.149, interval -0.592 to +0.308: **FAIL**
- **T2** line movement (bet365 2022-2024, n 767): coefficient +0.204, interval +0.114 to +0.301: **PASS**
- **T3** |fair − close| ≥ 1.5 at the closing price: n 705 in 68 weeks, covers 49.5%, ROI -4.9%, interval -12.7% to +2.6%: **FAIL**

| Season | Games | MAE simulator | MAE close |
|---|---|---|---|
| 2022 | 255 | 9.074 | 8.718 |
| 2023 | 256 | 10.422 | 9.818 |
| 2024 | 256 | 10.356 | 9.648 |
| 2025 | 256 | 10.499 | 9.959 |

| |fair − close| ≥ | Bets | Covers | ROI |
|---|---|---|---|
| 0.5 | 916 | 48.9% | -5.9% |
| 1.0 | 805 | 49.5% | -4.9% |
| 2.0 | 589 | 50.9% | -2.3% |
| 3.0 | 404 | 49.4% | -5.1% |

## G3 (step 3: team factors + QB and injuries)

- MAE vs actual margin (1023 games): simulator 9.985, closing spread 9.537.
- **T1** information beyond the close: coefficient on (fair − close) +0.031, interval -0.405 to +0.489: **FAIL**
- **T2** line movement (bet365 2022-2024, n 767): coefficient +0.299, interval +0.218 to +0.397: **PASS**
- **T3** |fair − close| ≥ 1.5 at the closing price: n 667 in 68 weeks, covers 49.7%, ROI -4.6%, interval -12.7% to +3.8%: **FAIL**

| Season | Games | MAE simulator | MAE close |
|---|---|---|---|
| 2022 | 255 | 9.042 | 8.718 |
| 2023 | 256 | 10.355 | 9.818 |
| 2024 | 256 | 10.178 | 9.648 |
| 2025 | 256 | 10.360 | 9.959 |

| |fair − close| ≥ | Bets | Covers | ROI |
|---|---|---|---|
| 0.5 | 912 | 49.2% | -5.4% |
| 1.0 | 797 | 49.3% | -5.2% |
| 2.0 | 564 | 50.5% | -3.2% |
| 3.0 | 378 | 48.9% | -6.2% |

G3 minus G2 MAE: -0.104 (negative = personnel layer closer to the actual margin).

