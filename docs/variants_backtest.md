# S1 variants backtest, 2024-2025 (exploration)

Pre-registration: docs/variants_preregistration.md. Interval: week-clustered, one-sided 0.025/12 per end. 2025 is the primary season (simulator and projection fitted on 2024). A pass is a hypothesis for a 2026 live record.

| ID | Season | Bets | Weeks | Win | Break-even | ROI | Interval | Verdict |
|---|---|---|---|---|---|---|---|---|
| V1 | 2025 | 61 | 13 | 62.3% | 59.2% | +5.2% | -24.8% to +35.9% | reference |
| V1 | 2024 | 2 | 1 | 100.0% | 61.1% | +63.9% | +63.9% to +63.9% |  |
| V2 | 2025 | 1289 | 18 | 55.6% | 56.5% | -1.6% | -8.8% to +7.6% | fail |
| V2 | 2024 | 889 | 18 | 57.5% | 59.0% | -2.7% | -8.6% to +4.0% |  |
| V3 | 2025 | 501 | 13 | 52.9% | 53.0% | -0.2% | -12.3% to +14.1% | fail |
| V3 | 2024 | 24 | 2 | 33.3% | 53.4% | -37.4% | -40.3% to -4.5% |  |
| V4 | 2025 | 630 | 18 | 57.9% | 58.8% | -1.3% | -9.9% to +8.0% | fail |
| V4 | 2024 | 857 | 18 | 58.0% | 59.1% | -2.0% | -8.0% to +4.7% |  |
| V5 | 2025 | 52 | 12 | 61.5% | 59.3% | +3.6% | -31.1% to +37.4% | fail |
| V5 | 2024 | 1 | 1 | 100.0% | 63.0% | +58.8% | +58.8% to +58.8% |  |
| V6 | 2025 | 52 | 13 | 61.5% | 58.9% | +4.6% | -35.0% to +39.7% | fail |
| V6 | 2024 | 0 | | | | | |  |
| V7 | 2025 | 403 | 13 | 55.6% | 54.1% | +2.7% | -10.6% to +17.9% | fail |
| V7 | 2024 | 17 | 1 | 47.1% | 54.5% | -14.7% | -14.7% to -14.7% |  |
| V8 | 2025 | 40 | 13 | 60.0% | 61.1% | -2.6% | -38.0% to +29.3% | fail |
| V8 | 2024 | 2 | 1 | 100.0% | 61.1% | +63.9% | +63.9% to +63.9% |  |
| V9 | 2025 | 33 | 12 | 57.6% | 58.9% | -2.4% | -49.9% to +43.4% | fail |
| V9 | 2024 | 0 | | | | | |  |
| V10 | 2025 | 45 | 13 | 66.7% | 59.1% | +12.6% | -24.7% to +51.4% | fail |
| V10 | 2024 | 0 | | | | | |  |
| V11 | 2025 | 882 | 18 | 57.3% | 56.5% | +1.4% | -7.5% to +9.6% | fail |
| V11 | 2024 | 620 | 18 | 58.7% | 59.2% | -1.0% | -8.3% to +7.0% |  |
| V12 | 2025 | 501 | 13 | 52.9% | 53.0% | -0.2% | -12.3% to +14.1% | fail |
| V12 | 2024 | 25 | 3 | 36.0% | 53.3% | -32.0% | -40.3% to +95.2% |  |
| V13 | 2025 | 562 | 13 | 53.9% | 53.7% | +0.4% | -11.1% to +14.1% | fail |
| V13 | 2024 | 27 | 3 | 40.7% | 53.9% | -24.9% | -31.6% to +95.2% |  |

## Result
No variant passes. None has a 2025 interval whose lower end is above 0 at the pre-registered level, so none goes
forward as a hypothesis for a 2026 live record. S1 stays as locked.

Known-answer check: V1 reproduces S1's registered 2025 numbers exactly (61 bets, 62.3%, +5.2%). V2 and V13 differ
from docs/screener_explore.txt by 4 and 1 bets (−1.6% vs −2.0%, +0.4% vs +0.2%), consistent with the prop files
being refetched after that exploration (task log: "Refetch props, rerun 2025 results").

Descriptive notes (not tests): every looser rule (V2, V3, V4, V7, V11-V13) wins more often but at better prices and
ends near break-even; the rules with positive point estimates (V1, V5, V6, V10) have 33-61 bets in 2025 and almost
none in 2024, so their intervals span roughly −35% to +50%. V9 (DraftKings vs FanDuel only, as the ParlayAPI
record) had 33 bets at −2.4% in 2025.
