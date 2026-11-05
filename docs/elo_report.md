# Elo + Poisson / negative binomial baseline: results

Code: src/nflbet/ats/elo.py. Pre-registration: docs/elo_preregistration.md (committed before any Elo output). Constants frozen in
data/backtests/elo_constants.json before 2022-2025 was run. Scripts: scripts/elo_fit.py, scripts/elo_g4_fit.py,
scripts/elo_confirm.py. Numbers: data/backtests/elo_confirm.json, per game data/backtests/elo_confirm_games.csv.
Confirm sample: 2022-2025 regular season weeks 2-18, 1023 games. Each test at 0.05 / 7, week-clustered bootstrap.

## Bottom line
- **A plain Elo is as close to the final margin as the play-by-play simulator** (MAE 9.964 vs 9.983; difference
  −0.019, interval −0.288 to +0.246). The simulator's extra machinery buys nothing on the mean margin.
- **Both lose to the closing line the same way.** Elo carries no information beyond the close (E1), betting its
  1.5+ point disagreements at the close lost (E3: 47.9% covers, ROI −7.8%), and its win probabilities are worse
  than the closing moneyline's (E4). Like the simulator, the line does move toward it from bet365's opener (E2,
  23% of the gap; the simulator's G3 figure was 30%).
- **Negative binomial beats Poisson** for the score (E5), clearly. Poisson is far too confident because NFL scores
  vary about four times as much as their mean. Even NB's cover probabilities are worse than a coin, though.
- **Elo as a simulator input adds nothing** (E7: G4 MAE 10.001 vs G3 9.983).

## The model as fitted (2016-2020)
- Rating gap d = home rating − away rating + 35 (home field; 0 at neutral sites). Win probability 1 / (1 + 10^(−d/400)).
- Expected points: league level × exp(±0.0853 · d/100), so 100 Elo points of gap ≈ 18.6% more points for the
  stronger side relative to the weaker. NB size θ = 6.00 (variance 100.6 vs mean 23.1 in the fit seasons).
- In-season update: ±25 · M · (result − win probability), M = ln(|margin| + 1) · 2.2 / (0.001 · winner's gap + 2.2).
  Between seasons each rating moves halfway back to 1505.
- Grid choice K 25, H 35, c 1/2 by win-probability log loss (0.62733). **c = 1/2 is the edge of the grid.**
- 2021 (descriptive): Elo margin MAE 11.304 vs close 10.682 (docs/elo_explore.txt).

## Confirm tests (family of 7)
| Test | Result | Verdict |
|---|---|---|
| E1 information beyond the close | coef on (Elo − close) −0.074, interval −0.456 to +0.350 | FAIL |
| E2 line movement (bet365 2022-2024, n 767) | coef +0.233, interval +0.136 to +0.345 | **PASS** |
| E3 bet \|Elo − close\| ≥ 1.5 at closing price | 627 bets in 68 weeks, 47.9% covers, ROI −7.8%, interval −16.7% to +1.4% | FAIL |
| E4 win probability vs closing moneyline (n 1021) | log loss market 0.6068, Elo 0.6349; market − Elo −0.0280, interval −0.0459 to −0.0116 | FAIL (market better) |
| E5 Poisson vs NB cover probability (n 994) | log loss Poisson 0.7754, NB 0.7129; difference +0.0626, interval +0.0414 to +0.0903 | **PASS** (NB better) |
| E6 simulator (G3) vs Elo, margin MAE | Elo − G3 −0.019, interval −0.288 to +0.246 | no difference shown (FAIL) |
| E7 simulator + Elo input (G4) vs G3 | G3 − G4 −0.018, interval −0.062 to +0.027 | FAIL |

## Descriptive
| Season | Games | Elo | Simulator G3 | G3 + Elo (G4) | Close |
|---|---|---|---|---|---|
| 2022 | 255 | 8.986 | 9.061 | 9.056 | 8.718 |
| 2023 | 256 | 10.463 | 10.316 | 10.348 | 9.818 |
| 2024 | 256 | 10.071 | 10.169 | 10.182 | 9.648 |
| 2025 | 256 | 10.333 | 10.381 | 10.413 | 9.959 |
| All | 1023 | 9.964 | 9.983 | 10.001 | 9.537 |

| \|Elo − close\| ≥ | Bets | Covers | ROI |
|---|---|---|---|
| 0.5 | 887 | 48.4% | −6.8% |
| 1.0 | 757 | 48.0% | −7.6% |
| 2.0 | 520 | 49.5% | −4.8% |
| 3.0 | 335 | 50.6% | −2.7% |

- Win-probability log loss (ties dropped): logistic curve 0.6349, NB score model 0.6368, Poisson score model 0.6634.
  The logistic curve and NB agree; Poisson is overconfident.
- QB-adjusted Elo (q = 400 Elo points per EPA/dropback of starting-QB change, fitted 2016-2020): margin MAE 9.901,
  win log loss 0.6288. Slightly better than plain Elo; not tested.
- 2026 ratings through week 8 (a ratings table, not picks): BUF 1662, CHI 1637, DEN 1633, JAX 1630, SF 1628,
  MIN 1622, SEA 1610, NE 1608, PIT 1593, CIN 1585, DET 1578, LA 1577, KC 1550, GB 1540, TB 1514, HOU 1496, BAL 1485,
  NYG 1484, ATL 1470, CLE 1468, DAL 1444, LV 1442, CAR 1440, WAS 1437, NO 1425, ARI 1405, IND 1394, PHI 1378,
  MIA 1372, LAC 1371, NYJ 1360, TEN 1324.

## Reading
- The simulator's step 2-3 layers reach the same place a one-number rating does. Its value, if any, is in things
  Elo cannot produce (player box scores, game-state paths), not in the margin.
- E2 passing for both Elo and the simulator says both pick up information the opener lacks and the close absorbs.
  That is a closing-line-value pattern, not an edge at the close.
- If the simulator is kept for spreads, a fair benchmark for any new layer is now "beats Elo", not only "beats G3".

## Disclosures
- Known-answer check 3 (planted signal) missed its pre-registered bar: the +7 team finished top 8 in 86.5% of 200
  synthetic seasons (bar 90%). Ranking those seasons by raw point differential gives 93.5%, so Elo's recency
  weighting and log margin cap lose some signal within a season. All other checks passed (tests/test_elo.py).
- Ratings update through playoff games too (FiveThirtyEight practice); forecasts and tests use regular-season games.
- The G3 per-game output was regenerated with its frozen constants and seed and reproduced the registered MAE
  (9.983) before E6 and E7 ran. The cache came from a new download script, scripts/gamesim_cache.py.
- Code lives in src/nflbet/ats/elo.py, not src/nflbet/elo.py as the pre-registration said (the repo layout test forbids new top-level modules); moved after the run, no logic changed.
- 2022-2025 had already been used to confirm the EPA rating and the simulator; this was the first Elo output on them.
