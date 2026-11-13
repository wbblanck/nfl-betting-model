# Engine A A-0.1 on the tune seasons

Written by `scripts/engine_a_tune.py`. Fitted on 2018-2021; every offense-game of 2022-2023 simulated
2,000 times (1,086 offense-games). This is tuning, not Test S: no 2024-2025 outcome and no price was read.

Accounting: every simulated box score reconciles (2,172,000 box scores checked).

CRPS is in the stat's own units, lower is better. 'Engine minus baseline' below 0 means the engine is better;
the interval is a week-clustered bootstrap.

| Market | Rows | Baseline | Baseline CRPS | Engine CRPS | Engine minus baseline (95% interval) | Engine central 50% covers | 80% | 90% |
|---|---|---|---|---|---|---|---|---|
| pass_att | 1,089 | B5 | 6.189 | 5.094 | -1.094 (-1.459 to -0.699) | 55.3% | 82.7% | 90.7% |
| pass_yds | 1,089 | B3 | 53.601 | 43.655 | -9.946 (-12.761 to -6.961) | 57.3% | 83.2% | 91.4% |
| rush_att | 2,029 | B4 | 3.125 | 2.892 | -0.233 (-0.281 to -0.184) | 54.3% | 81.8% | 90.0% |
| rush_yds | 2,029 | B3 | 18.554 | 17.381 | -1.173 (-1.481 to -0.842) | 47.3% | 78.4% | 88.0% |
| rec | 4,738 | B4 | 1.221 | 1.225 | +0.004 (-0.010 to +0.019) | 64.2% | 89.2% | 96.0% |
| rec_yds | 4,738 | B4 | 17.150 | 16.540 | -0.609 (-0.759 to -0.438) | 54.2% | 85.7% | 94.0% |

## Fitted on 2018-2021

| Split | Window | Prior weight m | Concentration kappa | Share to non-skill players |
|---|---|---|---|---|
| targets | w5 | 20 | 38 | 0.82% |
| carries | w8 | 20 | 15 | 0.54% |

- Catch-rate prior strength: 80 targets. Yards-per-catch factor: 80 catches. Yards-per-carry factor: 160 carries.
- Team-wide yardage shock (standard deviation of the multiplier): receiving 0.065, rushing 0.000.
- Expected starting quarterbacks in the fit seasons: 1,876; they threw every one of their team's passes in 78.4% of games and 95.6% of the passes on average.
- Targets per pass attempt 0.964; sacks per attempt 0.068; scrambles as a share of quarterback carries 0.43.

Mean of the runs minus mean of the outcomes, by market: pass_att -0.28, pass_yds +2.42, rush_att -0.55, rush_yds -1.87, rec -0.05, rec_yds -0.26.

## Reading (limits of this comparison)

- These are the tune seasons, where the engine's design was chosen, so the gaps flatter it. Only Test S on
  2024-2025, run once on a frozen version, counts.
- In the passing markets much of the gap is shape, not a better average: the baseline is one negative binomial,
  which is too wide for a starter's attempts (docs/engine/baselines.md), while the engine separates the usual
  full game from the occasional short one.
- The engine is told which skill players took a snap. That matches the inactive list published before kickoff
  but also reveals a player who only appeared because of an in-game injury. The quarterback split does not use
  it (a starter's draw ignores whether a backup played). A roster-based active set replaces this in the
  personnel layer.
- Not in this version: play-by-play game script, the two teams drawn jointly, availability draws,
  opponent-specific efficiency, touchdowns, interceptions.
