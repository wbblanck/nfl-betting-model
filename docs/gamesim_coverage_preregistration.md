# Game Simulator Coverage Layer (Man vs Zone): Pre-registration (2026-11-05)

Step 4 of the simulator plan (Claude Doc "ATS game simulator: data map and build plan"). Will asked for it on
2026-11-05 ("Begin"). This file is committed before any coverage label is fetched or read. Nothing in it was chosen
by looking at coverage data.

## Data
nflverse participation (`nflreadpy.load_participation`), with `defense_man_zone_type` (man or zone) per play, filled
from 2022. It is joined to play-by-play on game and play id. Plays with no label, or with a label other than man or
zone, are left out of every rate below (the share left out is reported). Only plays before the game being
simulated are used.

## What changes in the simulator (G3 becomes G4; every G3 constant is frozen)
1. **Defense man rate** m: the defense's share of labeled dropbacks in man coverage. It is recency-weighted with the
   G3 weights (half-life 8 games, an 8-game prior, the season regression 0.7). The prior is the league man rate of
   the earlier labeled seasons; for 2022 it is the 2022 league rate to date, from earlier weeks only.
2. **Offense splits**: for each offense and each coverage (man, zone), the deviation of its completion, interception
   and sack log-odds and its log yards per completion from its own overall rate on the same plays. Each deviation is
   recency-weighted as in 1 and shrunk toward 0 with k_cov pseudo-dropbacks.
3. **In the engine**, each dropback first draws man with probability m. The offense's pass factors (comp, int, sack,
   ypc) then shift by its man or zone deviation. Runs are unchanged.
4. **Receivers** (player engine, docs/gamesim_players_preregistration.md, c = 10): each receiver has a target share
   and yards per catch against man and against zone, from his plays in his previous 16 games (2022 onward). Each is
   shrunk toward his overall value with k_rec pseudo-targets. On a man dropback, receivers are drawn from
   (that run's Dirichlet share) x (man share / overall share), renormalized; zone works the same way. Yards per
   catch scales the same way.
5. Pressure (`was_pressure`) is not part of this step.

## Seasons
- **Explore 2022-2023:** choose k_cov from {100, 200, 400, 800} by log loss of completion on labeled 2022-2023 pass
  attempts. The prediction for each attempt is the offense's pre-game overall completion log-odds plus its split for
  that play's coverage. Choose k_rec from {10, 20, 40} by multinomial log loss of which roster receiver was targeted on
  labeled 2022-2023 targets. Also report G4 vs G3 margin MAE on 2022-2023 (descriptive).
- **Confirm 2024-2025**, with both k frozen. Two tests, Bonferroni 0.05/2, each a week-clustered bootstrap with a
  two-sided interval at 0.025:
  - **C1, spreads:** the paired difference |G4 margin error| − |G3 margin error| per game, at 1,000 runs per game and
    the same seed. Better if the interval is entirely below 0.
  - **C2, props:** the paired log-loss difference on 2024 and 2025 DraftKings props (the screen and markets of
    docs/gamesim_players.md), comparing the player engine with coverage against the player engine without it, at
    2,000 runs per game each and the same seed. Better if the interval is entirely below 0.
  - Descriptive only: T1-T3 of docs/gamesim_preregistration.md for G4, and calibration bands for C2.

## Known answers first
- On synthetic plays, an offense planted to complete every pass against man and none against zone gets a large
  positive man split and a negative zone split. With labels shuffled, splits shrink toward 0.
- A defense planted at 80% man has m near 0.8 after enough games.
- In the engine, m = 1 with a positive man completion split raises team completion rate, and all-zero splits leave
  team completion rate unchanged within noise.
- Receiver draw: a receiver planted with double share against man gets about double the man targets.

## Live 2026 (only if C1 or C2 passes; disclosed now)
There are no free 2026 play labels. A live version would take each defense's man rate from the weekly Sharp Football
snapshot (PR #9) and freeze offense and receiver splits at the end of 2025. That is weaker than the version tested
here, and it would need its own check before use.
