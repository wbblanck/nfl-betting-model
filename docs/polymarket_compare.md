# Polymarket US vs DraftKings and FanDuel, week 6 player props

Props matched: 282 side-quotes across 87 player-lines, source: live ParlayAPI and Polymarket US pulled together. Positive diff = Polymarket is cheaper.

- vs DK: 124 sides; Polymarket cheaper gross 72%, mean +1.32 cents per $1; cheaper after fee 43%, mean -0.40 cents.
- vs FD: 158 sides; Polymarket cheaper gross 81%, mean +1.33 cents per $1; cheaper after fee 29%, mean -0.38 cents.
Polymarket threshold markets with no bid/ask (not compared): 3300 of 3656; threshold markets quoted and compared: 356.
- DK hold on matched lines: median 6.0% (over+under implied minus 1).
- FD hold on matched lines: median 6.9% (over+under implied minus 1).
- Polymarket hold (quoted Yes + No minus 1, per binary market): median 4.0% of $1.

Fee: Polymarket US fee schedule (docs.polymarket.us, effective 2026-10-07): taker fee = Θ x C x p x (1-p) with Θ = 0.0695 for standard markets, Sports included (only Table Tennis differs, 0.10), charged per contract at the side's price p; the markets' own feeCoefficient field carries the same 0.0695. Not modelled: rounding of each fill's fee to the cent (banker's rounding) and taker rebates, which start at $250,000 a month in taker volume. Makers pay no taker fee.

