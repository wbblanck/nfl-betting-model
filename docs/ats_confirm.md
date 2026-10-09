# ATS model: confirm 2022-2025

Pre-registration: docs/ats_declaration.md; constants frozen in data/backtests/ats_constants.json.

- MAE vs actual margin (weeks 2-18, 1023 games): fair 10.112, closing spread 9.537.
- **T1** information beyond the close: coefficient on (fair − close) -0.174, interval -0.436 to +0.086: **FAIL**.
- **T2** |fair − close| ≥ 1.5 at the closing price: n 633 in 68 weeks, covers 46.8%, ROI -9.9%, interval -17.8% to -2.4%: **FAIL**.

| Threshold | Bets | Covers | ROI | Interval (one-sided 0.025/2) |
|---|---|---|---|---|
| ≥ 0.5 | 871 | 48.6% | -6.5% | -14.6% to +1.0% |
| ≥ 1.0 | 744 | 47.9% | -8.0% | -15.8% to -0.8% |
| ≥ 1.5 | 633 | 46.8% | -9.9% | -17.8% to -2.4% |
| ≥ 2.0 | 509 | 47.2% | -9.3% | -17.6% to -1.0% |
| ≥ 3.0 | 315 | 48.5% | -6.8% | -18.4% to +4.2% |

| Season | MAE fair | MAE close |
|---|---|---|
| 2022 | 9.023 | 8.718 |
| 2023 | 10.457 | 9.818 |
| 2024 | 10.365 | 9.648 |
| 2025 | 10.598 | 9.959 |

## Reading
Nothing passes. The rating is further from the actual margin than the closing spread in every season (by 0.3-0.7
points), its disagreements with the close carry no information beyond it (T1 coefficient −0.17, interval spans 0),
and betting its side at the closing price when it disagrees by 1.5+ points covered 46.8% (ROI −9.9%). The negative
ROI is not a signal to fade the model: that would be a new hypothesis chosen after seeing this result.

Per docs/ats_declaration.md, a live ATS tab may show this rating's fair line only as context; no game is labeled
Bet Now on the rating's say-so. The angle's other leg, line shopping against a sharp reference price, has no
history to test (no timestamped multi-book spreads before 2026) and would need its own forward pre-registration.
