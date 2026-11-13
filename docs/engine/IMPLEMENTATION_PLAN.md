# Implementation plan

Each phase ends at a gate. The next modelling phase does not start until the gate's tests are in CI and green.
Paths are under `src/nflbet/engine/` unless they start with another directory.

| Phase | Work | Files | Gate | State |
|---|---|---|---|---|
| 0 | Specs, registry, schemas, isolation rules | `config/markets.yaml`, `registry.py`, `contracts.py`, `pricing.py`, `accounting.py`, `ledger.py`, `novig_capture.py`, `scripts/fetch/novig_books.py`, `.github/workflows/novig-books.yml`, `tests/test_engine.py`, `docs/engine/` | registry, matching, pricing, accounting, ledger and isolation tests pass | **done 2026-11-12** |
| 1 | Warehouse: nflverse 2010-2025 to Parquet under `data/cache/engine/` (not in git), manifest with row counts and file hashes; player-week outcome table | `data/nflverse.py`, `data/player_week.py`, `scripts/engine_ingest.py`, `scripts/engine_coverage.py` | zero duplicate player-week keys; every stat row on that week's roster with the same team; games match the schedule; `docs/engine/coverage.md` committed | **done 2026-11-12** |
| 2 | Features as of a kickoff: per-game facts, then sums over each player's, offense's and defense's earlier games (last 3, 5, 8 games, season to date, last season) | `features/facts.py`, `features/build.py`, `scripts/engine_feature_check.py` | hand-computed sums match; scrambling every raw row from a cut-off on leaves all rows up to it identical, on synthetic data in CI and on the real warehouse (`docs/engine/feature_check.md`); a planted leak is caught | **done 2026-11-13** |
| 3 | Baselines (spec section 6), then Engine A layers: environment, script, personnel, opportunity, efficiency | `baselines.py`, `scoring.py`, `replication/environment.py`, `opportunity.py`, `efficiency.py`, `model.py`, `scripts/engine_baselines.py`, `scripts/engine_a_tune.py` | accounting holds on every simulated run; planted-signal test for each fitted layer | baselines **done**; Engine A version 0.2 built and run on the tune seasons (`docs/engine/engine_a_tune.md`): team volume, game-day active list with a chance-to-play draw, Dirichlet-multinomial split, catch and yardage. Still to build before it is frozen: expected starter from the depth chart, game script, joint draw of both teams, availability before the active list is out |
| 4 | Engine B: quantile, count, hierarchical models, joint layer | `challenger/*.py` | no import of Engine A; quantile crossing zero after correction; support tests | |
| 5 | Simulator completion: touchdowns, interceptions, longest play, combined stats | `simulation/*.py` | every box score reconciles with its events; seed stability within the Monte Carlo error | |
| 6 | Pricing against recorded Novig books | `pricing.py`, `contracts.py` (extend) | every matched contract re-derivable from the saved snapshot; unmatched never priced | partly built in phase 0 |
| 7 | Verification: Test S, calibration, A versus B | `verification/*.py`, `scripts/engine_test_s.py` | Test S run once per frozen version, report committed | |
| 8 | Paper fills against recorded books | `paper.py` | needs Will's CLAUDE.md exception and frozen rules first | blocked on Will |
| 9 | Dashboard pages and prospective Test M | `src/nflbet/dashboard.py` (extend) | Test M judged on its declared sample | |

## Phase 1 detail (the next commit)
1. `scripts/engine_ingest.py --seasons 2010-2025` pulls, per season: play-by-play, player stats, weekly rosters,
   snap counts, schedules; and where they exist: participation, depth charts, injuries, Next Gen Stats, FTN charting.
2. Before any modelling reads them, write `docs/engine/coverage.md`: rows and first/last season per source, share of
   player-games with a `player_id` in every joined table. This is schema and counts only.
3. Canonical keys: `player_id` = nflverse GSIS ID; `game_id` = nflverse `game_id`; team codes through
   `nflbet.sources.ids.TEAM_FIX`.
4. Tests on hand cases: a traded player appears once per week with the right team; a player with snaps and no stat
   row gets zeros (CLAUDE.md data trap); bye weeks produce no row.

## Order inside phases 3-4
Start with pass_yds, pass_att, rush_yds, rush_att, rec, rec_yds (the Test S markets), then pass_cmp, targets and the
two combined-yardage markets, then shadow markets. That is a build order, not a cut in coverage.
