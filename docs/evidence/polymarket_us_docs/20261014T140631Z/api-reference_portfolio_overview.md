> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Portfolio API Overview

> View positions, balances, and trading activity

# Portfolio API

The Portfolio API provides access to user positions, account balances, and trading activity history.

<Warning>
  **Authentication Required**

  All Portfolio API endpoints require API key authentication. See the [Authentication guide](/api/authentication) for details on signing requests.
</Warning>

## Base URL

```
https://api.polymarket.us
```

## Endpoints

### Positions

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v1/portfolio/positions` | Get user's trading positions |

### Activities

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v1/portfolio/activities` | Get trading activity history |

### Account

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v1/account/balances` | Get account balances |

## Positions Response

The positions response returns a **map of market slug to position**, not an array:

```json theme={null}
{
  "positions": {
    "will-x-happen": {
      "netPosition": "20",
      "netPositionDecimal": "19.6000",
      "qtyBought": "20",
      "qtyBoughtDecimal": "19.6000",
      "qtySold": "0",
      "qtySoldDecimal": "0.0000",
      ...
    },
    "another-market": {
      "netPosition": "-50",
      ...
    }
  },
  "nextCursor": "abc123",
  "eof": false
}
```

### Position Fields

| Field | Type | Description |
| - | - | - |
| `netPositionDecimal` | string (decimal) | Net position quantity in contracts (positive = long, negative = short) |
| `qtyBoughtDecimal` | string (decimal) | Total quantity bought in contracts |
| `qtySoldDecimal` | string (decimal) | Total quantity sold in contracts |
| `qtyAvailableDecimal` | string (decimal) | Quantity available to trade in contracts |
| `bodPositionDecimal` | string (decimal) | Beginning of day position in contracts |
| `netPosition` | string (int64) | Deprecated rounded quantity; use `netPositionDecimal` |
| `qtyBought` | string (int64) | Deprecated rounded quantity; use `qtyBoughtDecimal` |
| `qtySold` | string (int64) | Deprecated rounded quantity; use `qtySoldDecimal` |
| `cost` | Amount | Total cost basis |
| `realized` | Amount | Realized profit/loss |
| `cashValue` | Amount | Current unrealized value |
| `qtyAvailable` | string (int64) | Deprecated rounded quantity; use `qtyAvailableDecimal` |
| `bodPosition` | string (int64) | Deprecated rounded quantity; use `bodPositionDecimal` |
| `expired` | boolean | Whether the position has expired |
| `updateTime` | string (date-time) | Last update timestamp |
| `marketMetadata` | object | Market information (slug, title, outcome) |

Use the `*Decimal` quantity fields for display and calculations. The older integer fields remain for backward compatibility and should not be used for partial-contract markets.

## Activities Response

Activities are returned as an array with pagination:

```json theme={null}
{
  "activities": [
    {
      "type": "ACTIVITY_TYPE_TRADE",
      "trade": { ... }
    }
  ],
  "nextCursor": "xyz789",
  "eof": false
}
```

### Activity Structure

Each activity has a `type` field and a corresponding nested object:

| Type | Nested Field | Description |
| - | - | - |
| `ACTIVITY_TYPE_TRADE` | `trade` | Trade execution details |
| `ACTIVITY_TYPE_POSITION_RESOLUTION` | `positionResolution` | Market settlement details |
| `ACTIVITY_TYPE_ACCOUNT_DEPOSIT` | `accountBalanceChange` | Deposit details |
| `ACTIVITY_TYPE_ACCOUNT_ADVANCED_DEPOSIT` | `accountBalanceChange` | Advance issued against a pending deposit |
| `ACTIVITY_TYPE_ACCOUNT_WITHDRAWAL` | `accountBalanceChange` | Withdrawal details |
| `ACTIVITY_TYPE_TRANSFER` | `accountBalanceChange` | Transfer details |
| `ACTIVITY_TYPE_REFERRAL_BONUS` | `accountBalanceChange` | Referral incentive credit |
| `ACTIVITY_TYPE_TAKER_FEE_REBATE` | `accountBalanceChange` | Taker fee rebate credit |
| `ACTIVITY_TYPE_LIQUIDITY_PROGRAM` | `accountBalanceChange` | Liquidity program payout |

### Trade Object

| Field | Type | Description |
| - | - | - |
| `id` | string | Exchange-assigned trade ID |
| `marketSlug` | string | Market slug |
| `state` | string | Trade state; see [Trade States](#trade-states) |
| `price` | Amount | Trade price |
| `qtyDecimal` | string (decimal) | Trade quantity in contracts |
| `qty` | string | Deprecated rounded quantity; use `qtyDecimal` |
| `isAggressor` | boolean | True if user's order was the taker |
| `costBasis` | Amount | Cost basis for the trade |
| `realizedPnl` | Amount | Realized profit/loss |
| `createTime` | string (date-time) | Creation timestamp |
| `updateTime` | string (date-time) | Last update timestamp |

### Trade States

The `state` field on a trade progresses through the following values:

| State | Value | Description |
| - | - | - |
| `TRADE_STATE_NEW` | 1 | Trade created. |
| `TRADE_STATE_CLEARED` | 2 | Trade successfully cleared by the clearing house. |
| `TRADE_STATE_BUSTED` | 3 | The trade was voided post-execution by the exchange (an error trade) and the resulting position was rolled back. This is a terminal reversal, **not** a pending state. |
| `TRADE_STATE_INFLIGHT` | 4 | Trade information sent to the clearinghouse. |
| `TRADE_STATE_PENDING_RISK` | 5 | Clearinghouse is pending at least one DCM claim for the trade. |
| `TRADE_STATE_PENDING_CLEARED` | 6 | Clearinghouse is pending the counterparty DCM claim. |
| `TRADE_STATE_REJECTED` | 7 | Clearinghouse rejected the trade. |
| `TRADE_STATE_CLEARING_ACKNOWLEDGED` | 8 | Clearing request acknowledged by the clearing house. |
| `TRADE_STATE_RETRY_REQUEST` | 9 | Retry requested; pending resubmission to the clearing house. |

<Warning>
  **Handling `TRADE_STATE_BUSTED`**

  A busted trade was executed and then voided by the exchange (via an error-trade
  bust), and its position impact was reversed. Busted trades remain visible in trade
  history — treat them as reversed for position, P\&L, and reconciliation purposes.
  Do not silently drop them.
</Warning>

<Note>
  `TRADE_STATE_UNDEFINED` (value `0`) is the unset/unknown sentinel. It is omitted
  from API responses and does not appear in the published enum lists. Treat any
  unrecognized state value defensively rather than assuming the values above are
  exhaustive.
</Note>

### Position Resolution Object

| Field | Type | Description |
| - | - | - |
| `marketSlug` | string | Market slug |
| `beforePosition` | UserPosition | Position before resolution |
| `afterPosition` | UserPosition | Position after resolution |
| `side` | string | Resolution side (LONG, SHORT, NEUTRAL) |
| `tradeId` | string | Associated trade ID |
| `updateTime` | string (date-time) | Resolution timestamp |

### Account Balance Change Object

| Field | Type | Description |
| - | - | - |
| `transactionId` | string | Transaction ID |
| `status` | string | Status (PENDING, COMPLETED, REJECTED) |
| `amount` | Amount | Amount of the balance change |
| `createTime` | string (date-time) | Creation timestamp |
| `updateTime` | string (date-time) | Last update timestamp |

## Pagination

Both endpoints support cursor-based pagination. Use `cursor` parameter with the `nextCursor` value to fetch the next page. When `eof` is `true`, there are no more results.

<Tip>
  **Real-Time Position Updates**

  For real-time position changes, use the [WebSocket Private Stream](/api-reference/websocket/private) with the `SUBSCRIPTION_TYPE_POSITION` subscription instead of polling.
</Tip>

## Filtering Activities

Filter activities by type and market:

```bash theme={null}
GET /v1/portfolio/activities?types=ACTIVITY_TYPE_TRADE&marketSlug=will-x-happen
```

## Sort Order

Activities can be sorted ascending or descending by time:

| Sort Order | Description |
| - | - |
| `SORT_ORDER_DESCENDING` | Newest first (default) |
| `SORT_ORDER_ASCENDING` | Oldest first |

## Account Balances

The account balances endpoint returns current balance information:

```json theme={null}
{
  "balances": [
    {
      "currentBalance": 1000.00,
      "currency": "USD",
      "buyingPower": 850.00,
      "assetNotional": 500.00,
      "assetAvailable": 250.00,
      "openOrders": 400.00,
      "unsettledFunds": 0,
      "marginRequirement": 0,
      "lastUpdated": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Balance Fields

| Field | Description |
| - | - |
| `currentBalance` | Current fiat currency balance |
| `currency` | Currency code (e.g., USD) |
| `buyingPower` | Capital available for trading |
| `assetNotional` | Total notional value of securities |
| `assetAvailable` | Available collateral value |
| `pendingCredit` | Pending credit amounts |
| `openOrders` | Value tied up in open orders |
| `unsettledFunds` | Unsettled funds not yet available |
| `marginRequirement` | Required margin for positions |

### Buying Power

The `buyingPower` field represents unencumbered capital available for trading:

```
buyingPower = currentBalance
            + assetAvailable
            - openOrders
            - marginRequirement
```

<Tip>
  **Real-Time Balance Updates**

  For real-time balance changes, use the [WebSocket Private Stream](/api-reference/websocket/private) with the `SUBSCRIPTION_TYPE_ACCOUNT_BALANCE` subscription instead of polling.
</Tip>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.