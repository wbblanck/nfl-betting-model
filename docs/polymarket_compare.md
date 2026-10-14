# Polymarket US vs DraftKings and FanDuel, week 6 player props

Props matched: 210 side-quotes across 68 player-lines, source: live ParlayAPI and Polymarket US pulled together. Positive diff = Polymarket is cheaper.

- vs DK: 94 sides; Polymarket cheaper gross 80%, mean +0.24 cents per $1; cheaper after assumed fee 40%, mean -1.44 cents; at the docs' Sports rate 0.05: cheaper 50%, mean -0.97 cents.
- vs FD: 116 sides; Polymarket cheaper gross 79%, mean +1.39 cents per $1; cheaper after assumed fee 42%, mean -0.32 cents; at the docs' Sports rate 0.05: cheaper 55%, mean +0.16 cents.
Polymarket threshold markets with no bid/ask (not compared): 417 of 1044; threshold markets quoted and compared: 627.
- DK hold on matched lines: median 6.0% (over+under implied minus 1).
- FD hold on matched lines: median 7.0% (over+under implied minus 1).
- Polymarket hold (quoted Yes + No minus 1, per binary market): median 4.0% of $1.

Fee (Polymarket docs, taker only): fee = C x feeRate x p x (1-p), applied per share at the side's price p. Main figures use each market's own feeCoefficient (0.0695 on the Polymarket US markets; fallback 0.0695), as the docs direct. docs.polymarket.com's table lists 0.05 for Sports, but that page covers the international exchange, not Polymarket US; the 0.05 figures are shown for comparison only.

