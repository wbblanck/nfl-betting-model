# Polymarket US vs DraftKings and FanDuel, week 6 player props

Props matched: 206 side-quotes across 66 player-lines, source: live ParlayAPI and Polymarket US pulled together. Positive diff = Polymarket is cheaper.

- vs DK: 96 sides; Polymarket cheaper gross 78%, mean +0.23 cents per $1; cheaper after assumed fee 41%, mean -1.45 cents.
- vs FD: 110 sides; Polymarket cheaper gross 83%, mean +1.53 cents per $1; cheaper after assumed fee 45%, mean -0.18 cents.
Polymarket threshold markets with no bid/ask (not compared): 425 of 1044; threshold markets quoted and compared: 619.
- DK hold on matched lines: median 6.0% (over+under implied minus 1).
- FD hold on matched lines: median 7.0% (over+under implied minus 1).
- Polymarket hold (quoted Yes + No minus 1, per binary market): median 4.0% of $1.

Fee (Polymarket docs, taker only): fee = C x feeRate x p x (1-p), applied per share at the side's price p. feeRate = the market's feeCoefficient (0.0695 on every market in this run; fallback 0.0695). The public fee table lists 0.05 for Sports, which does not match the market field; unresolved, and it would raise the net figures.

