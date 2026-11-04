# Drive-Level Game Simulator: Pre-registration (2026-11-04)

Requested by Will (2026-11-04, plan doc "ATS game simulator: data map and build plan", steps 2-3, free data only).
Committed before the simulator is built and before any simulator output exists for any season. Code will live in
`src/nflbet/gamesim/`; scripts `scripts/gamesim_*.py`; tests `tests/test_gamesim.py`.

## What it is
A Monte Carlo simulator that plays every snap of a game, many times, from pre-game inputs only.
- **State:** score, quarter, clock, down, distance, yard line, possession, timeouts, overtime.
- **Play choice:** on 4th down go / punt / field goal, and after a TD kick / go for two, from league decision rates by
  field position, distance, score difference and time left (fitted on the fit seasons). Otherwise pass vs run from
  league rates by down, distance, field position, score difference and time, shifted by the offense's pass rate over
  expected.
- **Play outcome:** pass → sack, scramble, interception, incomplete, or completion with yards; run → yards; any play →
  fumble lost, penalty. Yards are drawn from league distributions by play type and field position, shifted by
  team factors; touchdowns, first downs and safeties follow from yards and state.
- **Team factors (step 2):** each rate is league rate × offense factor × defense factor (on the log-odds scale for
  probabilities, multiplicative for yards), estimated from the team's earlier games only, recency weighted and
  shrunk toward league average; carried across seasons with regression toward average.
- **Special teams:** field-goal success by distance, extra point, two-point success, punt net yards, kickoff start
  position (by season, because kickoff rules changed in 2024), all league rates from games before the one
  simulated.
- **Clock:** seconds per play from league distributions by play type, clock running or stopped; timeouts near the end
  of halves by league rates. Regular-season overtime under the rule in force that season.
- **Output:** home margin and total distributions; fair spread = mean simulated home margin.

## Step 3: personnel layer
- **Starting QB:** EPA per dropback of the game's starting QB (recorded starter in nflverse schedules: known at
  inactives, disclosed hindsight as in NFL_ATS v3) minus the team's recent QB play, from plays before the game,
  shrunk toward a replacement level. Shifts the offense's pass factors.
- **Injuries:** players listed Out or Doubtful on the last report before the game × their snap share in the team's
  previous 4 games, summed by group (OL, skill, QB excluded; DL, LB, DB for the defense). Shifts the matching factors.
- One coefficient per input, fitted on the fit seasons.

## Seasons
- **Fit 2016-2020** (league rates, decision models, factor constants, personnel coefficients). 2015 is history
  for the first priors.
- **Explore 2021:** the shrinkage / half-life grid below may be chosen here by margin MAE; anything else seen here
  is a hypothesis. Then all constants are frozen in `data/backtests/gamesim_constants.json`, committed before any
  2022-2025 simulator output is computed.
- **Confirm once on 2022-2025**, regular season weeks 2-18. These seasons were used to confirm the EPA rating
  (docs/ats_confirm.md) and the hybrid; no simulator output has been computed on them.
- Grid (explore only): half-life ∈ {4, 8, 16} games, prior weight ∈ {4, 8, 16} games, season regression ∈ {0.5, 0.7}.

## Known answers first (on 2016-2020, before 2021 is simulated)
1. Same seed → same output; no game's own plays enter its inputs (delete the game and later games, inputs unchanged).
2. Simulating average teams reproduces league points per team-game, plays per game, TDs and FGs per game, and the share
   of final margins landing on 3 and on 7, each within 10% of the actual fit-season value.
3. A planted strength (one team's offense factors doubled in a synthetic league) raises its simulated margin; equal
   teams give a mean margin within 0.5 points of the home-field term.

## Confirm tests (family of 6; Bonferroni, each at 0.05 / 6)
For **G2** (step 2 simulator) and **G3** (step 2 + personnel), each:
- **T1, information beyond the close:** OLS of home margin on the closing spread and (fair − close); pass if the
  coefficient on (fair − close) has a week-clustered bootstrap interval above 0.
- **T2, line movement:** OLS of (close − open) on (fair − open), bet365 opening and closing lines 2022-2024
  (`data/odds/asb_nfl_games.csv`); pass if the interval is above 0.
- **T3, betting:** where |fair − close| ≥ 1.5, the simulator's side at the closing price (nflverse closing spread and
  prices); pass if n ≥ 30 in ≥ 10 weeks and the week-clustered ROI interval (one-sided) is above 0.
Descriptive only: margin MAE vs the closing spread's, by season; cover rate at 0.5 / 1 / 2 / 3 point thresholds;
G3 minus G2 MAE. "Nothing passes" is a valid result and would end the simulator before any scheme data (step 4).
