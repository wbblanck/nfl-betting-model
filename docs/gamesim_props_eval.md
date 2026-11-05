# Game simulator player props: 2024-2025 vs DraftKings

Pre-registration: docs/gamesim_props_preregistration.md. 10,000 game runs per game (G3 simulator); player layer from nflbet.props.sim, constants unchanged. Research only: no pick list.

Game simulator: 544 games x 10000 runs; mean team pass attempts 33.78, carries 26.49

## 2024 (player-layer fit season, descriptive): 9349 of 9585 screened DK props
Log loss: game-sim props 0.7517 | old prop simulator 0.7532 | DK de-vigged 0.6893 | coin 0.6931

By market | n | game-sim | old sim | DK
rec | 2626 | 0.7206 | 0.7226 | 0.6828
rec_yds | 2860 | 0.7352 | 0.7364 | 0.6928
rush_att | 1074 | 0.7713 | 0.7760 | 0.6889
rush_yds | 1330 | 0.7444 | 0.7441 | 0.6921
pass_att | 484 | 0.8635 | 0.8576 | 0.6947
pass_cmp | 480 | 0.8379 | 0.8389 | 0.6887
pass_yds | 495 | 0.7964 | 0.8018 | 0.6928

Calibration: the side the game sim favors, by its probability | n | said | hit
50%-60% | 5053 | 54.7% | 50.5%
60%-70% | 2692 | 64.3% | 50.9%
70%-80% | 992 | 74.1% | 50.7%
80%-90% | 355 | 84.4% | 56.3%
90%-100% | 257 | 96.0% | 54.5%

Game sim at 75%+ on one side: 969 props (10.4% of all), hit 54.7%, ROI at DK's price +0.6% (descriptive)

## 2025 (evaluation): 8960 of 9212 screened DK props
Log loss: game-sim props 0.7496 | old prop simulator 0.7462 | DK de-vigged 0.6899 | coin 0.6931

By market | n | game-sim | old sim | DK
rec | 2585 | 0.7180 | 0.7172 | 0.6830
rec_yds | 2707 | 0.7264 | 0.7250 | 0.6934
rush_att | 823 | 0.7637 | 0.7649 | 0.6892
rush_yds | 1354 | 0.7509 | 0.7454 | 0.6924
pass_att | 494 | 0.8416 | 0.8208 | 0.6952
pass_cmp | 496 | 0.8476 | 0.8381 | 0.6923
pass_yds | 501 | 0.8238 | 0.8167 | 0.6931

Calibration: the side the game sim favors, by its probability | n | said | hit
50%-60% | 4796 | 54.7% | 50.7%
60%-70% | 2624 | 64.3% | 53.0%
70%-80% | 931 | 74.2% | 51.3%
80%-90% | 366 | 84.2% | 51.9%
90%-100% | 243 | 95.6% | 54.7%

Game sim at 75%+ on one side: 961 props (10.7% of all), hit 52.8%, ROI at DK's price -2.4% (descriptive)

Known answers: same seed reproduces: True; doubled target share raises mean targets: 11.93 vs 5.99; team attempts passed through: mean 33.39 from the game simulator

## Reading
- **The simulator's confidence does not hold up.** In 2025, props where the game-sim prop layer favored a side at
  80-90% hit 51.9% (366 props); at 90-100%, 54.7% (243). Every band from 60% up hit 51-55%, barely above a coin
  flip, in both seasons. "Beats his line 80% of the time" in this simulator means about 52% in practice.
- Log loss is worse than a coin flip (2025: 0.7496 vs 0.6931) and far worse than DraftKings' own price (0.6899).
  Feeding volume from the game simulator instead of the spread/total regression changed almost nothing (old prop
  simulator 0.7462).
- The overconfidence sits in the player layer (shares, catch rates and per-play yards drawn as if known), not in the
  number of runs: 10,000 runs pin down the simulator's own probability precisely, but that probability is wrong.
- Per the pre-registration nothing here becomes a rule. Any use of these probabilities in the prop model would first
  need a recalibration fitted on 2024 and checked on 2025, as its own pre-registered test.
