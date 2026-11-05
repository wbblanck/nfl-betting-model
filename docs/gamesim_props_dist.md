# Game simulator props: Poisson and negative binomial vs binomial

Pre-registration: docs/gamesim_props_dist_preregistration.md. Same 10,000 game runs per game for every version; only the count distribution for targets, carries and QB attempts changes.

## Negative binomial size chosen on 2024 (log loss on that count's markets)
- targets: r=2: 0.7316, r=4: 0.7271, r=8: 0.7262, r=16: 0.7268, r=32: 0.7271 -> **8**
- carries: r=2: 0.7307, r=4: 0.7321, r=8: 0.7362, r=16: 0.7412, r=32: 0.7440 -> **2**
- qb_att: r=2: 0.7646, r=4: 0.7716, r=8: 0.7811, r=16: 0.7907, r=32: 0.7980 -> **2**

## 2024 (NB size chosen here; descriptive): 9349 DraftKings props
Log loss: binomial 0.7516 | Poisson 0.7457 | negative binomial 0.7335 | DK de-vigged 0.6893 | coin 0.6931

By market (log loss) | n | binomial | Poisson | neg. binomial | DK
rec | 2626 | 0.7208 | 0.7198 | 0.7185 | 0.6828
rec_yds | 2860 | 0.7349 | 0.7342 | 0.7332 | 0.6928
rush_att | 1074 | 0.7711 | 0.7585 | 0.7344 | 0.6889
rush_yds | 1330 | 0.7444 | 0.7396 | 0.7278 | 0.6921
pass_att | 484 | 0.8634 | 0.8321 | 0.7726 | 0.6947
pass_cmp | 480 | 0.8361 | 0.8161 | 0.7678 | 0.6887
pass_yds | 495 | 0.7975 | 0.7852 | 0.7568 | 0.6928

Calibration: favored side's probability band | version | n | said | hit
60%-70% | B | 2694 | 64.3% | 51.2%
70%-80% | B | 1001 | 74.1% | 50.6%
80%-90% | B | 356 | 84.4% | 56.7%
90%-100% | B | 253 | 96.1% | 54.2%
75%+ | B | 974 | hit 54.9% | ROI +0.9%
60%-70% | P | 2684 | 64.2% | 51.2%
70%-80% | P | 901 | 73.9% | 51.5%
80%-90% | P | 339 | 84.2% | 57.5%
90%-100% | P | 222 | 96.0% | 52.7%
75%+ | P | 866 | hit 55.1% | ROI +1.3%
60%-70% | NB | 3214 | 64.1% | 51.6%
70%-80% | NB | 897 | 73.9% | 54.2%
80%-90% | NB | 274 | 84.2% | 53.6%
90%-100% | NB | 129 | 94.8% | 54.3%
75%+ | NB | 701 | hit 54.2% | ROI -1.0%

## 2025 (test): 8960 DraftKings props
Log loss: binomial 0.7498 | Poisson 0.7428 | negative binomial 0.7266 | DK de-vigged 0.6899 | coin 0.6931
- **P minus binomial:** -0.0069, interval -0.0084 to -0.0054: **BETTER**
- **NB minus binomial:** -0.0232, interval -0.0300 to -0.0157: **BETTER**

By market (log loss) | n | binomial | Poisson | neg. binomial | DK
rec | 2585 | 0.7180 | 0.7161 | 0.7110 | 0.6830
rec_yds | 2707 | 0.7263 | 0.7249 | 0.7211 | 0.6934
rush_att | 823 | 0.7637 | 0.7539 | 0.7256 | 0.6892
rush_yds | 1354 | 0.7512 | 0.7476 | 0.7379 | 0.6924
pass_att | 494 | 0.8416 | 0.8031 | 0.7386 | 0.6952
pass_cmp | 496 | 0.8488 | 0.8211 | 0.7573 | 0.6923
pass_yds | 501 | 0.8249 | 0.8094 | 0.7657 | 0.6931

Calibration: favored side's probability band | version | n | said | hit
60%-70% | B | 2588 | 64.3% | 53.0%
70%-80% | B | 948 | 74.2% | 51.9%
80%-90% | B | 357 | 84.2% | 52.9%
90%-100% | B | 244 | 95.6% | 53.3%
75%+ | B | 956 | hit 52.4% | ROI -3.1%
60%-70% | P | 2545 | 64.2% | 52.1%
70%-80% | P | 855 | 74.0% | 52.3%
80%-90% | P | 340 | 84.2% | 53.2%
90%-100% | P | 211 | 95.3% | 54.5%
75%+ | P | 866 | hit 52.8% | ROI -2.4%
60%-70% | NB | 2926 | 64.0% | 53.7%
70%-80% | NB | 857 | 74.0% | 53.7%
80%-90% | NB | 302 | 84.2% | 56.3%
90%-100% | NB | 95 | 93.9% | 49.5%
75%+ | NB | 703 | hit 53.9% | ROI -0.8%

## Reading
- **Both pass the pre-registered test:** on 2025, Poisson counts lower log loss vs binomial by 0.0069 and the
  negative binomial by 0.0232, intervals entirely below 0. Wider count distributions fix part of the overconfidence,
  most in the QB and carry markets (pass_att 0.8416 -> 0.7386).
- **It is still not usable.** The negative binomial version (0.7266) is still worse than a coin flip (0.6931) and
  well behind DraftKings (0.6899). Its 80-90% calls hit 56.3% (302 props), 90%+ calls 49.5% (95). Most of the
  miscalibration remains, likely because the player's share and per-play yards are still treated as known.
- Per the pre-registration, "better than binomial" does not make a version usable; any prop-model use would need
  its own test against DraftKings' price.
