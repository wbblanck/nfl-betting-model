# Game simulator with players on every play

Pre-registration: docs/gamesim_players_preregistration.md. Every throw goes to a receiver and every designed run to a rusher inside the game engine, so a simulated QB's line is the sum of his receivers' lines.

## Known-answer checks (2024 week 5)

Scramble share of rush attempts, 2016-2020: 0.0565
Checks on 2024 week 5: 14 games x 2000 runs
K1 box scores add up (QB yards = receivers' yards, completions = catches): mismatches 0 -> PASS
K2 team totals per team-game, with players vs without: pass attempts 33.80 vs 33.67; carries incl. kneels 27.25 vs 26.38 (without kneels); points 21.67 vs 21.77
K3 planted shares 0.2 vs 0.1 (c=inf): mean targets 6.36 vs 3.27, ratio 1.94 -> PASS
K3 planted shares 0.2 vs 0.1 (c=20.0): mean targets 6.51 vs 3.21, ratio 2.03 -> PASS
K4 same seed reproduces: PASS
Roster share sums before normalizing (2024): targets median 0.929 (min 0.305, max 1.300); carries median 0.998

c=5: simulated 254 games
c=10: simulated 254 games
c=20: simulated 254 games
c=40: simulated 254 games
c=80: simulated 254 games
## Concentration c chosen on 2024 (2,000 runs per game), log loss on 8821 DraftKings props
c=5: 0.7333, c=10: 0.7314, c=20: 0.7358, c=40: 0.7408, c=80: 0.7453 -> **c = 10**


## 2025 test: 8474 DraftKings props (738 dropped: player not on a simulated roster or no line for him in one version), c = 10, 10,000 runs per game
Log loss: players-on-every-play 0.7389 | negative binomial 0.7266 | DK de-vigged 0.6898 | coin 0.6931
- **Players minus negative binomial:** +0.0123, interval +0.0025 to +0.0210: **NOT BETTER**

By market (log loss) | n | players | neg. binomial | DK
rec | 2433 | 0.7126 | 0.7088 | 0.6825
rec_yds | 2553 | 0.7186 | 0.7205 | 0.6933
rush_att | 780 | 0.7856 | 0.7271 | 0.6892
rush_yds | 1289 | 0.7649 | 0.7428 | 0.6927
pass_att | 470 | 0.7880 | 0.7389 | 0.6952
pass_cmp | 472 | 0.7696 | 0.7573 | 0.6926
pass_yds | 477 | 0.7564 | 0.7626 | 0.6931

Calibration: favored side's probability band | version | n | said | hit
50%-60% | players | 4243 | 54.8% | 50.6%
60%-70% | players | 2756 | 64.5% | 51.3%
70%-80% | players | 1086 | 74.3% | 50.3%
80%-90% | players | 326 | 84.1% | 52.1%
90%-100% | players | 63 | 92.5% | 57.1%
75%+ | players | 824 | hit 51.6% | ROI -4.3%
50%-60% | NB | 4504 | 55.1% | 51.9%
60%-70% | NB | 2798 | 64.0% | 53.9%
70%-80% | NB | 800 | 74.0% | 53.2%
80%-90% | NB | 279 | 84.3% | 54.5%
90%-100% | NB | 93 | 93.9% | 53.8%
75%+ | NB | 660 | hit 52.6% | ROI -3.2%

## Reading
- Pre-registered verdict: **NOT BETTER**. Putting players on every play made props worse than the negative binomial
  version overall (log loss +0.0123, interval +0.0025 to +0.0210), and both stay worse than a coin flip and DraftKings.
- Descriptive only (not tested): yardage markets were about even or slightly better (rec_yds 0.7186 vs 0.7205,
  pass_yds 0.7564 vs 0.7626); count markets were clearly worse (rush_att 0.7856 vs 0.7271, pass_att 0.7880 vs 0.7389).
  The negative binomial version's very wide counts (size 2) fit those markets better than the engine's own volume.
  Any follow-up is a new hypothesis that needs its own pre-registration.
- Known limits: shares from players who left or are injured are renormalized onto the listed players (2024 target
  share sums before normalizing: median 0.929, min 0.305, max 1.300); injured players are not removed; 18 of 272
  2024 games had no roster for one team (no QB with 3+ earlier games) and were skipped.
- Box score: docs/gamesim_players_boxscore_2025_wk17_CHI_at_SF.md (QB lines now equal the sum of the receivers' lines).
