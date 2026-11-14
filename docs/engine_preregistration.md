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

