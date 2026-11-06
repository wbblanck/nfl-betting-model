# Batch 3 results: touchdown/field-goal score model, pregame starting QB

Pre-registration: docs/batch3_preregistration.md (committed before any batch 3 output). Constants fit on 2016-2020
and frozen in data/backtests/batch3_constants.json before the test ran (docs/batch3_fit.txt). Numbers:
data/backtests/batch3.json. Test: 2022-2025 regular season, weeks 2-18, 1,023 games (994 without a push against the
closing line). Holm at 0.05 over two tests; week-clustered bootstrap, 2,000 draws.

## Bottom line
**One of two passes, and the pass doesn't help betting.** The touchdown/field-goal model prices covers better than the
NB model (T2). But both are still worse than a coin flip against the closing line: cover log loss 0.7077 and 0.7129,
against 0.6931 for always saying 50%. It doesn't forecast the exact margin any better (T1).
The reason is in the descriptive table: the model gets **single-team** scores right (the 10, 17, 20 and 24 clumps),
but treats the two teams' scores as independent, so it barely moves the **margin** clumps. It puts 5.6% on a 3-point
margin against 15.2% actual. The margin-3 clump comes from how the two teams' scoring interacts late in games, which
independent teams can't produce.

| Test | Result | p | Holm level | Verdict |
|---|---|---|---|---|
| T2 cover log loss, NB minus TD/FG (n 994) | +0.0052, interval +0.0032 to +0.0073 | 0.000 | 0.025 | **PASS** |
| T1 log probability of the exact margin, TD/FG minus NB (n 1,023) | −0.0023, interval −0.0152 to +0.0105 | 0.617 | 0.050 | FAIL |

Power stated before the test: in-sample per-game SD of the T1 difference 0.229, so the standard error at about 1,000
games was 0.007.

## Fitted constants (2016-2020, 1,280 games)
- Touchdowns: c_T 0.1129, b_T 0.0983. θ_T went to the Poisson limit, which the pre-registration allowed.
- Field goals: c_F 0.0701, b_F 0.0318 (field goals depend on the rating gap about a third as much as touchdowns do).
- Conversion per touchdown: 0 points 10.6%, 1 point 85.4%, 2 points 4.0%. Safeties: 0.034 per team-game.
- 0.66% of team-games had points the counts don't explain (mean 0.007 points).

## Descriptive (not tested)
Share of games by absolute margin:

| Margin | Actual | NB | TD/FG |
|---|---|---|---|
| 1 | 5.0% | 5.5% | 4.3% |
| 2 | 5.1% | 5.5% | 3.5% |
| 3 | 15.2% | 5.4% | 5.6% |
| 7 | 8.1% | 4.8% | 5.6% |
| 10 | 4.7% | 4.2% | 4.9% |
| 14 | 4.6% | 3.3% | 4.1% |

Pushes: on the 151 games with a closing line of 3 (either side), 13.2% landed exactly on 3; NB said 2.9%, TD/FG 2.9%.
On the 48 games at 7: 4.2% actual, NB 2.8%, TD/FG 3.1%.

Single-team score shares:

| Points | Actual | NB | TD/FG |
|---|---|---|---|
| 3 | 1.8% | 0.3% | 2.7% |
| 7 | 1.5% | 1.4% | 3.5% |
| 10 | 5.2% | 2.6% | 5.5% |
| 17 | 6.3% | 4.1% | 6.0% |
| 20 | 7.7% | 4.0% | 5.6% |
| 24 | 6.1% | 3.4% | 4.6% |
| 27 | 5.9% | 2.8% | 4.2% |

Margin MAE: NB 9.964, TD/FG 9.963, closing line 9.537 (the two score models share the same Elo mean, so this is
expected). T1 by season: TD/FG ahead in 2023 and 2025, behind in 2022 and 2024. T2 favored TD/FG in all four seasons.

## Pregame starting QB (G1, descriptive only)
Elo + QB with the batch 1 constants, run once with the recorded starter and once with the starter expected from the
previous game and the final injury report:

| | Elo | Elo + QB, recorded starter | Elo + QB, expected starter |
|---|---|---|---|
| All 1,023 games, MAE | 9.964 | 9.902 | 9.921 |
| 194 games where the expected starter was wrong, MAE | 10.466 | 10.380 | 10.462 |

The expected starter differed from the recorded one in 10.2% of team-games (8 team-games fell to an unknown QB). With
only pregame information the QB layer keeps about two-thirds of its gain over Elo (0.043 of 0.062 points). In the games
where the guess was wrong, the gain disappears. A better pregame source (ESPN's live statuses, which the S1 tracker
already uses) would close part of that gap. Part of the 10.2% is the known gap: a starter moved to injured reserve
drops off the report, so the rule still expects him.

## Disclosures
- The two teams' scores are independent in both models. That is the most likely reason T1 failed, and a joint
  model (for example a bivariate count, or the simulator's own margin) would be a new hypothesis that needs fresh
  seasons.
- The NB model was scored on these seasons before (E5); the TD/FG model had not been.
- The 2024 kickoff rule change and the 2015 extra-point change fall inside or before the samples; conversion shares
  were fit on 2016-2020.
- nflverse's injury file has the final pregame report, not Wednesday's; G1 uses that (stated in the pre-registration).
