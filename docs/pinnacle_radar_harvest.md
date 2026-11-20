# PinnRadar (Pinnacle) harvest, 2026-11-19

Record only. Raw Pinnacle prices kept for later research. This is not a pick input and not a test. Will asked on
2026-11-19 to collect as much as possible before the key falls back to the free tier.

## What the API can give (pinnradar.com/docs, read 2026-11-19)

- **No history.** Every REST endpoint returns the board as it is now: `/kit/v1/markets` (in-play),
  `/kit/v1/prematch/fixtures`, `/kit/v1/prematch/markets` and `/kit/v1/prematch/lines`. `/api/drops` keeps about
  3 hours of price drops of 4.8% or more. The SSE and WebSocket streams are live only. Past seasons, past closes and
  Pinnacle prop history **cannot be pulled from PinnRadar at any plan level.** The only way to get Pinnacle line
  history is to record it ourselves while access lasts.
- The key was not on a paid plan. The hosted MCP tool `my_usage` (first harvest call, `usage.jsonl`) reported plan
  `demo_3d` ("Demo · 3 days"), 10 requests a second, status active, **expiring 2026-11-20T03:02:58Z**
  (10:02 PM ET, Thursday 2026-11-19).
- The football board (`sport_id=5`, which covers NFL, NCAA and NCAA FCS) with `include_specials=1` already carries,
  per game, every period PinnRadar lists (`num_0` game, `num_1` first half, `num_3` second half, the latter labeled
  "Half 3" by PinnRadar). For each period it has the moneyline, the full alternate ladders of spreads and totals,
  team totals, and the maximum stake on each line. It also carries every special as its own row with prices: player
  props, game props and futures.

## What was collected

`scripts/fetch/pinnradar_harvest.py`, run by `.github/workflows/pinnradar-harvest.yml` on a push to this branch.
The workflow has four chained jobs of up to 5.6 hours each. It stops at the plan's expiry, on a 401/403 or on any
429. It then writes `data/pinnacle/radar/STOP` so later jobs make no calls.

| Every | Call | File in `data/pinnacle/radar/<job stamp>/` |
| --- | --- | --- |
| 20 s (60 s in the first 15 min) | prematch football board, delta (`since`) | `prematch_deltas.jsonl.gz` |
| 20 s | in-play football board, delta | `live_deltas.jsonl.gz` |
| 30 min | full prematch and in-play boards | `full_<ts>.json.gz`, `live_full_<ts>.json.gz` |
| 10 min | prematch and live drops (first call 3 h back) | `drops.jsonl.gz` |
| 60 min | `/prematch/markets` per NFL game, `/health` | `markets.jsonl.gz`, `health.jsonl` |
| 15 min | `my_usage` (plan, expiry) | `usage.jsonl` (the key prefix is removed) |

Every request is logged in `calls.jsonl` (path, parameters, status, size, data-age headers). The key is never logged.
Note: the first data commit (15e37e8) stored the first 8 characters of the key that `my_usage` echoes back. That is
not enough to use the key. Later commits remove it.

Tidy tables: `python scripts/fetch/pinnradar_tidy.py` replays every snapshot and delta in time order. It writes
`data/pinnacle/radar/tidy/game_lines.csv.gz` and `specials.csv.gz`, with one row each time a quote changes. So the
first row for a key is the first time it was seen, and the last prematch row before kickoff is Pinnacle's close as
recorded. A line that is taken down (an alternate spread after the main line moves) just stops getting rows; no
removal row is written. Known-answer check: `tests/test_pinnradar_tidy.py`.

### Coverage

Computed 2026-11-20 from `calls.jsonl` and the tidy tables (`python scripts/fetch/pinnradar_tidy.py`).

- **Window:** 2026-11-19 17:52 UTC to 2026-11-20 03:00:54 UTC (last call). The job wrote `STOP` at 03:01:14 UTC
  ("plan expires 2026-11-20T03:02:58Z"). No call was made after expiry.
- **Calls:** 3,484, all status 200. That breaks down as 1,610 prematch board polls, 1,610 in-play board polls,
  141 `/prematch/markets`, 112 drops and 11 `/health`. There were also 20 full prematch boards and 20 full in-play
  boards. Raw files take 15 MB.
- **Game lines** (`game_lines.csv.gz`): 8,604 price changes. These are 599 moneyline, 4,083 spread, 2,654 total,
  644 home team-total and 624 away team-total changes. They cover 13 NFL games (2,574 rows), 61 NCAA games and 2 NCAA
  FCS games. The NFL games are week 11, from Colts at Texans (Thursday) through Bengals at Commanders (Monday).
- **Specials** (`specials.csv.gz`): 3,079 price changes, 3,075 of them NFL. There are 689 distinct NFL specials
  under 15 parent events: 1,791 player-prop rows, 1,176 game-prop rows, 88 futures rows and 20 make-the-playoffs
  rows.
- **Thursday close (Colts at Texans, kickoff 01:15 UTC):** the last prematch change was recorded at 01:13:54 UTC.
  At that point the near-even main lines were spread Texans -12.5 (1.943 / 1.952) and total 44 (over 1.952 /
  under 1.934). The moneyline was 1.146 / 6.26. The game has 942 prematch special changes across 81 props, and in-play
  prop rows after kickoff are tagged `board = live`.
- **Not covered:** Sunday and Monday closes. The demo ended before those games, so those closes come only from the
  free-tier jobs (props CLV, outliers tracker).

## After the demo: the free tier

- Free key: 100 requests a day in total, 20 a minute, 100 an hour; 429 until UTC midnight once the day is used up.
  Each call is one request, and one fixtures call returns every NFL prop.
- The props CLV job keeps working on that. It makes one Pinnacle call per snapshot: two marks per kickoff window in
  `props-close.yml`, plus one board call per `live-s1.yml` run. That is a little under 20 calls on a full Sunday.
- Caveat for Friday 2026-11-20 (UTC): if `usage_today` carries over from the demo, the harvest's calls since UTC
  midnight may use up that day's 100. No NFL game is on that day, and the counter resets at 00:00 UTC Saturday.
- Do not re-run the harvest workflow after the demo ends. If `my_usage` reads free or can't be read, the script
  stops after that one call, but each start still spends it. `pinnradar-probe.yml` also spends quota whenever its
  files are pushed to a non-main branch.
