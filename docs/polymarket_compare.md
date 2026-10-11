# Polymarket US vs DraftKings and FanDuel, week 5 player props

Props matched: 428 side-quotes across 131 player-lines, source: live ParlayAPI and Polymarket US pulled together. Positive diff = Polymarket is cheaper.

- vs DK: 216 sides; Polymarket cheaper gross 87%, mean +2.19 cents per $1; cheaper after assumed fee 58%, mean +0.49 cents.
- vs FD: 212 sides; Polymarket cheaper gross 94%, mean +2.61 cents per $1; cheaper after assumed fee 68%, mean +0.91 cents.
Polymarket threshold markets with no bid/ask (not compared): 138 of 2074; threshold markets quoted and compared: 1936.
- DK hold on matched lines: median 6.0% (over+under implied minus 1).
- FD hold on matched lines: median 7.0% (over+under implied minus 1).
- Polymarket hold (quoted Yes + No minus 1, per binary market): median 1.0% of $1.

Fee (Polymarket docs, taker only): fee = C x feeRate x p x (1-p), applied per share at the side's price p. feeRate = the market's feeCoefficient (0.0695 on every market in this run; fallback 0.0695). The public fee table lists 0.05 for Sports, which does not match the market field; unresolved, and it would raise the net figures.

