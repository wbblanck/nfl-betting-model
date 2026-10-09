# ATS rating vs bettable opening lines

Pre-registration: docs/ats_clv2_preregistration.md. Lines: data/odds/asb (personal use only).

## test_bet365_2022_2024

- **C1** (close − open) on (fair − open): coefficient +0.235, interval +0.151 to +0.334, n 767: **PASS**
- **C2** CLV, |fair − open| ≥ 1.5: n 446 in 51 weeks, mean +0.738 pts (toward the bet 53%), interval +0.490 to +0.992: **PASS**
- **C3** at the actual opening price: covers 53.6%, ROI +2.0%, interval -7.2% to +11.0%: **FAIL**

| |fair − open| ≥ | Bets | Mean CLV (pts) | CLV > 0 | Cover at open | ROI at open price | Cover at close |
|---|---|---|---|---|---|---|
| 0.5 | 654 | +0.525 | 49% | 51.6% | -1.6% | 48.7% |
| 1.0 | 542 | +0.636 | 51% | 51.7% | -1.4% | 48.6% |
| 1.5 | 446 | +0.738 | 53% | 53.6% | +2.0% | 50.7% |
| 2.0 | 359 | +0.855 | 56% | 51.0% | -2.8% | 47.7% |
| 3.0 | 218 | +1.365 | 63% | 49.8% | -5.0% | 45.6% |

## descriptive_pinnacle_2014_2017

- **C1** (close − open) on (fair − open): coefficient +0.106, interval +0.058 to +0.151, n 834: **PASS**
- **C2** CLV, |fair − open| ≥ 1.5: n 539 in 64 weeks, mean +0.377 pts (toward the bet 51%), interval +0.219 to +0.530: **PASS**
- **C3** at the actual opening price: covers 48.6%, ROI -5.5%, interval -14.6% to +3.0%: **FAIL**

| |fair − open| ≥ | Bets | Mean CLV (pts) | CLV > 0 | Cover at open | ROI at open price | Cover at close |
|---|---|---|---|---|---|---|
| 0.5 | 728 | +0.369 | 50% | 47.7% | -7.2% | 45.4% |
| 1.0 | 637 | +0.392 | 51% | 47.4% | -7.7% | 45.0% |
| 1.5 | 539 | +0.377 | 51% | 48.6% | -5.5% | 46.6% |
| 2.0 | 456 | +0.376 | 51% | 48.5% | -5.7% | 46.5% |
| 3.0 | 297 | +0.535 | 54% | 46.4% | -9.8% | 44.1% |

## Reading
- The CLV finding replicates on **named, bettable openers**. bet365 2022-2024 (held out): lines moved toward the
  rating by 24% of the gap (C1), and its side gained +0.74 points of CLV (C2). Pinnacle 2014-2017 (the sharpest
  openers): smaller but still clear, +0.38 points.
- It still does not make money at the opening price (C3): 53.6% covered at bet365's opening prices (ROI +2.0%,
  interval −7.2% to +11.0%); 48.6% at Pinnacle's (−5.5%). The CLV shows up in the line, but not reliably in covers.
- The size of the CLV falls as the opener gets sharper (bet365 +0.74 > unnamed SBRO +0.51 > Pinnacle +0.38): the
  rating finds soft opening numbers, and the softest books move the most toward it.
- For the ATS angle: "positive expected CLV" is real and measurable on history; a profitable rule still needs a
  pre-registered test of something more (e.g. only soft books, only crossings of 3 / 7, best number across books).
