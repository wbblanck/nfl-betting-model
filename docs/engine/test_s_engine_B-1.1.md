# Test S: Engine B-1.1 on 2024-2025

Pre-registration: docs/engine_preregistration.md. Written by `scripts/engine_test_s_b.py`.
Code at commit `e928a264a1`; frozen record `data/backtests/engine_b_frozen_B-1.1.json` matches: True.
Fitted on 2018-2021, settings and tail scales chosen on 2022-2023; 4,000 joint runs per team-game. No price was read.
Box rule (a player's yards need his own catch, carry or attempt) changed 920,678 values (yards without volume).
Versions of Engine B tested so far, this one included: 2. Level per market: 0.05 / 6 / 2 = 0.00417.

| Market | Rows | Baseline | Baseline CRPS | Engine B CRPS | B minus baseline (99.58% interval) | Central 50% covers (if right) | 80% | 90% |
|---|---|---|---|---|---|---|---|---|
| pass_att | 1,115 | B5 | 6.285 | 5.201 | -1.085 (-1.446 to -0.803) | 57.0% (53.9%) | 84.0% (82.3%) | 91.9% (91.6%) |
| pass_yds | 1,115 | B3 | 54.448 | 41.849 | -12.599 (-15.417 to -9.818) | 53.4% (50.6%) | 83.9% (80.7%) | 92.8% (90.3%) |
| rush_att | 2,059 | B4 | 2.929 | 2.649 | -0.280 (-0.351 to -0.204) | 58.3% (57.0%) | 86.7% (84.1%) | 94.6% (92.7%) |
| rush_yds | 2,059 | B3 | 17.800 | 16.452 | -1.348 (-1.746 to -0.932) | 55.1% (52.7%) | 83.7% (82.7%) | 92.6% (91.9%) |
| rec | 4,637 | B4 | 1.206 | 1.164 | -0.042 (-0.055 to -0.029) | 66.1% (64.5%) | 88.6% (88.5%) | 95.2% (95.2%) |
| rec_yds | 4,637 | B4 | 16.990 | 15.912 | -1.078 (-1.274 to -0.872) | 58.8% (55.4%) | 86.7% (85.8%) | 94.0% (94.0%) |

| Market | Verdict | Weeks | Pinball loss at 0.05 / 0.25 / 0.50 / 0.75 / 0.95 |
|---|---|---|---|
| pass_att | **PASS** | 36 | 0.986 / 2.880 / 3.631 / 2.978 / 1.041 |
| pass_yds | **PASS** | 36 | 7.683 / 23.115 / 29.451 / 23.934 / 8.335 |
| rush_att | **PASS** | 36 | 0.405 / 1.410 / 1.867 / 1.577 / 0.580 |
| rush_yds | **PASS** | 36 | 2.118 / 8.095 / 11.592 / 10.402 / 4.095 |
| rec | **PASS** | 36 | 0.162 / 0.595 / 0.824 / 0.715 / 0.263 |
| rec_yds | **PASS** | 36 | 1.980 / 7.750 / 11.220 / 10.155 / 3.896 |

PASS: the interval is entirely below 0 (the engine is better than the frozen baseline). FAIL: it is not.
WORSE: the interval is entirely above 0. Coverage in brackets is what a forecast that was exactly right would show.
Passed 6 of 6 markets.
