# Data dictionary

"Known at" is the rule that decides whether a row may feed a prediction made at time T: the row is used only if its
known-at time is before T. Coverage by season is not asserted here; phase 1 measures it and writes
`docs/engine/coverage.md` before any model reads the data.

## Football data (nflverse through `nflreadpy`; reachable from the sandbox)
| Table (loader) | Key | Used for | Known at |
|---|---|---|---|
| Play-by-play (`load_pbp`) | game_id, play_id | environment, play calling, yardage pools, events | end of that game |
| Player stats (`load_player_stats`) | player_id, season, week | outcomes for fitting and grading | end of that game |
| Snap counts (`load_snap_counts`) | pfr id, game | snap share; played-without-a-stat-row rule | end of that game |
| Participation (`load_participation`) | game_id, play_id | routes, personnel groupings, alignment | end of that game; release lags (measure) |
| Weekly rosters (`load_rosters_weekly`) | player_id, season, week | team, position, status | that week's roster date |
| Depth charts (`load_depth_charts`) | team, week, position | expected role | the chart's date; does not track injuries (CLAUDE.md) |
| Injuries (`load_injuries`) | player_id, season, week | availability model (historical) | the report's `date_modified` where present, else the final report day; **lags live** (CLAUDE.md) |
| Next Gen Stats (`load_nextgen_stats`) | player_id, season, week | time to throw, air yards, separation | end of that game |
| FTN charting (`load_ftn_charting`) | game_id, play_id | play action, pressure, first read where charted | end of that game |
| Schedules (`load_schedules`) | game_id | kickoff time, venue, roof, surface, rest | schedule release; kickoff time can move |
| Players (`load_players`) | player_id | identity, birth date, draft | static |

## Live-only inputs (fetched in GitHub Actions; the sandbox cannot reach them)
| Source | Module | Used for | Known at |
|---|---|---|---|
| ESPN injuries | `nflbet.sources.injuries` | live game status | the fetch time (saved) |
| ESPN depth charts | `nflbet.sources.depth` | healthy starter changes only | the fetch time |
| Forecast weather | `nflbet.sources.weather` | wind, temperature, precipitation | the forecast's issue time |

## Prices (pricing and verification only; never a model input)
| Source | Where | Fields | Time |
|---|---|---|---|
| DraftKings and FanDuel via ParlayAPI | `data/live/parlay/*.json.gz` | line, over and under price | snapshot file time |
| Action Network archive 2024-2026 wk 4 | `data/props/` | lines by book; no timestamps | none (CLAUDE.md trap) |
| Novig catalog | `data/live/novig_books/<stamp>/markets.json.gz` | marketId, eventId, marketType, strike, status, voids, fee, outcomes[].bid{price, qty}, volume, openInterest | `summary.json: catalog_fetched_utc` |
| Novig books | `.../books.jsonl.gz` | marketId, seq, orders by outcome (orderId, price, qty), depth 20 | each line's `fetched_utc` |

## Feature families (phase 2; each feature records the latest known-at time it used)
- **Team:** plays, dropback rate, pass rate over expected, pace (seconds per snap), yards per dropback and per carry,
  sack and scramble rates, red-zone trips; rolling 3, 5, 8 games, season to date, previous season.
- **Opponent:** the same allowed, plus pressure rate and yards allowed by position group.
- **Player usage:** snap share, routes per dropback, targets per route, target share, air-yards share, depth of
  target, carry share by down and distance, goal-line and red-zone shares, two-minute usage, slot and wide rates.
- **Quarterback:** dropbacks, designed runs, scramble rate, time to throw, air yards per attempt.
- **Personnel:** which teammates at the same position are active; offensive-line continuity; quarterback change.
- **Situation:** home, rest days, roof, surface, forecast wind and temperature, divisional game.
Rolling windows are inputs to fitted models; none is a hand-weighted average that sets the answer.

## Engine records (written once, hash-chained by `engine/ledger.py`)
| Record | Fields |
|---|---|
| prediction | engine, version, game_id, player_id, market, prediction time, feature snapshot hash, seed, runs, mean, median, quantiles, P(0) |
| quote | venue, snapshot stamp, market_id, contract fields (`engine/contracts.py`), other-side levels used, fee record |
| grade | game_id, player_id, market, actual, snaps, void flag, stats source date |
Corrections are new records that name the record they correct.
