# ATS Hybrid (line move + rating agrees): Pre-registration (2026-11-04)

Requested by Will (2026-11-04): "Have the spreads been tested as a hybrid when the market moves +1.5 and when it
does, [follow] the projection?" Committed with its code before any hybrid result is computed. Code:
`scripts/ats_hybrid.py`; known-answer checks in `tests/test_ats_hybrid.py`. Output: `docs/ats_hybrid.md`,
`data/backtests/ats_hybrid.json`.

## Seen before this was written (disclosed)
- The rating's own record: `docs/ats_confirm.md` (vs close 2022-2025, fails), `docs/ats_clv.md` and
  `docs/ats_clv2.md` (vs open; those tables include "cover at close" for every |fair − open| bet, not split by
  how far the line moved).
- NFL_ATS `docs/phase3_report.md`: the side the line moved toward beat the frozen opener 54.84% (2007-2021).
- No result split by line move and rating agreement has been computed in either repo.

## Rule (no constant is fitted)
- Rating: the frozen nfl-betting-model ATS rating (`data/backtests/ats_constants.json`), fair home margin `fair`.
- move = home_close − home_open (home favored > 0). Bet when **|move| ≥ 1.5** and the rating sits on the side the
  line moved toward: sign(fair − home_open) = sign(move).
- The bet is that side **at the closing number** (open and close are the only snapshots in these files, so the
  close is the price you would get after the move). Graded on the final margin; pushes refund.
- Regular season, weeks 2-18 (week 1 rating is the prior alone, as in the earlier tests).

## Samples
- **H-A:** Sportsbook Review 2008-2021 opening and closing spreads (`data/odds/sbro_nfl_games.csv`), −110 assumed.
- **H-B:** bet365 2022-2024 opening and closing spreads with the real closing price of the side
  (`data/odds/asb_nfl_games.csv`, personal use only; Pinnacle and betr eras excluded as in ats_clv2).

## Tests (family of 2; Bonferroni)
PASS (per sample) if n ≥ 30 bets in ≥ 10 weeks and the week-clustered bootstrap ROI interval (one-sided
0.025 / 2) has its lower end above 0. Either passing makes it a candidate for a forward live test only, not a
pick; both failing ends it.

## Descriptive only (not tested)
- Move thresholds 1.0, 2.0, 3.0.
- Move alone (no rating condition), same grading, as the reference the rating has to add to.
- Stricter: also sign(fair − home_close) = sign(move) (the rating still likes the side at the closing number).
- Moves that cross 3 or 7.
- By season.
