# Batch 5 results: joint scores, key-number margins, simulator totals, early-season ratings

Pre-registration: docs/batch5_preregistration.md (committed before any batch 5 fit). Constants fit on 2016-2020 and
frozen in data/backtests/batch5_constants.json before the test ran (docs/batch5_fit.txt). Numbers:
data/backtests/batch5.json. Holm at 0.05 over five tests; week-clustered bootstrap, 2,000 draws.

## Bottom line
**Two of five pass, both about the shape of the margin, not about beating a line.**
- The key-number model (K1) gets the margin clumps nearly right: 14.3% on 3 against 15.2% actual (NB 5.4%).
- The shared-touchdown model (S1) also beats NB on the exact margin, by much less.
- Neither prices covers better than NB against the closing line. All of them stay worse than a coin flip there,
  because their center is still Elo's number.
- Betting the simulator's totals lost money (−7.8% ROI on 611 bets, interval below zero).
- Starting Elo from the market and the ridge rating did not improve weeks 2-6.

| Test | Result | p | Holm level | Verdict |
|---|---|---|---|---|
| K1 key-number margin vs NB, exact-margin log probability (n 1,023) | +0.143, interval +0.111 to +0.176 | 0.000 | 0.0125 | **PASS** |
| S1 shared-touchdown model vs NB, same measure (n 1,023) | +0.035, interval +0.021 to +0.049 | 0.000 | 0.010 | **PASS** |
| R1 Elo with a market start vs Elo, weeks 2-6 MAE (n 811) | +0.032 points, interval −0.130 to +0.197 | 0.350 | 0.017 | FAIL |
| R2 ridge rating vs Elo, weeks 2-6 MAE (n 811) | +0.001 points, interval −0.135 to +0.142 | 0.502 | 0.025 | FAIL |
| D3 simulator's side vs the closing total, gap ≥ 1.5 (611 bets, 68 weeks) | 47.9% wins, ROI −7.8%, interval −13.9% to −2.3% | 0.991 | 0.050 | FAIL |

## Fitted constants (2016-2020)
- S1: shared touchdown rate c_0 = 0.0279 per point of scoring level, about 0.6 touchdowns a game shared by both teams.
- K1: σ 13.17. Weights by absolute margin (1 = what a smooth normal would give): 0: 0.17, 1: 0.80, 2: 0.76,
  **3: 2.60**, 4: 0.80, 5: 0.86, 6: 1.28, **7: 1.89**, 8: 0.93, 9: 0.38, **10: 1.11**, 11: 0.62, 12: 0.42, 13: 0.51,
  **14: 1.70**.
- R2: home field 1.5, λ 16, ρ 0.75. **λ 16 is the top of the pre-registered grid**, so stronger shrinkage might have
  done a little better; that can't be tested on these seasons now.

## Descriptive (not tested)
Share of 2022-2025 games by absolute margin:

| Margin | Actual | NB | S1 | K1 |
|---|---|---|---|---|
| 1 | 5.0% | 5.5% | 4.7% | 4.5% |
| 2 | 5.1% | 5.5% | 3.9% | 4.2% |
| 3 | 15.2% | 5.4% | 6.4% | 14.3% |
| 6 | 6.6% | 5.0% | 5.0% | 6.6% |
| 7 | 8.1% | 4.8% | 6.1% | 9.4% |
| 10 | 4.7% | 4.2% | 5.3% | 4.9% |
| 14 | 4.6% | 3.3% | 4.1% | 5.9% |

Cover log loss against the closing spread (994 games without a push): NB 0.7129, S1 0.7117, K1 0.7168, coin 0.6931.
K1's sharper clumps make its cover calls more confident around 3 and 7, and with Elo's mean that costs it here.

Totals (1,023 games): the simulator's total MAE is 10.41 against the closing total's 10.16. It sits 0.4 points below
the line on average and favors unders (about 60% of its bets). Its side by gap: 0.5+ 885 bets, ROI −6.0%; 1+ 733,
−8.8%; 2+ 496, −6.8%; 3+ 297, −3.7%.

Weeks 2-6 MAE, 2005-2015: Elo 10.823, market start 10.791, ridge 10.822. The market start helped in week 3
(10.65 vs 10.85) and the ridge in week 6 (10.38 vs 10.56), and neither held across weeks.

## What this means
The key-number table is real and well measured: it is the shape books price half points and teasers with. It does
not beat the closing line by itself, because the mean comes from Elo. Putting the K1 weights around the market's
own number (to value buying a half point off 3, or pushes in the pool) would be a new hypothesis and needs its own
pre-registration on fresh seasons.

## Disclosures
- 2022-2025 and 2005-2015 have held earlier tests (E1-E7, batches 1, 3 and 4). None of these five models had run on
  them, and the simulator's totals had never been compared with a line.
- K1 is normalized on margins −60 to 60; no test game fell outside that range.
- R2's λ sits at the edge of its grid (above).
- Totals bets use nflverse's closing over/under prices.
