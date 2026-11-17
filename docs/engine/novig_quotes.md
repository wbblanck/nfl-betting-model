# Novig executable quotes from the recorded books (phase 6)

Written by `scripts/engine_novig_quotes.py` from `data/live/novig_books/`. Market data only: no model probability,
expected value or side is read or written. One contract pays 1 cent; sizes are $10 (1,000 contracts) and $100
(10,000 contracts) of payout. Costs are dollars per $1 of payout; buying Over takes the resting orders on Under.
Fees are pregame (`WHEN_LIVE` charges nothing before the start). These are snapshots, not fills.

Re-derivation gate: 29,432 quote rows recomputed from the saved files, 0 differ. **PASS.**

## Snapshots with books

| Snapshot (UTC) | Books saved | Contracts quoted | Not quoted, by reason |
|---|---|---|---|
| 20261112T225713Z | 699 | 671 | no book saved 5,361; description does not read 'Player line TYPE' 377; player: not on either roster 3 |
| 20261115T182349Z | 1,635 | 1,526 | no book saved 4,561; description does not read 'Player line TYPE' 339; player: not on either roster 27 |
| 20261115T195320Z | 2,196 | 2,054 | no book saved 3,933; description does not read 'Player line TYPE' 264; player: not on either roster 31 |
| 20261115T202024Z | 2,197 | 2,055 | no book saved 3,877; description does not read 'Player line TYPE' 255; player: not on either roster 31 |
| 20261115T220538Z | 553 | 524 | no book saved 2,151; description does not read 'Player line TYPE' 167; player: not on either roster 31 |
| 20261115T232517Z | 557 | 528 | no book saved 2,028; description does not read 'Player line TYPE' 142; player: not on either roster 31 |

## By market type (all snapshots)

A contract seen in several snapshots is counted once per snapshot.

| Market type | Contracts | Fully filled at $10, both sides | At $100, both sides | Median two-side cost at $10 (1 = no margin) | At $100 | Median minutes before start |
|---|---|---|---|---|---|---|
| RECEIVING_YARDS | 2,414 | 95% | 93% | 1.030 | 1.030 | 133 |
| RUSHING_YARDS | 1,170 | 92% | 90% | 1.030 | 1.030 | 131 |
| RECEPTIONS | 1,081 | 89% | 86% | 1.025 | 1.027 | 132 |
| TOUCHDOWNS | 592 | 82% | 82% | 1.010 | 1.010 | 136 |
| PASSING_YARDS | 522 | 99% | 96% | 1.035 | 1.040 | 132 |
| LONGEST_RECEPTION | 402 | 96% | 93% | 1.115 | 1.121 | 121 |
| RUSHING_AND_RECEIVING_YARDS | 329 | 97% | 95% | 1.265 | 1.265 | 131 |
| PASSING_AND_RUSHING_YARDS | 270 | 46% | 34% | 1.195 | 1.274 | 110 |
| LONGEST_RUSH | 135 | 96% | 93% | 1.123 | 1.139 | 132 |
| RUSHING_ATTEMPTS | 118 | 99% | 99% | 1.020 | 1.025 | 114 |
| PASSING_TOUCHDOWNS | 112 | 93% | 93% | 1.020 | 1.020 | 125 |
| LONGEST_COMPLETION | 74 | 100% | 80% | 1.195 | 1.212 | 109 |
| PASSING_ATTEMPTS | 58 | 100% | 100% | 1.026 | 1.030 | 114 |
| PASSING_COMPLETIONS | 50 | 100% | 100% | 1.020 | 1.020 | 123 |
| INTERCEPTIONS_THROWN | 31 | 100% | 100% | 1.010 | 1.010 | 110 |

## Reading

- 'Two-side cost' adds what it costs to buy Over and to buy Under at that size: above 1 is the margin a taker
  pays across the pair at that moment; it is not the margin on any one side.
- A contract counts only if it matched exactly (engine/contracts.py), its player resolved to one player on the
  game's two rosters, and its book was fetched before the start and within
  60 minutes of the catalog read. 'No book saved' means the recorder did not pull that market's
  book (its game was not within the recorder's window), not that the market was empty.
- Rosters: nflverse weekly rosters for the game's week, or the latest earlier week if that week was not out yet
  (saved with each snapshot's quotes). Players not resolved (markets across snapshots, left unquoted, not guessed): Zonovan Knight (not on either roster) 144; Nikko Remigio (not on either roster) 6; Drew Ogletree (not on either roster) 4.
- Novig's overtime and FMV void rules remain unconfirmed (NOVIG_INTEGRATION.md).
