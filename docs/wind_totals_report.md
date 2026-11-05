# Moderate Wind and Game-Total Unders: Report

Pre-registration: docs/wind_totals_preregistration.md. One run. Lines are nflverse `total_line`, graded at -110 (break-even 0.5238).

**Gate 1 (wind for every game):** pass, 2954 confirm games.
**Gate 2 (ERA5 vs nflverse recorded wind):** Pearson r = 0.688 on 2876 games (needs >= 0.3).

## Primary test (2000-2014, 8 <= w < 15 knots)

Unders 420 of 771 (pushes dropped) = **0.545** vs break-even 0.524. One-sided exact binomial p = 0.1296. **FAIL**

## Descriptive only (not verdicts)

### 2000-2014 by wind bucket

| bucket | n | unders | total_minus_line | under_rate |
|---|---|---|---|---|
| calm <8 | 2061 | 1016 | 1.22 | 0.493 |
| moderate 8-15 | 771 | 420 | -0.32 | 0.545 |
| strong 15+ | 66 | 35 | -0.81 | 0.53 |

### 2000-2014 moderate bucket by season

| season | n | unders | total_minus_line | under_rate |
|---|---|---|---|---|
| 2000 | 50 | 29 | -1.6 | 0.58 |
| 2001 | 71 | 39 | -0.83 | 0.549 |
| 2002 | 49 | 26 | 1.22 | 0.531 |
| 2003 | 51 | 28 | 0.2 | 0.549 |
| 2004 | 61 | 35 | -1.44 | 0.574 |
| 2005 | 51 | 34 | -2.69 | 0.667 |
| 2006 | 57 | 28 | 1.52 | 0.491 |
| 2007 | 43 | 24 | 0.17 | 0.558 |
| 2008 | 61 | 31 | 2.65 | 0.508 |
| 2009 | 40 | 21 | -0.76 | 0.525 |
| 2010 | 58 | 25 | 1.28 | 0.431 |
| 2011 | 44 | 24 | -1.5 | 0.545 |
| 2012 | 39 | 20 | -1.15 | 0.513 |
| 2013 | 53 | 29 | -1.38 | 0.547 |
| 2014 | 43 | 27 | -1.55 | 0.628 |

### 2000-2014 using nflverse recorded wind (9.2 to 17.3 mph)

| moderate_mph | n | unders | total_minus_line | under_rate |
|---|---|---|---|---|
| False | 1949 | 986 | 0.78 | 0.506 |
| True | 871 | 447 | 0.71 | 0.513 |

### 2015-2025: outside work already reported these seasons, not a test

| bucket | n | unders | total_minus_line | under_rate |
|---|---|---|---|---|
| calm <8 | 1330 | 642 | 0.96 | 0.483 |
| moderate 8-15 | 614 | 358 | -1.57 | 0.583 |
| strong 15+ | 66 | 38 | -2.07 | 0.576 |

### 2026 games played so far (forward look)

| bucket | n | unders | total_minus_line | under_rate |
|---|---|---|---|---|
| calm <8 | 56 | 25 | 1.02 | 0.446 |
| moderate 8-15 | 14 | 8 | 0.0 | 0.571 |
