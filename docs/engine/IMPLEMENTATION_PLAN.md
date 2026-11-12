# Implementation plan

Each phase ends at a gate. The next modelling phase does not start until the gate's tests are in CI and green.
Paths are under `src/nflbet/engine/` unless they start with another directory.

| Phase | Work | Files | Gate | State |
|---|---|---|---|---|
| 0 | Specs, registry, schemas, isolation rules | `config/markets.yaml`, `registry.py`, `contracts.py`, `pricing.py`, `accounting.py`, `ledger.py`, `novig_capture.py`, `scripts/fetch/novig_books.py`, `.github/workflows/novig-books.yml`, `tests/test_engine.py`, `docs/engine/` | registry, matching, pricing, accounting, ledger and isolation tests pass | **done 2026-11-12** |
| 1 | Warehouse: nflverse 2010-2025 to Parquet under `data/cache/engine/` (not in git), manifest with row counts and file hashes | `data/nflverse.py`, `data/manifest.py`, `scripts/engine_ingest.py` | every table joins on `player_id` / `game_id` with zero duplicate keys; coverage table by season per source committed as `docs/engine/coverage.md` | next |
| 2 | Features as of a timestamp | `features/*.py`, `features/store.py` | perturbation tests: changing any row dated at or after the prediction time leaves the features byte-identical | |
| 3 | Baselines (spec section 6), then Engine A layers: environment, script, personnel, opportunity, efficiency | `baselines.py`, `replication/*.py` | accounting holds on every simulated run; planted-signal test for each fitted layer | |
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
