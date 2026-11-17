# Props closing-line value (CLV) record, 2026

Will asked (2026-11-17) whether CLV can be tracked on the props picks, and gave the go-ahead for a Pinnacle close
snapshot (PinnRadar free key, secret `PINN_API`). **Record only, unvalidated.** This is not a pick list and not a test:
it adds no picks, changes no rule, and nothing here is judged. Committed before any close snapshot exists and before
the line-move check below is run.

## What does not change
- The props mix tracker (docs/mix_live_rules.md): the official pick is still the last *tracker* run before kickoff, at
  DraftKings' price. Close snapshots are a separate job writing separate files (`data/live/close/`); the tracker never
  reads them, so they can never become the "last run" or change a pick.
- PR #27 (docs/ev_rules_2026_preregistration.md, rules K and Mo): untouched. CLV is not part of either rule.
- The mix's input stays DraftKings' no-vig price. Pinnacle is a display column and a CLV yardstick only.

## Close snapshot
- Job `.github/workflows/props-close.yml`, script `scripts/props_close.py watch`. Kickoff times come from the nflverse
  schedule (no API call). For each kickoff time the job takes a snapshot about 20 minutes and about 6 minutes before
  kickoff: Pinnacle's NFL board with props (PinnRadar, 1 request of the free 100 a day) and ParlayAPI DraftKings +
  FanDuel (3 requests of 1,000 a month; skipped if the key reports fewer than 200 left, to protect the trackers).
- Rows are saved with the snapshot time and minutes before kickoff (`data/live/close/pinnacle_2026.csv`,
  `data/live/close/books_2026.csv`, games kicking off within 60 minutes only).
- The **close** for a game and source is its last snapshot before kickoff, counted only if taken 30 minutes or less
  before kickoff. Otherwise the pick has no close for that source (shown as missing, never filled from an older run).
- Quote screen (CLAUDE.md, junk quotes): a close quote counts only if both sides are priced and the hold is under 10%.
  The 0.35-0.65 de-vigged band is not applied, because mix picks can sit on props outside it.

## CLV per official mix pick
For a pick on `side` at line `L_p`, DraftKings price `d` (decimal), and a close source with line `L_c` and de-vigged
(multiplicative) P(over at `L_c`) = `q`:
- `p_close` = the close's fair chance of the pick's side **at the pick's line**. Same line: `q` (or `1 - q`). Line
  moved: converted with the normal model below.
- **CLV (EV at close)** = `p_close x d - 1`: the pick's expected return if the close is the true probability. Also at
  the pick's best recorded price: `p_close / best_cost - 1`.
- **No-vig move** = `p_close -` the pick's own DraftKings no-vig chance at its run (probability points).
- **Line move** = close line minus pick line, signed so positive means the line moved toward the pick (over: line went
  up; under: line went down).
Sources: Pinnacle, DraftKings, FanDuel, each reported separately, plus the count of picks with a close.
Summaries: picks with a close, mean CLV, share of picks with CLV > 0, by source. Shown on the dashboard and in
docs/props_clv.md, labeled unvalidated. Prior work found Pinnacle's prop close no sharper than DK/FanDuel
(drburke-droid/NFL, outside repo, not rerun here), so no source is called "the truth".

## Line-move conversion (checked on known answers before use)
Model: the stat is Normal(mu, sigma) with sigma = s_m x sqrt(line) for market m. Given a quote (L, q), mu = L +
sigma x Phi^-1(q), sigma taken at L; then P(over L') = Phi((mu - L') / sigma) with sigma taken at the midpoint of L and L'.
- **Fit:** s_m per market by least squares on DraftKings vs FanDuel quotes for the same prop in the same ParlayAPI
  snapshot at different lines, snapshots of weeks 5-8 2026 (predict FanDuel's de-vigged P(over) at its line from
  DraftKings' quote). Grid s_m in 0.5..15 step 0.05 (yards markets) and 0.05..3 step 0.01 (receptions, attempts,
  completions).
- **Check:** the same pairs from weeks 9-10 snapshots, one pair per prop per week (the last snapshot), so repeated
  snapshots do not inflate the count. Baseline: ignore the line difference (predict FanDuel's P(over) = DraftKings').
- **Use it only if** the model's mean absolute error beats the baseline's on the check pairs overall and in each market
  with 30+ pairs. A market that fails, or has fewer than 30 check pairs, reports line-moved picks with the line move
  only and no converted CLV. "Fails" is a valid outcome.
- Planted-signal check in tests: a synthetic Normal stat with known sigma recovers s_m, and P at the same line is
  returned unchanged.
