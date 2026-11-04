# Projection Recalibration: Pre-registration (2026-11-04)

Requested by Will (2026-11-04, "run the test and fixes") after docs/signals_report.md found the projection running
high on 2022-2023 (mean actual − projection about −2.5 yards on prop-type players). **Rule conflict, disclosed:**
CLAUDE.md says never add a hypothesis because a held-out result looked interesting. Will asked for this test
explicitly, so it is run, but **not on 2022-2023** (where the over-shoot was seen): it uses seasons never used for
any accuracy question. Committed with its code (`scripts/recalibration_eval.py`) before those seasons are read.

## Why it may be real
The projection's (a, b) are fitted on all player-games, but props, and these tests, keep only players whose recent
usage clears a floor. Selecting on high recent usage selects players who were partly lucky, so their next game
regresses: the projection should run high on exactly the rows books post lines for.

## Fix (one rule)
adjusted = projection x c, with c per market fitted on the training seasons' **floored** rows (the same selection
as the test), from 0.80 to 1.10 by 0.01, minimizing squared error. (a, b) fitted on the training seasons, all rows,
as now.

## Seasons
**Train 2014, 2015, 2016; confirm once 2017, 2018** (2013 as usage history). Never used for any test in this repo.

## Rows
Regular season, projected players, floors and positions as docs/five_signals_preregistration.md: rec, rec_yds
(RB/WR/TE; floors 2, 20), rush_att, rush_yds (RB; 6, 25), pass_yds (QB; 150). Five markets.

## Test (Bonferroni two-sided 0.05 / 5)
Primary: squared error of adjusted minus current on confirm rows, week-clustered bootstrap (4,000, seed 7). A market
**passes** if c ≠ 1 and the interval lies entirely below 0. MAE difference reported alongside (descriptive; MAE
alone would reward any downward shift on right-skewed stats, so it is not the criterion). Also: mean (actual −
projection) before and after.

## Use
A pass means future rules should recalibrate projections on the rows they select. It does not change P1 or S1
(frozen for 2026). "No pass" is a valid result.
