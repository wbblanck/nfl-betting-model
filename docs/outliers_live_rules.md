# Outliers tracker: rules (frozen 2026-11-20, before its first run)

Will asked for this on 2026-11-20 and chose "track and grade on CLV" (CLAUDE.md, sixth exception). It records prop and
game-line sides whose best price is an outlier against Pinnacle, and grades each one on closing-line value. **It is
unvalidated. It is a record, not advice. Nothing here sets a stake.** The method is the sharp-lag scan
(docs/sharp_lag_scan.md, `src/nflbet/props/sharp_lag.py`). These rules fix how it runs live. Any change to them is a
dated amendment below, made before the data it would affect is read.

## Window
NFL 2026, from the first run after this file is on `main` through week 18. Weeks are the nflverse 2026 weeks.

## Sources and refresh (`.github/workflows/outliers-live.yml`, `scripts/outliers_live.py`)
- **Pinnacle**: PinnRadar free key (secret `PINN_API`), one `prematch/fixtures` call per poll. The job caps its own
  calls at **55 per UTC day** (counted in `data/live/outliers/pinn_calls.csv`), which leaves the rest of the free 100
  for the props CLV job and the tracker's board call.
- **Cadence**: a poll every 15 minutes while any NFL game kicks off within 3 hours. Otherwise hourly, 6 AM-2 AM ET.
  No polls outside those hours. Each poll also reads Novig, Kalshi and Polymarket US (keyless).
- **Books**: DraftKings and FanDuel from the newest ParlayAPI snapshot the S1 tracker already saved
  (`data/live/parlay/`). This job makes no ParlayAPI requests. A book price counts only if its snapshot is at most
  60 minutes older than the poll.

## What is recorded
A side qualifies at a poll when all of these hold:
1. Same contract at the venue and at Pinnacle: same game, market, player, line and side (sharp_lag.py rules).
2. Best price = cheapest eligible venue. Exchange prices need $50+ of payout behind them.
3. **Edge ≥ 3%** under both de-vig methods, proportional and power: Pinnacle fair ÷ best cost − 1.
4. **Best price ≥ 5% better than the next best**, decimal payout ratio, with Pinnacle's own price counted as a venue.
5. Pinnacle's two-way hold under 10%.
6. Kickoff at least 10 minutes after the poll.

The first time a side qualifies it gets one row in `data/live/outliers/records_2026.csv` with its time, venue, price,
depth, Pinnacle prices, both fairs, edge, gap and Pinnacle's move since the side was first seen. Later polls never add
a second row for that side. They only update its latest Pinnacle quote until kickoff. `current.csv` holds what
qualifies at the newest poll (the dashboard list).

## Grading (closing-line value)
- **Close** = Pinnacle's last quote for the same contract taken by this job before kickoff. It must come from a poll
  no more than 30 minutes before kickoff, or the row is "no close". A line that moved (e.g. 70.5 to 71.5) also means
  "no close", because nothing is converted between lines.
- **CLV** = Pinnacle closing fair (power method) ÷ the recorded price − 1. The proportional version is stored too.
- Rows are graded after kickoff (`python scripts/outliers_live.py grade`), weekly figures are descriptive, and nothing
  is judged before week 18 is complete.

## The one look (after week 18)
Pass if: 30+ graded rows from 5+ weeks, and the week-clustered bootstrap 95% interval of mean CLV (power method) is
above zero. Otherwise it fails. "Nothing survives" is a valid result. Win/loss results are not part of the verdict.

## Amendments
None.
