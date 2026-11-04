# Injury Usage Redistribution: Pre-registration (2026-11-04)

Requested by Will (2026-11-04): borrow the "who gains when a teammate is out" idea from a public repo
(MirageGiri/SportsProps `src/injury_impact.py`: drop the injured player and renormalize teammates' shares). That repo
has no license, so only the idea is used; the code here is written from scratch. Committed with its code
(`src/nflbet/props/injury_redist.py`, `scripts/injury_redist_eval.py`) **before any injury report or player stat of
the seasons below is read for this question**. Nothing here changes P1, S1, R1-R3 or any live record.

## Why
The projection (`nflbet.props.player_proj`) uses each player's own past usage. When a teammate is ruled out, the
volume he would have had goes to the players left, and the projection does not see that (CLAUDE.md: injury news is
invisible to the model).

## Adjustment (one rule)
For a team-game (team T, season s, week w) and market m:
- **Recent players R:** players whose most recent game for T was in season s, weeks w-4 to w-1. Each has a usage
  value U = the exponentially weighted mean of m over his games up to and including that game (half-life 4, as the
  projection), so it uses only earlier games.
- **Absent A:** players in R listed **Out** or **Doubtful** for (s, w, T) in nflverse injury reports
  (`report_status`, regular season). Only the report is used, never whether he then played (pre-game information).
- **Pool:** receiving markets (`rec`, `rec_yds`, `rush_rec_yds`): RB, WR, TE. Rushing markets (`rush_att`,
  `rush_yds`): RB only. QBs and passing markets are not adjusted or tested.
- **Freed share:** F = sum of U over pool players in A; S = sum of U over pool players in R not in A. Ratio
  q = min(F / S, 1) (0 if S = 0).
- **Adjusted usage** of a projected pool player in R \ A: usage x (1 + alpha x q). alpha = 1 is a full proportional
  hand-out of the absent players' volume; alpha = 0 is the current model.
- **Fit:** the projection's (a, b) are fitted on the training seasons exactly as now (alpha = 0); then alpha per
  market from {0, 0.25, ..., 1.5} minimizing squared error on the training seasons, (a, b) held fixed.

## Seasons
- **Train (fit a, b, alpha): 2019, 2020, 2021.** **Confirm once: 2022, 2023.** Never used for this question
  before; 2024-2026 are not touched (they belong to the prop rules). nflverse player stats and injury reports.
- Rows: regular season; pool positions for the market; projected players (the model's 3-game minimum); prop-type
  players, i.e. base usage at least rec 2, rec_yds 20, rush_att 6, rush_yds 25, rush_rec_yds 30 (as
  docs/accuracy_preregistration.md).

## Test (family of 5 markets; Bonferroni two-sided 0.05 / 5)
On confirm rows with q > 0 (a teammate in the pool was listed out): mean absolute error of the adjusted projection
minus that of the current projection, week-clustered bootstrap (season-week clusters, 4,000 resamples, seed 7).
A market **passes** if alpha > 0 was chosen on training and the interval lies entirely below 0.
Descriptive: rows with q = 0 (unchanged by construction), n affected, chosen alpha, the current projection's mean
(actual - projection) on affected rows (it should be above 0 if the idea is right), all-rows MAE.

## Known answers first (tests/test_injury_redist.py, run before real data)
- Hand case: WRs with usage 6, 4, 2 and the 4 listed Out: q = 4/8; at alpha = 1 the 6 becomes 9 and the 2 becomes 3.
- Planted signal: synthetic games where actual = usage x (1 + q) + noise; the fit picks alpha near 1.
  Noise: absences unrelated to actual; the fit picks alpha 0 or 0.25.
- Point in time: an absent player's U never includes the game being projected.

## Use
A pass only means the adjustment makes the projection more accurate. Using it in any betting rule would need its
own pre-registration on a season not yet seen. "Nothing passes" is a valid result.
