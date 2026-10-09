# ATS Rating vs Bettable Opening Lines (bet365, 2022-2024): Pre-registration (2026-10-09)

Follow-up to docs/ats_clv.md, whose openers (Sportsbook Review) came from an unnamed book. Will supplied the
Australia Sports Betting file (data/odds/asb/README.md), with **named-book opening and closing spreads and prices**.
Committed before any rating is compared with these lines. Already seen: the file checks in its README (match
rates by source era); no rating was computed against them.

## Model, sample
- The ATS rating as frozen in data/backtests/ats_constants.json. No new constants.
- **Test seasons 2022-2024** (bet365 opening and closing spreads with prices; never used in a CLV test),
  regular season, weeks 2-18, games with opening and closing spread and both opening prices.
- Descriptive: Pinnacle 2014-2017 (bettable sharp openers; seasons overlap the first CLV test). 2025-2026 (betr) are
  left out: their closing lines are unreliable.

## Tests (family of 3; Bonferroni), as docs/ats_clv_preregistration.md but at real prices
- **C1:** OLS of (close − open) on (fair − open); pass if the week-clustered interval (two-sided 0.05 / 3) is above 0.
- **C2:** |fair − open| ≥ 1.5, the model's side at the opening number: mean CLV in points (toward the bet) above 0
  (one-sided 0.025 / 3), n ≥ 30 in ≥ 10 weeks.
- **C3:** the same bets at the **actual opening price** of that side, graded on the final margin, pushes refunded:
  ROI interval (one-sided 0.025 / 3) above 0.
