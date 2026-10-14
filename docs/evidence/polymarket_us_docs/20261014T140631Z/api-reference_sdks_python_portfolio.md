> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Portfolio

> View positions and trading activity

<Note>Requires authentication.</Note>

The Portfolio resource provides access to your trading positions and activity history.

## Methods

| Method | Endpoint | Description |
| - | - | - |
| `positions(params?)` | `GET /v1/portfolio/positions` | Get trading positions |
| `activities(params?)` | `GET /v1/portfolio/activities` | Get activity history |

***

## positions

Get your current trading positions. Returns a map of market slug to position data.

```python theme={null}
positions = client.portfolio.positions()

for slug, pos in positions["positions"].items():
    meta = pos["marketMetadata"]
    print(f"{meta['title']}")
    print(f"  Net Position: {pos['netPositionDecimal']}")
    print(f"  Cost: ${pos['cost']['value']}")
    print(f"  Cash Value: ${pos['cashValue']['value']}")
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `cursor` | str | Pagination cursor |
| `limit` | int | Maximum results |

### Position Fields

| Field | Type | Description |
| - | - | - |
| `netPositionDecimal` | str | Net quantity in contracts (positive = long, negative = short) |
| `qtyBoughtDecimal` | str | Total quantity bought in contracts |
| `qtySoldDecimal` | str | Total quantity sold in contracts |
| `qtyAvailableDecimal` | str | Quantity available to trade in contracts |
| `netPosition` | str | Deprecated rounded quantity; use `netPositionDecimal` |
| `qtyBought` | str | Deprecated rounded quantity; use `qtyBoughtDecimal` |
| `qtySold` | str | Deprecated rounded quantity; use `qtySoldDecimal` |
| `cost` | Amount | Total cost basis |
| `realized` | Amount | Realized profit/loss |
| `cashValue` | Amount | Current unrealized value |
| `qtyAvailable` | str | Deprecated rounded quantity; use `qtyAvailableDecimal` |
| `expired` | bool | Whether position has expired |
| `marketMetadata` | object | Market information |

***

## activities

Get your trading activity history including trades, settlements, deposits, and withdrawals.

```python theme={null}
activities = client.portfolio.activities({"limit": 20})

for act in activities["activities"]:
    print(f"{act['type']}: {act.get('trade', act.get('accountBalanceChange', {}))}")
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `limit` | int | Maximum results |
| `cursor` | str | Pagination cursor |
| `types` | list\[str] | Filter by activity types |
| `marketSlug` | str | Filter by market |
| `sortOrder` | str | `SORT_ORDER_DESCENDING` (default) or `SORT_ORDER_ASCENDING` |

### Activity Types

| Type | Nested Field | Description |
| - | - | - |
| `ACTIVITY_TYPE_TRADE` | `trade` | Trade execution |
| `ACTIVITY_TYPE_POSITION_RESOLUTION` | `positionResolution` | Market settlement |
| `ACTIVITY_TYPE_ACCOUNT_DEPOSIT` | `accountBalanceChange` | Deposit |
| `ACTIVITY_TYPE_ACCOUNT_ADVANCED_DEPOSIT` | `accountBalanceChange` | Advance issued against a pending deposit |
| `ACTIVITY_TYPE_ACCOUNT_WITHDRAWAL` | `accountBalanceChange` | Withdrawal |
| `ACTIVITY_TYPE_TRANSFER` | `accountBalanceChange` | Internal transfer |
| `ACTIVITY_TYPE_REFERRAL_BONUS` | `accountBalanceChange` | Referral incentive credit |
| `ACTIVITY_TYPE_TAKER_FEE_REBATE` | `accountBalanceChange` | Taker fee rebate credit |
| `ACTIVITY_TYPE_LIQUIDITY_PROGRAM` | `accountBalanceChange` | Liquidity program payout |

### Trade Fields

| Field | Type | Description |
| - | - | - |
| `id` | str | Trade ID |
| `marketSlug` | str | Market slug |
| `price` | Amount | Trade price |
| `qtyDecimal` | str | Trade quantity in contracts |
| `qty` | str | Deprecated rounded quantity; use `qtyDecimal` |
| `isAggressor` | bool | True if taker |
| `realizedPnl` | Amount | Realized P\&L |

<Tip>
  For real-time position updates, use the [WebSocket](/api-reference/sdks/python/websocket) with `SUBSCRIPTION_TYPE_POSITION` instead of polling.
</Tip>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.