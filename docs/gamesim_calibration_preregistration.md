# Calibrating the Game Simulator Against the Market: Pre-registration (2026-11-05)

Will asked (2026-11-05) how to calibrate the simulator. Every test so far points the same way: the market is the
better base, so both tests below ask how far to move off the market toward the simulator. Family of 2 tests, each at
0.05 / 2. Committed before either test's numbers are computed.

## M1, props: market + simulator mix
- **Simulator probability:** the negative binomial version (docs/gamesim_props_dist.md: 10,000 runs per game, sizes
  chosen on 2024), recomputed with the same code and seed. It is the best prop version so far.
- **Model:** logit(p) = a_g + b_g · logit(p_DK) + c_g · logit(p_sim), with p_DK the de-vigged DraftKings price. The
  groups g are receiving (rec, rec_yds), rushing (rush_att, rush_yds) and passing (pass_att, pass_cmp, pass_yds).
  It is fit by maximum likelihood on 2024 DraftKings props (screen and markets as before), then frozen.
- **Test on 2025:** the paired per-prop log-loss difference (mix − DK de-vigged), with a week-clustered bootstrap and a
  two-sided interval at 0.025. Better if it is entirely below 0.
- Reported alongside: the fitted weights (c_g near 0 means the simulator adds nothing), calibration bands, and,
  descriptively, the ROI at DraftKings prices where the mix gives a side 55% or more.

## M2, spreads: bet at the opener
- **Rule (fixed in advance, Will's 1.5 points):** take G3's fair margin (docs/gamesim_confirm.md, 1,000 runs per
  game, the registered confirm run). If |fair − open| ≥ 1.5, bet the simulator's side at the opening spread and
  opening price (data/odds/asb_nfl_games.csv; a missing price is taken as −110). The bet is graded against the
  opening spread, and a push is 0.
- **2022-2024 (descriptive only):** these openers were already used by T2 (lines move toward the simulator), so they
  cannot test this rule.
- **Test on 2025** (openers not used before; weeks 2-18): pass if there are 30+ bets in 10+ weeks and the ROI interval
  (week-clustered bootstrap, two-sided at 0.025) is entirely above 0. Also reported: the cover rate and the
  closing-line value of each bet (close − open, toward the bet side).

## After
If a test passes, its rule is frozen and tracked forward on 2026 weeks 10-18 before any use, labeled unvalidated.
"Nothing survives" is a valid result.
