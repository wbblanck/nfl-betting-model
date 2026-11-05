# Sharp vs Soft Prices: Confirmation Pre-registration (2026-11-04)

Chosen on 2026 weeks 5-8 (exploration, `docs/sharp_soft_explore.txt`), per docs/five_signals_preregistration.md.
Committed before any week-9 game is played. Code: `scripts/sharp_soft.py` (`confirm`, rules in `RULES`).

## What exploration showed (hypotheses only)
Same-run DraftKings vs exchange prices, last capture before kickoff. ProphetX gaps lost at every threshold (e.g.
gap ≥ 3: 250 bets, ROI +2.3%, interval −15.6% to +18.4%). Kalshi and BettorEdge gaps of 3+ points won:
Kalshi with $20+ on the side 95 bets, won 70.5%, ROI +30.5% (interval +22.8% to +37.8%); BettorEdge 70 bets, won
68.6%, ROI +29.3% (+14.2% to +49.5%). Only 4 weeks, mostly unders on receptions (Kalshi: 88 of 103 bets were
unders, 74 were receptions). Numbers this large on 4 weeks are far more likely to shrink than to hold. Larger gaps
(5+) have too few bets to judge.

## Rules (two; Bonferroni)
- **E1** Kalshi no-vig P(side) at least 3 points above DraftKings' no-vig P(side), at DraftKings' exact line, at
  least $20 fillable on Kalshi on that side; bet that side at DraftKings' price.
- **E2** The same with BettorEdge, any size.

## Decision
After 2026 week 18, on weeks 9-18 only: a rule PASSES if n ≥ 30 bets in ≥ 5 weeks and the week-clustered ROI
interval (one-sided 0.025 / 2) has its lower end above 0. Interim looks (`python scripts/sharp_soft.py interim`)
are descriptive. Missed captures are absent games, never backfilled. Grading as in the explore step (nflverse
player stats by name and team; no stat row but offensive snaps = 0; neither = void).
