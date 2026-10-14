> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Exchange Data

## Overview

Two anonymized CSVs for every trading day, published at
[data.novig.com](https://data.novig.com). **Trades** records every executed
trade; **Markets** snapshots every market. Static files behind a CDN — no API,
no authentication.

| Path | Contents |
| - | - |
| `/reporting/trade-data/index.json` | Which dates each file below is available for |
| `/reporting/trade-data/<date>/trades.csv` | Every executed trade that date (midnight–midnight Eastern) |
| `/reporting/trade-data/<date>/markets.csv` | Every market that date: open interest, volume, OHLC |

Each day publishes shortly after midnight Eastern. A day that fails validation
is withheld rather than published incomplete.

The manifest lists each file's dates separately, because the two publish
independently — a day whose trades are withheld still gets its market snapshot:

```json index.json theme={"dark"}
{
  "dates": ["2026-08-06", "2026-08-07"],
  "marketDates": ["2026-08-06", "2026-08-07"]
}
```

`dates` is **Trades**. `marketDates` is **Markets**, and is absent on manifests
published before that file existed — read it as an empty list.

## Trades

### Rows are sides, not trades

Every trade appears once per side: one `TAKER` row — the order or quote request
that executed the trade — plus a `MAKER` row for each counterparty.

```csv trades.csv theme={"dark"}
timestamp,outcomeId,marketId,contractSeries,league,marketType,tradeType,legs,cost,qty,side
2026-08-04T17:03:11Z,0b1c…,7f2e…,Basketball Moneyline,NBA,MONEY,STRAIGHT,1,45.5,100,TAKER
2026-08-04T17:03:11Z,44d9…,7f2e…,Basketball Moneyline,NBA,MONEY,STRAIGHT,1,54.5,100,MAKER
2026-08-04T18:41:52Z,9d8c…,9d8c…,Parlay,,,COMBO,3,50,200,TAKER
2026-08-04T18:41:52Z,9d8c…,9d8c…,Parlay,,,COMBO,3,150,200,MAKER
```

<Tip>
  **Working with the data:**

  * **Count trades** — count `TAKER` rows
  * **Price one side paid** — `cost / qty`, a probability between 0 and 1
  * **Total amount staked** — sum `cost` over all rows
  * **Notional volume in dollars** — sum `qty` over `TAKER` rows
</Tip>

### Columns

<ResponseField name="timestamp" type="timestamp">
  Execution time, ISO-8601 (UTC).
</ResponseField>

<ResponseField name="outcomeId" type="string">
  Outcome that traded. For a `COMBO`, the contract the combination cleared
  against — unique to that trade, so it cannot group two trades of the same
  legs.
</ResponseField>

<ResponseField name="marketId" type="string">
  Market of the trade. For a `COMBO`, the same value as `outcomeId`.
</ResponseField>

<ResponseField name="contractSeries" type="string">
  Product group: a sport and a family, e.g. `Basketball Moneyline`. Multi-leg
  trades read `Parlay`; an unrecognized sport or family reads `Other`. Group by
  this column to total volume per product.
</ResponseField>

<ResponseField name="league" type="string">
  League the contract is listed under, e.g. `NBA`. Empty for a `COMBO`.
</ResponseField>

<ResponseField name="marketType" type="string">
  Market type the contract is listed under, e.g. `MONEY`. Empty for a `COMBO`.
</ResponseField>

<ResponseField name="tradeType" type="STRAIGHT | COMBO">
  `STRAIGHT` is a single-outcome trade matched on the order book. `COMBO` is a
  trade on a combination of outcomes, filled against a requested quote.
</ResponseField>

<ResponseField name="legs" type="integer">
  Outcomes the contract combines. Every `STRAIGHT` trade has `1`.
</ResponseField>

<ResponseField name="cost" type="string">
  Dollars this side staked. The two sides of a trade together stake its
  notional value.
</ResponseField>

<ResponseField name="qty" type="string">
  Quantity in contracts, where one contract pays \$1. May carry a fraction.
</ResponseField>

<ResponseField name="side" type="TAKER | MAKER">
  Which side of the trade this row reports.
</ResponseField>

<Note>
  `cost` and `qty` are strings carrying full numeric precision, with no
  trailing zeros. **Fees are not included** in `cost` on either side.
</Note>

## Markets

`markets.csv` carries one row per market per day, whether or not it traded.
Most markets on any given day have no activity and report zeros — the file is a
census of what was listed, not of what moved.

<Note>
  **A combination appears on the day it executes, and only that day.** A
  combination trades once and never changes afterwards, so republishing it each
  day would repeat one trade indefinitely. Its `reportTicker` is `COMBO`, and
  because it has a single trade its `open`, `high`, `low` and `close` are all
  that one price, and its `openInterest` equals its `dailyVolume`.

  Order-book markets appear every day they are listed, traded or not, up to and
  including the day they settle. After that they do not appear again — a settled
  market can no longer change, so there is nothing further to report.
</Note>

```csv markets.csv theme={"dark"}
date,marketId,reportTicker,openInterest,dailyVolume,open,high,low,close,status
2026-08-09,019fddfe…,ATP-FIRST_SET_MONEYLINE,0.00,420.73,50.5,54.5,50.5,51.0,finalized
2026-08-09,019fe4ad…,COMBO,0.00,85.91,20.0,20.0,20.0,20.0,finalized
2026-08-09,019fcbf2…,MLB-AL_CENTRAL_DIVISION_WINNER,9.25,0.00,,,,,active
```

### Columns

<ResponseField name="date" type="string">
  Trading day the row describes, `YYYY-MM-DD`, midnight–midnight Eastern.
</ResponseField>

<ResponseField name="marketId" type="string">
  Market the row describes. The same identifier as `marketId` in `trades.csv`,
  so the two files join on it.
</ResponseField>

<ResponseField name="reportTicker" type="string">
  Product family the market belongs to — a sport and a bet type, e.g.
  `MLB-SPREAD`. Every combination reads `COMBO`. Group by this column to total
  open interest or volume per product.
</ResponseField>

<ResponseField name="openInterest" type="string">
  Contracts outstanding at the close of the day, cumulative across every day the
  market has traded — not just this one. A holder with offsetting positions on
  both sides is counted only for the difference, and each contract is counted
  once rather than once per side. A market reports `0.00` on the day it settles,
  which is its last appearance.
</ResponseField>

<ResponseField name="dailyVolume" type="string">
  Contracts traded during this day alone. A market can carry open interest with
  no volume, meaning it traded on an earlier day and those positions are still
  open.
</ResponseField>

<ResponseField name="open" type="string">
  First price traded during the day, in cents to one decimal, `0.0`–`100.0`.
  Empty if the market did not trade that day, which is not the same as having
  traded at zero. Never carried forward from an earlier session.
</ResponseField>

<ResponseField name="high" type="string">
  Highest price traded during the day, in cents. Empty on a day with no trades.
</ResponseField>

<ResponseField name="low" type="string">
  Lowest price traded during the day, in cents. Empty on a day with no trades.
</ResponseField>

<ResponseField name="close" type="string">
  Last price traded during the day, in cents. Empty on a day with no trades.
</ResponseField>

<ResponseField name="status" type="active | closed | determined | finalized">
  `active` accepts orders. `closed` has stopped trading and awaits a result.
  `determined` has a known result not yet paid out. `finalized` has settled.
</ResponseField>

<Note>
  `openInterest` and `dailyVolume` are in contracts, where one contract pays
  \$1, with two decimal places. Prices are in cents with one, because fills do
  not land on whole-cent ticks — a `close` of `47.5` is a probability of 0.475.
</Note>

## Anonymity & Stability

Rows identify no trader, wallet, or order, and `COMBO` contract identifiers are
unique per trade by construction, so positions cannot be linked across trades.

Columns may be added over time — read the header row rather than assuming
positions. Files for past dates are immutable once published, except for
announced corrections, which republish the affected date in place.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.