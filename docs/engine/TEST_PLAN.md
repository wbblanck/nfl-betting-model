# Test plan

Every test below runs in CI (`pytest -q`). "Planted" means the test builds a case with a known wrong answer and
checks the code finds it, as CLAUDE.md requires before any analysis code is trusted.

## In place (tests/test_engine.py)
| Blueprint test | What is checked |
|---|---|
| Contract matching | exact identity only; a different line, a combined stat, partial-game text, whole-number lines, wrong outcomes, a missing or mismatched event are each refused with a reason |
| Player identity | same name on a team not in the game is ignored; two candidates = ambiguous = unmatched; spelling variant falls back to last name + initial only when unique |
| Fee calculation | pregame zero on WHEN_LIVE, live and ALWAYS hand cases, unknown rule raises |
| Executable price | buying a side walks the other side's levels cheapest first; partial fill, limit price and empty book hand cases; checked against a real saved Novig book |
| Completion, reception, target, carry accounting; QB/receiver reconciliation; distribution support | clean box passes; each planted break is found in exactly the broken run; float arrays refused |
| Market-input isolation (imports) | planted forbidden imports are found, including inside functions; engines A and B import no price layer, no line reader, no research layer and not each other |
| Immutable records | editing, deleting or reordering a ledger line breaks verification and blocks further appends |
| Simulation precision | Monte Carlo standard error matches the binomial formula at 5,000-100,000 runs |
| No execution | no order code or write call in the engine; `LIVE_EXECUTION` is False |
| Registry | every graded market has a definition; shadow families cannot be un-shadowed; Novig types exist in the saved probe |

## Required before each later phase's gate
| Phase | Test | Pass condition |
|---|---|---|
| 1 | Player identity validation | zero duplicate (player_id, season, week) rows; traded player on the right team each week (hand cases) |
| 1 | Roster reconciliation | every stat row's player is on that week's roster or listed in an exceptions file with a reason |
| 2 | Historical timestamp validation | every feature's latest known-at time is before its prediction time |
| 2 | Future-data perturbation | scramble all rows dated at or after T (stats, injuries, rosters): features for T are byte-identical |
| 2 | Current-game perturbation | scramble the game's own outcomes: its pregame features are byte-identical |
| 3-5 | Price perturbation | scramble every line, quote and close on disk: both engines' outputs are byte-identical for a fixed seed |
| 3-5 | Accounting on every run | `accounting.violations` is empty for every simulated team-game, not a sample |
| 3-4 | Planted signal | each fitted layer recovers a planted effect in synthetic data and finds none in shuffled data |
| 4 | Quantile crossing | zero crossings after rearrangement |
| 5 | Simulation convergence | two seeds agree within 4 Monte Carlo standard errors on every reported probability |
| 7 | Quantile coverage, calibration | reported per market on 2024-2025 (Test S); thresholds are the pre-registration's |
| 6 | Quote freshness | a quote older than its limit, or a snapshot whose catalog and book times differ by more than the limit, is not priced |
| 8 | Partial fills, settlement, position reconciliation | hand cases, once paper rules exist |

## Acceptance gates that are not ROI
No gate uses historical return. A phase passes on correctness (leakage, accounting, support, reproducibility) and
the pre-registered accuracy tests. Few or no qualifying prices is an acceptable outcome and thresholds are not
loosened to produce more.
