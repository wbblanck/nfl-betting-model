# Market EV on 2025 props: report

Pre-registration: [market_ev_preregistration.md](market_ev_preregistration.md), committed before this run. Run once with `python scripts/market_ev_test.py run`.

**Sample:** 1,141 props with 3+ screened books (weeks 1-18, 2025, Action Network). 36,086 book quotes before the screen, 22,045 after it. One candidate side per prop.

| Rule | Bet when | Graded bets | Weeks | Wins | Mean EV at bet | ROI at best book | 95% week-bootstrap | p | Holm threshold | Verdict | Smallest ROI detectable (80% power) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | EV > 0 | 211 | 13 | 106 | +3.7% | +4.2% | -10.1% to +16.2% | 0.2478 | 0.0250 | fail | +20.2% |
| M2 | EV >= 3% | 67 | 13 | 37 | +9.3% | +19.6% | -14.1% to +53.2% | 0.1279 | 0.0125 | fail | +35.8% |

ROI is per 1 unit at the best book's price. The p-value is the share of 10,000 week-resampled ROIs at or below 0 (seed 7). Action Network lines carry no timestamps, so a best price may not have been live alongside the others: a pass would be an upper bound (pre-registration, "Known bias").

## Result

Nothing passes. Both rules made money in 2025, but with 211 and 67 bets the intervals include losses, and at these sizes
only an ROI above about +20% (M1) or +36% (M2) would have been detectable. Most props have no line that three
books share: the sample is 1,141 props out of 22,045 screened quotes. So this test can neither confirm nor rule out a
few-percent line-shopping edge. Market EV stays a display on the dashboard, labeled unvalidated (pre-registration,
"What a result changes"). 2025 is now used for this rule and cannot be re-tested with a new threshold.
