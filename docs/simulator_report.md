# Prop Simulator: Report

Plan: `docs/simulator_declaration.md` (commit 260ad26, before the simulator was built or any ladder line was
fetched). Code: `src/nflbet/sim.py`, `src/nflbet/ladder.py`; outputs `docs/sim_eval.txt`, `docs/ladder_explore.txt`.

## Result: nothing to take forward; no 2026 rule is registered

### Over/unders (fit 2024, check 2025)
| 2025 | Simulator | DraftKings de-vigged |
|---|---|---|
| Log loss (coin flip 0.6931) | 0.7500 | 0.6902 |
| Mean miss vs actual | 17.90 | 16.25 |

Overconfident: where it said 16% the over hit 47%. Betting where it differed from DraftKings by 5+ points:
overs −6.1%, unders +0.1%. Its spread of outcomes is roughly right for yardage (results inside its 80% range
76-86% of the time), too wide for receptions.

### Milestone ladders (simulator centered on the same book's main line)
| Milestone "yes" bets | 2024 (fit season) | 2025 (check) |
|---|---|---|
| Every rung, implied < 10% | −24.2% (n 1,924) | −37.7% (n 18,513) |
| Every rung, implied 75%+ | −8.1% (n 2,590) | −6.2% (n 11,875) |
| Model ≥ 5 points above implied | −10.7% (n 2,748) | −32.8% (n 13,484) |

The centered simulator's upper tail is too fat: on longshot rungs it says 9-11%, books imply 6-8%, results hit
4-6%. It beat the books only on near-sure rungs (2025: book 86.7%, simulator 79.2%, hit 81.4%), where only the
"yes" side is sold. The one profitable 2024 slice (passing yards, +19.8%, n 328) reversed in 2025 (−11.0%, n 332).

### What it does show
DraftKings' milestone ladders carry the heaviest margins seen in this project: "yes" lost money in every
probability band in both seasons. 2026 milestone lines were fetched by the weekly job but never read.

## Addendum: opponent-defense matchup (`docs/matchup_eval.txt`)
Each defense's record against the position group in its last 16 games (catch rate, yards per catch / carry /
completion, completion rate, share of targets and carries to the position), relative to league average and shrunk.
Chosen on 2024 by over/under log loss: weight 0 (0.7546), 0.5 (0.7548), 1.0 (0.7578), 1.5 (0.7624), so the rule
picks no matchup. Descriptive 2025 at full weight: log loss 0.7514 vs 0.7500 without, mean miss 17.92 vs 17.90;
ladder "yes" bets where the model beats the price −5.7% to −11.2%. The matchup, measured this way, adds nothing
the spread and total don't already carry.
