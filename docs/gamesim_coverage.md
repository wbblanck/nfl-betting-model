# Game simulator coverage layer (man vs zone)

Pre-registration: docs/gamesim_coverage_preregistration.md. Two tests at 0.05 / 2.

## Known-answer checks

2022: labeled dropbacks 17979 of 20298 dropback rows in play-by-play
2023: labeled dropbacks 20610 of 20770 dropback rows in play-by-play
2024: labeled dropbacks 20070 of 20215 dropback rows in play-by-play
2025: labeled dropbacks 19717 of 19830 dropback rows in play-by-play
K1 planted offense (100% vs man, 0% vs zone): comp split man +1.17, zone -1.17 -> PASS
K1b same with labels shuffled: man +0.01, zone -0.02 -> PASS
K2 planted 80% man defense after 29 games: m 0.694, by hand 0.694, raw weighted rate 0.792 -> PASS
K3 engine completion rate: no coverage 0.6526; all-zero splits 0.6522; m = 1 with +1.0 man split 0.8212 -> PASS
K4 receiver planted at double share against man: targets man-only / zone-only 1.68, expected about 1.73 (= 2 / (1 + share)) -> PASS

## Explore 2022-2023: completion on 35332 labeled attempts
No split (overall pre-game rate): log loss 0.63978
k_cov 100: 0.63483
k_cov 200: 0.63586
k_cov 400: 0.63705
k_cov 800: 0.63810
-> **k_cov = 100**
k_rec 10: target log loss 2.38540 on 32535 targets
k_rec 20: target log loss 2.38127 on 32535 targets
k_rec 40: target log loss 2.37850 on 32535 targets
k_rec none (overall share): target log loss 2.38045 on 32535 targets
-> **k_rec = 40**

Descriptive 2022-2023 (511 games, weeks 2-18, 1,000 runs): margin MAE G3 9.694, G4 9.726, close 9.269


## Confirm 2024-2025, k_cov 100, k_rec 40
- **C1 spreads** (512 games, weeks 2-18, 1,000 runs): margin MAE G4 10.291 vs G3 10.253 (close 9.804); difference +0.0376, interval -0.0226 to +0.0972: **NOT BETTER**
- Descriptive G4: T1 coefficient +0.038; T3 bets 354, covers 50.7%, ROI -2.9%; T2 coefficient +0.210 (2024 bet365, n 256)
- **C2 props** (17295 DraftKings props, 2024-2025, 2,000 runs): log loss with coverage 0.7350 vs without 0.7351; difference -0.0001, interval -0.0009 to +0.0007: **NOT BETTER**

By market | n | with coverage | without
rec | 4899 | 0.7144 | 0.7151
rec_yds | 5246 | 0.7235 | 0.7230
rush_att | 1797 | 0.7611 | 0.7616
rush_yds | 2550 | 0.7580 | 0.7579
pass_att | 929 | 0.7621 | 0.7652
pass_cmp | 927 | 0.7623 | 0.7615
pass_yds | 947 | 0.7398 | 0.7382

Calibration with coverage: band | n | said | hit
50%-60% | 8824 | 54.9% | 50.9%
60%-70% | 5466 | 64.4% | 52.1%
70%-80% | 2214 | 74.1% | 50.7%
80%-90% | 656 | 83.9% | 54.1%
90%-100% | 135 | 93.3% | 58.5%

## Reading
- **Both pre-registered tests: NOT BETTER.** Man/zone matchups did not make the simulator's spreads (C1) or props (C2)
  more accurate on 2024-2025. "Nothing survives" for this layer.
- Exploration showed team splits predict single-play completion a little better when the play's real coverage is
  known (log loss 0.63978 to 0.63483, k_cov 100 at the edge of its grid). In the simulator the coverage has to be
  drawn from the defense's man rate, and that predictive edge did not carry through to game margins or player lines.
- Receiver man/zone splits barely beat overall shares even in exploration (k_rec 40 at the grid edge: 2.37850 vs 2.38045).
- The live 2026 version (Sharp man rates plus frozen 2025 splits) is not built, because neither test passed.
