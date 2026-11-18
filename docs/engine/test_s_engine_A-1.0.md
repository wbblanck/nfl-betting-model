# Test S: Engine A-1.0 on 2024-2025

Pre-registration: docs/engine_preregistration.md. Written by `scripts/engine_test_s.py`.
Code at commit `0e00370500`; frozen record `data/backtests/engine_a_frozen.json` matches: True.
Fitted on 2018-2021, settings chosen on 2022-2023; 1,088 offense-games, 4,000 runs each. No price was read.
Accounting: every simulated box score reconciles.
Versions of Engine A tested so far, this one included: 1. Level per market: 0.05 / 6 / 1 = 0.00833.

| Market | Rows | Baseline | Baseline CRPS | Engine CRPS | Engine minus baseline (99.17% interval) | Central 50% covers (if right) | 80% | 90% |
|---|---|---|---|---|---|---|---|---|
| pass_att | 1,115 | B5 | 6.285 | 5.367 | -0.919 (-1.407 to -0.451) | 55.8% (56.3%) | 79.6% (83.0%) | 88.2% (91.3%) |
| pass_yds | 1,115 | B3 | 54.448 | 45.100 | -9.348 (-13.391 to -5.474) | 53.0% (50.7%) | 80.7% (80.8%) | 88.3% (90.4%) |
| rush_att | 2,059 | B4 | 2.929 | 2.720 | -0.208 (-0.272 to -0.146) | 58.4% (56.7%) | 84.0% (84.2%) | 93.2% (92.7%) |
| rush_yds | 2,059 | B3 | 17.800 | 16.661 | -1.139 (-1.537 to -0.749) | 48.8% (51.9%) | 78.7% (81.7%) | 90.5% (91.3%) |
| rec | 4,637 | B4 | 1.206 | 1.190 | -0.016 (-0.027 to -0.004) | 66.5% (63.8%) | 90.5% (88.4%) | 96.4% (95.2%) |
| rec_yds | 4,637 | B4 | 16.990 | 16.200 | -0.789 (-0.971 to -0.610) | 54.8% (52.6%) | 87.0% (84.3%) | 94.0% (93.1%) |

| Market | Verdict | Weeks | Pinball loss at 0.05 / 0.25 / 0.50 / 0.75 / 0.95 |
|---|---|---|---|
| pass_att | **PASS** | 36 | 1.061 / 2.850 / 3.728 / 3.172 / 1.050 |
| pass_yds | **PASS** | 36 | 8.280 / 23.903 / 31.340 / 26.548 / 9.727 |
| rush_att | **PASS** | 36 | 0.416 / 1.452 / 1.929 / 1.622 / 0.557 |
| rush_yds | **PASS** | 36 | 2.121 / 8.251 / 11.816 / 10.478 / 3.925 |
| rec | **PASS** | 36 | 0.164 / 0.609 / 0.843 / 0.731 / 0.270 |
| rec_yds | **PASS** | 36 | 1.970 / 7.889 / 11.486 / 10.310 / 3.978 |

PASS: the interval is entirely below 0 (the engine is better than the frozen baseline). FAIL: it is not.
WORSE: the interval is entirely above 0. Coverage in brackets is what a forecast that was exactly right would show.
Passed 6 of 6 markets.
