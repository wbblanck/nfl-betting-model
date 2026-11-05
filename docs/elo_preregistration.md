# Elo rating + score-distribution baseline: Pre-registration (2026-11-05)

Requested by Will (2026-11-05): a simple rating model as a **baseline, not a betting model**, built his way: each
team gets one rating; a logistic curve turns the rating gap into a win probability; Poisson and negative binomial
distributions forecast the score itself; ratings update through the season. Compared against the play-by-play game
simulator (src/nflbet/gamesim, docs/gamesim_confirm.md) and the closing line, and tested as a team-strength input to
the simulator. Committed before any Elo output exists for any season and before the simulator's per-game 2022-2025
output is regenerated. Code: `src/nflbet/elo.py`, `scripts/elo_*.py`, tests `tests/test_elo.py`.

## The model
1. **Rating.** One number per franchise (relocations merged: STL→LA, SD→LAC, OAK→LV). Every franchise starts at
   1500 in 1999 (first nflverse season); 1999-2004 are burn-in only.
2. **Win probability.** Gap d = R_home − R_away + H (H = 0 at neutral sites). P(home win) = 1 / (1 + 10^(−d/400)).
3. **Score forecast.** Expected points: log μ_home = a + b·d/100, log μ_away = a − b·d/100, where
   a = log(league points per team-game), estimated from games before the one forecast: the previous regular season's
   mean blended with the current season to date, (128·prev + Σ current) / (128 + n current team-games).
   b is fitted once by Poisson maximum likelihood on 2016-2020. Two score distributions with the same means:
   **Poisson**, and **negative binomial** with one size θ fitted by maximum likelihood on 2016-2020. The two teams'
   scores are independent given the means. Fair spread = μ_home − μ_away. Cover, win and margin probabilities come from
   convolving the two score distributions (scores 0-100).
4. **In-season update** (FiveThirtyEight form). After each game both ratings move by ±K·M·(S − P), S = 1 / 0.5 / 0 for a
   home win / tie / loss, P the pre-game win probability, M = ln(|margin| + 1) · 2.2 / (0.001·d_w + 2.2) with d_w the
   gap from the winner's side (M = 1 for a tie). Ratings use games strictly before the one forecast. Between seasons
   each rating moves a fraction c of the way back to 1505.
5. **Optional QB adjustment (descriptive only).** d += q·(qb_delta_home − qb_delta_away), where qb_delta is the
   simulator's personnel-layer starting-QB input (EPA per dropback, src/nflbet/gamesim/personnel.py); q fitted on
   2016-2020 by win-probability log loss. Reported, not tested.

## Seasons
- **Fit 2016-2020** (regular season, all weeks; ties dropped from log loss). Grid, chosen by win-probability log loss:
  K ∈ {15, 20, 25, 30}, H ∈ {20, 35, 50, 65}, c ∈ {1/4, 1/3, 1/2}. Then b, θ, q fitted with the chosen K, H, c.
- **Explore 2021:** descriptive only (nothing is chosen there). All constants then frozen in
  `data/backtests/elo_constants.json`, committed before any 2022-2025 Elo output is computed.
- **Confirm once on 2022-2025**, regular season weeks 2-18 (the simulator's confirm games). These seasons were used
  to confirm the EPA rating and the simulator; no Elo output has been computed on them in this repo.

## Simulator with an Elo input (G4)
The simulator's personnel layer (step 3, G3) shifts each offense's rates by a weighted least-squares fit of rate
residuals on six inputs (fit seasons 2016-2020). G4 adds one input, **elo_gap** = (own pre-game rating − opponent's
pre-game rating) / 100, H not included, refits all seven coefficients on 2016-2020 with the frozen factor constants,
and is otherwise the G3 simulator (same seed 101, 1000 simulations per game). G3's per-game output on 2022-2025 is
regenerated with its frozen constants and seed; it must reproduce docs/gamesim_confirm.md's G3 MAE (9.983) to three
decimals or the comparison is not run.

## Known answers first (synthetic data and 1999-2015 only, before 2016+ output)
1. Hand case: 1500 v 1500, H = 0, home wins by 7, K = 20 → home +20.79, away −20.79. Ratings sum is unchanged by
   every update. Same input → same output.
2. No look-ahead: deleting a game and all later games leaves every earlier pre-game rating unchanged.
3. Planted signal: in a synthetic league where one team's true margin edge is +7, its Elo ends in the top 8 in ≥ 90% of 200
   seasons; in an all-equal league the season-end rating spread's correlation with the next synthetic season's
   results is within ±0.1 of 0.
4. Score model: on synthetic Poisson and NB scores with known b and θ, the fit recovers b within 10% and θ within 25%;
   Poisson convolution P(home win) matches 200,000-draw Monte Carlo within 0.005.

## Confirm tests (family of 7; Bonferroni, each at 0.05 / 7; week-clustered bootstrap, 2,000 draws)
"Elo" below means the NB score model's fair spread unless stated.
- **E1, information beyond the close:** OLS of home margin on the closing spread and (Elo fair − close); pass if the
  coefficient on (Elo fair − close) has an interval above 0.
- **E2, line movement:** OLS of (close − open) on (Elo fair − open), bet365 2022-2024 (`data/odds/asb_nfl_games.csv`);
  pass if the interval is above 0.
- **E3, betting:** where |Elo fair − close| ≥ 1.5, Elo's side at the nflverse closing price; pass if n ≥ 30 in ≥ 10
  weeks and the one-sided ROI interval is above 0.
- **E4, win probability vs the market:** log loss of Elo's logistic P(home win) vs the de-vigged nflverse closing
  moneyline, games with both prices, ties dropped; pass (Elo better) if the interval of (market − Elo) is above 0.
- **E5, Poisson vs negative binomial:** log loss of P(home covers the closing spread), pushes dropped; pass (NB better)
  if the interval of (Poisson − NB) is above 0.
- **E6, simulator vs Elo:** paired margin MAE, d = |Elo fair − margin| − |G3 fair − margin|. Two-sided interval:
  "simulator better" if above 0, "Elo better" if below 0, otherwise "no difference shown". Pass = simulator better.
- **E7, Elo as a simulator input:** paired margin MAE, d = |G3 − margin| − |G4 − margin|; pass (G4 better) if the
  interval is above 0.

Descriptive only: margin MAE of Elo (Poisson and NB means are the same), G3, G4 and the close, by season; Elo-logistic
vs count-model win probability log loss; cover log loss of both count models vs a coin; Elo bets at 0.5 / 1 / 2 / 3
point thresholds; the QB-adjusted variant; current 2026 ratings (a table of ratings, not picks).
"Nothing passes" is a valid result. Elo is a baseline here; a pass on E1-E4 would need its own forward test before
any use.
