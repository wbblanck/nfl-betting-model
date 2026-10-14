> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Private Updates Channel

> Receive private fill and cancel notifications

### Channel Name

**Channel:** `private` (Automatically subscribed when authenticated)

<Note>
  The private channel is automatically available when you connect with a valid Bearer token. You do not need to explicitly
  subscribe.
</Note>

### Event Types

The private channel broadcasts three types of events, each wrapped in the standard `{ "event": ..., "data": ... }` envelope:

* **place** - Your order has been accepted onto the book
* **fill** - Your order has been filled (partially or completely)
* **cancel** - Your order has been explicitly cancelled

### Place Events

Sent when your order is placed. Same `data` shape as cancel events (your order, unobfuscated):

```json theme={"dark"}
{
    "event": "place",
    "data": {
        "id": "123e4567-e89b-12d3-a456-426614174002",
        "outcomeId": "123e4567-e89b-12d3-a456-426614174000",
        "marketId": "123e4567-e89b-12d3-a456-426614174003",
        "price": 0.667,
        "qty": 110,
        "originalQty": 110,
        "currency": "COIN",
        "timestamp": "2023-10-05T12:00:00Z",
        "status": "OPEN",
        "flags": "ABC12345"
    }
}
```

### Fill Events

Sent when your order is matched with another order on the book.

#### Message Format

```json theme={"dark"}
{
    "event": "fill",
    "data": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "orderId": "123e4567-e89b-12d3-a456-426614174001",
        "price": 0.667,
        "qty": 50,
        "createdAt": "2023-10-05T12:00:00Z",
        "isWash": false,
        "isTaker": true,
        "marketId": "123e4567-e89b-12d3-a456-426614174002",
        "outcomeId": "123e4567-e89b-12d3-a456-426614174003"
    }
}
```

#### Fill Fields

| Field | Type | Description |
| - | - | - |
| `id` | string | UUID of the fill |
| `orderId` | string | UUID of your order that was filled |
| `price` | number | Execution price in decimal probability (0-1) |
| `qty` | number | Quantity filled in Minimum Currency Units |
| `createdAt` | string | ISO 8601 timestamp of the fill |
| `isWash` | boolean | Whether this was a wash trade |
| `isTaker` | boolean | Whether you were the taker (true) or maker (false) |
| `marketId` | string | UUID of the market |
| `outcomeId` | string | UUID of the outcome |

<Note>
  Real-time `fill` events carry only the fields above. `outcomeStatus`, `fee`, and `transactions` — the
  outcome's grading status, the fee charged to you, and the ledger rows debiting your wallet for the fill — are populated
  only on the fill history at `GET /nbx/v2/emm/fills/all`. Fetch the fill by `id` there when you need them.
</Note>

### Cancel Events

Sent when your order is **explicitly cancelled**. This includes:

* **User-initiated cancellations** via API requests
* **GTT (Good-Til-Time) order expirations**

<Warning>
  **Implicit cancellations** (e.g., when a market closes) do **not** send individual cancel messages. Use the [Market Lifecycle
  Channel](/deprecated/api-reference/WSS/lifecycle-channel) to handle market close events.
</Warning>

#### Message Format

```json theme={"dark"}
{
    "event": "cancel",
    "data": {
        "id": "123e4567-e89b-12d3-a456-426614174002",
        "outcomeId": "123e4567-e89b-12d3-a456-426614174000",
        "marketId": "123e4567-e89b-12d3-a456-426614174003",
        "price": 0.667,
        "qty": 60,
        "originalQty": 110,
        "currency": "COIN",
        "timestamp": "2023-10-05T12:00:00Z",
        "status": "CANCELLED",
        "flags": "ABC12345"
    }
}
```

#### Cancel Fields

| Field | Type | Description |
| - | - | - |
| `id` | string | UUID of the cancelled order |
| `outcomeId` | string | UUID of the outcome |
| `marketId` | string | UUID of the market |
| `price` | number | Order price in decimal probability |
| `qty` | number | Remaining quantity when cancelled |
| `originalQty` | number | Original order quantity |
| `currency` | string | CASH or COIN |
| `timestamp` | string | ISO 8601 timestamp of cancellation |
| `status` | string | Order status (CANCELLED) |
| `flags` | string | Custom 8-character metadata (if set) |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.