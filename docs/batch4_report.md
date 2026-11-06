# Batch 4 results: XGBoost margin model

Pre-registration: docs/batch4_preregistration.md (committed before any XGBoost training). Model trained on 2016-2021
and frozen in data/backtests/batch4_model.json before the test ran (docs/batch4_fit.txt). Numbers:
data/backtests/batch4.json. Test: 2022-2025 regular season, weeks 2-18, 1,023 games with closing spreads and prices.

## Bottom line
**Neither test passes.** XGBoost forecasts the margin no better than plain Elo (it's slightly worse), and betting its
side against the closing line lost 9.3% on 608 bets. That loss is large enough that its interval sits wholly below
zero. On about 1,500 training games the trees have little to learn beyond the ratings they're given: the best tree
count was the smallest one allowed (100), and a plain linear regression on the same features did slightly better.

| Test | Result | p | Holm level | Verdict |
|---|---|---|---|---|
| X1 beats Elo, MAE gain (n 1,023) | −0.039 points, interval −0.191 to +0.113 | 0.686 | 0.025 | FAIL |
| X2 its side vs the close, gap ≥ 1.5 (608 bets, 68 weeks) | 47.1% covers, ROI −9.3%, interval −15.9% to −2.7% | 0.986 | 0.050 | FAIL |

## Training
- 1,457 games, no missing feature values.
- Tree count by leave-one-season-out MAE: 100 → 10.368, rising steadily to 1,000 → 10.890. 100 was the edge of the
  pre-registered grid, so fewer trees might have done a little better. That can't be tested on these seasons now.

## Descriptive (not tested)
Margin MAE, points:

| Season | Games | XGBoost | Elo | Linear, same features | Close |
|---|---|---|---|---|---|
| 2022 | 255 | 9.056 | 8.986 | 8.848 | 8.718 |
| 2023 | 256 | 10.657 | 10.463 | 10.434 | 9.818 |
| 2024 | 256 | 9.998 | 10.071 | 10.048 | 9.648 |
| 2025 | 256 | 10.298 | 10.333 | 10.449 | 9.959 |
| All | 1,023 | 10.003 | 9.964 | 9.946 | 9.537 |

XGBoost's side against the close, by gap: 0.5+ 892 bets, 47.5%, ROI −8.7%; 1+ 748, 47.6%, −8.4%; 2+ 501, 48.3%,
−7.2%; 3+ 324, 49.1%, −5.7%.

Feature importance (gain), top five: Elo gap, Kalman margin, Elo fair margin, away offensive EPA (last 8 games), home
QB. XGBoost and Elo forecasts correlate at 0.91.

## Disclosures
- Spreads only; a props version would need its own pre-registration on 2026.
- The test seasons were used for other models' tests before (E1-E7, batch 3); no tree model had touched them.
- The QB input is the expected pregame starter (batch 3 G1 rule), not the recorded one.
- Prices are nflverse's closing spread prices.
