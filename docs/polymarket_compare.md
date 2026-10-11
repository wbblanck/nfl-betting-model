# Polymarket US vs DraftKings and FanDuel, week 5 player props

Props matched: 406 side-quotes across 120 player-lines, source: live ParlayAPI and Polymarket US pulled together. Positive diff = Polymarket is cheaper.

- vs DK: 200 sides; Polymarket cheaper gross 82%, mean +2.10 cents per $1; cheaper after assumed fee 52%, mean +0.39 cents.
- vs FD: 206 sides; Polymarket cheaper gross 93%, mean +2.50 cents per $1; cheaper after assumed fee 61%, mean +0.79 cents.
Polymarket threshold markets with no bid/ask (not compared): 243 of 2052; threshold markets quoted and compared: 1809.
- DK hold on matched lines: median 6.0% (over+under implied minus 1).
- FD hold on matched lines: median 7.0% (over+under implied minus 1).
- Polymarket hold (quoted Yes + No minus 1, per binary market): median 2.0% of $1.

Fee (Polymarket docs, taker only): fee = C x feeRate x p x (1-p), applied per share at the side's price p. feeRate = the market's feeCoefficient (0.0695 on every market in this run). The public fee table lists 0.05 for Sports, which does not match the market field; unresolved, and it would raise the net figures.

