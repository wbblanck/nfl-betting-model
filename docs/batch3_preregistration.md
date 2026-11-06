# Batch 3: touchdown/field-goal score model, pregame starting QB: Pre-registration (2026-11-06)

Requested by Will (2026-11-06, "Sure" to batch 3; master list rows D2 + M1 and G1). Committed before the new score
model or the pregame-QB input has produced any output, and before the play-by-play touchdown and field-goal counts are
tabulated for any season. Code: `src/nflbet/ats/tdfg.py`, `scripts/batch3.py`, tests `tests/test_tdfg.py`.

## Why
The negative binomial (NB) score model treats points as a smooth count. Real scores clump at multiples of 3 and 7, and
so do margins (the simulator lands on 3 12.0% of the time against 14.2% actual, master list D2). Spread pricing
depends on those clumps. G1 asks whether the Elo + QB layer still works when it only knows the QB a bettor could know
before kickoff, not the starter recorded after the game.

## Samples
- **Fit: 2016-2020** regular season (the seasons the frozen Elo and NB constants were fit on). 2021 is not used.
- **Test: 2022-2025** regular season, weeks 2-18, games with an nflverse closing `spread_line`. The NB model was
  scored on these seasons before (E5, docs/elo_report.md); the touchdown/field-goal model has never been run on them.
- Elo ratings and the scoring level are the frozen ones (`data/backtests/elo_constants.json`: K 25, home 35,
  regression 1/2, b 0.0853, NB θ 5.996). Both score models use the same Elo gap d and the same scoring level L.
- Spread sign: nflverse, positive = home favored. Home covers when margin > `spread_line`; margin = line is a push.

## Models
- **NB (baseline, frozen):** each team's points ~ NB(μ, θ), μ_home = L·exp(b·d/100), μ_away = L·exp(−b·d/100).
- **TD/FG (D2 + M1), each team independently:**
  - Touchdowns T ~ NB(λ_T, θ_T) with λ_T = c_T·L·exp(±b_T·d/100) (θ_T → ∞ allowed, i.e. Poisson).
  - Field goals F ~ Poisson(λ_F) with λ_F = c_F·L·exp(±b_F·d/100).
  - Each touchdown adds 6 plus a conversion worth 0, 1 or 2 with probabilities (p0, p1, p2), independent across
    touchdowns.
  - Safeties S ~ Poisson(s), worth 2 each.
  - Points = 6T + conversions + 3F + 2S. The two teams are independent; the margin distribution is their convolution.
- **Counts, from nflverse play-by-play.** T = touchdowns credited to the team (`td_team`, all phases). F = made field
  goals by the possession team. S = safeties credited to the defense. Conversions: extra point good = 1, two-point
  attempt success = 2, anything else = 0, per touchdown not followed by a conversion play = 0. Points these counts do
  not explain (defensive two-point returns, data errors) are reported, not modeled.
- **Fit (2016-2020):** c_T, b_T, θ_T by NB maximum likelihood of T; c_F, b_F by Poisson maximum likelihood of F;
  p0-p2 and s as observed shares and rates. Frozen in `data/backtests/batch3_constants.json` before the test runs.

## Tests (family of 2, Holm at 0.05; week-clustered bootstrap, 2,000 draws; one-sided)
- **T1 exact margin:** per game, d = log P_TDFG(observed home margin) − log P_NB(observed home margin). Pass: mean d
  interval above 0.
- **T2 cover:** per game with no push against `spread_line`, d = cover log loss of NB − cover log loss of TD/FG,
  where P(home covers) = P(margin > line) / (1 − P(margin = line)). Pass: mean d interval above 0.
- Holm: compare the smaller one-sided p (share of bootstrap means ≤ 0) with 0.025, then the other with 0.05; stop at
  the first failure. Intervals are reported at each test's Holm level.

## Pregame starting QB (G1, descriptive only, no pass/fail)
- nflverse has no Wednesday report snapshot: its injury file keeps the final pregame report per player-week. So the
  input is the starter a bettor could expect from the final report, not from Wednesday (a deviation from the
  master-list wording, made here before any data is read).
- **Expected starter:** the team's QB with the most dropbacks in its previous regular-season game that season. If the
  final report lists him Out or Doubtful for this game, the team's other QB with the most dropbacks so far that season;
  if there is none, an unknown QB at the frozen replacement level.
- Elo + QB with the batch 1 constants (q 400, c 1/2, b 0.0868), run twice on 2022-2025 weeks 2-18: once with the
  recorded starter (`home_qb_id`/`away_qb_id`), once with the expected starter. Report: share of team-games where the
  two differ; margin MAE of Elo, Elo + QB recorded and Elo + QB expected, on all games and on games where they differ.
- Known gap, disclosed now: a starter moved to injured reserve leaves the report, so the rule still expects him.

## Power, stated in advance
About 1,000 test games. The fit seasons give the per-game SD of the T1 difference; the fit script prints the
resulting standard error (SD/√1,000) before the test runs. T2's per-game log-loss differences between two models
that share the same mean are small, so T2 can only find an effect if the clumps move cover probabilities near key
numbers; a fail there means "no evidence".

## Known answers first (synthetic data, before any real output)
1. The TD/FG points distribution sums to 1 and its mean equals λ_T·(6 + p1 + 2·p2) + 3λ_F + 2s.
2. It matches a 200,000-draw Monte Carlo of the same model within 0.003 at every point total.
3. On scores generated by the TD/FG model with known parameters, the fit recovers c_T, b_T, c_F, b_F within 10%.
4. Planted signal: on 2,000 synthetic games generated by the TD/FG model, the T1 difference against a fitted NB is
   above 0. Noise: on 2,000 games generated by an NB model, the T1 difference of a fitted TD/FG model is not above 0.
5. Expected-starter rule on a hand case: the previous starter listed Out hands the start to the backup with the most
   dropbacks; Questionable keeps the previous starter.

Descriptive only: share of margins on 3 and 7 (actual, NB, TD/FG), single-team score shares by total, push rates at
lines 3 and 7, both models' MAE and cover log loss by season.
