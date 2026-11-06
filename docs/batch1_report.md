# Batch 1 results: Elo at the opener, line movement, opener blend, Elo + QB, Kalman

Pre-registration: docs/batch1_preregistration.md (committed before any 2005-2015 output). Constants fit on 2016-2021
and frozen in data/backtests/batch1_constants.json before the test ran (docs/batch1_fit.txt). Numbers:
data/backtests/batch1.json. Test seasons 2005-2015 (2,640 games, weeks 2-17) and, where SBRO lines are needed,
2007-2015 (2,160 games). Holm at 0.05 over five tests; week-clustered bootstrap.

## Bottom line
**One of five passes.** From the opener, the line moves toward Elo by the close (H2), as it did on 2022-2025. Nothing
else clears its bar. Betting Elo's side at the opener came closest: 54.0% covers and ROI +3.1% on 1,324 bets, but
p = 0.094 against a Holm level of 0.017, so that's no evidence of an edge. Elo + QB and the Kalman rating were
not measurably better than plain Elo.

| Test | Result | p | Holm level | Verdict |
|---|---|---|---|---|
| H2 line moves toward Elo (n 2,160) | coefficient +0.108, interval +0.046 to +0.188 | 0.000 | 0.010 | **PASS** |
| H3 opener blend beats the opener (n 2,160) | +0.001 points, interval −0.000 to +0.002 | 0.013 | 0.0125 | FAIL (and too small to matter) |
| H1 Elo's side at the opener, gap ≥ 1.5 (1,324 bets, 144 weeks) | 54.0% covers, ROI +3.1%, interval −2.0% to +8.0% | 0.094 | 0.017 | FAIL |
| H4 Elo + QB beats Elo (n 2,640) | +0.016 points, interval −0.015 to +0.047 | 0.167 | 0.025 | FAIL |
| H5 Kalman beats Elo (n 2,640) | +0.007 points, interval −0.050 to +0.064 | 0.407 | 0.050 | FAIL |

Holm stops at the first failure in p order (H2 passes, H3 fails), so H1, H4 and H5 fail regardless of their own p.

## Fitted constants (2016-2021)
- Elo + QB: q 400 Elo points per EPA/dropback, regression c 1/2 (inside the widened grid this time), b 0.0868.
- Kalman: home field 1.49 points, margin noise σ 12.04, weekly drift τ_w 0.83, between-season shrink ρ 0.56, τ_s 3.18.
- Blend weight w = 0.008 on 1,457 games 2016-2021: Elo adds almost nothing to the opener's forecast of the margin.
  H3 was close to a pass only because a near-zero blend almost never hurts; its gain is 0.001 points per game.

## Descriptive (not tested)
Margin MAE, points:

| Forecast | Games | MAE |
|---|---|---|
| nflverse closing spread | 2,640 | 10.700 |
| SBRO close | 2,160 | 10.794 |
| Blend | 2,160 | 10.898 |
| SBRO opener | 2,160 | 10.899 |
| Elo + QB | 2,640 | 10.898 |
| Kalman | 2,640 | 10.907 |
| Elo | 2,640 | 10.914 |
| Elo (on the 2,160 line games) | 2,160 | 10.985 |

Elo's side against the opener by gap, with the same bets graded against the close:

| Gap ≥ | Bets | Covers vs opener | ROI vs opener | Covers vs close |
|---|---|---|---|---|
| 0.5 | 1,845 | 52.7% | +0.6% | 52.5% |
| 1.0 | 1,600 | 53.8% | +2.6% | 53.6% |
| 2.0 | 1,100 | 54.0% | +3.0% | 53.8% |
| 3.0 | 656 | 56.0% | +6.6% | 55.0% |

The covers rise with the gap, and they hold against the close too. That pattern is descriptive only. The rules say a
held-out result that looks interesting does not become a new hypothesis on these seasons; it would need fresh seasons
(none are left for Elo before 2005, and the 2022-2025 close test already failed: E3, 47.9%).

## Disclosures
- Kalman tracks each team's strength without the covariance between teams (diagonal approximation).
- SBRO has no prices; bets were graded at −110.
- Parameters fit on 2016-2021 were applied to 2005-2015; scoring and rules differ between those eras.
- Ratings update through playoff games; tests use regular-season weeks 2-17.
