# Game simulator: confirm 2022-2025

Pre-registration: docs/gamesim_preregistration.md; constants: data/backtests/gamesim_constants.json (frozen before this ran). Regular season weeks 2-18, 1000 simulations per game. Each test at 0.05 / 6.

## G2 (step 2: team factors)

- MAE vs actual margin (1023 games): simulator 10.098, closing spread 9.537.
- **T1** information beyond the close: coefficient on (fair − close) -0.154, interval -0.601 to +0.296: **FAIL**
- **T2** line movement (bet365 2022-2024, n 767): coefficient +0.195, interval +0.109 to +0.288: **PASS**
- **T3** |fair − close| ≥ 1.5 at the closing price: n 710 in 68 weeks, covers 49.2%, ROI -5.4%, interval -12.7% to +1.9%: **FAIL**

| Season | Games | MAE simulator | MAE close |
|---|---|---|---|
| 2022 | 255 | 9.029 | 8.718 |
| 2023 | 256 | 10.432 | 9.818 |
| 2024 | 256 | 10.424 | 9.648 |
| 2025 | 256 | 10.503 | 9.959 |

| |fair − close| ≥ | Bets | Covers | ROI |
|---|---|---|---|
| 0.5 | 922 | 49.2% | -5.4% |
| 1.0 | 812 | 48.9% | -6.0% |
| 2.0 | 599 | 50.2% | -3.6% |
| 3.0 | 413 | 49.4% | -5.1% |

## G3 (step 3: team factors + QB and injuries)

- MAE vs actual margin (1023 games): simulator 9.983, closing spread 9.537.
- **T1** information beyond the close: coefficient on (fair − close) +0.058, interval -0.366 to +0.478: **FAIL**
- **T2** line movement (bet365 2022-2024, n 767): coefficient +0.295, interval +0.215 to +0.390: **PASS**
- **T3** |fair − close| ≥ 1.5 at the closing price: n 680 in 68 weeks, covers 49.6%, ROI -4.7%, interval -12.8% to +3.7%: **FAIL**

| Season | Games | MAE simulator | MAE close |
|---|---|---|---|
| 2022 | 255 | 9.061 | 8.718 |
| 2023 | 256 | 10.316 | 9.818 |
| 2024 | 256 | 10.169 | 9.648 |
| 2025 | 256 | 10.381 | 9.959 |

| |fair − close| ≥ | Bets | Covers | ROI |
|---|---|---|---|
| 0.5 | 898 | 49.3% | -5.2% |
| 1.0 | 800 | 49.7% | -4.5% |
| 2.0 | 565 | 50.8% | -2.6% |
| 3.0 | 379 | 49.6% | -5.0% |

G3 minus G2 MAE: -0.115 (negative = personnel layer closer to the actual margin).

## Reading
- **T2 passes for both versions; T1 and T3 fail for both.** When the simulator disagrees with bet365's opener, the
  line moves toward it by kickoff: 20% of the gap for G2, 30% for G3 (the EPA rating's figure on the same 767 games
  was 24%, docs/ats_clv2.md). But the simulator carries no information about the final margin beyond the closing
  spread (T1), and betting its 1.5+ point disagreements at the closing price lost (G3: 49.6% covers, ROI −4.7%).
- The personnel layer helps: G3 is 0.115 points closer to the actual margin than G2, and both are closer than the
  EPA rating was on these games (10.112, docs/ats_confirm.md). All are further from the result than the close (9.537).
- Per the pre-registration, a pass on T2 keeps step 4 (scheme data) open, but only as a line-movement (CLV) tool.
  Nothing here supports betting the simulator's side at the closing number. A test of betting it at the opener
  would be a new pre-registration.

## Disclosures
- Known-answer check K2 failed on key numbers: equal teams land on a 3-point margin 12.0% of the time vs 14.2%
  actual, and on 7 points 10.6% vs 9.4% (docs/gamesim_explore.txt). End-of-game behaviour (kneels, playing for a
  field goal) is simplified. The tests above use only the mean margin, which this affects little; cover
  probabilities near 3 and 7 from this simulator should not be trusted.
- The first home-field fit used a straight line and failed its check (0.70 vs 1.51 points); it was refit by bisection
  on 2016-2020 before any 2022-2025 output (scripts/gamesim_hfa.py; check 1.55 vs 1.51). The 2021 grid was run with
  the first fit; the grid choice was not rerun.
- Not modeled: individual timeouts (their average effect is in the clock table), accepted penalties on plays that
  were not no-plays, opponent adjustment of team factors, onside kicks. Injury statuses are nflverse's weekly final
  report; starting QBs are the recorded starters (known at inactives).
