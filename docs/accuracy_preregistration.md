# Model Accuracy Without Lines, 2021-2023: Pre-registration (2026-10-08)

Requested by Will: no prop lines exist before 2024 (docs/props_data_audit.md), so instead of win rate, test how
well the two S1 models predict players' stats. Committed before anything below was computed (script:
`scripts/accuracy_eval.py`, committed with this file). Nothing here changes S1 or any live record.

## What this can and cannot show
It shows whether the projection and the simulator predict stats better than a plain recent average in seasons the
models were never fitted on (both are fitted on 2024). It cannot show whether they beat the books: books set lines
more accurately than a recent average (2024-25: the books' line missed by less than the simulator's mean,
docs/sim_eval.txt).

## Sample
- Seasons 2021, 2022, 2023 (regular season), pooled; 2025 reported alongside as a reference season (also never
  fitted on). nflverse player stats; markets = the nine S1 markets.
- Player-games where the player has at least the projection model's minimum prior games and is a prop-type player:
  his average over his previous 5 games (any season, strictly before the game) is at least rec 2, rec_yds 20,
  rush_att 6, rush_yds 25, rush_rec_yds 30, pass_att 20, pass_cmp 12, pass_yds 150, pass_rush_yds 160; pass
  markets QBs only.
- **Baseline** = that previous-5-game average. **Pseudo-line** = baseline rounded down to the nearest whole number,
  plus 0.5 (a line near the player's recent level, as a book would set it from recent games alone).

## Tests (family of 9 markets for each; Bonferroni: two-sided 0.05 / 9)
**A. Projection vs baseline.** Mean absolute error of the projection minus that of the baseline, per market, with a
week-clustered bootstrap interval (season-week clusters, 4,000 resamples, seed 7). The projection is **better** in a
market if the interval lies entirely below 0.

**B. Simulator at the pseudo-line.** Log loss of the simulator's P(over pseudo-line) minus that of the baseline
frequency (share of the player's previous up-to-10 games over the pseudo-line, shrunk as (hits + 1) / (n + 2)).
Same interval; the simulator is **better** in a market if the interval lies entirely below 0. Also reported:
coin-flip log loss (0.6931), calibration by decile, calibration slope (logistic fit of the outcome on logit P; below
1 = overconfident), and how often the actual falls inside the simulated 50% / 80% ranges.

"The models are no better than a recent average" is a valid result.
