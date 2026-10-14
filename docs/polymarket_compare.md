# Polymarket US vs DraftKings and FanDuel, week 6 player props

Props matched: 284 side-quotes across 84 player-lines, source: live ParlayAPI and Polymarket US pulled together. Positive diff = Polymarket is cheaper.

- vs DK: 142 sides; Polymarket cheaper gross 79%, mean -0.06 cents per $1; cheaper after fee 41%, mean -1.72 cents.
- vs FD: 142 sides; Polymarket cheaper gross 85%, mean +1.68 cents per $1; cheaper after fee 50%, mean -0.03 cents.
Polymarket threshold markets with no bid/ask (not compared): 498 of 1154; threshold markets quoted and compared: 656.
- DK hold on matched lines: median 6.0% (over+under implied minus 1).
- FD hold on matched lines: median 7.0% (over+under implied minus 1).
- Polymarket hold (quoted Yes + No minus 1, per binary market): median 3.0% of $1.

Fee: Polymarket US fee schedule (docs.polymarket.us, effective 2026-10-07): taker fee = Θ x C x p x (1-p) with Θ = 0.0695 for standard markets, Sports included (only Table Tennis differs, 0.10), charged per contract at the side's price p; the markets' own feeCoefficient field carries the same 0.0695. Not modelled: rounding of each fill's fee to the cent (banker's rounding) and taker rebates, which start at $250,000 a month in taker volume. Makers pay no taker fee.

