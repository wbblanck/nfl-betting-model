# Prop Simulator: Declaration

Committed 2026-10-02 before the simulator was built and before any milestone (ladder) line was fetched.

## Plan
- A Monte Carlo simulator of each player's game: team plays from the closing spread and total, the player's
  share of targets / carries / dropbacks, yards per opportunity, touchdowns. Inputs are pre-game only.
- Uses: (1) probabilities for every over/under line; (2) pricing milestone ladders ("60+ receiving yards") with
  the distribution calibrated to the book's own main line, which does not require beating the book's mean.

## Seasons and slicing
- **Fit on 2024. Check on 2025, where rules may be chosen** (slices by market, threshold or rung are allowed
  there; everything found is a hypothesis).
- **2026 is the test.** No 2026 milestone line is read, and no 2026 simulator output is compared with a 2026
  result, until `docs/simulator_confirm.md` (at most 3 rules, fixed thresholds, Bonferroni, pass criteria) is
  committed. 2026 is then graded whole; interim looks are descriptive.

## Evaluation fixed now
1. Known answers first: identical inputs reproduce; a planted effect is found and noise is not; no game's own
   result enters its inputs.
2. Over/under probabilities on 2025: log loss against the de-vigged DraftKings price; calibration by decile;
   distribution width (share of results inside the simulated 50% and 80% ranges).
3. Ladders: on 2024–2025, compare each milestone price with the probability implied by the simulator centered on
   the same book's main line; any rule is a bet at the posted milestone price, graded on the actual stat.

## Addendum (2026-10-02, before any matchup result): opponent defense
The simulator v1 results are in `docs/simulator_report.md`. Added input: the opponent defense's record against
the player's position group in its earlier games only (catch rate, yards per catch, yards per carry, completion
rate, yards per completion allowed, and the share of targets / carries going to that position), relative to
the league average and shrunk toward average. One strength weight is chosen on 2024 (grid 0, 0.5, 1, 1.5);
2025 checks it. Same evaluation as above; anything found is still a hypothesis for 2026.
