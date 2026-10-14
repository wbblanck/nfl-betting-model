> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Execution Feed & Reconciliation

> Watch RFQ executions live and reconcile the ones you won

The webhook endpoints are how Novig calls **you**. The two endpoints on this page are the reverse — **you call Novig** to observe executions: a live WebSocket tape of every execution platform-wide, and a REST listing of the RFQs **you** won. Together they let you track fills in real time and reconcile anything you missed.

<Note>
  These endpoints are an observability layer, not part of the trade path. Nothing here affects pricing, selection, or settlement
  — they exist so you can monitor and reconcile your RFQ activity.
</Note>

<Info>
  **Looking for RFQ fills?** They're here, not on [Get all my fills](/deprecated/api-reference/positions/get-all-my-fills). That endpoint
  (`GET /nbx/v2/emm/fills/all`) covers single contract fills — the contracts you filled by resting or taking on `/nbx/v2`. RFQs
  you quoted and won are a separate surface and are listed only by `GET /rfq/executions` below.
</Info>

## Authentication

Both endpoints use the same OAuth 2.0 Client Credentials token as the rest of the API — see [Authentication](/deprecated/api-reference/authentication). Send it as a bearer token:

```bash theme={"dark"}
Authorization: Bearer YOUR_ACCESS_TOKEN
```

<Warning>
  You must be an LP **with a registered pricer**. The token identifies your LP trader, and that trader must own a live pricer
  registration (see [Registration](/deprecated/api-reference/rfq/registration)).
</Warning>

| Environment | Base URL |
| - | - |
| Production | `https://api.novig.com` |
| QA | `https://api-qa.novig.us` |

## `GET /rfq/executions` — your executed RFQs

Returns the RFQs **you** priced and won, most recent first. Use it to reconcile fills and to backfill anything you missed on the live feed.

```bash theme={"dark"}
curl https://api.novig.com/rfq/executions \
  --header "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Query parameters

Both are optional — omit them and you get the 500 most recent executions.

| Parameter | Type | Default | Notes |
| - | - | - | - |
| `limit` | integer | `500` | Executions per page. **May not exceed 500** — a larger value returns `400 Bad Request`. |
| `offset` | integer | `0` | Number of executions to skip, counting back from the most recent. **May not exceed 50,000** — a larger value returns `400 Bad Request`. |

<Warning>
  This `offset` is a **row count, not a sequence number**. It is unrelated to the feed's `data.offset` below — passing a feed
  offset here will skip to an arbitrary point in your history. To backfill a feed gap, page from the newest execution until you
  reach `rfq_id`s you've already recorded.
</Warning>

Walk your history by holding `limit` fixed and advancing `offset` until a page comes back short (fewer than `limit` items),
comes back empty, or `offset` reaches 50,000:

```bash theme={"dark"}
curl "https://api.novig.com/rfq/executions?limit=100&offset=200" \
  --header "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

<Note>
  Pages are ordered by `executed_at` descending, with `rfq_id` descending as a tiebreak, so executions sharing a timestamp can't
  straddle a page boundary or repeat across one.
</Note>

<Warning>
  Paging is offset-based over a live listing. A new execution landing mid-walk shifts every later row one position deeper, which
  can re-show a row you already read. Deduplicate on `rfq_id` as you page — and for large backfills, page from newest to oldest
  in one pass rather than re-walking.
</Warning>

### Response

`200 OK` with a JSON array, ordered by `executed_at` descending:

```json theme={"dark"}
[
    {
        "rfq_id": "0193abcd-0000-7000-8000-000000000001",
        "wager": "100.00",
        "price": "0.42",
        "outcome_ids": ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"],
        "executed_at": "2026-06-16T22:13:20Z"
    }
]
```

| Field | Type | Notes |
| - | - | - |
| `rfq_id` | UUID string | The executed RFQ. |
| `wager` | string | Taker stake that filled, in Novig Cash. JSON string to preserve precision. |
| `price` | string | The price you quoted and won at. JSON string. |
| `outcome_ids` | array of UUID strings | The parlay legs, sorted by outcome ID. The `rfq_created` event lists the same legs in request order. **Only the REST listing carries these** — the live feed omits them (derive from `rfq_id` there). |
| `executed_at` | RFC3339 string | Immutable execution time, in UTC. Matches the feed's value for the same `rfq_id`. |

<Note>
  A single page is capped at **500** executions, and `offset` is capped at **50,000**, so paging reaches your most recent
  50,500 executions. For open exposure, call `GET /rfq/collateral` instead of walking history. An empty array (`[]`)
  means either you've paged past the end or you haven't won any RFQs yet.
</Note>

## `GET /rfq/executions/feed` — live execution tape

A WebSocket broadcast of **every** successful RFQ execution, platform-wide — not just yours.

```
wss://api.novig.com/rfq/executions/feed
```

Open it with the same bearer token in the `Authorization` header on the upgrade request. The same LP-with-pricer gate applies before the socket upgrades.

<Warning>
  The feed is **anonymous** — it never reveals which LP won. It's a market-wide print tape, not a per-LP fill stream. To see
  only your own fills, use `GET /rfq/executions`.
</Warning>

### Message shape

One text frame per execution:

```json theme={"dark"}
{
    "event": "rfq_executed",
    "data": {
        "offset": 12345,
        "rfq_id": "0193abcd-0000-7000-8000-000000000001",
        "wager": "50",
        "price": "0.5",
        "executed_at": "2026-06-16T22:13:20Z"
    }
}
```

| Field | Type | Notes |
| - | - | - |
| `event` | string | The print kind. Currently always `"rfq_executed"`; the envelope is forward-compatible for future kinds, so branch on this value. |
| `data.offset` | integer | Monotonically increasing sequence number. Use it for **gap detection** — see below. |
| `data.rfq_id` | UUID string | The executed RFQ. `outcome_ids` are **not** on the feed; derive them from `rfq_id` or the REST listing. |
| `data.wager` | string | Taker stake. JSON string. |
| `data.price` | string | Execution price. JSON string. |
| `data.executed_at` | RFC3339 string | Execution time, UTC. |

### Connection behavior

<Steps>
  <Step title="No replay on connect">
    You receive only executions that happen **after** you connect. The feed is live market data, not a replayable log. Connect
    first, then act — anything that printed before you connected is gone from the socket (use the REST listing to catch up).
  </Step>

  <Step title="Heartbeat every 15s">
    The server sends a WebSocket **Ping** every 15 seconds to keep the connection alive through the load balancer's 30-second
    idle timeout. Standard WebSocket clients auto-respond with a Pong; you don't need to send anything.
  </Step>

  <Step title="Detect gaps with offset">
    `offset` increases by one per print. If it jumps (e.g. `41 → 44` after a lag or disconnect), you missed prints. Backfill
    the gap from `GET /rfq/executions` — page from the newest execution until you reach `rfq_id`s you already hold, rather
    than passing this sequence number as the listing's `offset` parameter — then resume consuming the live feed.
  </Step>
</Steps>

<Note>
  Implement reconnection with exponential backoff. On every (re)connect, compare the first `offset` you see against the last one
  you processed and backfill via REST if there's a gap.
</Note>

## How the two fit together

| Use case | Endpoint |
| - | - |
| React to executions in real time | `GET /rfq/executions/feed` |
| Reconcile / backfill your own fills | `GET /rfq/executions` |
| Walk history past the most recent 500 | `GET /rfq/executions?limit=…&offset=…` |
| Get the parlay legs (`outcome_ids`) | `GET /rfq/executions` (the feed omits them) |
| Reconcile **single contract** fills instead | `GET /nbx/v2/emm/fills/all` (not RFQs) |

The typical pattern: hold the WebSocket open for live prints, and periodically (or after any `offset` gap) call the REST listing to confirm you've recorded every RFQ you won.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.