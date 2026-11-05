# Polymarket US vs DraftKings prop prices, 2026 weeks 5-8: plan (2026-11-05)

Will asked (2026-11-05) to backtest each prop, comparing the Polymarket US price with DraftKings'. A descriptive price
comparison, not a betting rule; nothing here is a pick. Written before any Polymarket price history is fetched.

## Sample
- **DraftKings:** for each game of 2026 weeks 5-8, the last saved ParlayAPI snapshot (`data/live/parlay/*_w{week}.json.gz`)
  taken before kickoff; DraftKings two-sided full-game rows in rec, rec_yds, rush_att, rush_yds, pass_att, pass_cmp,
  pass_yds; the usual screen (de-vigged P(over) 0.35-0.65, hold under 10%).
- **Polymarket US:** the "Will X record N+ ..." market of the same game, player and stat with N - 0.5 equal to
  DraftKings' line. Its price is read from `/v1/price-history` (one-minute points, the 24 hours before the snapshot
  time): the last point at or before the snapshot time. Over cost = longPrice (best ask on Yes), under cost =
  shortPrice (1 - best bid), each plus the taker fee 0.0695 x p x (1 - p). A side quoted at 0.97 or more, or 0.03 or
  less, is treated as unquoted (an empty book shows 0.98). No size is available in the history, so fill is not known.
- Player match: normalized name within the game, as elsewhere; no guesses.

## Reported (descriptive)
- Props matched; sides quoted at both venues.
- Per side: Polymarket all-in cost minus DraftKings' implied cost, in cents per $1 of payout; share of sides where
  Polymarket is cheaper; by stat and by over/under.
- Graded with nflverse player stats (snaps but no stat row = 0, no snaps = void): ROI of buying every quoted side at
  DraftKings, at Polymarket US, and at the cheaper of the two, with a week-clustered bootstrap interval. Buying both
  sides of every prop must lose about the hold; this is the known-answer check.
