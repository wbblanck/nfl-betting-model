# Batch 4: XGBoost margin model: Pre-registration (2026-11-06)

Requested by Will (2026-11-06: "Sure include it in the current list of testing going on", after asking what an
XGBoost model is). Committed before any XGBoost model has been trained on these features and before any of its output
exists. Code: `src/nflbet/ats/xgb.py`, `scripts/batch4.py`, tests `tests/test_xgb.py`. Spreads only. A props version
would need its own pre-registration on the 2026 season.

## What it is
XGBoost (gradient-boosted decision trees) builds hundreds of small decision trees in sequence, each one correcting the
errors of the ones before. Unlike Elo or a regression, it can find interactions and thresholds by itself (for example
"rest matters only for road favorites"). The cost is that it overfits easily on a small sample, and NFL seasons are
small (about 270 games each).

## Samples
- **Train: 2016-2021** regular season, weeks 2-18 (about 1,500 games). Ratings run forward from 1999.
- **Test: 2022-2025** regular season, weeks 2-18, games with an nflverse closing `spread_line` and both spread prices
  (the same 1,023-game sample as E1-E7 and batch 3). These seasons have been used for other models' tests; no
  tree model has ever been trained or scored on them.
- Spread sign: nflverse, positive = home favored. Home covers when margin > `spread_line`; margin = line is a push.

## Features (all known before kickoff; target = home margin)
1. Frozen Elo gap d and Elo fair margin (`data/backtests/elo_constants.json`).
2. QB: qb_delta for home and away from the **expected** starter (batch 3 G1 rule: previous game's starter unless the
   final report lists him Out or Doubtful), EPA/dropback rating as in the simulator.
3. Kalman fair margin and its variance (batch 1 constants).
4. Each team's offensive and defensive EPA per play over its previous 8 regular-season games (across seasons).
5. League scoring level, home rest days, away rest days, neutral site, division game, dome (roof `dome` or `closed`),
   week.
No market input (spread, total or moneyline) is a feature.

## Model, fixed in advance
`reg:squarederror`, max_depth 3, learning_rate 0.03, subsample 0.8, colsample_bytree 0.8, min_child_weight 20,
reg_lambda 1, seed 0. The only tuned setting is the number of trees, chosen from {100, 200, …, 1000} by
leave-one-season-out mean absolute error on 2016-2021. Then the model is refit on all of 2016-2021 and frozen
(`data/backtests/batch4_model.json`) before the test runs.

## Tests (family of 2, Holm at 0.05; week-clustered bootstrap, 2,000 draws; one-sided)
- **X1 beats Elo:** paired d = |Elo − margin| − |XGB − margin|. Pass: interval above 0.
- **X2 beats the closing line:** where |XGB − spread_line| ≥ 1.5, bet XGBoost's side at the closing line at the
  listed nflverse price (`home_spread_odds` / `away_spread_odds`); pushes return 0. Pass: n ≥ 100 bets in ≥ 30 weeks
  and the ROI interval is above 0.
Holm: smaller p against 0.025, the other against 0.05, stopping at the first failure.

## Power, stated in advance
- X1: the per-game SD of a paired MAE difference was about 3.2 points for Elo vs the simulator on 2022-2025, so at
  1,023 games the standard error is about 0.10 points. Only a gain of roughly a quarter point or more would be
  detected reliably.
- X2: one bet's profit has SD about 0.95 units; at 500 bets the ROI standard error is about 4.2%, so only an edge near
  +10% ROI would be detected reliably. A fail means "no evidence", not "no edge".

## Known answers first (synthetic data, before any real output)
1. Planted interaction: on synthetic data where the margin depends on x1·[x2 > 0] plus noise (SD 13), the model with
   these settings beats a linear regression on held-out MAE.
2. Noise: on a target unrelated to the features, held-out MAE is not better than predicting the training mean by more
   than 1%.
3. No look-ahead: the rolling EPA features for a game are unchanged when every later game is deleted.
4. Same seed, same data → identical predictions.

Descriptive only: MAE of XGBoost, Elo, a linear regression on the same features, and the closing line, by season;
X2 at 0.5 / 1 / 2 / 3-point gaps; feature importance (gain).
