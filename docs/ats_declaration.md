# NFL Against-the-Spread Model: Declaration and Backtest Pre-registration (2026-10-09)

Requested by Will (angle: long-term line value and CLV on NFL pre-game point spreads, from an opponent-adjusted,
regressed power rating plus line shopping, key numbers and sharp reference prices). Lane: NFL regular-season
pre-game spreads only. Committed before any rating is computed.

## Factors (as agreed 2026-10-09)
| Factor | Grade | Source | Status |
|---|---|---|---|
| Multi-book spreads and juice | GATE | Action Network, ParlayAPI, OpenMarkets | live only (probe pending) |
| Key player availability | GATE | ESPN injuries / depth charts | live only; position values need their own test |
| Sharp reference | GATE | exchange spreads via OpenMarkets (Kalshi, Polymarket, ProphetX); Pinnacle via ParlayAPI where present | live only; Circa not available |
| Opponent-adjusted efficiency | WEIGH | nflverse play-by-play (EPA/play) | **tested here** |
| Key numbers / half points | WEIGH | nflverse final margins | computed here (descriptive) |
| Price vs number | WEIGH | margin distribution + juice | math |
| Expected closing line / CLV | CONTEXT | own timestamped snapshots from 2026 | no history before 2026 |
| Tactical unit matchups | CONTEXT | none free | dropped until a source exists |
| Small-sample volatility | CONTEXT | play-by-play | regression built into the rating |
| Weather | CONTEXT | nflverse (history), Open-Meteo (live) | context |
Pressure rate and yards per route run are dropped (no free source).

## Rating (v1)
- Plays: nflverse play-by-play, `play_type` pass or run, excluding QB kneels and spikes, with win probability
  between 0.05 and 0.95 at the snap (garbage time excluded).
- Per team-game: offensive EPA/play and defensive EPA/play allowed.
- Opponent adjustment: a game's offensive value is its EPA/play minus the opponent's defensive rating going into the
  game (relative to league average); defense likewise.
- Rating going into a week: exponentially weighted mean of the team's adjusted games this season (half-life h
  games) combined with a prior worth k games: (sum w_i x_i + k * prior) / (sum w_i + k). Prior = the team's final
  rating last season times r (regression toward average).
- Net rating = offense − defense. Fair home margin = HFA + c × (net_home − net_away). c and HFA by least squares.
- Constants h ∈ {4, 8, infinite}, k ∈ {2, 4, 8}, r ∈ {0.3, 0.5, 0.7}, c and HFA: chosen **on 2016-2021 only**, by
  mean absolute error of the fair margin against the actual margin (weeks 2-18; week 1 uses the prior alone).
  2015 is history for the 2016 prior.

## Protocol
1. Explore on 2016-2021: fit constants, report fair-line error vs the closing spread's error, the key-number table
   (1999-2021 margins), and anything else looked at. Exploration results are hypotheses.
2. Freeze the constants in `data/backtests/ats_constants.json` and commit the confirm script **before** computing
   any 2022-2025 rating.
3. Confirm once on 2022-2025 (closing `spread_line` and `home/away_spread_odds` from nflverse schedules).

## Confirm tests (family of 2; Bonferroni)
- **T1, information beyond the close:** OLS of the home margin on the closing spread and (fair − close). Pass if
  the coefficient on (fair − close) is above 0 with a week-clustered bootstrap interval (two-sided 0.05 / 2) whose
  lower end is above 0.
- **T2, betting the disagreements:** where |fair − close| ≥ 1.5 points, take the side the model prefers at the
  closing price. Pass if n ≥ 30 in ≥ 10 weeks and the week-clustered ROI interval (one-sided 0.025 / 2) has its
  lower end above 0. Pushes refund.
- Descriptive only: thresholds 0.5 / 1 / 2 / 3 points, subsets crossing 3 or 7, cover rate, by season.
Bets here are at the closing line, so CLV is zero by construction: this asks whether the rating beats the close
itself. Beating earlier lines (the live tracker's CLV) can only be measured from 2026 snapshots.
"Nothing passes" is a valid result; the live tab would then show the fair line as context, with every game No
Value unless a later test passes.
