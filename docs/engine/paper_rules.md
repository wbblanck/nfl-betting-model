# Engine paper fills at Novig: rules (frozen 2026-11-18, before any week-11 game)

Will asked for this on 2026-11-18 ("Make the paper fill exception"); CLAUDE.md carries the exception. This is a
**paper record, not a test and not advice**: no order is placed, `engine.LIVE_EXECUTION` stays False, and every page
that shows it says "unvalidated". Nothing here may change because of a result; a change is a new dated section below,
made before the week it first applies to, and the weeks before it are kept as they were.

## What is filled
- Weeks: 2026 regular season, weeks 11-18.
- Engines: A-1.0 and the Engine B version Test M uses (B-1.1 from amendment 2026-11-18 (3) of docs/engine_preregistration.md
  if it passes its Test S, else none), kept as two separate portfolios. No blend. B fills only where it forecasts
  (the Test S eligibility rows).
- Markets: the six Test S markets at Novig (PASSING_ATTEMPTS, PASSING_YARDS, RUSHING_ATTEMPTS, RUSHING_YARDS,
  RECEPTIONS, RECEIVING_YARDS), contracts matched exactly by `engine/contracts.py` (half-point lines, full game).
- Book: per contract, the **last** book recorded in `data/live/novig_books/` before kickoff that `engine/quotes.py`
  accepts (fetched before the start, within 60 minutes of its catalog read, market open, player resolved to one
  player on the game's two rosters). One fill decision per contract per engine.
- Forecast: the engine's distribution for that player-game built exactly as in Test M (`scripts/engine_forecast.py`),
  except that the ESPN injury snapshot used is the latest one stamped **at or before that book's fetch time** (not
  before kickoff), so the forecast knows nothing the book did not. If that snapshot differs from the Test M one, the
  game is forecast again for paper fills; Test M's own forecasts are untouched.

## Which side, what size
- Size: 1,000 contracts ($10 of payout) per fill. The cost of a side is what buying 1,000 contracts takes from the
  other side's resting orders, plus Novig's pregame fee from the market's fee record (`quotes.side_quote`); a side
  that cannot fill all 1,000 is not available.
- Edge of a side = engine P(side) - all-in cost per $1 of payout. P(Over) is the share of the engine's runs above the
  line; P(Under) = 1 - P(Over).
- Fill the side with the larger edge if that edge is **at least 0.03** ($0.03 per $1 of payout). Otherwise no fill.
  0.03 was set here before any engine probability was compared with a Novig price; it was not tuned.

## Grading
- Over wins when the player's stat (nflverse, as in Test M) is above the line. A fill on a player who did not play
  (no stat row and no offensive snap) is void and returns its cost. Novig's own overtime and FMV void rules are still
  unconfirmed (NOVIG_INTEGRATION.md); the record follows these rules and notes any game where Novig graded otherwise
  if that becomes known.
- Profit per fill: $10 - cost if it wins, -cost if it loses, 0 if void.
- Reported weekly per engine: fills, total cost, profit, ROI (profit / cost), mean edge at fill, and per market.
  After week 18 the season ROI is shown with a week-clustered bootstrap 95% interval, as a description. There is no
  pass/fail: this portfolio is not a pre-registered test, and nothing is concluded from it alone.

## Where it lives
`src/nflbet/engine/paper.py` (choice and grading), `scripts/engine_paper.py` (one week), records in
`data/live/engine_paper/`, run by `.github/workflows/engine-test-m.yml` after each week, shown on the dashboard's
Engine tab beside the Test M interim numbers.
