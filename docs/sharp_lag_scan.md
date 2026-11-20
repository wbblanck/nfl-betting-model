# Sharp-lag scan: Pinnacle vs Novig (guide for any session)

Will asked on 2026-11-19 for a scan of "sharp line movement where Novig is slow to follow, 3%+ edge". This guide
fixes the method so every session runs it the same way. Script: `scripts/audit/sharp_lag_scan.py`.

**Status.** Descriptive snapshot only. It is not a tested edge and not one of the CLAUDE.md pick-list exceptions:
do not record, track, grade or put its output on the dashboard without a new exception from Will. Label every reply
"unvalidated, one-off snapshot". Do not commit its output CSVs to the repo. Attach them to the reply instead.

## 1. Data

| Source | What | Where |
| --- | --- | --- |
| Pinnacle | Prematch NFL board as recorded by the PinnRadar harvest: game lines with alternate ladders, team totals, player props | `data/pinnacle/radar/<job>/` (raw), `data/pinnacle/radar/tidy/` (change-only history; build with `python scripts/fetch/pinnradar_tidy.py`) |
| Novig | Live public catalog: every NFL market with each outcome's best resting bid and its size. Keyless, read-only. | `GET https://api.novig.com/v3/public/catalog/events` and `/markets` (`league=NFL`), via `nflbet.sources.venues.nv_get` |

The Pinnacle "now" state is the newest `full_*.json.gz` plus every later line of `prematch_deltas.jsonl.gz`. A delta
event replaces the stored event whole. Always report the Pinnacle time and the Novig time; they should be within
minutes of each other.

**After 2026-11-20 03:03 UTC the PinnRadar demo is over.** No harvest runs then, and the free key (100 calls a day)
belongs to the props CLV job (docs/props_clv_rules.md). A later scan needs Will's go-ahead to spend free calls, or a
new Pinnacle source. Without fresh Pinnacle data, say so and don't scan stale prices.

## 2. Matching (exact or nothing)

Only identical contracts are compared. Never interpolate between lines or move a price to a nearby line.
- **Moneyline:** Novig `MONEY` outcome team code against Pinnacle period `num_0` `money_line`.
- **Spread:** Novig `SPREAD` outcome `"DET -7.5"` against the Pinnacle `spreads` entry whose home handicap equals it
  (away team -x means home +x). Alternates count.
- **Total:** Novig `TOTAL` strike against the Pinnacle `totals` entry with the same points. Alternates count.
- **Team total:** Novig `TEAM_TOTAL` ("<full team name> <k> TEAM_TOTAL") against Pinnacle `team_totals.home|away` at the same points.
- **Player props:** Pinnacle special "<Player> Total <units>" against Novig "<Player> <k> <TYPE>" with the same strike,
  matched on `nflbet.sources.ids.norm_name`. Units map: Receptions→RECEPTIONS, Receiving Yards→RECEIVING_YARDS,
  Rushing Yards→RUSHING_YARDS, Rush Attempts→RUSHING_ATTEMPTS, Passing Yards→PASSING_YARDS,
  Pass Attempts→PASSING_ATTEMPTS, Pass Completions→PASSING_COMPLETIONS, Touchdown Passes→PASSING_TOUCHDOWNS,
  Interceptions→INTERCEPTIONS_THROWN, Touchdowns 0.5 (anytime TD)→TOUCHDOWNS 0.5. Ignore Novig `*_PROTECTED` markets.
- Full game only (`num_0`), pregame only (Novig event `OPEN_PREGAME`, market `OPEN`), two-outcome markets only.

## 3. Prices

- **Novig cost** to take a side = 1 − best resting bid on the other outcome (dollars per $1 of payout). Depth = that
  bid's quantity / 100, in dollars of payout. Add `venues.nv_fee` (zero pregame: NFL fees are charged `WHEN_LIVE`).
- **Pinnacle fair probability**, de-vigged two ways from the side's and the other side's decimal prices:
  proportional `p = (1/a) / (1/a + 1/b)`, and power: find `k` with `(1/a)^k + (1/b)^k = 1`, then `p = (1/a)^k`.
- **Edge** = fair / Novig cost − 1, computed under each method.

## 4. What qualifies

All three must hold:
1. Edge ≥ 3% under **both** de-vig methods. Longshots (big moneyline dogs, rarely-scoring anytime TDs) often pass
   proportional and fail power. That means their "edge" is a modeling choice, not a price gap.
2. Novig depth ≥ $50.
3. Exact match per section 2.

## 5. Direction of the Pinnacle move

Move = Pinnacle proportional fair % for that side now, minus at its first recorded quote of the same contract (from
the tidy tables), in percentage points. Label it **toward** (≥ +0.3 pp), **away** (≤ −0.3 pp) or **flat**. "Sharp move
that Novig lags" in Will's sense means **toward** plus a qualifying edge. Report how many rows meet that separately
from the rest, and say how long the recording window is. Moves before the first recording are unseen, and a line
that moved (e.g. 59.5 to 60.5) starts a new contract with no history.

## 6. Output

Run `PYTHONPATH=src python scripts/audit/sharp_lag_scan.py --out <scratch dir>`. Reply with:
- One opening sentence: how many qualify, and how many of those have Pinnacle moving toward the side.
- The script's table: Market | Game | Side | Pinnacle (American) | Pinnacle fair (power) | Novig (American) |
  Edge (lower of the two methods) | Novig depth | Pinnacle move.
- The method in one line: matched sides count, times of both snapshots.
- The caveats in section 7 that apply. Attach the full CSV.

## 6b. Line shopping (`--shop`)

`--shop --week <NFL week> --parlay <ParlayAPI snapshot>` prices each Pinnacle player prop at every venue the repo
reads, at the exact line, and takes the cheapest eligible price:
- **Novig:** as above.
- **Kalshi:** ask + fee M x 0.07 x p(1-p), with the ask's size (`venues.ks_quotes`). "N+" is the over at N − 0.5.
- **Polymarket US:** quoted price + 0.0695 x p(1-p) (`venues.pm_quotes`). There is no size without a book call, so
  it stays eligible unsized, as in `props/bestprice.py`.
- **DraftKings / FanDuel:** implied probability of the American price, vig included, from the newest
  `data/live/parlay/*.json.gz` on main. ParlayAPI costs quota (1,000 requests a month), so never fetch it just for
  this scan.

Exchange prices need $50+ behind them. Game lines are priced at Novig only: no other venue the repo reads carries
NFL spreads, totals or moneylines yet. Report each source's time. **A book price older than the Pinnacle quote it is
compared with is not a lag finding.** When Pinnacle moved after the book snapshot (check the tidy history), say the
book row is stale and needs a fresh look before anyone acts on it.

**Outlier filter (`--min-gap 0.05`).** Will's bestbook.app shows how much better the best price pays than the
next-best (decimal payout ratio − 1). Will asked on 2026-11-20 for 5%+ better than the next best and 3%+ edge.
Pinnacle counts as a venue for "next best". We read fewer venues than bestbook, so our gaps can run larger.

## 7. Caveats to state

- Pinnacle props carry about 6.5-7% hold and max stakes of $250-2,000. A 3-5% gap is the size of that vig's
  uncertainty. Outside work (drburke-droid/NFL) found Pinnacle prop closes no sharper than DK/FanDuel.
- Pinnacle main game lines (5-20k limits, ~3-4% hold) are the sharper reference; gaps there mean more.
- In one snapshot (2026-10-21, docs/novig_compare.md) Novig prop sides cost a mean 1.52 cents more than DK's and
  0.23 cents more than FanDuel's, with median $200 at the best price. Thin books can jump between snapshots.
- Not tested, not tracked. No ROI or win-rate claim is possible from one snapshot.

## Validation (2026-11-19)

The de-vig functions give 0.5 on equal prices. Power gives the favourite more than proportional does
(1.5/2.7: 0.651 vs 0.643). The first run (Pinnacle 23:54 UTC, Novig 23:56 UTC) matched 1,312 sides and found 19
qualifying, 1 of them with Pinnacle moving toward the side (Titans team total Under 22.5). It reproduced the
hand-built scan posted in the thread.
