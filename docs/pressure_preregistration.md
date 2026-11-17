# Pass-rush Pressure vs QB Props: Pre-registration (2026-11-13)

Requested by Will (2026-11-13). The idea comes from a third-party data survey
(tylerm08martinez-wq/gambling, `docs/research/v4-nfl-free-data.md`) that lists PFR pressure data as free and
updated in-season; that document is a plan with no backtests, so nothing in it counts as evidence. Committed with
its code (`src/nflbet/props/pressure.py`, `scripts/pressure_eval.py`, `tests/test_pressure.py`) **before any
pressure value or QB outcome of the seasons below is read for this question**. Before this commit only file
schemas (column names and types) and team codes of nflverse `pfr_advstats` and player stats were looked at, to
write the code. Nothing here changes any live tracker or rule.

## Why
The projection (`nflbet.props.player_proj`) sees how many passing yards, interceptions and sacks a defense allowed
to QBs, but not how often it pressures the passer, and not how often a team's own line lets the passer get
pressured. If pressure carries information beyond those, adding it should make QB projections more accurate.

## Data
- **Pressures:** nflverse `pfr_advstats`, weekly, `stat_type="pass"` (from PFR; available from 2018), column
  `times_pressured`, summed over a team's passers per regular-season game. PFR's definition is used as published.
  The Raiders are `OAK` in PFR files for 2018-2019 and `LV` in player stats; mapped to `LV`.
- **Dropbacks:** nflverse player stats `attempts + sacks_suffered`, summed over the team's players per game.
- A team-game with no PFR passing row counts as missing on both sides (pressures and dropbacks) and is skipped.
- Not used: the defender file (`def_pressures` double-counts plays with two pressuring defenders), FTN charting
  rushers and blitzers (start in 2022, so no training seasons before the confirm seasons).

## Factors (pre-game only)
For team T's game at time t (season x 100 + week):
- **Q (own line):** T's passers' pressures over T's dropbacks in T's strictly earlier games (any season),
  exponentially weighted with half-life 4 games (the projection's half-life).
- **D (opponent defense):** pressures the opponent's defense generated over dropbacks it faced, in its strictly
  earlier games, weighted the same way.
- Each rate is divided by the league rate (pooled pressures / dropbacks) of the **previous season**, shrunk toward 1
  as (n x ratio + 4) / (n + 4) with n = prior games with data, and clipped to [0.5, 2] (the projection's
  opponent-factor recipe). 2018 is burn-in only (history for 2019; its league rate is its own).

## Model
`adjusted = proj x D^c x Q^d`. `proj` is the current projection with (a, b) fitted on the training seasons as now.
(c, d) per market from the grid {-1.5, -1.25, ..., 1.5}^2 minimizing squared error on the training seasons with
(a, b) held fixed (ties: smaller |c| + |d|). c = d = 0 is the current model.

## Seasons
- **Train (fit a, b, c, d): 2019, 2020, 2021.** **Confirm once: 2022, 2023.** Never used for this question before.
  2024-2026 are not touched (prop rules and the engine's test seasons).
- Rows: regular season; QBs with the projection's 3-game minimum and a projected pass-attempts usage of at least 20
  (starters, as the pass_att floor in docs/accuracy_preregistration.md); markets `pass_yds`, `pass_int`, `sacks`
  (sacks taken, nflverse `sacks_suffered`).

## Test (family of 3 markets; Holm at 0.05)
On confirm rows: mean of (adjusted − actual)^2 minus (current − actual)^2, week-clustered bootstrap (season-week
clusters, 4,000 resamples, seed 7). p = two-sided percentile-bootstrap p-value (2 x the smaller share of resampled
means on either side of 0). Holm step-down over the 3 markets at 0.05.
A market **passes** if (c, d) ≠ (0, 0) on training, the mean difference is below 0, and Holm rejects.
Squared error is the metric because the projection is a mean (for interceptions and sacks, mean absolute error
rewards projecting the median, near 0).
Descriptive only: MAE both ways, the current projection's mean (actual − projection), the spread of log D and
log Q, the difference by confirm season, and whether the signs match the idea (more pressure: fewer yards, more
interceptions, more sacks).

## Power analysis (step 1, before training or confirm data are read)
Run on 2018 weeks 5+ only (`python scripts/pressure_eval.py --power`). For each market and a range of true c:
plant outcomes `proj x D^c + permuted 2018 residuals` (the permutation breaks any real link between D and the
outcome), take the squared-error gain of the true model, and scale its week-clustered standard error to the 36
confirm weeks. Power = P(z > 2.39), the Holm first-step level 0.05 / 3 two-sided. Optimistic: it assumes (c, d) is
known; 2018 factors carry less history than the confirm seasons' will. It is appended to this file as a dated
addendum and changes no rule.

## Known answers first (tests/test_pressure.py, run before real data)
- Hand case: 10 pressures on 40 dropbacks with a 0.2 league rate gives ratio 1.25 and factor (1.25 + 4) / 5 = 1.05,
  for the offense (Q) and for the defense that faced it (D).
- Point in time: changing a game's own pressures leaves its factors unchanged.
- A team-game with no PFR row is skipped (factor stays 1, n = 0); OAK maps to LV.
- Planted signal: outcomes = proj x D^-1 + noise; the fit picks c in [-1.25, -0.75]. Noise: the fit picks
  |c|, |d| <= 0.5.
- Holm and bootstrap p-value hand cases.

## Use
A pass only means pressure makes QB projections more accurate. Any betting use would need its own
pre-registration on a season not yet seen (the remaining 2026 weeks or 2027), against prices. "Nothing passes" is a
valid result. In-season use would also depend on the PFR file landing before kickoff (the survey says a 1-2 day
lag; not checked here).

## Side check: nfl_data_py
The survey says `nfl_data_py` was archived in favor of `nflreadpy`. This repo does not use `nfl_data_py` anywhere
(pyproject lists `nflreadpy>=0.1.5`; every loader imports `nflreadpy`). No migration needed.

## Addendum 1 (2026-11-13): power analysis on 2018, before training or confirm data were read
`python scripts/pressure_eval.py --power` → `data/backtests/pressure_power.json`. 2018 weeks 5-17 (13 week
clusters, 339 starter-QB rows per market); spread of log D 0.105; residual SD of the current projection 80.7
passing yards, 0.96 interceptions, 1.82 sacks. Power at the Holm first-step level, scaled to 36 confirm weeks:

| True c | pass_yds power (mean shift, yds) | pass_int power | sacks power |
|---|---|---|---|
| ±0.25 | 0.14 (5.4) | 0.02-0.03 | 0.04 |
| ±0.5 | 0.62-0.66 (10.7) | 0.06-0.07 | 0.10-0.13 |
| ±0.75 | 0.92-0.95 (16.1) | 0.11-0.13 | 0.30-0.33 |
| ±1.0 | 0.98-0.99 (21.5) | 0.22-0.26 | 0.59-0.61 |
| ±1.5 | 1.00 (32.4) | 0.45-0.54 | 0.82-0.84 |

Reading: passing yards can detect an effect of about c = 0.6 or more (a defense with 10% more pressure than average
moving the projection about 6%, roughly 13 yards on a typical shift). Sacks need |c| near 1.5; interceptions are
underpowered at every c tried, so an interceptions FAIL says little. No rule changes.

Two fixes found while running this step on 2018 (no rule change; tests updated): (1) one 2018 player-stats row
(ARI, week 7) has no opponent, which split a team-game in two and counted its pressures twice; team-games are now
keyed by team, season and week only. (2) The power formula first used the realized mean gain, which includes a noise
term 2e(truth − proj) and overstated power for small c; it now uses the expected gain mean((truth − proj)^2).
