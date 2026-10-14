> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Account

> View account balances and buying power

<Note>Requires authentication.</Note>

The Account resource provides access to your account balances and financial information.

## Methods

| Method | Endpoint | Description |
| - | - | - |
| `balances()` | `GET /v1/account/balances` | Get account balances |

***

## balances

Retrieve your current account balances, buying power, and pending withdrawals.

```python theme={null}
balances = client.account.balances()

print(f"Current Balance: ${balances['currentBalance']}")
print(f"Buying Power: ${balances['buyingPower']}")
print(f"Open Orders: ${balances['openOrders']}")
```

### Response Fields

| Field | Type | Description |
| - | - | - |
| `currentBalance` | float | Current fiat currency balance |
| `currency` | str | Currency code (e.g., "USD") |
| `buyingPower` | float | Capital available for trading |
| `assetNotional` | float | Total notional value of positions |
| `assetAvailable` | float | Available collateral value |
| `openOrders` | float | Value tied up in open orders |
| `unsettledFunds` | float | Unsettled funds not yet available |
| `marginRequirement` | float | Required margin for positions |
| `pendingWithdrawals` | list | Active withdrawal requests |

### Buying Power

The `buyingPower` field represents unencumbered capital available for trading:

```
buyingPower = currentBalance + assetAvailable - openOrders - marginRequirement
```

<Tip>
  For real-time balance updates, use the [WebSocket](/api-reference/sdks/python/websocket) with `SUBSCRIPTION_TYPE_ACCOUNT_BALANCE` instead of polling.
</Tip>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.