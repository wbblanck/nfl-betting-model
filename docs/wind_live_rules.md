# Live Wind Unders Tracker: Rules (committed 2026-11-05, before 2026 week 9 kicks off)

Requested by Will on 2026-11-05 ("I want to monitor these windy bets live going forward"), after the pre-registered
2000-2014 test FAILED (docs/wind_totals_report.md: unders 420 of 771 = 0.545 in 8-15 knot games vs break-even
0.5238, one-sided p = 0.13). The rule is therefore **unvalidated**; every page that shows it says so. This is the
third pick-list exception in CLAUDE.md. Nothing here changes any other tracker or test.

## The rule (frozen)
- **Games:** 2026 regular season from week 9 on (and 2027 regular season), `location != "Neutral"`, nflverse `roof`
  in {`outdoors`, `open`} **as listed at run time**. Retractable roofs that nflverse leaves blank before the game are
  not recorded (the 2000-2014 test included retractable games played open; live, the roof is unknown in advance).
- **Wind:** Open-Meteo **forecast** (`api.open-meteo.com/v1/forecast`, best-match model), hourly 10 m wind in knots
  at the home stadium (`data/weather/stadiums.csv`); w = mean of the kickoff hour (UTC, rounded down) and the next
  three hours, as in the backtest. The backtest used ERA5 reanalysis (what happened); the forecast is what is known
  before kickoff, so live results may differ from the backtest for that reason alone.
- **Pick:** under when 8 <= w < 15 knots.
- **Line and price:** ESPN's odds feed for the game, DraftKings when listed (else the first book listed, named in
  the `book` column): total and under price at run time. No line recorded: nflverse `total_line` at -110, flagged.

## Recording
`.github/workflows/wind-live.yml` runs before each game window (Thursday, Saturday, Sunday before London, 1 PM,
4 PM and night games, Monday). Each run records every eligible game kicking off in the next 30 hours to
`data/live/wind/records_2026.csv` (all buckets, so calm and strong games are kept for description). **The official
row for a game is the last one recorded before kickoff**; rows recorded at or after kickoff never count. Nothing
is edited after kickoff. **Amendment (2026-11-08, before any week 9 Sunday kickoff):** a row whose forecast fetch
failed does not replace an earlier row with a forecast (one such failure hit ARI @ SEA at 15:51 UTC); it counts only
when no run before kickoff got a forecast. Scheduled runs fire only from `main`.

## Grading
Final score vs the official line: under wins below the line, push on equal (stake returned), else loss. 1 unit per
pick at the recorded under price (-110 if none). Void if the game is not played or nflverse's final `roof` is not
outdoors/open. `docs/wind_live.md` shows the record, units, ROI, each week, every pick, and the calm/strong buckets
(descriptive). Graded Tuesdays and after every recording run.

## Verdict (one look)
After the 2027 regular season, on all official picks from 2026 week 9 through 2027 week 18 (pushes and voids
dropped): **PASS** if the one-sided exact binomial test of under rate > 0.5238 gives p < 0.05. Otherwise FAIL.
Weekly numbers before then are descriptive.

**Power, computed before any live game (2026-11-05):** the backtests averaged about 51 (2000-2014) and 56
(2015-2025) moderate-wind games a season. At 80 picks, the pass mark is 50 unders; the chance of passing is 0.09 if
the true rate is 0.545 and 0.26 if it is 0.583. At 150 picks: 0.10 and 0.37. A FAIL here is therefore weak evidence
against a small edge; a PASS would be strong evidence for one.
