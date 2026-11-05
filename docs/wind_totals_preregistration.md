# Moderate Wind and Game-Total Unders: Pre-registration (2026-11-04)

Requested by Will (2026-11-04), after the outside-repo review (project notes "Review notes: 7 NFL betting repos").
Committed with its code **before** any schedule, score, line or weather row below has been fetched or read for
this question. Nothing here changes P1, S1, R1-R3, the ATS tracker or any live record. Analysis only: no picks.

## Why this is a new hypothesis, not a retest
Signal D (docs/five_signals_preregistration.md) tested recorded wind as a multiplier on **player prop
projections** (pass_yds, rec_yds) on 2022-2023 and failed. This test asks a different question of a different
market: are **game totals** too high when game-time wind is **moderate (8 to 15 knots)**?

The idea comes from outside work (drburke-droid/NFL, `outputs/reports/sentiment_props.md`), which reports unders
hitting more often in 8-15 knot games on 2015-2025. Those seasons are therefore not usable here. **1999-2014 have
not been used by that work or by this repo for totals**, so they are the confirm sample. The test runs once.

## Data
- **Games:** nflverse schedules (`nflreadpy.load_schedules`), seasons 1999-2014, `game_type == "REG"`,
  `location != "Neutral"`, `roof` in {`outdoors`, `open`}, `total_line`, `home_score` and `away_score` not null.
- **Line:** nflverse `total_line` (the closing consensus total nflverse carries; no prices). Every bet is graded
  at -110, so break-even is 110/210 = 0.5238.
- **Kickoff:** `gameday` + `gametime` read as America/New_York local time (how nflverse records it), converted
  to UTC.
- **Wind:** Open-Meteo historical archive (ERA5 reanalysis, `archive-api.open-meteo.com/v1/archive`), hourly
  `wind_speed_10m` in knots, at the home stadium's coordinates. **w = mean of the four hourly values at the
  kickoff hour (UTC, rounded down) and the next three hours.**
- **Stadium coordinates:** a hand table `data/weather/stadiums.csv` keyed by nflverse `stadium_id`. It is written
  after the stadium list is dumped (ids, names, roof and game counts only; no scores or lines) and committed
  **before** any wind or outcome is fetched. A game whose stadium has no coordinates stops the run; none is
  dropped silently.

## Primary test (family of 1)
- **Bucket:** 8 <= w < 15 knots.
- **Outcome:** under if home_score + away_score < total_line; pushes (equal) dropped.
- **Statistic:** under rate in the bucket.
- **Pass:** one-sided exact binomial test of under rate > 0.5238 gives p < 0.05. Otherwise **FAIL**. "Fail" is a
  valid result and is reported as such.

## Gates checked first (any failure stops the run before the result is computed)
1. Every game in the sample has stadium coordinates and a wind value.
2. **Wind sanity:** on sample games where nflverse also records `wind` (mph, from game books), the Pearson
   correlation between w and nflverse wind is at least 0.3. Below that, the ERA5 wind or the kickoff join is
   treated as broken.
3. At least 150 games in the bucket (else report UNDERPOWERED, no verdict).

## Descriptive only (printed, never a verdict)
Under rate and mean (total - line) for w < 8, 8-15 and w >= 15; the primary bucket by season; the same bucket
using nflverse recorded wind (9.2 to 17.3 mph, the knot band converted); 2026 regular-season games played so far
(forward look); 2015-2025 labeled "outside work already reported these seasons, not a test".

## Known answers first (`tests/test_wind_totals.py`)
Hand cases: kickoff conversion in daylight and standard time; the four-hour window mean; bucket edges (8.0 in,
15.0 out); push handling. Evaluator: a planted sample with a 0.60 under rate in the bucket (n = 600) passes; a
0.50 sample fails.

## Code
`src/nflbet/sources/weather.py` (kickoff and wind window), `scripts/fetch/game_wind.py` (stadium list, then wind
per game), `scripts/wind_totals_eval.py` (gates, test, report `docs/wind_totals_report.md`),
`.github/workflows/wind-totals.yml` (the sandbox cannot reach Open-Meteo or nflverse, so fetch and evaluation
run in GitHub Actions).

## Amendment 1 (2026-11-05, before any outcome was read)
The first evaluation stopped at Gate 1: nflverse schedules carry no `gametime` for any 1999 game (192 sample
games), so the kickoff rule above cannot place their wind window and they have no wind value. No under rate,
bucket count or other outcome had been computed. Will chose (2026-11-05) to **drop 1999**: the confirm sample is
**2000-2014**. Every other rule, gate and the pass criterion is unchanged. The test still runs once.
