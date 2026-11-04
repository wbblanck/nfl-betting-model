# DraftKings / FanDuel prop rules D1-D2: Pre-registration (2026-11-04)

Requested by Will (2026-11-04, decision card: "Re-register on DK/FD data") after Action Network's props API went
empty for every game (docs/an_props_outage.md). R1-R3 and P1 were registered on Action Network's multi-book lines;
only week 4 of 2026 was saved, so they **cannot be graded as registered** and are dropped for 2026, as is the S1
live tracker's grade (no picks since week 4). They are not re-scored on other data.

D1 and D2 carry over P1 and R2 to the two books we still capture (ParlayAPI DraftKings and FanDuel,
data/live/parlay, from 2026 week 5). These are new rules, not P1 and R2: two books instead of five or more, and the
"high line" is the higher of the two. R1 (three+ books) and R3 (BetRivers/BetMGM) have no two-book analogue.

**Committed with its code (`scripts/dkfd_rules.py`, hand cases `tests/test_dkfd_rules.py`) before week 9 kickoff
(2026-11-06 ~00:15 UTC).** Weeks 5-8 DK/FD props have never been read for any line-disagreement or projection rule
and are not used: the test is weeks 9-18 only.

## Rows
- Markets: rec, rec_yds, rush_yds, rush_att, pass_yds, pass_att, pass_cmp (`sharp_soft.STAT`), full-game only.
- Each snapshot is junk-screened per quote: de-vigged P(over) 0.35-0.65 and hold < 10%.
- A prop counts when DK and FD both quote it in the same snapshot before kickoff; the last such snapshot is used.
- Books disagree: lines differ, and the gap is at most 30% of the lower line (as docs/selective_props_confirm.md).
- Graded on nflverse stats as signal E (`sharp_soft.grade`): played without a stat row = 0, no snaps = void,
  pushes dropped.

## Rules (bet the under, 1 unit at the quoted price)
- **D1** (P1 on two books): DK's line is the higher, and (DK line - projection) / DK line >= 10%. Price: DK's
  under. Projection: `nflbet.props.projection.projections(2026)`, unchanged from P1.
- **D2** (R2 on two books): under at the higher line, at that book's price, when that under is priced below -120.

## Pass criteria (Bonferroni over 2 rules)
A rule **passes** with at least 30 graded bets in at least 5 weeks and a week-clustered bootstrap ROI interval
(one-sided 0.025 / 2) entirely above 0. "Nothing passes" is a valid result.

## Schedule
`python scripts/dkfd_rules.py interim` runs each Tuesday in `fetch-props.yml` (docs/dkfd_rules_report.md,
descriptive only, no verdict). `python scripts/dkfd_rules.py confirm` runs once after week 18.

## Note on wording
The decision card said "weeks 10-18". Week 9 starts after this commit, so weeks 9-18 are used.
