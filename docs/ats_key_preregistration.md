# ATS Rule K1 (key number at a soft book's opener): Pre-registration (2026-10-09)

Chosen in exploration on 2014-2024 opening lines with prices (docs/ats_rules_explore.txt; those seasons were already
used in docs/ats_clv*.md, so the choice is a hypothesis). Eight candidate rules were looked at; this is the only
one taken forward (no Bonferroni needed for a single test, but the selection among eight is disclosed).

## Rule K1
Take the ATS rating's side (frozen constants, data/backtests/ats_constants.json) at a **soft book's opening number
and opening price** when |fair − open| ≥ 1 and the side's number sits on the better side of 3 or 7 relative to the
fair line (`crosses_key` in scripts/ats_rules_explore.py). Regular season, weeks 2-18. "Soft book": not Pinnacle,
Circa or an exchange.

Exploration (descriptive): bet365 2018-2024 n 552, covered 53.7%, ROI +2.2%; Pinnacle 2014-2017 n 314, 48.5%, −6.3%.

## Confirm sample (not yet computed for K1)
- **2025** regular season: betr opening spreads and prices from data/odds/asb_nfl_games.csv (openers only; betr
  closing lines are not used).
- **2026** regular season: the live ATS tracker's recorded opening numbers and prices at soft books (from its first
  run onward).

## Decision (after the 2026 regular season)
Pooled 2025 + 2026: PASS if n ≥ 30 bets in ≥ 10 weeks and the week-clustered ROI interval (one-sided 0.025) has its
lower end above 0. 2025 alone is reported now as an interim, descriptive number; it decides nothing by itself.
Expect low power: the exploration rate (+2.2%) would need well over 1,000 bets to clear a 95% interval.
