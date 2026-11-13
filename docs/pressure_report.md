# Pressure vs QB props: confirm 2022-2023

Pre-registration: docs/pressure_preregistration.md. (a, b) and (c, d) fitted on 2019-2021. Metric: squared error of adjusted minus current projection (negative = pressure helps); week-clustered bootstrap, Holm over 3 markets at 0.05.

- Team-games 3,166; without a PFR passing row 0.

| Market | c (defense) | d (own line) | Rows | MSE current | MSE adjusted | Diff (95% interval) | p | Holm | Verdict | MAE current / adjusted | Current mean (actual − proj) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pass_yds | -0.25 | +0.00 | 1,034 | 6869.386 | 7009.786 | +140.3997 (+31.0941 to +255.2004) | 0.0120 | reject | **FAIL** | 65.154 / 66.252 | -2.801 |
| pass_int | +0.25 | +0.00 | 1,034 | 0.818 | 0.816 | -0.0021 (-0.0059 to +0.0016) | 0.2675 | keep | **FAIL** | 0.728 / 0.727 | -0.004 |
| sacks | +0.00 | -0.25 | 1,034 | 3.024 | 3.012 | -0.0120 (-0.0430 to +0.0175) | 0.4445 | keep | **FAIL** | 1.396 / 1.396 | -0.046 |

## Reading
Nothing passes. Pressure does not make the QB projections more accurate in 2022-2023.
- **Passing yards:** training picked c = −0.25 (the expected sign: more opponent pressure, fewer yards), but on the
  confirm seasons the adjusted projection was **worse**, by 140 squared yards (interval +31 to +255, p 0.012). Holm
  rejects "no difference", in the wrong direction, so this is a clear FAIL, not a near miss. It was worse in both
  seasons (2022 +102, 2023 +178). Descriptive check (not a test): the adjustment did not shift the average much
  (adjusted minus current +4.0 yards in 2022, +0.2 in 2023), so the loss comes from re-ranking games, not from a
  level drift.
- **Interceptions:** c = +0.25 (expected sign); a tiny gain (−0.002) with an interval spanning 0. The power
  analysis (Addendum 1) showed this market cannot detect any effect size tried, so this says little either way.
- **Sacks taken:** training picked d = −0.25 on the own-line factor and nothing on the opponent (c = 0), the
  opposite sign from the idea for d; −0.012 with an interval spanning 0. Power was low below |c| = 1.5.
- The current projection's mean (actual − projection) on these rows is −2.8 passing yards, close to the
  over-projection of about 2.5 yards seen for QBs in 2022-2023 earlier (PR #7).

Per the pre-registration the projection stays as it is. Nothing here is a reason to add a rule or to retest
pressure on these seasons with a different recipe.

## Disclosures
- PFR passing rows matched every regular-season team-game 2018-2023 (0 missing after mapping OAK to LV).
- League pressure rate (PFR pressures per nflverse dropback) by season: 2018 0.254, 2019 0.254 (uses 2018),
  then 2020 0.237, 2021 0.239, 2022 0.238, 2023 0.217 (each season's factors use the previous season's rate).
- Spread of log D and log Q on confirm rows: 0.158 and 0.186 (wider than 2018's 0.105 in the power analysis, which
  had less history), so the power analysis was if anything conservative on spread.
- The projection's opponent factor (existing code) divides by a league mean taken over every season in the frame,
  including the confirm seasons. That affects the current and the adjusted projection alike.
- Not tested: FTN rushers/blitzers (2022+ only), PFR coverage-allowed stats, and whether the PFR file lands before
  kickoff in-season.
