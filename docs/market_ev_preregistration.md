# Market EV: fair-price method and 2025 test, pre-registration (2026-11-13)

Requested by Will (2026-11-13, project thread "Show EV% on dashboard props"). He approved the recommended order of
work from the Prop Outliers review. Items 4 and 5 of that order are fixed here, before any code computes them and before
any 2025 row is read for this rule:

- **Item 4.** A multi-venue fair price for the live dashboard.
- **Item 5.** A pre-registered test of market-EV picks on 2025.

"Market EV" is the return per $1 staked when a price is judged against the market's own fair probability rather than
against a model. A price is market +EV when one venue pays more than the other venues' consensus. That is line
shopping. It says nothing about whether the consensus is right.

The idea comes from a third-party dashboard (Prop Outliers). It was not found in our data. Its EV column equals fair
probability x decimal odds - 1, with exchange fees taken off. That was checked against seven of the prices it showed.
Its fair-price method is not stated, and we do not copy it.

## Part A: live fair price (dashboard, display only)

For each mix pick at each run (src/nflbet/props/bestprice.py):

1. Each venue's all-in cost per $1 of payout is recorded on **both** sides at the pick's line. The pick's side is
   already in `venues`; the other side goes in a new `venues_opp` column.
2. A venue counts toward the fair price when it has both sides with:
   - each cost below 0.97;
   - for exchanges (Novig, Kalshi, Polymarket US), at least $10 of payout on each side (`MIN_SIZE`).
3. Venue v's fair probability for the side is p_v = cost_side / (cost_side + cost_other). This is the multiplicative
   de-vig. For an exchange it removes spread and fee alike.
4. **Fair = the median of p_v over the counting venues other than the venue with the best price for the side
   (leave-one-out).** Two or more such venues are required. With fewer, the fair is DraftKings' no-vig probability and
   the card says so.
5. Market EV = fair / best_cost - 1. It is shown next to the model EV, labeled "market EV", with its fair probability
   and the number of venues behind it.

This is a display and is not validated. It changes no pick, grade or rule of the mix tracker (docs/mix_live_rules.md).
Rows written before this change have no `venues_opp`, so they fall back to DraftKings' no-vig fair.

## Part B: 2025 test of market-EV picks

**Sample.** `data/props/an_props_2025.csv` through `props.core.load_lines(2025)`, which keeps real books only and
refuses two lines per book per prop. The rest of the sample:

- Over/under markets only (no anytime TD), weeks 1-18.
- Each book's two-sided quote is junk-screened: de-vigged P(over) 0.35-0.65 and hold under 10%. A failing quote is
  dropped.
- A prop is (game, player, market, line) with at least **3 books** quoting that line two-sided after the screen.

This rule has never been computed on 2025. 2025 props were explored for other rules (CLAUDE.md season roles). The rule
form below comes from the third-party dashboard, not from any look at our data.

**Rule, per prop and side.**

- The best book is the one with the lowest implied cost for that side. A tie goes to the alphabetically first book name.
- fair_loo = the median of the other books' multiplicatively de-vigged P(side).
- EV = fair_loo / cost_best - 1.
- At most one bet per prop: the side with the larger EV, when it meets the rule's threshold.
- 1 unit at the best book's price.

| Rule | Bet when |
| --- | --- |
| M1 | EV > 0 |
| M2 | EV >= 3% |

**Grading.** `props.core.join` with nflverse 2025 stats and snap counts:

- A player who played without a stat row is graded 0; a player with no snaps is void.
- Pushes and voids are dropped.
- Ambiguous or unmatched names are dropped, as in `core.graded`.

**Pass criteria (Holm over 2 rules, family one-sided alpha 0.025).** A rule passes with all of:

- at least 30 graded bets in at least 5 weeks;
- a week-clustered bootstrap p-value (share of 10,000 resampled ROIs <= 0, seed 7) below its Holm threshold: 0.0125
  for the smaller p, then 0.025.

"Nothing passes" is a valid result.

**Power (computed before any data, normal approximation, unit-return sd 0.95, one-sided alpha 0.0125, 80% power).**
About 3,431 bets are needed to detect a true ROI of +5%, 9,531 for +3% and 21,446 for +2%. If the rules select fewer
bets, a real line-shopping edge of a few percent may go undetected. The report will state the n and the smallest ROI
detectable at that n.

**Known bias, stated now.** Action Network lines carry no timestamps (CLAUDE.md data traps), so the best book's price
may not have been live at the same time as the others. A stale price can look like an outlier that could not have been
bet. A pass is therefore an upper bound, and it would need confirmation on 2026 live runs, whose venue prices are read
in one run. A fail is informative.

**Validation before the real run** (tests/test_market_ev.py):

- Hand cases for the de-vig, leave-one-out median, EV, tie-break and one-bet-per-prop rules.
- A planted-signal simulation: true probability = the consensus, one book pays 5% over fair, outcomes drawn from the
  truth. M2 must show a clearly positive ROI.
- Noise: no book off-fair, outcomes from the truth. ROI must be about the vig, and the rules must not pass.

**What a result changes.** A pass makes market EV a candidate for the dashboard filter and for a forward check on 2026
runs (pre-registered separately). A fail leaves market EV as a display. No result here adds a pick list (CLAUDE.md).

Code: `src/nflbet/props/market_ev.py` and `scripts/market_ev_test.py`, committed with the tests before
`scripts/market_ev_test.py run` is executed. Report: `docs/market_ev_report.md`.
