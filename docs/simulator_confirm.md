# Screener Rule S1: Confirmation Pre-registration (2026)

Committed before any screener or simulator number was computed on 2026 (docs/simulator_declaration.md). Code:
`src/nflbet/screener.py` (`scored`, `rule_s1`, `bets_frame`), graded by `scripts/grade_2026.py`. Exploration:
`docs/screener_explore.txt`.

## Rule
**S1** Score every screened DraftKings over/under prop on four pre-game signals (books disagreeing with DK at the
extreme line; the projection model 10%+ from the line; the simulator 5+ points from the de-vigged price; DK
already pricing a side below −120). Bet only props where **all four** point the same way, on that side, at DK's
price. Simulator fitted on 2024 (no matchup), projection constants fitted on 2024.

## Why only this one
2024 and 2025 were explored: more agreeing signals raised the win rate, but every looser cut lost money (2025: 2+
agree −3.1%, 3+ agree −2.0%; top 3/5/10/20 per week −5.8% to −9.8%). All four agreeing: 2025 n 61 in 13 weeks, won
62.3%, ROI +5.2% (95% interval −16.3% to +26.9%); 2024 n 2. Weak support, disclosed.

## Decision
After the 2026 regular season: PASS if n >= 30 bets in >= 10 weeks and the week-clustered ROI interval (one-sided
2.5%) has its lower end above 0. Interim numbers are descriptive.
