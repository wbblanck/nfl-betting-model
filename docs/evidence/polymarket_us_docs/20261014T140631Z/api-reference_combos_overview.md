> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Combos API Overview

> Create and read combo instruments through the Retail API

A combo is a user-defined instrument containing 2–50 legs. Each leg identifies an existing market symbol and whether the combo buys or sells that leg. Once open, a combo trades through the normal [Orders API](/api-reference/orders/overview); an RFQ is optional and provides a price-discovery and paired order-submission workflow over the same order book.

All calls use normal [Retail API authentication](/api-reference/authentication) at:

```text theme={null}
https://api.polymarket.us
```

## Endpoints

| Method | Endpoint | Description |
| - | - | - |
| `POST` | `/v1/combos` | Create or retrieve the canonical combo for a set of legs |
| `GET` | `/v1/combos?symbol={symbol}` | Get a combo by exact symbol |

On the Retail API, Combo and RFQ creation share an additional [edge rate limit](/api-reference/rate-limits) of 10 requests per 10 seconds, enforced per API key and per IP.

Separately, combo creation has a participant-wide service quota of 1,000 new instruments per week across all accounts and both Retail and Institutional APIs. The quota resets Monday at 00:00 UTC; returning an existing canonical combo does not consume it.

## Create a Combo

`POST /v1/combos` accepts 2–50 unique legs:

```json theme={null}
{
  "legs": [
    {
      "symbol": "market-a",
      "side": "SIDE_BUY"
    },
    {
      "symbol": "market-b",
      "side": "SIDE_SELL"
    }
  ]
}
```

Leg symbols must be open, tradable, supported instruments. Duplicate symbols and invalid combinations are rejected. Treat the combo symbol as opaque: existing combos use `caoc-...` and new combos use `crossd-...`. Within one product, a canonical set of legs always maps to the same symbol, so creating an existing combo returns that instrument.

```json theme={null}
{
  "combo": {
    "id": "caoc-...",
    "legs": [
      {
        "symbol": "market-a",
        "side": "SIDE_BUY"
      },
      {
        "symbol": "market-b",
        "side": "SIDE_SELL"
      }
    ],
    "state": "INSTRUMENT_STATE_OPEN",
    "createdTime": "2026-07-29T14:00:00Z",
    "tickSize": 0.001
  }
}
```

## Get a Combo

`GET /v1/combos?symbol=caoc-...` requires the exact combo symbol. The response contains a `combos` array; an unknown symbol returns an empty array. This endpoint does not paginate.

## See Also

<CardGroup cols={2}>
  <Card title="RFQ API" icon="code" href="/api-reference/rfqs/overview">
    Create and manage combo RFQs and quotes
  </Card>

  <Card title="Authentication" icon="key" href="/api-reference/authentication">
    Sign Retail API requests
  </Card>

  <Card title="Private WebSocket" icon="bolt" href="/api-reference/websocket/private#rfq-subscriptions">
    Receive RFQ and quote lifecycle events
  </Card>
</CardGroup>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.