# OpenMarkets NFL props probe (2026-10-09)

Read-only API calls with the repo's OPENMARKETS_API_KEY (no orders, no account linking). Script:
`scripts/audit/openmarkets_props.py`.

- 238 open NFL contests (220 games, 18 season-long); the 15 games of the next 8 days returned 1,288-1,581 positions
  each, mostly player props and alternate lines.
- Venues on S1-type player props: Kalshi, ProphetX, BettorEdge (Polymarket / PolymarketUS / 4Casters on game lines
  only). No DraftKings, FanDuel or other sportsbooks.
- Kalshi and BettorEdge quote full two-sided ladders (every half-point rung); ProphetX mostly one main two-sided
  line plus one-sided rungs. Depth is thin: median fillable amount on the thinner side of a two-sided line $25
  (Kalshi), $40 (BettorEdge), $92 (ProphetX) across all rungs.
- At DraftKings' exact line (DraftKings from ParlayAPI 2026-10-08 22:51 UTC, about 9 hours earlier): Kalshi has a
  two-sided quote on 109 of 410 DK props, ProphetX 191, BettorEdge 86. Mean absolute gap in no-vig P(over)
  1.3-1.7 points (median 1.1); 0-4% differ by 5+ points. Depth at those lines: median $76-$200.
- No odds archive (docs: tick-level history not shipped; price-history queryable in 6-hour windows).
