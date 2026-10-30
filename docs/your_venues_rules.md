# "Your venues" records: Rules (pre-registered 2026-10-30, before the first run that writes them)

Requested by Will (2026-10-30): the official trackers price at venues he does not use, so a label resting on a
DraftKings or Caesars number is no use to him. These records rerun the same rules with the best number restricted to
his venues. They sit beside the official records and change nothing in them: S1 stays graded at the DraftKings price
(docs/s1_live_rules.md), the ATS tracker stays on the five Action Network books (docs/ats_live_rules.md), and the
season-end tests in those documents are unchanged. Both new records are **descriptive and unvalidated**: no pass/fail
test is attached; their numbers are reported, not judged.

## Venues (Florida)
| Venue | Spreads (ATS) | Player props (S1) | Source |
|---|---|---|---|
| Hard Rock Bet (FL) | yes | yes | OddsPapi, bookmaker `hardrockbet` (secret ODDSPAPI_API_KEY) |
| Kalshi | yes | yes | spreads: OpenMarkets partner `Kalshi`; props: Kalshi read directly (as the best-price record) |
| Polymarket US | yes | yes | spreads: OpenMarkets partner `PolymarketUS` only (international `Polymarket` excluded); props: Polymarket US gateway |
| Novig | yes, where its catalog lists game spreads | yes | Novig public catalog (as the best-price record) |
| PrizePicks | no | standard lines only | ParlayAPI `prizepicks` |
| Underdog | no | yes | ParlayAPI `underdog` |
| Sleeper | no | yes | ParlayAPI `sleeper` |

A venue with no quote at a run is simply absent from that run. If a source cannot be read, the run records that and
goes on; it never falls back to a book outside this list.

## All-in cost per $1 of payout (the price used everywhere below)
- **Hard Rock:** implied probability of its American price (vig included).
- **Kalshi:** price p plus taker fee 0.07 × M × p × (1 − p), M = the series' fee multiplier where read, else 1.
- **Polymarket US:** price p plus taker fee 0.0695 × p × (1 − p).
- **Novig:** 1 − best resting price on the other outcome, plus its taker fee where charged (none pregame).
- **Exchanges need size:** a quote with less than $10 of payout at that price is listed but not eligible (as
  bestprice.MIN_SIZE). A quote whose size cannot be read stays eligible.
- **Pick'em, 2-pick Power** (what Will plays). A 2-pick entry paying X× wins only if both picks win; each pick is priced
  at the per-pick share 1/√X of the stake, so two picks at costs c1, c2 have positive expected value exactly when
  p1·p2 > c1·c2. Per pick:
  - PrizePicks: standard lines only, X = 3, cost 1/√3 = 0.5774. Goblin and demon lines are excluded (their payout is
    not published per pick).
  - Underdog: cost 1/(√3.5 × m), m = the pick's payout multiplier as ParlayAPI reports it (`selection_by_side`).
    The 3.5 base is what ParlayAPI's own per-pick decimals imply on 653 of 1,563 sides of the 2026-10-08 probe
    (docs/evidence/parlay/20261008T050251Z); a side whose reported decimal disagrees with √3.5 × m by more than
    0.02 is excluded and counted.
  - Sleeper: implied probability of the per-pick American price ParlayAPI reports.
  - Pick'em lines are ParlayAPI's national lines; Florida's apps may differ. That is a known gap, not corrected.

## ATS on your venues (one row per game per run, appended to data/live/ats_yv_runs_2026.csv)
- **Same inputs as the official tracker:** the frozen fair line, the rating's side against the consensus, the sharp
  reference (exchange median main spread), the QB gate, the key-number test, expected CLV = 0.235 × gap.
- **Best number, your venues:** among the quotes for the rating's side at Hard Rock, Kalshi, Polymarket US and Novig,
  every two-sided line counts (main and alternate), but only quotes whose all-in cost is at most 0.5455 (−120)
  are eligible, so an alternate line bought at a steep price cannot pose as a better number. Best = the eligible line
  most favorable to the side; ties go to the lower cost.
- **Labels:** the official rules applied to that number (Bet Now / Wait / Monitor / No Value). With no eligible quote
  the label is **No line at your venues**.
- **Official row** for a game: the last run before kickoff. **Grading:** CLV against the nflverse closing spread from
  the recorded number; ATS result at the recorded number and all-in cost (win pays 1/cost − 1 per unit; pushes
  refund). Reported by label, descriptively.

## S1 on your venues (one row per official S1 pick per run, appended to data/live/s1_yv_2026.csv)
- **Picks:** exactly the official S1 picks (player, market, side). No new picks, none dropped by price.
- **Price:** the lowest all-in cost among your venues at a line at least as good for the side as the pick's
  DraftKings line (under: line ≥ DK line; over: line ≤ DK line), exchanges subject to the size rule.
- With no eligible quote the pick is recorded as **No line at your venues** and is not graded in this record.
- **Grading:** at the venue's own line (it can differ from DK's) and the recorded cost: win pays 1/cost − 1 per unit,
  loss −1, push 0. Pick'em picks are graded per pick at their per-pick cost; real entries pair two picks, so this is
  the expected-value equivalent, not an entry ledger.

## Not in these rules
- No new label thresholds, no cover probabilities, no "playable down to" numbers: any of those would be a new rule
  needing its own pre-registration.
- Venue availability in Florida (Kalshi, Polymarket US and Novig are contested by the state; pick'em apps run
  peer-to-peer formats there) is Will's to judge; the records only report prices.
