# ATS rating vs opening lines

Pre-registration: docs/ats_clv_preregistration.md. Opening/closing spreads: SBRO (data/odds/README.md).

## test_2008_2015

- **C1** (close − open) on (fair − open): coefficient +0.154, interval +0.096 to +0.230, n 1578: **PASS**
- **C2** CLV of the model's side, |fair − open| ≥ 1.5: n 992 in 128 weeks, mean +0.506 pts (moved toward the bet 52%), interval +0.397 to +0.612: **PASS**
- **C3** ATS at the opening number, −110: covers 53.4%, ROI +1.8%, interval -4.7% to +7.9%: **FAIL**

| |fair − open| ≥ | Bets | Mean CLV (pts) | CLV > 0 | Cover at open | ROI at open (−110) | Cover at close |
|---|---|---|---|---|---|---|
| 0.5 | 1354 | +0.421 | 50% | 52.2% | -0.4% | 51.7% |
| 1.0 | 1165 | +0.443 | 50% | 53.2% | +1.5% | 52.5% |
| 1.5 | 992 | +0.506 | 52% | 53.4% | +1.8% | 52.6% |
| 2.0 | 808 | +0.544 | 53% | 51.7% | -1.2% | 51.0% |
| 3.0 | 510 | +0.670 | 55% | 50.0% | -4.4% | 48.5% |

## descriptive_2016_2021

- **C1** (close − open) on (fair − open): coefficient +0.136, interval +0.074 to +0.196, n 1384: **PASS**
- **C2** CLV of the model's side, |fair − open| ≥ 1.5: n 881 in 97 weeks, mean +0.533 pts (moved toward the bet 52%), interval +0.372 to +0.692: **PASS**
- **C3** ATS at the opening number, −110: covers 50.4%, ROI -3.6%, interval -10.6% to +3.4%: **FAIL**

| |fair − open| ≥ | Bets | Mean CLV (pts) | CLV > 0 | Cover at open | ROI at open (−110) | Cover at close |
|---|---|---|---|---|---|---|
| 0.5 | 1216 | +0.437 | 50% | 50.0% | -4.4% | 48.3% |
| 1.0 | 1065 | +0.473 | 51% | 50.0% | -4.5% | 48.2% |
| 1.5 | 881 | +0.533 | 52% | 50.4% | -3.6% | 47.9% |
| 2.0 | 722 | +0.554 | 53% | 50.7% | -3.1% | 48.7% |
| 3.0 | 455 | +0.641 | 53% | 51.5% | -1.7% | 49.8% |

## Reading
- Known-answer check first: a "model" equal to the closing line gives C1 coefficient 1.000 and positive CLV on every
  bet (mean +2.31 points), so the scoring is right.
- **C1 and C2 pass** in the test seasons and hold in 2016-2021: when the rating disagrees with the opening number, the
  line moves about 15% of the way toward the rating by kickoff, and the rating's side gains about half a point of
  closing-line value on average (2008-2015: +0.51 points on 992 games; 2016-2021: +0.53 on 881).
- **C3 fails:** half a point of CLV is not enough to cover −110 juice. At the opening number the rating's side
  covered 53.4% (2008-2015) and 50.4% (2016-2021); break-even is 52.4%.
- So the rating carries information the opening line lacks, and the market absorbs it by the close. That is what
  "positive expected CLV" means in the angle's FIRE rule, measured on history. Turning it into profit needs better
  than −110 at the open (reduced juice, or the best number across books), which these data cannot show.
- Caveat: the archive does not name the opener's book, so these openers may not have been bettable.
