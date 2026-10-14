> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# RFQ API Overview

> Manage combo RFQs and quotes and query RFQ trades

An RFQ requests two-sided liquidity for the exact symbol of a [combo instrument](/api-reference/combos/overview). All calls use normal [Retail API authentication](/api-reference/authentication) at `https://api.polymarket.us`.

The Retail API derives the participant and account from the API key; clients do not send an account.

## Endpoints

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v1/rfqs/user-id` | Get your pseudonymous RFQ user ID |
| `GET` | `/v1/rfqs` | Query visible RFQs |
| `GET` | `/v1/rfqs/trades` | Query anonymous RFQ-originated fills |
| `POST` | `/v1/rfqs` | Create an RFQ |
| `DELETE` | `/v1/rfqs/{rfqId}` | Close your open RFQ |
| `GET` | `/v1/rfqs/quotes` | Query visible quotes |
| `POST` | `/v1/rfqs/quotes` | Create or replace your quote |
| `DELETE` | `/v1/rfqs/{rfqId}/quotes/{quoteId}` | Delete your quote |
| `PUT` | `/v1/rfqs/{rfqId}/quotes/{quoteId}/accept` | Accept one side of a quote |
| `PUT` | `/v1/rfqs/{rfqId}/quotes/{quoteId}/confirm` | Confirm an accepted quote during last look |

See [rate limits](/api-reference/rate-limits#limits) for endpoint limits. RFQ-specific business limits and participant restrictions are enforced separately by the RFQ service.

For `GET /v1/rfqs/quotes`, provide an `rfqId` or exactly one of `userFilter=USER_FILTER_SELF` and `rfqUserFilter=USER_FILTER_SELF`. Cursors are opaque and must be reused with the same filters and authenticated participant.

## RFQ Trade History

`GET /v1/rfqs/trades` returns anonymous fills where either order originated from an RFQ, including single instruments, combos, and later fills on resting orders. All participants see the same trades. Prints contain no participant, account, order, RFQ, or quote IDs.

| Parameter | Description |
| - | - |
| `limit` | Page size, from 1 to 100. Omitted or `0` means 100. |
| `cursor` | Opaque continuation from the previous response. URL-encode it as a query value. |
| `startTime` | Inclusive RFC 3339 execution time. Defaults to the start of available feed coverage. |
| `endTime` | Exclusive RFC 3339 execution time. Defaults to the time the first request was received. |
| `symbol` | Exact, case-sensitive instrument symbol. Omit for all symbols. |

For example, `GET /v1/rfqs/trades?limit=100&symbol=caoc-example` can return:

```json theme={null}
{
  "trades": [
    {
      "tradeId": "trade-example",
      "symbol": "caoc-example",
      "price": "0.1234",
      "qtyDecimal": "12.3456",
      "aggressorSide": "SIDE_BUY",
      "executedTime": "2026-10-01T12:34:56.123456789Z"
    }
  ],
  "cursor": "opaque-continuation"
}
```

Prices and quantities are decimal strings. `aggressorSide` is the incoming order's side (`SIDE_BUY` or `SIDE_SELL`). Results are ordered by execution time descending, then trade ID descending.

### Pagination and Recovery

Repeat the same authenticated participant, filters, and limit on every continuation, changing only `cursor`. Keep omitted time bounds omitted; the cursor preserves them. Continue until the response cursor is empty, even if a page contains no trades.

On startup or reconnect, subscribe to the [RFQ WebSocket](/api-reference/websocket/private#rfq-subscriptions) first, then query overlapping history and deduplicate by `tradeId`. History is eventually visible and pagination is not a snapshot. Repeat overlapping queries to find late arrivals.

These are original prints: later corrections and busts do not amend them. Use your order and account data for reconciliation.

Invalid queries or cursors return HTTP `400`. Requests before available coverage also return `400`; unavailable history or a feed coverage gap returns `503`.

## Replace a quote

Every successful `POST /v1/rfqs/quotes` returns a new `quoteId`, including replacements. Send the same `rfqId` with new prices. Use the returned ID to delete the new quote; use `quoteAccepted.quote.id` to confirm or decline an accepted quote.

`quoteDeleted` identifies a canceled old quote; `quoteCreated` carries the new ID. Check `GET /v1/rfqs/quotes` if an older quote's state is unclear.

## RFQ price tick

`tickSize` is the instrument's minimum price increment in dollars. It appears on RFQs returned by `GET /v1/rfqs` and in `rfqCreated` and `rfqClosed` WebSocket events.

Quote prices must be multiples of `tickSize` and within the instrument's price limits. For example, `"0.1234"` is aligned to a `0.0001` tick but not a `0.001` tick.

If `tickSize` is absent, read it from `GET /v1/combos?symbol=<rfq.symbol>`.

## Real-time stream

RFQ and quote lifecycle events and anonymous `rfqTrade` prints are available on the [Private WebSocket](/api-reference/websocket/private#rfq-subscriptions). Subscribe with `SUBSCRIPTION_TYPE_RFQ`.

For missed events, follow [Pagination and Recovery](#pagination-and-recovery). Reconcile RFQ and quote state with `GET /v1/rfqs` and `GET /v1/rfqs/quotes`.

## Execution

`QUOTE_STATUS_EXECUTED` and `quoteExecuted` mean the paired exchange orders were submitted and their order IDs were recorded. They do not mean the orders filled.

Use `SUBSCRIPTION_TYPE_RFQ` for the RFQ lifecycle and anonymous trade prints, and `SUBSCRIPTION_TYPE_ORDER` for your own fills, rejections, cancellations, and expirations. Correlate your orders using `creatorOrderId` for the maker and `rfqCreatorOrderId` for the requester; both IDs are also returned by `GET /v1/rfqs/quotes`. Anonymous prints cannot be linked to your order IDs.

RFQ orders enter the normal combo order book and may trade with other resting liquidity. Combo instruments can also be traded directly through the [Orders API](/api-reference/orders/overview); using an RFQ is optional. If either `restRemainder` setting is true, unfilled quantity on that side may remain on the book.

## See Also

<CardGroup cols={2}>
  <Card title="Combos API" icon="shuffle" href="/api-reference/combos/overview">
    Create and read combo instruments
  </Card>

  <Card title="Private WebSocket" icon="bolt" href="/api-reference/websocket/private#rfq-subscriptions">
    Receive RFQ lifecycle events and anonymous trade prints
  </Card>

  <Card title="Authentication" icon="key" href="/api-reference/authentication">
    Sign Retail API requests
  </Card>
</CardGroup>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.