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

## Features (phase 2, built: `engine/features/`)
One row per skill player (QB, RB, WR, TE) per regular-season game he played or was active for. A row holds sums over EARLIER
games only: its own game and every later game are excluded (`docs/engine/feature_check.md`).
- **Windows:** the subject's last 3, 5 and 8 games (across seasons), this season before the game, all of last
  season; each with its game count (`n_w3` ... `n_prev`) and `last_kickoff`.
- **`p_*` player:** offensive snaps, attempts, completions, passing yards, sacks taken, carries, rushing yards,
  targets, receptions, receiving yards; his team's attempts, carries, targets and dropbacks in the games he played;
  dropbacks he was on the field for and the team's charted dropbacks (2016 on; the routes stand-in).
- **`o_*` his offense, `d_*` the opposing defense (what offenses did against it):** attempts, completions, passing
  yards, sacks, carries, rushing yards, targets, scrambles, dropbacks, plays, points scored and points allowed
  (final scores from the schedule file; its betting lines are never read).
- Features are sums, not ratios: a model divides window totals (targets by team targets, yards by carries).
- Rows: everyone who played, plus everyone on the game-day active list who did not (`played` False; weekly roster
  status ACT, published about 90 minutes before kickoff). A game someone did not play adds nothing to his sums.
  `played` is a fact about the game, not a feature; it defines the Test S sample and is never a model input.
- `depth_rank`: the player's rank on his team's pregame depth chart at quarterback (1 = listed starter, 9 = not
  listed). Through 2024 the weekly chart for that week; from 2025 the latest dated chart from before game day.
- Not built yet: coverage, pressure, personnel groupings, weather, rest, injuries, depth chart ranks at other positions. Each is added only
  with its own as-of rule and the same scramble test.

## Engine records (written once, hash-chained by `engine/ledger.py`)
| Record | Fields |
|---|---|
| prediction | engine, version, game_id, player_id, market, prediction time, feature snapshot hash, seed, runs, mean, median, quantiles, P(0) |
| quote | venue, snapshot stamp, market_id, contract fields (`engine/contracts.py`), other-side levels used, fee record |
| grade | game_id, player_id, market, actual, snaps, void flag, stats source date |
Corrections are new records that name the record they correct.
