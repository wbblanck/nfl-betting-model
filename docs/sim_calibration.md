# Simulator calibration: result

Pre-registration: docs/sim_calibration_preregistration.md.

**Primary (2024-2025 DraftKings lines, 21519 props):** log loss raw 0.7525, corrected 0.7153 (DraftKings de-vigged 0.6901, coin 0.6931). Difference -0.0371, 95% interval -0.0448 to -0.0302; 2025 alone -0.0376. **PASS**.

| Season | n | Raw | Corrected | DraftKings |
|---|---|---|---|---|
| 2024 | 11492 | 0.7546 | 0.7179 | 0.6900 |
| 2025 | 10027 | 0.7500 | 0.7124 | 0.6902 |

| Market | a | b (slope) | n | Raw | Corrected | DraftKings |
|---|---|---|---|---|---|---|
| rec | -0.13 | 0.66 | 5211 | 0.7201 | 0.7041 | 0.6829 |
| rec_yds | -0.07 | 0.79 | 5567 | 0.7313 | 0.7203 | 0.6931 |
| rush_att | -0.19 | 0.38 | 1897 | 0.7714 | 0.7006 | 0.6890 |
| rush_yds | -0.22 | 0.50 | 2684 | 0.7445 | 0.7080 | 0.6923 |
| rush_rec_yds | -0.10 | 0.70 | 2319 | 0.7439 | 0.7208 | 0.6929 |
| pass_att | +0.06 | 0.38 | 978 | 0.8388 | 0.7214 | 0.6950 |
| pass_cmp | +0.06 | 0.37 | 976 | 0.8388 | 0.7230 | 0.6905 |
| pass_yds | +0.10 | 0.57 | 996 | 0.8090 | 0.7378 | 0.6929 |
| pass_rush_yds | +0.12 | 0.59 | 891 | 0.8270 | 0.7490 | 0.6931 |

Corrected calibration (decile: n, mean P, over rate):

- [0.02, 0.32] n 2152: P 0.249, over 0.474
- [0.32, 0.37] n 2150: P 0.351, over 0.449
- [0.37, 0.40] n 2154: P 0.388, over 0.487
- [0.40, 0.42] n 2148: P 0.413, over 0.468
- [0.42, 0.45] n 2153: P 0.435, over 0.485
- [0.45, 0.47] n 2152: P 0.457, over 0.480
- [0.47, 0.49] n 2153: P 0.479, over 0.499
- [0.49, 0.52] n 2153: P 0.503, over 0.472
- [0.52, 0.56] n 2151: P 0.534, over 0.482
- [0.56, 0.89] n 2153: P 0.602, over 0.491

Descriptive only (seasons S1 was built on): S1 with the corrected simulator in its simulator vote:

- 2024: 0 bets
- 2025: n 41, weeks 13, win 63.4%, ROI +6.9%

## Reading
- The correction passes the pre-registered test: it lowers the simulator's log loss at DraftKings' lines in both
  held-out seasons (−0.0371, interval −0.0448 to −0.0302), most in rush attempts and the passing markets, where it
  pulls the simulator's probabilities about 60% of the way toward 50%.
- It does not make the simulator informative at the books' lines. Corrected log loss (0.7153) is still worse than a
  coin flip (0.6931) and than DraftKings' own price (0.6901), and the corrected deciles are flat: whether the
  corrected simulator says 25% or 60%, the over hit 45-50% of the time. At a book's line the simulator knows less
  than the line does; the pass means "less wrong", not "an edge".
- S1 is locked for 2026 and is not changed. With the corrected simulator S1 would have had 41 bets in 2025 (63.4%,
  +6.9%) and 0 in 2024 instead of 61 and 2: exploration on seasons S1 was built on, deciding nothing.
