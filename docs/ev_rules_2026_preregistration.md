# Market EV vs model EV on 2026 weeks 11-18 (K, Mo): pre-registration (2026-11-16)

Requested by Will (2026-11-16, project thread "Show EV% on dashboard props": "Yes" to the rule posted there). In week 10
the props mix picks with positive market EV went 17-9, and those with positive model EV went 32-36. That split was
chosen after the results, so it is a hypothesis only (CLAUDE.md). This test judges it on games not yet played.

**Committed before week 11 kicks off (Thursday 2026-11-19).** No week 11-18 result exists at commit time.

## Sample
- Official props mix picks (docs/mix_live_rules.md: sides the mix gives 55% or more), weeks 11-18 of 2026.
- One row per pick at its official run, the last before kickoff (`data/live/mix_record_2026.csv`).
- Graded W or L as the mix tracker grades them. Voids, pushes and pending picks are left out.

## Price and probabilities (from the same official run)
- **Best price.** The cheapest all-in cost per $1 of payout at the pick's line and side
  (`data/live/mix_bestprice_2026.csv`). DraftKings' price is used when nothing beats it.
- **Market fair.** docs/market_ev_preregistration.md, Part A: the leave-one-out median of the other venues'
  two-sided de-vigged probabilities. It is DraftKings' no-vig probability when fewer than two other venues quote both
  sides.
- **Model probability.** The mix probability of the side (`p_side`).

## Rules (1 unit per pick at the best price)
| Rule | Take the pick when |
| --- | --- |
| K | market EV = market fair / best cost - 1 > 0 |
| Mo | model EV = mix probability / best cost - 1 > 0 |

A pick can be in both rules. The two are judged separately.

## Pass criteria (Holm over 2 rules, family one-sided alpha 0.025)
A rule passes with all of:
- at least 30 graded bets in at least 5 weeks;
- a week-clustered bootstrap p-value (share of 10,000 week-resampled ROIs <= 0, seed 7) below its Holm threshold:
  0.0125 for the smaller p, then 0.025.

ROI at DraftKings' price is reported beside each rule but does not decide the verdict. "Neither passes" is a valid
result.

## Power (stated before any data)
Week 10 had 26 K picks among 111 graded picks. At that rate, weeks 11-18 give roughly 200 K bets. With unit-return sd
0.95, one-sided alpha 0.0125 and 80% power, 200 bets detect an ROI of about +20% or more. A true edge of a few
percent would likely fail. A fail is therefore weak evidence against a small edge, and a pass would have to be large.

## Schedule
- `python scripts/ev_rules_2026.py interim` writes docs/ev_rules_2026_report.md when Will asks. It is descriptive,
  with no verdict.
- `python scripts/ev_rules_2026.py confirm` runs once after week 18 is graded.

Code: `src/nflbet/props/market_ev.py` (`forward_rows`), hand-case tests in `tests/test_market_ev.py`. The code reproduces
the week 10 numbers (K 17-9, +4.97 units at the best price; Mo 32-36, -10.49) when pointed at week 10; week 10 is not
part of this test.

## What a result changes
A pass for K makes it a candidate rule for 2027, with its own pre-registration. Neither result adds a pick list or
changes the mix tracker (CLAUDE.md).
