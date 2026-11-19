# Vacated-role study: what happens to the engine when a lead player sits

Pre-registered 2026-11-18, before any 2022-2023 outcome below was read for this question. Asked by Will in the
"Compare engine box scores to a real game" thread.

## Why
In 2026 week 10 (KC at ATL, outside Test M) Kenneth Walker III was listed Out and correctly removed from KC's list,
but Engine A-1.0 gave Emmett Johnson about 7.5 carries; he had 22. Engine A splits a team's carries and targets by
each active player's own recent share, rescaled to sum to one (`replication/opportunity.py`), so a backup with a
small share stays small when the lead player sits. Engine B-1.1 rescales the same way (`challenger/design.py`,
`active_share`) and skips players below its eligibility rule. Will's hypothesis: each team's offensive style decides
where the vacated share goes (a one-back team hands the job to the next back; a committee team spreads it).

This is a measurement on the engine's tune seasons. It changes no frozen engine, no Test M rule and no paper-fill
rule. Any rule built from it would be a new engine version with its own Test S on 2024-2025.

## Sample
Regular-season games of 2022 and 2023 (the engines' tune seasons). Engine A-1.0 with its frozen saved parameters
(`data/backtests/engine_A-1.0_params.pkl.gz`, hash-checked), 2,000 runs per game, on the engine's feature table
(`player_game.parquet`, rebuilt by `scripts/engine_feature_check.py`). No price and no 2024-2026 outcome is read.

## Definitions (from earlier games only)
- **Prior share**: a player's share of his team's RB carries (or of the team's targets) in the team's previous
  3 games of the same season. At least 2 previous team games are required.
- **RB event**: a team-game where the RB with the highest prior carry share has share >= 0.50, played in the
  team's previous game, and is not active in this game (no row marked played in the feature table).
- **Target event**: the same with the player with the highest prior target share, share >= 0.25.
- **Next man**: among this game's active players at the absent player's position (RB events: RBs; target events: same
  position as the absent player), the one with the highest prior share. Ties: lower gsis id.
- **Beneficiaries**: all active same-position teammates in an event game.

## Questions and measures
1. **How often**: events per season and per week; beneficiary player-games as a share of all forecast player-games.
2. **How much error**: Engine A CRPS for beneficiaries vs all other played rows (rush_att and rush_yds for RB
   events; rec and rec_yds for target events), the beneficiaries' share of the market's total CRPS, the next man's
   mean signed error (engine mean minus actual) with a week-clustered bootstrap 95% interval, and the share of next
   men whose actual is above the engine's 90th percentile (10% if calibrated).
3. **Fake edges**: no 2022-2023 prop prices are in the repo, so these cannot be counted. The 90th-percentile
   exceedance in (2) is the proxy and is reported only.
4. **Team style** (RB events only): the next man's actual share of team RB carries, predicted three ways from
   earlier games only:
   - P0 proportional (the engines' rule): s_next / (1 - s_lead)
   - P1 team style (next man inherits the lead role): s_lead
   - P2 halfway: (P0 + P1) / 2
   Measure: mean absolute error of the share. Compared: P1 vs P0 and P2 vs P0, week-clustered paired bootstrap,
   Bonferroni over the two comparisons (97.5% intervals).

## Decision rule (fixed now)
- **Problem is real** if the next man's mean signed error in rush_att is below 0 with its 95% interval below 0
  AND at least 20% of next men are above the engine's 90th percentile in rush_att.
- **Team style helps** if P1 or P2 has lower MAE than P0 with its 97.5% interval entirely below 0.
- Real and helps: recommend building a team-style reallocation rule as a candidate engine version (tuned on
  2022-2023, its own Test S on 2024-2025, shadow only alongside Test M).
- Real but does not help: recommend a flag instead (mark players on a team with a vacated lead role as engine
  unreliable), not a new model.
- Not real: nothing to fix at scale; report it.
Interim looks during the run are descriptive. "Nothing survives" is a valid result.

## Code check before the run
Hand cases with known answers: a planted team where the lead back is absent and the backup's share is set, to
confirm event detection, next-man choice and the three predictors; a team without an absence must produce no event.
