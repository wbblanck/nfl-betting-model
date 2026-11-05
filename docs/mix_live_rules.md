# Props Mix Live Tracker: Frozen Rules (2026-11-05)

Will asked (2026-11-05) to track the M1 props mix forward and see its picks on the dashboard. M1 passed on 2025
(docs/gamesim_calibration.md), but most of its gain came from recalibrating DraftKings' own price, and its 55%+
sides lost 0.3% at DraftKings prices. **Unvalidated. These are tracker records, not recommendations.**

## Inputs at each run (all frozen)
- **Lines:** the newest ParlayAPI snapshot the S1 runs saved (`data/live/parlay/*.json.gz`), DraftKings only, for
  games not yet started. The usual screens apply: full-game lines only, de-vigged P(over) between 0.35 and 0.65, and
  hold under 10%. Markets: rec, rec_yds, rush_att, rush_yds, pass_att, pass_cmp, pass_yds.
- **Simulator:** the G3 game simulator (data/backtests/gamesim_constants.json) at 10,000 runs per game, giving team pass
  attempts and carries per run. Then the negative binomial player layer (sizes in
  data/backtests/gamesim_props_dist.json). Injuries come from nflverse, which lags, as disclosed in CLAUDE.md.
- **Mix:** the 2024-fitted weights in data/backtests/gamesim_calibration_m1.json:
  P(over) = logistic(a_g + b_g · logit(P_DK) + c_g · logit(P_sim)).

## Picks
- A prop is a pick when the mix gives a side 55% or more. The bet is that side at DraftKings' price.
- Each pick also shows its edge (mix probability minus the price's break-even), and the dashboard sorts by edge. The
  edge is shown for information only; it is not part of the rule.
- The official pick for a game is the last run before kickoff, the same as S1.

## Grading and judgment
- Picks are graded with nflverse player stats. A player with snaps but no stat row is graded 0, and no snaps is a
  void, the same as S1. One unit per pick.
- Every scored prop is saved, not just the picks (`data/live/mix_props_2026.csv`), so the mix can be judged on log loss.
- Judged after 2026 week 18, on weeks 10-18: the paired log-loss difference (mix − DK de-vigged) on every official
  scored prop, week-clustered bootstrap, two-sided 0.05. It holds up if the interval is entirely below 0. The picks'
  ROI is reported alongside, descriptively.

## Amendment (Will, 2026-11-05, before week 10): best available price, record only
Will asked whether line shopping makes the picks profitable. From this date each run also prices every pick at its
own line and side at every venue the S1 best-price record reads (src/nflbet/props/bestprice.py): DraftKings and
FanDuel from the same ParlayAPI snapshot, and Kalshi, Novig and Polymarket US read live, all-in with taker fees, with
the same minimum size ($10 of payout) for an exchange price to count. The cheapest is saved per pick per run in
`data/live/mix_bestprice_2026.csv`, and the graded record adds the units at the official run's best price
(`units_best`). A pick with no priced venue keeps DraftKings' price. This changes no pick, no grade at DraftKings'
price and not the log-loss judgment. The best-price ROI is descriptive. Exchange quotes are read a little after the
snapshot was saved, so the two may not have been live at the same moment.
