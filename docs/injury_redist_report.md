# Injury usage redistribution: confirm 2022-2023

Pre-registration: docs/injury_redist_preregistration.md. Train 2019-2021. Interval: week-clustered, two-sided 0.05/5. Affected = a pool teammate was listed Out or Doubtful.

- Injury report rows 26,865; listed Out/Doubtful 5,597, of which 1,814 match a player in the stats.

| Market | alpha (train) | Affected rows | Mean q | Current: mean (actual − proj) | MAE current | MAE adjusted | Diff (interval) | Verdict | All rows MAE current / adjusted |
|---|---|---|---|---|---|---|---|---|---|
| rec | 0.00 | 1,666 of 4,790 | 0.133 | -0.16 | 1.71 | 1.71 | +0.000 (+0.000 to +0.000) | **FAIL** | 1.74 / 1.74 |
| rec_yds | 0.00 | 1,686 of 4,786 | 0.136 | -1.46 | 24.45 | 24.45 | +0.000 (+0.000 to +0.000) | **FAIL** | 24.22 / 24.22 |
| rush_rec_yds | 0.00 | 1,723 of 4,961 | 0.128 | -0.83 | 29.51 | 29.51 | +0.000 (+0.000 to +0.000) | **FAIL** | 28.71 / 28.71 |
| rush_att | 0.50 | 137 of 1,603 | 0.365 | +1.50 | 5.30 | 5.06 | -0.237 (-0.785 to +0.344) | **FAIL** | 4.56 / 4.54 |
| rush_yds | 0.50 | 134 of 1,609 | 0.368 | +6.00 | 27.61 | 27.98 | +0.368 (-1.931 to +2.436) | **FAIL** | 26.67 / 26.70 |

## Reading
Nothing passes. For receiving markets the training seasons chose alpha = 0: the current projection already runs
slightly *high* on players whose teammate was listed out (mean actual − projection −0.16 receptions, −1.46 yards),
so handing them the absent player's targets only makes it worse. Targets spread across the whole roster, the QB
and the run game, not proportionally to the players left. For running backs alpha = 0.5 was chosen and affected
backs were projected low (+1.50 carries, +6.00 yards), but on 137 confirm rows the carries gain (−0.24 MAE) has an
interval that spans 0 and rushing yards got worse. Per the pre-registration the projection stays as it is; the
rushing-carries lean is a hypothesis only, never a reason to add a rule.

## Disclosures
- **Team code:** nflverse injury reports label the 2019 Raiders `OAK` while player stats use `LV`, so 2019
  Raiders absences were missed in training. Rerun with the code mapped: identical alphas (rec 0, rec_yds 0,
  rush_rec_yds 0, rush_att 0.5, rush_yds 0.5), so the confirm results above are unchanged. Confirm seasons are
  unaffected.
- Of 1,602 Out/Doubtful report rows for WR/RB/TE in 2019-2023, 1,585 match a player id in the stats; the rest of
  the 5,597 listed rows are other positions.
- Players placed on IR between weeks are not on the weekly report: if they played in the previous 4 weeks they
  count as active, so their volume is not handed out (the adjustment can miss some absences).
- Found while running: injury-report `season`/`week` arrive as floats; cast before joining (no rule change).
