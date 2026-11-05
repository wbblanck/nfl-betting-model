# Game simulator: market calibration results

Pre-registration: docs/gamesim_calibration_preregistration.md (family of 2, each at 0.05 / 2).

## M1 props: fit on 2024 (9349 DraftKings props)
Group | n 2024 | intercept a | weight on DK b | weight on simulator c
receiving | 5486 | -0.0528 | +1.1492 | -0.0657
rushing | 2404 | -0.0605 | +1.1326 | +0.1562
passing | 1459 | -0.0434 | +1.2721 | -0.0358

## M1 test on 2025 (8960 props)
Log loss: mix 0.68873 | DK de-vigged 0.68987 | simulator alone 0.72679 | coin 0.69315
- **Mix minus DK:** -0.00114, interval -0.00179 to -0.00048: **BETTER**

By group | n | mix | DK
receiving | 5292 | 0.68738 | 0.68829
rushing | 2177 | 0.68899 | 0.69118
passing | 1491 | 0.69311 | 0.69353

Descriptive (not registered): DK-only refit 0.68894; mix minus DK-only refit -0.00021, interval -0.00073 to +0.00026

Calibration of the mix: band | n | said | hit
50%-55% | 6838 | 51.8% | 51.9%
55%-60% | 1644 | 57.1% | 58.3%
60%-70% | 478 | 62.2% | 60.9%
Descriptive: mix gives a side 55%+ on 2122 props: hit 58.9%, ROI at DK prices -0.3%

## M2 spreads: bet the simulator's side at the opener when |fair − open| ≥ 1.5
Sample | games | bets | weeks | covers | ROI | interval | avg CLV (pts toward bet)
2022-2024 (descriptive) | 767 | 484 | 51 | 53.8% | +2.6% | -8.2% to +13.4% | +1.03
2025 (test) | 242 | 174 | 16 | 53.4% | -0.8% | -16.1% to +11.9% | +0.84
2025 sensitivity: implausible opener prices dropped (not registered) | 229 | 161 | 16 | 53.4% | +1.4% | -13.7% to +15.3% | +0.44
- **M2 on 2025: FAIL** (needs 30+ bets in 10+ weeks and ROI interval above 0).

## Reading
- **M1 props: PASS.** The 2024-fitted mix beat DraftKings' de-vigged price on 2025 (log loss 0.68873 vs 0.68987).
  The first run gave 0.68871 with the same verdict; the 0.00002 difference comes from run-to-run ordering in the
  input frames.
- Most of the gain is not the simulator. The weights on DraftKings are above 1 and the intercepts are negative: on
  these props DraftKings' price was a little too timid and slightly favored overs. A refit with DraftKings alone
  (descriptive, not registered) gets 0.68894. The simulator's added part, mix minus DraftKings-only refit, is −0.00021
  with an interval of −0.00073 to +0.00026, not distinguishable from zero. Its weight is positive only for rushing
  (+0.156) and slightly negative for receiving and passing.
- Where the mix gives a side 55% or more (2,122 props), it hit 58.9% but returned −0.3% at DraftKings prices
  (descriptive), so there is no profit after the vig.
- **M2 spreads at the opener: FAIL.** 2025: 174 bets, 53.4% covers, ROI −0.8%, interval −16.1% to +11.9%. The bets
  did gain closing-line value (+0.84 points), consistent with T2, but not enough to clear the bar. 14 games in 2025
  carry implausible opener prices (for example −233 / +185 on a spread). Dropping them (not registered) gives ROI
  +1.4%, interval −13.7% to +15.3%: still a fail.
- Next per the pre-registration: M1 would be frozen and tracked forward on 2026 weeks 10-18. That needs a 2026
  DraftKings prop-line feed, because Action Network no longer serves them.
