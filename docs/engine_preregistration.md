# Player-Prop Engine: Declaration and Pre-registration (2026-11-12)

Will supplied the blueprint "NFL Player-Prop Engine: Comprehensive Implementation Blueprint" on 2026-11-12. This
file is committed before any engine model exists and before any data is fetched for the engine. Will may amend it
until the commit that first fetches engine data; after that, changes are dated amendments.

**Approved by Will, 2026-11-12, unchanged, before any engine data was fetched.** Changes from here are dated amendments.

## What is being tested
Two independently trained engines (A: game-simulation replication; B: direct distributional challenger;
docs/engine/MODEL_SPECIFICATION.md) each produce a full distribution per player per market before kickoff. Three
questions, tested separately: are the distributions accurate (S), do they beat the market's price (M), and is the
price obtainable (E).

## What has already been seen (this limits what any test here can claim)
- 2024 and 2025 DraftKings prop lines are explored (README; CLAUDE.md). The existing game simulator's count sizes
  were chosen on 2024 and tested on 2025 (docs/gamesim_props_dist.md); the M1 mix was fit on 2024 and tested on 2025
  (docs/gamesim_calibration.md).
- 2022-2025 game results were used to confirm the game simulator (docs/gamesim_preregistration.md), and 2019-2023
  player outcomes were used by the signals and injury tests (README).
- 2026 lines through week 10 have been read by the live trackers.
- So no past season is clean for a question about prices. The blueprint's "2024-2025 locked" split is used below
  for outcome accuracy only, with this stated.

## Season roles for the engine
| Seasons | Role |
|---|---|
| 2010-2017 | history only: priors and rolling features |
| 2018-2021 | fit |
| 2022-2023 | tune: anything may be chosen here (features, model family, shrinkage, dispersion, simulation settings) |
| 2024-2025 | test S, once per frozen engine version, outcomes only, no prices |
| 2026 from the first week after an engine version is frozen, and 2027 | tests M and E, prospective only |

Every prediction for a game uses only data dated before that game's kickoff (features rebuilt as of the prediction
time; nothing chosen on 2022-2023 is re-chosen later). Nothing inherited from the existing simulator's 2024-2025
tuning (its negative binomial sizes, mix weights) may be carried into either engine; each refits on 2018-2023.

## Test S: distribution accuracy (2024-2025, regular season weeks 1-18)
- Markets: pass_yds, pass_att, rush_yds, rush_att, rec, rec_yds (config/markets.yaml). Others are reported, not tested.
- Sample: every player-game with at least one snap at QB, RB, WR or TE whose team's depth chart or prior-4-game
  usage would have made a prop plausible; the exact filter is frozen in code on 2022-2023 before 2024 is run.
- Baseline: the best of the simple baselines in MODEL_SPECIFICATION section 6, chosen per market on 2022-2023.
- Statistic: mean paired difference in CRPS (engine minus baseline) per player-game; week-clustered bootstrap,
  10,000 resamples; two-sided 0.05 / 6 per market for each engine.
- Pass, per market: the interval is entirely below 0. Reported alongside: coverage of the central 50%, 80% and 90%
  intervals and the pinball loss at 0.05-0.95.
- An engine version is run on 2024-2025 once. A later version is a new test, and the number of versions run is
  reported and divides the level again.
- "Neither engine beats the baseline" is a valid result.

## Test M: against the market (prospective)
- Props: DraftKings lines from the saved ParlayAPI snapshots, full game, de-vigged P(over) 0.35-0.65, hold under
  10% (the screens in CLAUDE.md), the six markets above, last snapshot before kickoff.
- Statistic: paired log-loss difference (engine's P(over) at DraftKings' line minus DraftKings de-vigged),
  week-clustered bootstrap, two-sided 0.05 / 2 (two engines).
- Pass: interval entirely below 0, on at least 2,000 props over at least 8 weeks. Fewer is "inconclusive".
- Prior evidence against: on 2025 the existing simulator scored 0.7266 against DraftKings' 0.6899 and a coin's
  0.6931 (docs/gamesim_props_dist.md). The engines start from the assumption that they lose this test.
- A-versus-B is the same statistic between the two engines, reported, not a pass/fail.

## Test E: execution at Novig (descriptive until authorized)
From the recorded books (docs/engine/NOVIG_INTEGRATION.md): fill rate, depth and all-in cost for a fixed size.
No decision record, paper portfolio or list of priced sides is produced until Will adds a CLAUDE.md exception for it
and its rules are frozen in their own file first.

## Not allowed
- Choosing anything on 2024-2025 or on prospective weeks; adding a market or rule because a test result looked good.
- Any price as a model input (tests/test_engine.py enforces the import rule; the perturbation test in
  docs/engine/TEST_PLAN.md enforces it on outputs).
- Blending the two engines before each has its own Test S and Test M result.

## Amendment 2026-11-13: Test S sample and baselines frozen (before any 2024-2025 outcome is scored)
- Sample filter, as the Test S section promised to freeze: a player-game counts when the player had at least 2 of
  his last 3 games on record and, per game in them, at least 15 pass attempts (pass_att, pass_yds), 5 carries
  (rush_att, rush_yds) or 3 targets (rec, rec_yds). Code: `nflbet.engine.baselines.eligible`. Set before any result
  was computed and not tuned.
- Baseline per market, chosen on 2022-2023 by mean CRPS (docs/engine/baselines.md, constants in
  data/backtests/engine_baselines.json): pass_att B5, pass_yds B3, rush_att B4, rush_yds B3, rec B4, rec_yds B4.
  These are what each engine is compared with in Test S.

## Amendment 2026-11-14: Engine A version A-1.0 frozen for Test S (before any 2024-2025 outcome is scored)
- Frozen record: `data/backtests/engine_a_frozen.json` (hashes of the fitted parameters, the yardage pools, the
  baselines file and the 2018-2023 feature rows). Fitted on 2018-2021; design choices made on 2022-2023
  (docs/engine/engine_a_tune.md). No tune-season multiplier is applied: the what-if runs did not improve the scores.
- What the engine is given for a game: the game-day active list and data from earlier games. Each player's forecast
  is conditional on his taking a snap, which is how the Test S sample (and a prop) is defined.
- Test procedure, fixed in `scripts/engine_test_s.py` and committed before it is run: 4,000 runs per offense-game,
  seeds fixed by game; per market the paired CRPS difference (engine minus frozen baseline) with a week-clustered
  bootstrap of 10,000 resamples at two-sided level 0.05 / 6 / (versions of Engine A tested so far, this one
  included); PASS when the interval is entirely below 0. The script refuses to run twice for a version, with
  uncommitted changes, or if the parameters no longer match the frozen record.
- A dry run of the same script on the tune seasons passed 5 of 6 markets (not receptions). That is not a test
  result: those are the seasons the design was chosen on.
- Will approves the run before it is made.


## Amendment 2026-11-16: Engine B version B-1.0 frozen for Test S (before any 2024-2025 outcome is scored)
- Frozen record: `data/backtests/engine_b_frozen.json` (hashes of the fitted parameters including the copula's
  correlations, the yardage boosters, the baselines file and the 2018-2023 feature rows). Fitted on 2018-2021; family
  per market, yardage tree settings and tail scales chosen on 2022-2023 (docs/engine/engine_b_tune.md).
- What the engine is given for a game: the game-day active list and data from earlier games; each forecast is
  conditional on the player taking a snap, as for Engine A.
- Test procedure, fixed in `scripts/engine_test_s_b.py` and committed before it is run: the same sample, frozen
  baselines, statistic and bootstrap as Engine A's; 4,000 joint runs (copula and the box rule as used, seed 7); level
  0.05 / 6 / (versions of Engine B tested so far, this one included). PASS when the interval is entirely below 0. The
  script refuses to run twice for a version, with uncommitted changes, or if the parameters no longer match.
- A versus B is reported, not tested (as declared above). No blend of the two engines.
- Will approved the run on 2026-11-16 ("go-ahead") before it was made.

## Amendment 2026-11-17: Test M frozen (before any week-11 game is played)
Written and committed before Thursday 2026-11-19's game, the first of the sample. Nothing below was chosen on a
2026 Test M outcome: no engine probability has been compared with a DraftKings price on any 2026 game.

- **Engines:** A-1.0 and B-1.0 exactly as frozen (`data/backtests/engine_a_frozen.json`, `engine_b_frozen.json`),
  fitted on 2018-2021 with settings from 2022-2023; nothing is refitted on later seasons. A week's forecast counts
  only if, when it is made, both engines' parameters match their frozen records and the 2018-2023 feature rows hash
  as frozen (`scripts/engine_forecast.py` checks all three and refuses otherwise). 4,000 runs per team-game.
- **Sample:** the 2026 regular season, weeks 11-18 (8 weeks). The engines and the feature pipeline cover regular-
  season games only, so the "at least 8 weeks" rule needs every one of these weeks to have scored props; a week with
  none makes the test inconclusive, not extended.
- **Forecasts, built only from what was known before each kickoff** (`engine/forecast.py`):
  - facts of 2026 games before the target week (nflverse), every fact of the target week and later removed, so the
    target games enter the feature table unplayed;
  - a projected active list in place of the game-day list, which no free source publishes in time: QB/RB/WR/TE whose
    latest 2026 weekly roster row before the target week puts them on that team as ACT or INA, or whom the nflverse
    depth chart dated before the game's day lists there; a player that chart lists on another team is dropped (a
    trade since the last roster week). Then anyone the latest ESPN injury snapshot in `data/live/injuries/` stamped
    before kickoff (and at most 72 hours before it) lists as Out, Doubtful, Injured Reserve, Suspension or PUP is
    removed. A game with no such snapshot is not forecast and leaves the sample for both engines. The depth-chart
    correction was added after a dry run on week 10 (outside the sample; availability only, no price compared):
    without it, players traded at the deadline were missed (18 of 553 screened week-10 props had no forecast; with it, 4,
    all one player absent from every 2026 roster file);
  - the quarterback depth chart dated before the game's day, as in Test S.
  The forecasts are computed after each week from those saved inputs, by the code at the commit that adds this
  amendment; the 2026 nflverse rows used are saved with each week's forecasts so the run can be repeated. Any later
  change to the forecaster, the engines or the grading code is reported with the result, with both versions'
  numbers shown, never made silently.
- **Props:** DraftKings rows (`sources.parlay.parse`, book `dk`: full game, two-sided) in the six Test S markets
  from the ParlayAPI snapshots in `data/live/parlay/`; per game, the last snapshot stamped before kickoff.
  Half-point lines only (a whole-number line can push). Screens from CLAUDE.md: de-vigged P(over) (multiplicative,
  `quant.odds.no_vig_over`) 0.35-0.65 and hold under 10%. The player is matched by normalized full name, else last
  name and first initial, among the forecast rows of the game's two teams; unmatched or ambiguous props are dropped
  and counted. A prop counts only if the player played (a stat row or an offensive snap); otherwise it is void, as
  books grade it. A player with a prop but no forecast (not on the projected list) is dropped and counted.
- **Statistic:** per prop, log loss of the engine's P(over) (share of its runs above the line, clipped to
  0.001-0.999) minus log loss of DraftKings' de-vigged P(over); mean over props; week-clustered bootstrap, 10,000
  resamples, two-sided 0.05 / 2 (two engines). **Pass:** the interval lies entirely below 0 on at least 2,000 props
  over 8 weeks. Fewer is "inconclusive". Each engine on the props both engines forecast (the same rows).
- **Reported, not tested:** A minus B on the same props; each market separately; the count of props dropped at each
  step; the share of props whose player was on the projected list but did not play, and the reverse.
- **Looks before week 18:** weekly runs report counts only (games forecast, props matched, props dropped by
  reason). No log loss is computed until week 18 is complete; it is then computed once.
- **Known handicaps, stated in advance:** the projected list is cruder than the game-day list both engines were
  tested with; Engine B's route-share feature (`db_share_w3`) is missing for every 2026 game because nflverse
  publishes no 2026 participation, so it takes its "missing" value throughout. Both work against the engines.

## Amendment 2026-11-18: frozen parameters saved (before any week-11 game is played)
A dry run of the weekly job on GitHub's machines refused: refitting the engines there did not reproduce the frozen
records, because nflverse revises its players and schedule tables daily (positions, team, kickoff times), so a
warehouse rebuilt later is not the one the engines were frozen on. The fitted parameters of A-1.0 and B-1.0 are now
saved as they were frozen (`data/backtests/engine_A-1.0_params.pkl.gz`, `engine_B-1.0_params.pkl.gz`, written by
`scripts/engine_save_params.py` only after the refit matched both frozen records), with their SHA-256 in
`data/backtests/engine_params_sha256.json`. The forecaster loads them, refuses unless the files hash as recorded and
the loaded parameters reproduce both frozen records, and no longer refits. The 2018-2023 feature hash is still
computed and reported but no longer gates a forecast. Nothing else in the Test M rules changes; no Test M outcome
or price existed when this was decided. A week-10 dry run with the saved parameters: both records match.

## Amendment 2026-11-18 (2): weekly interim results shown, at Will's request (before any week-11 game is played)
Will asked to see Test M results as the weeks go rather than only after week 18. From week 11 on, the weekly job
also computes the Test M statistic on the weeks completed so far and shows it on the dashboard's Engine tab and in
`docs/engine/test_m_interim.md`, labeled **interim, descriptive**. Under the standing rule (CLAUDE.md: interim looks
are descriptive) nothing changes because of an interim number: not the engines, the sample, the screens, the
statistic, the level or the pass rule, and the test is not stopped early in either direction. The verdict is the
`--grade` run after week 18, as frozen. The paper fills (docs/engine/paper_rules.md) can rebuild a game's forecast
with an earlier injury snapshot, through an option of the forecaster that Test M's own forecasts do not use; with the
option off the forecaster's output is unchanged (checked on the week-10 dry run).

## Amendment 2026-11-18 (3): Engine B-1.1 in place of B-1.0 (before any week-11 game is played; pending Will's choice)
A dry run on 2026 week 10 (outside the sample) showed B-1.0 forecasting near-zero yards for regular receivers
(CeeDee Lamb about 0.8 receiving yards against about 102 from A). The "known handicap" stated above is far larger than
expected: B-1.0 learned that a missing route share (`db_share_w3`) marks a fringe player, and nflverse publishes no
2026 participation, so every 2026 row looks like one. On 2023 week 10, blanking that one input dropped B's
receiving-yards forecasts for regular WRs from about 37-70 yards to under 1.

- **B-1.1** is B-1.0 without the route-share input (`challenger/model.py`: `ROUTE_SHARE = False`), everything else
  unchanged: same fit seasons (2018-2021), the same tuning procedure on 2022-2023 (`docs/engine/engine_b_tune_B-1.1.md`;
  it beats the frozen baselines in all six markets there, and the family choice is unchanged), frozen in
  `data/backtests/engine_b_frozen_B-1.1.json` with its parameters saved in `engine_B-1.1_params.pkl.gz` before any
  2024-2025 outcome was read for it.
- **Test S for B-1.1** is run once on 2024-2025 as for every version, at 0.05 / 6 / 2 per market (second version of
  Engine B). B-1.1 enters Test M only if it passes all six markets; otherwise Test M and the paper fills run Engine A
  alone and Test M's level becomes 0.05 (one engine).
- **Rows B-1.1 forecasts:** a market only for the player-games it was fitted and tested on, the Test S eligibility
  (`baselines.eligible`: at least 2 of the last 3 games on record at the market's minimum volume, from earlier games
  only). Outside them its fitted models extrapolate (on week 10 it gave tight ends about 25 rushing yards). Test M
  scores both engines on the props both forecast, as frozen above, so those props now leave Test M for both engines:
  on the week-10 dry run 384 of 549 screened DraftKings props remain, about 3,000 over eight weeks against the
  2,000 minimum. Engine A is unchanged.
- **Prices seen:** checking B-1.1's week-10 forecasts, means of P(over) by market were compared with DraftKings'
  week-10 de-vigged P(over). Week 10 is outside the sample and nothing was tuned on it: B-1.1's settings come from
  2022-2023 only and the eligibility rule was set before any result. Reported here so the look is on record.
- **Result (2026-11-18, Will chose this option):** B-1.1's Test S ran once on 2024-2025 at 0.05 / 6 / 2: PASS in all
  six markets (`docs/engine/test_s_engine_B-1.1.md`). B-1.1 replaces B-1.0 in Test M and the paper fills from week 11;
  Test M's level stays 0.05 / 2.
