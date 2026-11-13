# Engine A A-0.2 on the tune seasons

Written by `scripts/engine_a_tune.py`. Fitted on 2018-2021; every offense-game of 2022-2023 simulated
2,000 times (1,086 offense-games). This is tuning, not Test S: no 2024-2025 outcome and no price was read.

Accounting: every simulated box score reconciles (2,172,000 box scores checked).

CRPS is in the stat's own units, lower is better. 'Engine minus baseline' below 0 means the engine is better;
the interval is a week-clustered bootstrap.

| Market | Rows | Baseline | Baseline CRPS | Engine CRPS | Engine minus baseline (95% interval) | Engine central 50% covers | 80% | 90% |
|---|---|---|---|---|---|---|---|---|
| pass_att | 1,089 | B5 | 6.189 | 5.488 | -0.701 (-1.114 to -0.280) | 55.6% | 80.9% | 88.7% |
| pass_yds | 1,089 | B3 | 53.601 | 46.801 | -6.800 (-9.785 to -3.819) | 54.2% | 80.1% | 88.5% |
| rush_att | 2,029 | B4 | 3.125 | 2.896 | -0.230 (-0.269 to -0.188) | 56.0% | 83.3% | 90.8% |
| rush_yds | 2,029 | B3 | 18.554 | 17.423 | -1.131 (-1.431 to -0.818) | 48.6% | 78.8% | 88.3% |
| rec | 4,738 | B4 | 1.221 | 1.223 | +0.002 (-0.010 to +0.016) | 64.5% | 89.6% | 96.4% |
| rec_yds | 4,738 | B4 | 17.150 | 16.530 | -0.620 (-0.745 to -0.470) | 53.7% | 86.0% | 94.5% |

## Fitted on 2018-2021

| Split | Window | Prior weight m | Concentration kappa | Share to non-skill players |
|---|---|---|---|---|
| targets | w5 | 20 | 38 | 0.82% |
| carries | w8 | 20 | 15 | 0.54% |

- Catch-rate prior strength: 80 targets. Yards-per-catch factor: 80 catches. Yards-per-carry factor: 160 carries.
- Team-wide yardage shock (standard deviation of the multiplier): receiving 0.065, rushing 0.000.
- Expected starting quarterbacks in the fit seasons: 1,876; they threw every one of their team's passes in 78.4% of games and 95.6% of the passes on average.
- Chance an active skill player takes a snap, fit seasons: 83.4% overall (QB 56.5%, RB 77.4%, TE 93.5%, WR 92.5%).
- Targets per pass attempt 0.964; sacks per attempt 0.068; scrambles as a share of quarterback carries 0.43.

Mean of the runs minus mean of the outcomes, by market: pass_att -0.38, pass_yds +2.02, rush_att -0.36, rush_yds -1.03, rec +0.11, rec_yds +1.59.

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
- The expected starting quarterback is guessed from earlier games. A starter returning from injury is not
  recognized, which hurts the engine on those rows; a depth-chart input would fix it and is not built.
- Not in this version: play-by-play game script, the two teams drawn jointly, availability draws,
  opponent-specific efficiency, touchdowns, interceptions.
