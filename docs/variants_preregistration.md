# S1 Variants: Backtest Pre-registration (2026-10-08)

Requested by Will after week 5's first runs produced one S1 pick, priced at −168: "backtest all the variants".
Committed before any variant below was computed (script: `scripts/variants_backtest.py`, committed with this file).
S1 itself is unchanged and stays the locked 2026 rule (docs/simulator_confirm.md).

## Status of the evidence
2024 and 2025 were both used to build S1 (docs/screener_explore.txt), so this is exploration, not confirmation:
anything that passes below is a **hypothesis**. It becomes a rule only if it is then tracked live on 2026 as its own
record, written down before its first pick, and judged at season end. 2026 data is not used here (it is S1's
test season).

Three variants already have 2024-25 answers in docs/screener_explore.txt (3+ of 4 agree, 2+ of 4, no price
signal). They are re-run here with the same code path so every variant is graded the same way.

## Data and grading
- Final Action Network lines, 2024 and 2025 regular season (`data/props/an_props_<season>.csv`), DraftKings props
  in the nine S1 markets, screened as S1 is (de-vigged P(over) 0.35-0.65, hold < 10%, player matched), pushes
  dropped. Signals computed exactly as `screener.score` (simulator and projection constants fitted on 2024, so
  **2025 is the primary season**; 2024 is in-sample for those constants).
- One bet per prop, 1 unit at DraftKings' price on the variant's side. ROI per unit; week-clustered bootstrap
  interval (4,000 resamples, seed 7), as S1's own test (`props_selective.evaluate`).

## Variants (the family is V2-V13: 12 tests)
Signals: B = books disagree (DK at the extreme line), J = projection >= 10% from the line, M = simulator >= 5
points from DK de-vigged P(over), $ = DK prices that side below −120. "Agree" = point the same way.

| ID | Rule |
|---|---|
| V1 | S1 reference: B, J, M, $ all agree (not in the family) |
| V2 | 3 or more of 4 agree, none against |
| V3 | B, J, M agree; $ neutral (neither side below −120) |
| V4 | J, M, $ agree; B neutral (DK line equal to the others) |
| V5 | S1 with projection threshold 15% instead of 10% |
| V6 | S1 with simulator threshold 8 points instead of 5 |
| V7 | S1 with price threshold −110 instead of −120 |
| V8 | S1 with price threshold −130 instead of −120 |
| V9 | S1 with B computed from DraftKings vs FanDuel only (the "S1 on ParlayAPI lines" record) |
| V10 | S1, unders only |
| V11 | V2, unders only |
| V12 | B, J, M agree and the side is priced −120 or longer (better prices) |
| V13 | B, J, M agree, price ignored |

## Pass criteria (hypothesis screen)
A variant passes if, on **2025**: n >= 30 bets in >= 10 weeks, and the week-clustered ROI interval at one-sided
0.025 / 12 (Bonferroni over the 12) has its lower end above 0; **and** on 2024 its ROI is not below 0 when it has
>= 30 bets there (fewer than 30 in 2024 does not count against it). "Nothing passes" is a valid result.

All 13 rows are reported with n, weeks, win rate, mean break-even, ROI and interval for each season.
