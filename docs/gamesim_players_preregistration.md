# Game Simulator with Players on Every Play: Pre-registration (2026-11-05)

Requested by Will (2026-11-05): "The simulation should be like a game of Madden, right? Realistic." Follow-up to the
box score (QB and receiver lines did not add up) and docs/gamesim_props_dist.md (wider counts helped but every
version stayed worse than a coin flip and DraftKings). Committed before the player engine is built or run.

## Change
Inside the game engine (G3 simulator, frozen constants), every play is credited to a player:
- **Roster per team-game:** the players in `nflbet.props.sim` inputs for that team and week (3+ earlier games), with
  their target share, carry share, catch rate, yards per catch and yards per carry from earlier games only (constants
  unchanged). Shares are normalized to sum to 1 within the team. The QB with the largest attempt share is the passer.
- **Role uncertainty:** at the start of each run, the team's target shares and carry shares are drawn from a Dirichlet
  with mean = the shares and concentration c, so a player's role varies from run to run as it does week to week.
- **Each throw** (completion, incompletion or interception) goes to one receiver drawn from that run's shares. The
  completion chance is the play's team-level chance shifted by the receiver's catch rate relative to the team's
  share-weighted average (log-odds). Completion yards are the play's draw times his yards per catch over the team's
  share-weighted average. Each designed run goes to one rusher the same way; scrambles go to the QB.
- The QB's attempts, completions and passing yards are the sum of the same plays, so box scores add up.
- Team totals are unchanged in expectation (shifts are relative to the team average).

## Seasons
- **2024 (fit):** choose c from {5, 10, 20, 40, 80} by log loss on the 2024 DraftKings props (markets rec, rec_yds,
  rush_att, rush_yds, pass_att, pass_cmp, pass_yds), at 2,000 runs per game.
- **2025 (test):** 10,000 runs per game with the chosen c.

## Test on 2025 (one comparison)
Paired difference in log loss per prop vs the negative binomial version of docs/gamesim_props_dist.md (the best so
far, recomputed on the same props), week-clustered bootstrap interval two-sided 0.05: **better** if entirely below 0.
Reported alongside: log loss vs DraftKings' de-vigged price and a coin flip, calibration bands, the 75%+ bucket's hit
rate and ROI (descriptive). Better than the previous version is not "usable": that still needs a pre-registered test
against DraftKings' price.

## Known answers first
Box scores add up (QB yards = receivers' yards; completions = catches); team attempts and carries match the engine
without players; a planted receiver with double the target share gets about double the targets; same seed reproduces.
