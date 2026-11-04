# Action Network props outage (found 2026-11-04)

`web/v2/games/{id}/props` now answers HTTP 200 with every field empty
(`{"game_props": {}, "player_props": {}, "prop_order": [], "players": {}, "market_rules": {}}`) for every game,
including past games: a 2026 week-9 game, all 2026 weeks 1-18 (fetch-props run 41771910392: 272 games, 0 rows) and
a 2025 week-9 game. Scoreboards still answer. Other paths tried (v1 props, game detail, `periods`, `bookIds`, league
prop pages) return 404 or 400 (`docs/evidence/an_endpoints/20261104T042118Z.json`). So Action Network has stopped
serving prop lines on its keyless API; this is not a parsing bug and no URL change in this repo fixes it.

## What 2026 data exists
- `data/props/an_props_2026.csv`: header only. Weeks 1-3 were never saved (the weekly fetch wrote nothing).
- `data/live/lines/`: Action Network snapshots from the S1 live runs, **week 4 only** (14 runs). S1's last picks are
  week 4 for the same reason.
- `data/live/parlay/`: DraftKings and FanDuel two-sided prices (ParlayAPI), weeks 5-8 and continuing.
- `data/live/openmarkets/`: Kalshi, ProphetX, BettorEdge, weeks 5-8 and continuing.

## Effect on pre-registered tests
R1-R3 need BetRivers and BetMGM lines; P1 and S1 need multi-book "books disagree" votes on Action Network's book set.
None can be graded on weeks 5-18 as registered. Any switch of source is a rule change and needs its own
pre-registration before the data it runs on is read.
