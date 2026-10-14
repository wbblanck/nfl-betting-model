> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Quickstart

> Get started with the Python SDK

## Installation

```bash theme={null}
pip install polymarket-us
```

Requires Python 3.10+.

[GitHub](https://github.com/Polymarket/polymarket-us-python) · [PyPI](https://pypi.org/project/polymarket-us/)

***

## Configuration

```python theme={null}
import os
from polymarket_us import PolymarketUS

client = PolymarketUS(
    key_id=os.environ["POLYMARKET_KEY_ID"],
    secret_key=os.environ["POLYMARKET_SECRET_KEY"],
    timeout=30.0,  # optional, default 30s
)
```

Generate API keys at [polymarket.us/developer](https://polymarket.us/developer).

***

## Public Endpoints

No authentication required for market data:

```python theme={null}
from polymarket_us import PolymarketUS

client = PolymarketUS()

# Events
events = client.events.list({"limit": 10, "active": True})
event = client.events.retrieve_by_slug("super-bowl-2025")

# Markets
markets = client.markets.list({"limit": 10})
market = client.markets.retrieve_by_slug("btc-100k")
book = client.markets.book("btc-100k")
bbo = client.markets.bbo("btc-100k")

# Search
results = client.search.query({"query": "bitcoin"})

# Series and Sports
series = client.series.list()
sports = client.sports.list()

client.close()
```

***

## Authenticated Endpoints

Trading requires API credentials:

```python theme={null}
import os
from polymarket_us import PolymarketUS

client = PolymarketUS(
    key_id=os.environ["POLYMARKET_KEY_ID"],
    secret_key=os.environ["POLYMARKET_SECRET_KEY"],
)

# Account
balances = client.account.balances()

# Portfolio
positions = client.portfolio.positions()
activities = client.portfolio.activities()

# Orders
open_orders = client.orders.list()
order = client.orders.create({
    "marketSlug": "your-market-slug",
    "intent": "ORDER_INTENT_BUY_LONG",
    "type": "ORDER_TYPE_LIMIT",
    "price": {"value": "0.555", "currency": "USD"},
    "quantity": 0.5,
    "tif": "TIME_IN_FORCE_GOOD_TILL_CANCEL",
})

client.close()
```

***

## Async Usage

```python theme={null}
import asyncio
from polymarket_us import AsyncPolymarketUS

async def main():
    async with AsyncPolymarketUS(
        key_id="your-key-id",
        secret_key="your-secret-key",
    ) as client:
        # Concurrent requests
        events, markets = await asyncio.gather(
            client.events.list({"limit": 10}),
            client.markets.list({"limit": 10}),
        )
        print(f"Found {len(events['events'])} events")

asyncio.run(main())
```

***

## Error Handling

```python theme={null}
from polymarket_us import (
    PolymarketUS,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
)

client = PolymarketUS(key_id="...", secret_key="...")

try:
    order = client.orders.create({"marketSlug": "..."})
except AuthenticationError as e:
    print(f"Invalid credentials: {e.message}")
except BadRequestError as e:
    print(f"Invalid parameters: {e.message}")
except RateLimitError as e:
    print(f"Rate limited: {e.message}")
except NotFoundError as e:
    print(f"Not found: {e.message}")
except APITimeoutError:
    print("Request timed out")
except APIConnectionError as e:
    print(f"Connection error: {e.message}")
```

### Error Types

| Exception | Description |
| - | - |
| `AuthenticationError` | Invalid or missing credentials |
| `BadRequestError` | Invalid request parameters |
| `NotFoundError` | Resource not found |
| `RateLimitError` | Rate limit exceeded |
| `APITimeoutError` | Request timed out |
| `APIConnectionError` | Network connection error |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.