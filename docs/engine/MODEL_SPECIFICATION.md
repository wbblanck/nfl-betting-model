# Model specification

Two engines predict the same thing: for each player in a game, a joint distribution over the statistics in
`config/markets.yaml`, produced before kickoff from data dated before kickoff. They share the warehouse, the
feature store, the registry and the accounting rules. They share no fitted parameter and neither reads the other's
output. Neither reads a price. Seasons: `docs/engine_preregistration.md`.

Notation: team t, game g, player i, simulation run s. "Fit" = 2018-2021, "tune" = 2022-2023.

## 1. Definitions (both engines, and grading)
- **Dropback** = pass attempt + sack + scramble. A sack is not a pass attempt. A scramble is a carry.
- **Carry** = designed run + scramble + kneel. Team carries = sum of player carries.
- **Target** = pass attempt aimed at a player. Team targets <= team pass attempts (throwaways, spikes and batted
  balls have no target).
- **Passing yards** are gross: equal to the sum of receivers' yards on completions. Sack yards are separate.
- **Full game**: overtime counts. Regular season only for fitting and testing.
- **Did not play**: no snaps = void, as books grade; snaps without a stat row = zeros (CLAUDE.md).
- A line L ends in .5; P(over) = P(stat > L). Whole-number lines are not priced until push rules are confirmed.

## 2. Engine A: game-simulation replication
The blueprint describes six layers. Each is fitted on the fit seasons, tuned on the tune seasons, then frozen.

**2.1 Team environment.** For each team-game, a joint draw of plays, dropbacks, designed runs and per-play
efficiency. Means from gradient-boosted regressions on team and opponent rolling features; the joint residual
(plays, pass share, yards per dropback, yards per carry, for both teams) is drawn from the empirical residual
vectors of the fit seasons, so the two teams' volumes and efficiencies stay correlated the way they were.

**2.2 Game script.** No fixed scripts. Each run carries a latent pace and efficiency draw per team; the play-call
model is `P(pass | score difference, time left, down, distance, field position, team tendency)`, a logistic
regression fitted on play-by-play, so volume responds to the simulated score.

**2.3 Personnel.** Two separate draws per player per run:
- active: Bernoulli(p_active), p_active from a logistic model on the injury report status and practice
  participation known at the prediction time (1 when no report lists the player);
- role given active: snap share, route share and carry share from a hierarchical model on the player's recent role,
  depth-chart slot and which teammates are active in that run. A backup's role when the starter is out is learned
  from historical starter absences at that position, not copied from the starter.

**2.4 Opportunity allocation.** For each team and run, with team pass attempts A and designed carries C fixed by 2.1-2.2:
- targets: `pi ~ Dirichlet(kappa_t * mu)`, `(targets_1..n, untargeted) ~ Multinomial(A, pi)`, where mu is the
  expected target share of each active player plus an "untargeted" bucket, and kappa (concentration) is a fitted
  function of role stability: games in the current role, variance of recent share, whether personnel changed.
- carries: the same with designed carries; scrambles go to the quarterback and are drawn from dropbacks.
This is the layer the existing simulator lacks (it treats shares as known), and the Dirichlet variance is what
widens its over-confident player distributions.

**2.5 Efficiency.** Per player, partially pooled toward position: catch rate `~ Beta` with a position prior
(receptions | targets is then beta-binomial, so receptions <= targets by construction); yards per reception and per
carry drawn from position-and-depth empirical yardage pools scaled by a shrunk player factor
`theta_i ~ N(mu_pos, tau^2)`, posterior from the player's opportunities to date. Quarterback completions are the sum
of receivers' receptions and passing yards the sum of their yards, so the passing box reconciles exactly.

**2.6 Simulation.** 25,000 runs per game, vectorized over runs. The run count rises to 50,000 or 100,000 only where
`pricing.mc_se` says the sampling error matters for the probability being reported. `accounting.violations` runs on
every team-game and any violation fails the run.

## 3. Engine B: challenger
Different statistical route: direct conditional distributions per player-market, then a dependence layer.

**3.1 Counts** (pass_att, rush_att, targets): negative binomial regression with log link; mean from player, team
and opponent features; dispersion modelled separately (by position and role stability); player and team random
effects. Hurdle variant where the zero mass is under-fitted on the tune seasons. Bounded counts (rec | targets,
pass_cmp | pass_att): beta-binomial on the simulated parent count.

**3.2 Yardage** (pass_yds, rush_yds, rec_yds): gradient-boosted quantile regression at 0.05, 0.10, 0.25, 0.50,
0.75, 0.90, 0.95, conditional on the same features plus the count model's mean. Crossing is removed by sorting
(rearrangement); the distribution between quantiles is piecewise linear, with tails fitted on tune-season exceedances.
P(over L) is read from that distribution, so any line can be priced.

**3.3 Rare events** (shadow): hierarchical Poisson for touchdown counts with exposure = red-zone and goal-line
opportunities, not a share of team touchdowns; hierarchical logistic for interceptions per attempt.

**3.4 Dependence.** Marginals from 3.1-3.3 are joined by a Gaussian copula per team-game whose correlation matrix is
estimated from fit-season residual ranks (quarterback with receivers, receivers with each other, backs with game
margin). After sampling, the passing box is reconciled: receivers' receptions and yards are rescaled to the
quarterback's completions and yards by multinomial and proportional allocation, so the same accounting rules pass.

**3.5 Selection.** Model family per market is chosen on the tune seasons against the baselines. If no candidate
beats the baseline there, the baseline is Engine B for that market and that is reported.

## 4. Combined and derived markets
Sums (pass_rush_yds, rush_rec_yds, tds, fantasy points under a stated scoring rule) are computed per run from the
simulated box, never from marginals. Longest play and first touchdown need play-level events and are produced by
Engine A only until Engine B has an event layer.

## 5. Outputs (one record per player-market per engine per prediction time)
Mean, median, quantiles 0.05-0.95, P(stat = 0), P(over) at any requested line, the engine version, the feature
snapshot hash and the seed. Written through `engine/ledger.py`; probabilities as fixed 4-decimal strings.

## 6. Baselines (must be beaten on the tune seasons to be used at all)
B1 previous-season per-game distribution; B2 current-season games to date; B3 trailing 8 games across seasons;
B4 opportunity-only (trailing share x team trailing volume x position-average efficiency); B5 position-and-role
average. Each as an empirical or negative binomial distribution, with its own fallback order when history is short.

## 7. Agreement tiers (diagnostic only)
A: same side, both pass Test S on that market, no data flag. B: same side, one materially wider. C: opposite sides
or P(over) apart by more than a tune-season-chosen gap. D: data flag, short history or uncertain availability.
A tier is a label on a record; it grants nothing.

## 8. Open points (not invented here)
- No published Projexions methodology was found; section 2 follows the blueprint's description only.
- Novig's overtime and FMV void rules for player props (NOVIG_INTEGRATION.md).
- Timestamped historical injury reports: nflverse gives the final weekly report, not when each line was posted
  (DATA_DICTIONARY.md). Historical availability inputs are therefore weaker than live ones.
