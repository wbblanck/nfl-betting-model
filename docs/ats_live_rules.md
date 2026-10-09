# Live ATS Tracker: Rules (pre-registered 2026-10-09, before its first run)

Requested by Will (NFL against-the-spread angle; CLAUDE.md second exception). Descriptive, **unvalidated**: the
rating does not beat closing spreads (docs/ats_confirm.md) and rule K1's first unseen season was −20.9% on 70 bets
(docs/ats_k1.md). Code: `src/nflbet/ats_live.py`, run inside the S1 workflow (`scripts/live_s1.py`), no extra API cost
(Action Network scoreboard is keyless; exchange spreads come from the OpenMarkets calls the S1 run already makes).

## Each run, for every game of the week not yet started
- **Fair line:** the ATS rating with the frozen constants (data/backtests/ats_constants.json), from games strictly
  before the week.
- **Books:** DraftKings, FanDuel, BetRivers, BetMGM, Caesars spread and price (Action Network); Action Network
  consensus as a reference; its "Open" is ignored.
- **Sharp reference:** median of the exchanges' main spread (Kalshi, Polymarket, ProphetX, others via OpenMarkets);
  if none, the Action Network consensus.
- **Side:** the rating's side against the consensus line. **Best number:** the best line for that side across the
  books (ties: better price). **Gap** = fair − best number, from the side's view.
- **Key:** the best number sits on the better side of 3 or 7 relative to the fair line (rule K1's condition).
- **Expected CLV** = 0.235 × gap (points): the share of the gap bet365 openers moved toward the rating by the close
  in 2022-2024 (docs/ats_clv2.md). An estimate, not a promise.
- **QB gate:** a team's recent starting QB (most attempts, last 3 weeks) listed Questionable or worse on ESPN.

## Labels
- **Bet Now:** gap ≥ 1, key, and the best number is at least as good as the sharp reference, QB gate clear.
- **Wait:** the same, but a QB is listed.
- **Monitor:** gap ≥ 1.5, or gap ≥ 1 with key but not beating the sharp reference.
- **No Value:** everything else.
The official label for a game is the last run before kickoff. Nothing is edited after kickoff.

## Grading and season-end test (2026 regular season, from the first run on)
- Each official game: **CLV** = points the closing spread (nflverse `spread_line`) moved toward the side from the
  recorded best number; **ATS result** at the recorded best number and price (pushes refund).
- Tests on the official **Bet Now** games (family of 2, Bonferroni): (1) mean CLV above 0 with a week-clustered
  interval (one-sided 0.025 / 2) above 0; (2) ROI interval (one-sided 0.025 / 2) above 0. Both need n ≥ 30 in ≥ 10
  weeks; with fewer, the result is "not enough games", not a pass.
- Rule K1 (docs/ats_key_preregistration.md) for 2026 uses this tracker's **first recorded number and price of the
  week at a soft book** for each game, pooled with 2025.
- Other labels are reported descriptively.
