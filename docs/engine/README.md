# Player-prop engine

Built from Will's blueprint of 2026-11-12. Two independent prediction engines, one pricing layer, one audit trail.
Tests and season roles: `docs/engine_preregistration.md`.

| File | What it settles |
|---|---|
| `IMPLEMENTATION_PLAN.md` | phases, files, gates, what is done |
| `MODEL_SPECIFICATION.md` | both engines, the simulator, baselines |
| `DATA_DICTIONARY.md` | every input, its source and the time it is known |
| `TEST_PLAN.md` | mandatory tests and where each lives |
| `NOVIG_INTEGRATION.md` | book recording, contract matching, cost, fees |

## Where the blueprint was changed, and why
| Blueprint | Here | Reason |
|---|---|---|
| Separate repository `nfl-player-props` | Package `src/nflbet/engine/` in this repo | This session can only write to this repo. The engine reuses the odds arithmetic, HTTP client, name keys and Novig reader already tested here, and imports no research code, so it can be lifted out later. |
| 2024-2025 are locked out-of-sample | 2024-2025 test outcome accuracy only; prices are tested prospectively | Both seasons' prop lines are already explored in this repo (pre-registration, "What has already been seen"). |
| `picks_enabled: true` on yardage and count markets | `shadow: false` means "may be compared with a price in a test"; nothing produces picks | CLAUDE.md allows four named trackers and no other pick list. A paper portfolio needs a fifth exception from Will. |
| Novig fee table (no pregame fee, 0.06 live) | Fee read from each market's own `fee` record, saved with the quote | The saved catalog shows the coefficient differs by market and date: 0.03 on props on 2026-10-14, 0.06 on spreads in the later spread probe. |
| WebSocket book capture as the primary collector | REST snapshots from GitHub Actions on a schedule | Actions jobs are short-lived and the sandbox cannot reach Novig. Snapshots are sparse; a streaming collector needs an always-on host. |
| PostgreSQL, Streamlit | CSV/JSONL records in git, the existing static dashboard | That is how every tracker here runs (Actions writes, Pages reads). Revisit when a record outgrows git. |
| Engine A reproduces Projexions | Engine A follows the blueprint's description of that method | No published Projexions methodology was found by search on 2026-11-12, so nothing here is checked against it. |
| Live order placement (Mode 3) | No order code exists | Out of scope until separately authorized; `tests/test_engine.py` fails if order code appears. |

## Starting point
The repo already has a play-level game simulator (`src/nflbet/gamesim/`) with a negative binomial player layer. On
2025 DraftKings props it scored a log loss of 0.7266 against DraftKings' 0.6899 and a coin flip's 0.6931
(`docs/gamesim_props_dist.md`), and the M1 mix of the two scored 0.68873 against 0.68987, mostly by recalibrating
DraftKings' own price (`docs/gamesim_calibration.md`, `docs/mix_live_rules.md`). That report names the likely cause:
player share and per-play yards treated as known. Sections 5.3-5.5 of the blueprint (role uncertainty,
Dirichlet-multinomial allocation, shrunk efficiency) address exactly that, so Engine A is that work, not a second
simulator from scratch. Neither engine may import `gamesim`; shared ideas are re-fit on the engine's own seasons.
