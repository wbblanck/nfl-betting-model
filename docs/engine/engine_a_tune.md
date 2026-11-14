# Engine A A-1.0 on the tune seasons

Written by `scripts/engine_a_tune.py`. Fitted on 2018-2021; every offense-game of 2022-2023 simulated
2,000 times (1,086 offense-games). This is tuning, not Test S: no 2024-2025 outcome and no price was read.

Accounting: every simulated box score reconciles (2,172,000 box scores checked).

CRPS is in the stat's own units, lower is better. 'Engine minus baseline' below 0 means the engine is better;
the interval is a week-clustered bootstrap. Coverage columns show the share of outcomes inside the engine's
band and, in brackets, the share that would fall inside if the forecast were exactly right (whole-number stats
with small counts cover more than the nominal level). The two should match.

| Market | Rows | Baseline | Baseline CRPS | Engine CRPS | Engine minus baseline (95% interval) | Central 50% covers (if right) | 80% | 90% |
|---|---|---|---|---|---|---|---|---|
| pass_att | 1,089 | B5 | 6.189 | 5.318 | -0.871 (-1.229 to -0.506) | 55.6% (55.5%) | 81.4% (82.8%) | 88.4% (91.0%) |
| pass_yds | 1,089 | B3 | 53.601 | 45.567 | -8.034 (-10.584 to -5.524) | 54.5% (51.1%) | 79.7% (80.3%) | 88.7% (90.1%) |
| rush_att | 2,029 | B4 | 3.125 | 2.897 | -0.228 (-0.267 to -0.188) | 56.0% (57.0%) | 83.1% (84.3%) | 90.9% (92.6%) |
| rush_yds | 2,029 | B3 | 18.554 | 17.420 | -1.133 (-1.429 to -0.821) | 48.6% (51.6%) | 79.2% (81.6%) | 88.4% (91.1%) |
| rec | 4,738 | B4 | 1.221 | 1.221 | -0.000 (-0.012 to +0.013) | 64.8% (63.9%) | 89.5% (88.5%) | 96.3% (95.1%) |
| rec_yds | 4,738 | B4 | 17.150 | 16.502 | -0.648 (-0.771 to -0.499) | 54.1% (52.8%) | 85.7% (84.4%) | 94.3% (93.1%) |

## Fitted on 2018-2021

| Split | Window | Prior weight m | Concentration kappa | Share to non-skill players |
|---|---|---|---|---|
| targets | w5 | 20 | 38 | 0.82% |
| carries | w8 | 20 | 15 | 0.54% |

- Catch-rate prior strength: 80 targets. Yards-per-catch factor: 80 catches. Yards-per-carry factor: 160 carries.
- Team-wide yardage shock (standard deviation of the multiplier): receiving 0.065, rushing 0.000.
- Expected starting quarterbacks in the fit seasons: 1,920; they threw every one of their team's passes in 78.9% of games and 95.9% of the passes on average.
- Chance an active skill player takes a snap, fit seasons: 83.4% overall (QB 56.5%, RB 77.4%, TE 93.5%, WR 92.5%).
- Game script in the team-volume means, per point of expected margin: +0.116 pass attempts, +0.071 carries; per point of expected total: +0.048 attempts, -0.015 carries. A game's two offenses share one volume surprise per run.
- Targets per pass attempt 0.964; sacks per attempt 0.068; scrambles as a share of quarterback carries 0.43.

Mean of the runs minus mean of the outcomes, by market: pass_att -0.46, pass_yds +1.48, rush_att -0.35, rush_yds -1.02, rec +0.09, rec_yds +1.30.

## Reading (limits of this comparison)

- These are the tune seasons, where the engine's design was chosen, so the gaps flatter it. Only Test S on
  2024-2025, run once on a frozen version, counts.
- In the passing markets much of the gap is shape, not a better average: the baseline is one negative binomial,
  which is too wide for a starter's attempts (docs/engine/baselines.md), while the engine separates the usual
  full game from the occasional short one.
- What the engine is told: each team's game-day active list (published about 90 minutes before kickoff) and
  earlier games. It is not told who went on to play. Each player's forecast comes from the runs in which he
  plays, because a prop on a player who does not play is void; his teammates' participation stays uncertain.
  So these are forecasts as of the active list; a forecast made earlier in the week would also need
  availability drawn from the injury report, which is not built.
- Two earlier runs of this comparison were wrong in opposite directions and are not reported: one told the
  engine who actually played (hindsight, flattering it), the other made it forecast for players regardless of
  whether they played (scoring it on outcomes that are void).
- The expected starting quarterback is the recent starter if there is one, otherwise the depth chart's number
  one, otherwise the active quarterback with the most recent volume. On 2018-2021 that names the actual leader
  in attempts in 92.8% of team-games. A change announced during the week and not yet on the chart is missed.
- The weekly depth charts through 2024 carry no timestamp and are taken as that week's pregame chart; from
  2025 they are dated and only a chart from before game day is used.
- Not in this version: play-by-play game script (volume reacting to the simulated score), availability draws,
  opponent-specific efficiency, touchdowns, interceptions.
