# Test S: Engine B-1.0 on 2024-2025

Pre-registration: docs/engine_preregistration.md. Written by `scripts/engine_test_s_b.py`.
Code at commit `986d4b4e4f`; frozen record `data/backtests/engine_b_frozen.json` matches: True.
Fitted on 2018-2021, settings and tail scales chosen on 2022-2023; 4,000 joint runs per team-game. No price was read.
Box rule (a player's yards need his own catch, carry or attempt) changed 931,880 values (yards without volume).
Versions of Engine B tested so far, this one included: 1. Level per market: 0.05 / 6 / 1 = 0.00833.

| Market | Rows | Baseline | Baseline CRPS | Engine B CRPS | B minus baseline (99.17% interval) | Central 50% covers (if right) | 80% | 90% |
|---|---|---|---|---|---|---|---|---|
| pass_att | 1,115 | B5 | 6.285 | 5.200 | -1.085 (-1.411 to -0.817) | 56.9% (53.9%) | 83.9% (82.3%) | 92.0% (91.6%) |
| pass_yds | 1,115 | B3 | 54.448 | 41.841 | -12.607 (-15.222 to -10.031) | 53.0% (50.7%) | 83.8% (80.7%) | 92.6% (90.4%) |
| rush_att | 2,059 | B4 | 2.929 | 2.648 | -0.281 (-0.346 to -0.212) | 58.4% (56.9%) | 86.8% (84.0%) | 94.6% (92.7%) |
| rush_yds | 2,059 | B3 | 17.800 | 16.436 | -1.363 (-1.740 to -0.971) | 55.2% (52.7%) | 83.5% (82.7%) | 92.6% (91.9%) |
| rec | 4,637 | B4 | 1.206 | 1.161 | -0.045 (-0.058 to -0.032) | 65.8% (64.6%) | 88.6% (88.4%) | 95.2% (95.2%) |
| rec_yds | 4,637 | B4 | 16.990 | 15.888 | -1.101 (-1.287 to -0.917) | 58.7% (55.4%) | 86.8% (85.8%) | 94.0% (94.0%) |

| Market | Verdict | Weeks | Pinball loss at 0.05 / 0.25 / 0.50 / 0.75 / 0.95 |
|---|---|---|---|
| pass_att | **PASS** | 36 | 0.986 / 2.873 / 3.632 / 2.988 / 1.039 |
| pass_yds | **PASS** | 36 | 7.719 / 23.182 / 29.423 / 23.908 / 8.336 |
| rush_att | **PASS** | 36 | 0.405 / 1.411 / 1.865 / 1.576 / 0.580 |
| rush_yds | **PASS** | 36 | 2.119 / 8.096 / 11.552 / 10.411 / 4.093 |
| rec | **PASS** | 36 | 0.160 / 0.594 / 0.824 / 0.713 / 0.263 |
| rec_yds | **PASS** | 36 | 1.976 / 7.731 / 11.210 / 10.137 / 3.881 |

PASS: the interval is entirely below 0 (the engine is better than the frozen baseline). FAIL: it is not.
WORSE: the interval is entirely above 0. Coverage in brackets is what a forecast that was exactly right would show.
Passed 6 of 6 markets.

## A versus B on the same rows (reported, not tested)

Means from the two committed Test S results (`data/backtests/engine_test_s_A-1.0.json`, `engine_test_s_B-1.0.json`). The pre-registration makes A versus B a report, not a pass or fail, and no per-row interval was computed.

| Market | Rows A / B | Engine A CRPS | Engine B CRPS | B minus A |
|---|---|---|---|---|
| pass_att | 1,115 / 1,115 | 5.367 | 5.200 | -0.166 |
| pass_yds | 1,115 / 1,115 | 45.100 | 41.841 | -3.259 |
| rush_att | 2,059 / 2,059 | 2.720 | 2.648 | -0.072 |
| rush_yds | 2,059 / 2,059 | 16.661 | 16.436 | -0.225 |
| rec | 4,637 / 4,637 | 1.190 | 1.161 | -0.029 |
| rec_yds | 4,637 / 4,637 | 16.200 | 15.888 | -0.312 |
