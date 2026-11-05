# Game Simulator Player Props: Pre-registration (2026-11-04)

Requested by Will (2026-11-04): the game simulator should run 5,000-10,000 times per game and project player props
("if Luther Burden III beats his receiving line 80% of the time, that is a prop we should consider in the player prop
model"). Committed before the player layer is built and before any of its output exists. Research only: no pick
list (CLAUDE.md); any rule found is a hypothesis until confirmed.

## Method (no new constant is fitted)
- Each game is simulated 10,000 times with the frozen game simulator (G3: team factors + QB and injuries,
  data/backtests/gamesim_constants.json). Each run records both teams' pass attempts (throws, excluding sacks and
  scrambles) and designed carries.
- For every player-game, run i takes its team's attempts and carries from game run i; the player's targets, carries,
  catches, yards (and a QB's attempts, completions, yards) are drawn with the existing prop simulator's player layer
  (`nflbet.props.sim.simulate_row`, constants unchanged; position means from 2024). So game script (blowouts, shootouts)
  now drives volume, replacing the old regression on spread and total.
- P(over) = share of runs above the line; runs landing on the line are pushes and leave the denominator.
- Markets: rec, rec_yds, rush_att, rush_yds, pass_att, pass_cmp, pass_yds. Full-game lines only.

## Seasons and lines
- 2024: fit season of the player layer (position means). Reported descriptively.
- **2025: evaluation season.** DraftKings (book 68) lines in `data/props/an_props_2025.csv`, junk-screened (de-vigged
  P(over) 0.35-0.65, hold < 10%), graded on nflverse stats (played without a stat row = 0, no snaps = void).
- Anything found on 2025 is a hypothesis. A 2026 confirm (DK/FanDuel lines from data/live/parlay) needs its own
  committed rule before those lines are read for this purpose.

## What is reported (2025)
1. Log loss of P(over) vs the de-vigged DraftKings price and vs a coin flip, overall and by market; the old prop
   simulator on the same props for reference.
2. **Calibration:** props grouped by the simulator's P(over) (0-10%, ..., 90-100%) and by P(under) the same way:
   how often the over (or under) actually hit in each band. The question Will asked: when it says 80%, does it hit
   about 80%?
3. Share of 10,000-run probabilities at 75%+ for either side, and their hit rate and ROI at DraftKings' price
   (descriptive only).
4. Known answers first: identical seeds reproduce; a player with doubled target share gets more simulated targets;
   simulated team attempts and carries match the game simulator's own totals; no game's own stats enter its inputs.
