# Batch 6 results: key-number margins around the market line

Pre-registration: docs/batch6_preregistration.md (committed before the weights were fit). Weights fit per era and
frozen in data/backtests/batch6_constants.json before the test ran (docs/batch6_fit.txt). Numbers:
data/backtests/batch6.json. Holm at 0.05 over two tests; week-clustered bootstrap over 171 season-weeks, 2,000 draws.

## Bottom line
**Both pass, by small margins.** With the market's closing number as the center, the key-number weights price a line
away from the market (the opener) and the chance of a push at the market's number better than a smooth curve does.
- Push rate at whole-number closes: actual 4.1%, key-number model 4.0%, smooth curve 3.0%. At a close of 3: actual
  7.1%, key-number 7.2%, smooth 3.0%.
- **Not a fresh confirmation.** NFL_ATS's `keynum` model, a close relative, already ran on 2007-2021 and failed
  against NFL_ATS's own estimator. This is a second look at those seasons against a different baseline (a smooth
  normal with the same center), not an independent test.

| Test | Result (mean log-probability gain per game) | p | Holm level | Verdict |
|---|---|---|---|---|
| P1 opener ≠ close, outcome against the opener (n 2,053) | +0.0069, interval +0.0010 to +0.0133 | 0.009 | 0.025 | **PASS** |
| P2 whole-number close, push or not (n 1,550) | +0.0065, interval +0.0014 to +0.0116 | 0.017 | 0.050 | **PASS** |

## Fitted weights (1 = what the smooth curve gives)
| Era (fit seasons) | σ smooth | σ key-number | 3 | 6 | 7 | 10 | 14 |
|---|---|---|---|---|---|---|---|
| Older (1999-2006), applied to 2007-2014 | 13.19 | 13.96 | 3.07 | 1.02 | 1.97 | 1.47 | 1.34 |
| Newer (2016-2020), applied to 2015, 2021 | 12.80 | 13.43 | 2.61 | 1.28 | 1.89 | 1.11 | 1.69 |

## Descriptive (not tested)
- By era: older P1 +0.0079 (1,622 games), P2 +0.0058 (1,264); newer P1 +0.0034 (431), P2 +0.0096 (286). The newer
  era alone is too small to say anything by itself (the power check expected that).
- **The P1 gain does not come from lines that cross 3 or 7.** On the 182 P1 games whose opener and close sit on
  opposite sides of 3 or 7, the mean gain is −0.0001 (about zero). The gain comes from pricing pushes at whole-number
  openers and from the general shape.
- Half points at the newer era's weights, for a close of exactly 3 or 7 (home favored by that number):

  | Close | Favorite covers | Push | Dog covers | Break-even price to buy the half point, if the key number is at −110 |
  |---|---|---|---|---|
  | 3 | 45.4% | 6.6% | 48.0% | about −125 (either side) |
  | 7 | 43.4% | 4.8% | 51.8% | about −121 (either side) |

  The model is not symmetric at its center (the dog's side gets the bump at −3 and −7 margins), so it leans to the
  dog at a key-number close. That lean was not tested and should not be read as an edge.

## What this means
The weights are real around the market's number too: a push at 3 is more than twice as likely as a smooth curve
says, and the model gets the rate right. The practical uses are pricing a half-point buy (worth up to about −125
off 3 and −121 off 7 when the key number is at −110) and pricing pushes in the pool. It does not say which side
covers: the gain at lines crossing 3 or 7, where a pick would change, is about zero, which fits NFL_ATS's `keynum`
failing on picks.

## Disclosures
- 2007-2021 held NFL_ATS's `keynum` walk-forward test (failed), so this is not fresh evidence; Will chose this sample
  after that was raised. 2007-2015 also held batch 1's tests; 2021 held the ATS rating's exploration.
- SBRO openers come from an unnamed book; 11 newer-era games had none and are left out of P1.
- Weights only at 3, 6, 7, 10 and 14, chosen in advance after a synthetic power check (no real data).
