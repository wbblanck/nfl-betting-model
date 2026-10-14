> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Markets

> Query market data, order books, and prices

The Markets resource provides access to market information, pricing, and order book data. Markets represent individual tradeable contracts within an event.

## Methods

| Method | Endpoint | Description |
| - | - | - |
| `list(params?)` | `GET /v1/markets` | List markets with filtering |
| `retrieve(id)` | `GET /v1/market/id/{id}` | Get market by ID |
| `retrieve_by_slug(slug)` | `GET /v1/market/slug/{slug}` | Get market by slug |
| `book(slug)` | `GET /v1/markets/{slug}/book` | Get full order book |
| `bbo(slug)` | `GET /v1/markets/{slug}/bbo` | Get best bid/offer |
| `settlement(slug)` | `GET /v1/markets/{slug}/settlement` | Get settlement price |

***

## list

Fetch a paginated list of markets with optional filters.

```python theme={null}
markets = client.markets.list({
    "limit": 20,
    "active": True,
    "categories": ["sports", "crypto"],
})

for market in markets["markets"]:
    print(f"{market['slug']}: {market['question']}")
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `limit` | int | Maximum results to return |
| `offset` | int | Pagination offset |
| `active` | bool | Filter by active trading status |
| `closed` | bool | Filter by closed status |
| `archived` | bool | Filter by archived status |
| `categories` | list\[str] | Filter by category slugs |
| `sportsMarketTypes` | list\[str] | Filter by sports market type (MONEYLINE, SPREAD, TOTAL, PROP) |
| `volumeNumMin` | float | Minimum trading volume |
| `liquidityNumMin` | float | Minimum liquidity |

### Response Fields

| Field | Type | Description |
| - | - | - |
| `id` | int | Unique market identifier |
| `slug` | str | URL-friendly identifier |
| `question` | str | Market question |
| `description` | str | Detailed description |
| `active` | bool | Whether market accepts orders |
| `lastTradePrice` | float | Most recent trade price |
| `bestBid` | float | Best bid price |
| `bestAsk` | float | Best ask price |
| `volume` | str | Total trading volume |
| `liquidity` | str | Current liquidity |

***

## retrieve\_by\_slug

Get a single market by its URL slug.

```python theme={null}
market = client.markets.retrieve_by_slug("btc-100k-2025")

print(f"Question: {market['question']}")
print(f"Status: {market['active']}")
print(f"Last Price: {market['lastTradePrice']}")
```

***

## book

Get the full order book with all bid and offer levels.

```python theme={null}
book = client.markets.book("btc-100k-2025")

print(f"State: {book['marketData']['state']}")
print(f"Bids: {len(book['marketData']['bids'])}")
print(f"Offers: {len(book['marketData']['offers'])}")

for bid in book["marketData"]["bids"][:5]:
    print(f"  ${bid['px']['value']} x {bid['qty']}")
```

### Response Fields

| Field | Type | Description |
| - | - | - |
| `marketSlug` | str | Market identifier |
| `bids` | list | Buy orders (highest price first) |
| `offers` | list | Sell orders (lowest price first) |
| `state` | str | Market state (OPEN, SUSPENDED, etc.) |
| `stats` | object | Market statistics |

***

## bbo

Get best bid/offer only. Use this lightweight endpoint when you only need top-of-book prices.

```python theme={null}
bbo = client.markets.bbo("btc-100k-2025")

data = bbo["marketData"]
print(f"Best Bid: ${data['bestBid']['value']}")
print(f"Best Ask: ${data['bestAsk']['value']}")
print(f"Last Trade: ${data['lastTradePx']['value']}")
```

### Response Fields

| Field | Type | Description |
| - | - | - |
| `bestBid` | Amount | Best (highest) bid price |
| `bestAsk` | Amount | Best (lowest) ask price |
| `lastTradePx` | Amount | Last trade price |
| `bidDepth` | int | Number of bid levels |
| `askDepth` | int | Number of ask levels |
| `openInterest` | str | Current open interest |

***

## settlement

Get the settlement price for a resolved market.

```python theme={null}
settlement = client.markets.settlement("btc-100k-2025")

print(f"Settlement: ${settlement['settlement']}")
```

Settlement values are typically `0.00` (No) or `1.00` (Yes).

<Tip>
  For real-time market data, use the [WebSocket](/api-reference/sdks/python/websocket) markets stream instead of polling.
</Tip>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.