# Polymarket US fee schedule (as provided 2026-10-14)

Source: docs.polymarket.us "Fee Schedule" page (index https://docs.polymarket.us/llms.txt), pasted into the
session on 2026-10-14 because the sandbox cannot reach the site. Key terms used by scripts/polymarket_compare.py:

- Standard fees, effective exchange-wide from 10 AM ET, Wednesday 2026-10-07: `Fee = Θ × C × p × (1 - p)`,
  C = contracts, p = trade price ($0.01-$0.99).
- Taker Θ = 0.0695 (all markets except Table Tennis, Θ = 0.10). Maker rebate Θ = -0.0125 (makers pay no taker fee).
- Each fill's fee is rounded to the nearest $0.01 with banker's rounding.
- Taker rebate: none below $250,000 of prior-calendar-month taker volume.
- From 1:00 PM ET Monday 2026-10-19: maker and taker rebates move to volume tiers (maker Tier 1, below $10,000,000,
  gets no rebate; taker Tier 1, below $250,000, gets none). Taker fee formula and coefficients do not change.
- Combo (parlay) taker fee: `C × p × [0.0695 × (1 - p) + 0.06 × (1 - p)^4]`, no maker rebate.

This replaces the 0.05 Sports rate on docs.polymarket.com, which describes Polymarket's international exchange.
The markets' own `feeCoefficient` field (0.0695 on every Polymarket US market pulled so far) agrees.
