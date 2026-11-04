# Five New Signals: Pre-registration (2026-11-04)

Requested by Will (2026-11-04, "do all"): test QB changes, snap-count trends, Next Gen Stats, wind, and sharp vs
soft prices. Committed with its code before any data below is read for these questions. Nothing here changes P1,
S1, R1-R3 or any live record. Code: `src/nflbet/props/signals.py`, `scripts/signals_eval.py` (A-D),
`scripts/sharp_soft.py` (E explore; its confirm step is committed with `docs/sharp_soft_confirm.md`).

## A-D: projection accuracy (no lines)
Seasons: **train 2019-2021, confirm once 2022-2023** (as docs/injury_redist_preregistration.md; a different
question, never looked at for these signals). Base = the current projection (`nflbet.props.player_proj`), (a, b)
fitted on the training seasons. Each signal x enters as **adjusted = projection x exp(k x)**, k per market chosen
on the training seasons from the listed grid (k = 0 included) by squared error, projection held fixed. Rows:
regular season, projected players, prop-type floors (base usage at least rec 2, rec_yds 20, rush_att 6, rush_yds 25,
pass_yds 150); rec / rec_yds RB, WR, TE; rush markets RB; pass_yds QB.

| | Signal x (pre-game only) | Markets | k grid | Rows tested |
|---|---|---|---|---|
| A QB change | 1 if the team's starting QB (nflverse schedule `home_qb_id` / `away_qb_id`) differs from the most common starter of its previous 3 games this season, else 0 | rec, rec_yds, pass_yds (the new starter himself) | −0.5 to 0.5 by 0.05 | x = 1 |
| B snap trend | player's offensive snap share in his team's previous game minus his mean share over the 4 games before that (nflverse snap counts; at least 3 earlier rows) | rec, rec_yds, rush_att, rush_yds | −2 to 2 by 0.25 | x not null |
| C Next Gen Stats | rush_yds: player's mean rush yards over expected per attempt over his previous up to 8 NGS weeks; rec_yds: mean average separation over previous up to 8 NGS weeks minus that season-to-date league mean of those rows | rush_yds, rec_yds | −0.5 to 0.5 by 0.05 | x not null |
| D wind | max(wind mph − 10, 0) for games with roof `outdoors` or `open` (nflverse schedule), else 0 | pass_yds, rec_yds | −0.05 to 0.05 by 0.005 | x > 0 |

**Test (family of 11 market-tests, Bonferroni two-sided 0.05 / 11):** on confirm rows, MAE(adjusted) − MAE(base),
week-clustered bootstrap (season-week clusters, 4,000 resamples, seed 7). A market-test **passes** if k ≠ 0 was
chosen and the interval lies entirely below 0. Descriptive: chosen k, n, base mean (actual − projection) on tested
rows, all-rows MAE.

**Disclosures fixed now:** A uses the recorded starter (known at inactives, about 90 minutes before kickoff, as
NFL_ATS's players-v3 disclosed), not a pre-lock snapshot. D uses the recorded game wind, not a forecast; live use
would need forecasts (Open-Meteo). C: NGS weekly tables list only players above NGS minimums, so x is missing for
many rows (not tested there).

**Known answers first** (`tests/test_signals.py`): hand cases for each x; planted signal (actual = projection x
exp(0.3 x) with noise) gives k near 0.3; pure noise gives k at or next to 0; no x uses the game it is attached to.

## E: sharp vs soft prices (forward test, 2026)
No historical sharp prop prices exist (no Pinnacle props; ParlayAPI and OpenMarkets snapshots start 2026 week 5).
- **Data:** `data/live/openmarkets/` (Kalshi, ProphetX, BettorEdge no-vig P(over)) joined to `data/live/parlay/`
  (DraftKings two-sided prices) from the **same run**, same player, market and line; the last run before kickoff
  that has both. Graded with nflverse player stats (players with no stat row: snap counts, as CLAUDE.md).
- **Signal:** gap = exchange no-vig P(side) − DraftKings no-vig P(side). Bet the side at DraftKings' price.
- **Explore: 2026 weeks 5-8** (already captured; outcomes never yet compared with these gaps). Choose at most 2
  rules from: venue (each, or any), threshold T in {3, 5, 8, 12} points, minimum exchange size on that side in
  {0, $20}. Exploration output committed to `docs/sharp_soft_explore.txt` with the frozen rules in
  `docs/sharp_soft_confirm.md` before any week-9 result exists.
- **Confirm: 2026 weeks 9-18**, graded once after week 18. PASS if n ≥ 30 bets in ≥ 5 weeks and the week-clustered
  ROI interval (one-sided 0.025 / number of rules) has its lower end above 0. Interim looks are descriptive.
- If the capture misses runs, those games are simply absent; no backfill from any later source.

"Nothing passes" is a valid result for every test.
