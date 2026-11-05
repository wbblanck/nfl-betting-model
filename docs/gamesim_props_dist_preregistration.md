# Game Simulator Props: Poisson and Negative Binomial Counts (2026-11-04)

Requested by Will (2026-11-04): "Can you do a Poisson [/ negative] binomial distribution test and see if that changes
any of the results for the better?" Follow-up to docs/gamesim_props_eval.md (binomial counts: 2025 log loss 0.7496,
80-90% calls hit 51.9%). Committed before any Poisson or negative binomial output exists.

Already seen (disclosed): the binomial version's 2024 and 2025 results above. The question is chosen because that
version is overconfident; wider count distributions are the obvious candidate, so this is a test of a stated
mechanism, not a search.

## Versions (game runs and everything else unchanged: G3 simulator, 10,000 runs per game, same player layer)
- **B (reference):** as now. Targets ~ Binomial(team attempts, share), carries ~ Binomial(team carries, share), QB
  attempts ~ Binomial(team attempts, share).
- **P:** the same three counts ~ Poisson(team count x share).
- **NB:** the same three counts ~ negative binomial with mean team count x share and size r (variance mean + mean²/r),
  one r per count (targets, carries, QB attempts), chosen on **2024** from {2, 4, 8, 16, 32} by log loss on the 2024
  DraftKings props of the markets that count drives (targets: rec, rec_yds; carries: rush_att, rush_yds; QB attempts:
  pass_att, pass_cmp, pass_yds).
- Catches and completions stay binomial thinning of those counts; per-play yards unchanged.

## Test on 2025 (DraftKings props screened as before; family of 2, Bonferroni)
For P and NB each: the paired difference in log loss vs B, per prop, averaged; week-clustered bootstrap interval
(two-sided 0.05 / 2). **Better** if the interval is entirely below 0. Reported alongside: log loss vs DraftKings'
de-vigged price, calibration bands (60-70% ... 90-100% on the favored side), and the 75%+ bucket's hit rate and ROI
(descriptive). Being better than B does not make a version usable: it would still have to beat or add to
DraftKings' price in its own pre-registered test.
