# ATS Rating vs Opening Lines (expected CLV): Pre-registration (2026-10-09)

Requested by Will ("add the data and stats you can"). The ATS rating failed against closing spreads
(docs/ats_confirm.md). The angle's main claim is about **closing-line value**: does the rating point to where the line
will move from open to close? Opening lines now exist for 2007-2021 (data/odds/sbro_nfl_games.csv). Committed before
any rating is computed for the test seasons. Already seen before this file: the archive's checks in
data/odds/README.md (match rates, mean |close − open| 1.38 points over 2007-2021); no rating was computed against
opening lines.

## Model
The ATS rating exactly as frozen in data/backtests/ats_constants.json (fitted on 2016-2021 margins). No new
constants. 2007 play-by-play is history for the 2008 prior.

## Sample
- **Test seasons 2008-2015** (never used to fit or look at the rating), regular season, weeks 2-17, games with
  both SBRO opening and closing spreads.
- 2016-2021 reported alongside, descriptive only (the rating's constants were fitted there).

## Tests (family of 3; Bonferroni)
- **C1, line movement:** OLS of (close − open) on (fair − open). Pass if the coefficient's week-clustered
  bootstrap interval (two-sided 0.05 / 3; 4,000 resamples, seed 7) lies above 0.
- **C2, CLV of the model's side:** for games with |fair − open| ≥ 1.5, take the model's side at the opening
  number; CLV = points the line moved toward that side by the close (home side: close − open; away side:
  open − close). Pass if n ≥ 30 in ≥ 10 weeks and the mean CLV's interval (one-sided 0.025 / 3) lies above 0.
- **C3, ATS at the opening number:** the same bets graded against the final margin at the opening number, price
  −110 assumed (SBRO has no spread prices), pushes refunded. Pass if the ROI's interval (one-sided 0.025 / 3) lies
  above 0.
- Descriptive: thresholds 0.5 / 1 / 2 / 3, cover rate at the close for the same bets, moves across 3 and 7.

Caveat: the archive does not name the book behind its opener, so C2 and C3 may describe numbers no one could bet.
"Nothing passes" is a valid result.
