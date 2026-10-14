> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Orders

> Create, cancel, and manage orders

<Note>Requires authentication.</Note>

The Orders resource provides order entry and management capabilities for trading on markets.

## Methods

| Method | Endpoint | Description |
| - | - | - |
| `create(params)` | `POST /v1/orders` | Create a new order |
| `list(params?)` | `GET /v1/orders/open` | Get open orders |
| `retrieve(order_id)` | `GET /v1/order/{orderId}` | Get order by ID |
| `cancel(order_id, params)` | `POST /v1/order/{orderId}/cancel` | Cancel an order |
| `modify(order_id, params)` | `POST /v1/order/{orderId}/modify` | Modify an order |
| `cancel_all(params?)` | `POST /v1/orders/open/cancel` | Cancel all open orders |
| `preview(params)` | `POST /v1/order/preview` | Preview order before submission |
| `close_position(params)` | `POST /v1/order/close-position` | Close an existing position |

***

## create

Create a new order on a market.

```python theme={null}
order = client.orders.create({
    "marketSlug": "btc-100k-2025",
    "intent": "ORDER_INTENT_BUY_LONG",
    "type": "ORDER_TYPE_LIMIT",
    "price": {"value": "0.555", "currency": "USD"},
    "quantity": 0.5,
    "tif": "TIME_IN_FORCE_GOOD_TILL_CANCEL",
})

print(f"Order ID: {order['id']}")
print(f"State: {order['state']}")
```

### Parameters

| Parameter | Type | Required | Description |
| - | - | - | - |
| `marketSlug` | str | Yes | Market to trade |
| `intent` | str | Yes | Order intent (see below) |
| `type` | str | Yes | `ORDER_TYPE_LIMIT` or `ORDER_TYPE_MARKET` |
| `price` | Amount | Limit only | Limit price |
| `quantity` | float | Yes | Number of contracts. Can be decimal when the market `minimumTradeQty` is less than 1. |
| `tif` | str | Yes | Time in force (see below) |

### Order Intent

| Value | Description |
| - | - |
| `ORDER_INTENT_BUY_LONG` | Buy YES contracts |
| `ORDER_INTENT_SELL_LONG` | Sell YES contracts |
| `ORDER_INTENT_BUY_SHORT` | Buy NO contracts |
| `ORDER_INTENT_SELL_SHORT` | Sell NO contracts |

### Time in Force

| Value | Description |
| - | - |
| `TIME_IN_FORCE_GOOD_TILL_CANCEL` | Remains active until filled or canceled |
| `TIME_IN_FORCE_GOOD_TILL_DATE` | Expires at specified time |
| `TIME_IN_FORCE_IMMEDIATE_OR_CANCEL` | Fill immediately available quantity, cancel rest |
| `TIME_IN_FORCE_FILL_OR_KILL` | Fill entirely or cancel completely |

***

## list

Get all open orders.

```python theme={null}
orders = client.orders.list()

for order in orders["orders"]:
    print(f"{order['id']}: {order['marketSlug']} - {order['state']}")
```

***

## cancel

Cancel a specific order.

```python theme={null}
client.orders.cancel("order-id-123", {
    "marketSlug": "btc-100k-2025"
})
```

***

## cancel\_all

Cancel all open orders, optionally filtered by market.

```python theme={null}
result = client.orders.cancel_all()
print(f"Canceled: {result['canceledOrderIds']}")

# Or cancel for a specific market
result = client.orders.cancel_all({"marketSlug": "btc-100k-2025"})
```

***

## preview

Preview an order before submitting. Returns estimated fills and costs.

```python theme={null}
preview = client.orders.preview({
    "marketSlug": "your-market-slug",
    "intent": "ORDER_INTENT_BUY_LONG",
    "type": "ORDER_TYPE_LIMIT",
    "price": {"value": "0.555", "currency": "USD"},
    "quantity": 0.5,
})

print(f"Estimated Cost: ${preview['estimatedCost']}")
```

***

## close\_position

Close an existing position at market price. This sells your entire position in a single call.

```python theme={null}
result = client.orders.close_position({
    "marketSlug": "btc-100k-2025",
})
```

### close\_position vs Sell Order

| | `close_position` | Sell Order (`create`) |
| - | - | - |
| **Position size** | Entire position | Any quantity |
| **Order type** | Market only | Limit or market |
| **Use case** | Quick full exit | Partial sells, limit prices |

Use `close_position` when you want to fully exit a position at market price. Use a sell order (`ORDER_INTENT_SELL_LONG` or `ORDER_INTENT_SELL_SHORT`) when you need to sell a specific quantity or set a limit price.

### Slippage Tolerance

For market orders and close position, you can specify slippage tolerance:

```python theme={null}
result = client.orders.close_position({
    "marketSlug": "btc-100k-2025",
    "slippageTolerance": {
        "currentPrice": {"value": "0.50", "currency": "USD"},
        "ticks": 5
    }
})
```

***

## Order States

Orders progress through these states:

| State | Description |
| - | - |
| `ORDER_STATE_PENDING_NEW` | Received, not yet processed |
| `ORDER_STATE_PARTIALLY_FILLED` | Partially executed |
| `ORDER_STATE_FILLED` | Fully executed |
| `ORDER_STATE_CANCELED` | Canceled |
| `ORDER_STATE_REJECTED` | Rejected by exchange |
| `ORDER_STATE_EXPIRED` | Expired (GTD orders) |

<Tip>
  For real-time order updates, use the [WebSocket](/api-reference/sdks/python/websocket) with `SUBSCRIPTION_TYPE_ORDER` instead of polling.
</Tip>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.