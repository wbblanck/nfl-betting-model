# Engine A event layer (events-0.1) on the tune seasons

Written by `scripts/engine_a_events.py`. Engine A-1.0 as frozen, plus the event layer fitted on 2018-2021; every
offense-game of 2022-2023 simulated 2,000 times (1,086 offense-games). Shadow and combined markets: reported,
not tested. No 2024-2025 outcome and no price was read.

## Gates

- Every box agrees with its events (plays add up to yards, touchdowns within plays, passing touchdowns within the
  receiving touchdowns credited, longest equal to the yards on a single catch): **yes**, every run.
- The six A-1.0 markets with the layer on are bit-identical to A-1.0 without it (first 20 games checked): **yes**.
- Two seeds on the first 40 games: 4,948 probabilities at fixed lines, 1 beyond 4 Monte Carlo
  standard errors (largest 4.29). **Fail** (the gate is every probability within 4).
  If the errors are right, 4,948 checks put 0.31 beyond 4 on average, and one as far out
  as 4.29 or more turns up with probability 0.09. The threshold is not changed after the fact.

## Scores on 2022-2023 (lower is better; interval: week-clustered bootstrap, 95%)

| Market | Rows | Score | Engine | Baseline | Engine minus baseline | Central 50% / 80% / 90% covers |
|---|---|---|---|---|---|---|
| anytime_td | 5,721 | log loss | 0.5452 | 0.5576 | -0.0124 (-0.0175 to -0.0073) |  |
| pass_td | 1,089 | CRPS | 0.5625 | 0.5765 | -0.0141 (-0.0278 to +0.0006) | 75.3% / 96.1% / 99.4% |
| pass_int | 1,089 | CRPS | 0.4297 | 0.4385 | -0.0088 (-0.0168 to -0.0006) | 82.7% / 94.4% / 96.1% |
| long_rec | 4,738 | CRPS | 6.9028 | none |  | 55.2% / 86.0% / 93.6% |
| long_rush | 2,029 | CRPS | 5.7549 | none |  | 51.2% / 79.8% / 89.8% |
| pass_rush_yds | 1,089 | CRPS | 47.3573 | 56.3499 | -8.9926 (-11.5828 to -6.4291) | 53.5% / 79.3% / 87.8% |
| rush_rec_yds | 5,721 | CRPS | 18.8998 | 20.0996 | -1.1998 (-1.3892 to -1.0173) | 50.8% / 82.1% / 91.8% |

Anytime touchdown: engine's average probability 27.6%, baseline's 27.2%, actual 26.1%.
Mean of the runs minus mean of the outcomes: pass_td +0.10, pass_int -0.02, long_rec +0.45, long_rush +0.60, pass_rush_yds +1.32, rush_rec_yds +1.21.

## Fitted on 2018-2021

- Touchdown share of plays in the pools: catches QB 0.072, RB 0.040, WR 0.079, TE 0.084, OTH 0.116; carries QB 0.046, RB 0.032, WR 0.040, TE 0.079, OTH 0.043.
- Touchdown factor prior strength: 160 catches, 320 carries. Interception rate 0.0229 per attempt, prior strength 320 attempts.

## Baselines and limits

- Anytime touchdown: Poisson with the player's touchdowns per game this season and last, shrunk with 4 games of the
  fit-season average (rows in the receiving or rushing sample, quarterbacks left out). The outcome counts special
  teams and fumble-return touchdowns, as books grade it; the engine does not model them.
- Interceptions: the same Poisson from interceptions per game. Passing touchdowns: no per-player passing-touchdown
  history is kept, so the baseline uses passing yards this season and last at one touchdown per 155 yards: a weak
  baseline, and the comparison says little.
- Combined yards: negative binomial around the player's last-8-game average of the sum, size fitted on 2018-2021.
- Longest catch and carry: no baseline; coverage only. A player with no catch (or carry) in a run has 0 for it.
- Not built: first touchdown scorer (needs the order of scores), defensive and special-teams touchdowns.
- Touchdowns depend on the play's yards (pool plays carry their own flags) and on the player's own touchdown rate;
  field position and the red zone are not simulated.
