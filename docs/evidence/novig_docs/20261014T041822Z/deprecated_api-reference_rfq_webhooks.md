> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Webhook Endpoints

> The /quote, /confirm, and /ping endpoints your pricer must implement

<Note>
  Webhooks are one of two ways to price RFQs. The [maker WebSocket](/deprecated/api-reference/rfq/websocket) carries the same rounds over
  one outbound connection, with no public endpoint to operate and no signature to verify.
</Note>

Your pricer exposes three endpoints under whatever base URL you register. Novig calls them; you respond. Every body is JSON and carries an `X-Novig-Signature` header. `/quote` and `/confirm` sit on the trade path and have hard timing requirements; `/ping` is an on-demand connectivity check (not on the trade path) but is still subject to a request timeout (currently 3 seconds).

## `POST {webhook_url}/quote`

Novig calls `/quote` for every parlay RFQ that names outcomes you might quote. You return a price and a maximum wager you're willing to back at that price.

### Request body

```json theme={"dark"}
{
    "rfq_id": "9b1d76e0-2fa9-0c1d-8e74-b3a5f6c218e0",
    "outcome_ids": ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"],
    "timestamp": "2026-04-29T18:42:11.123Z",
    "min_wager": "50.00"
}
```

| Field | Type | Notes |
| - | - | - |
| `rfq_id` | UUID string | Novig-issued RFQ identifier. Echoed back as `rfq_id` on `/confirm`. |
| `outcome_ids` | array of UUID strings | Novig outcome IDs in request order. One leg per ID. `GET /rfq/executions` returns them sorted by outcome ID. See [Outcome IDs](/deprecated/api-reference/outcome-ids). |
| `timestamp` | RFC3339 string | When Novig created the RFQ. |
| `min_wager` | string, optional | Minimum stake the taker wants covered. **Omitted entirely** when the taker didn't set one. A quote whose `max_wager` can't cover it (or the platform minimum of 10.00, whichever is higher) is never selected. |

Header: `X-Novig-Signature: BLAKE3(shared_secret, body).hex()` — see [Signing](/deprecated/api-reference/rfq/signing).

### Response body

```json theme={"dark"}
{
    "price": 0.45,
    "max_wager": "250.00",
    "quote_id": "pricer-quote-xyz"
}
```

| Field | Type | Notes |
| - | - | - |
| `price` | number, `(0, 1)` | Decimal probability you're quoting. `0.45` means `$0.45` stake per `$1.00` payout. <br /><br />Prices are resolved on a **0.001 grid** (`0.001`–`0.999`); more precision is rounded to the nearest tick. The standard order-book tick-size constraints **do not apply** to RFQ quotes. |
| `max_wager` | string | Maximum taker stake you're willing to accept on this quote, in Novig Cash. **JSON string** to preserve precision. |
| `quote_id` | string, optional | Your own ID for the quote. If supplied, Novig echoes it back as `external_flag` on `/confirm`. |

<Note>
  There is **no expiry field**. Quote validity is platform-owned: Novig anchors a TTL when the auction closes (currently 30
  seconds pregame, 10 seconds for live markets) — your quote simply lapses when it expires.
</Note>

### Hard rules

<Warning>
  **Novig's total budget for `/quote` fanout is 3 seconds.** A response that arrives later is silently dropped. The taker sees
  only the quotes that landed inside the window.
</Warning>

* Non-2xx responses are dropped.
* `max_wager <= 0` is dropped.
* Malformed/unparseable JSON is dropped.
* A bad signature is dropped.

In every drop case the taker simply doesn't see your quote — there is no penalty beyond losing the trade.

### Declining to quote

If you don't want to quote a particular RFQ, return **HTTP 204 No Content**. Any non-2xx also drops your quote, but a 204 records a deliberate pass, where an error or a timeout looks like a broken pricer.

## `POST {webhook_url}/confirm`

If your quote is selected as the winner, Novig calls `/confirm` with the actual taker wager (which may be ≤ your `max_wager`) immediately before writing the trade. This is your last chance to back out.

<Warning>
  **You have 1 second to answer.** The confirm window is a fixed 1-second last look: a pricer that hasn't responded by the bell
  is **rejected** (the trade does not execute). The window never closes early either — an early answer is held to the bell — so
  there is no advantage to racing, but a hard penalty for being slow.
</Warning>

### Request body

```json theme={"dark"}
{
    "rfq_id": "9b1d76e0-2fa9-0c1d-8e74-b3a5f6c218e0",
    "wager": "100.00",
    "price": "0.45",
    "external_flag": "pricer-quote-xyz"
}
```

| Field | Type | Notes |
| - | - | - |
| `rfq_id` | UUID string | Same `rfq_id` from the original `/quote`. |
| `wager` | string | Taker stake in Novig Cash. JSON string. Always `<= max_wager` you returned. |
| `price` | string | Price Novig selected — yours, since only the winning pricer is asked. JSON string. |
| `external_flag` | string, optional | The `quote_id` you returned on `/quote`. **Field is omitted entirely** when none was provided — don't expect a `null`. |

Header: same `X-Novig-Signature` scheme as `/quote`.

### Response body

```json theme={"dark"}
{ "confirmed": true }
```

| Field | Type | Notes |
| - | - | - |
| `confirmed` | boolean, **required** | `true` accepts the trade. `false` rejects — Novig writes nothing and the parlay is rejected. |

<Warning>A **missing `confirmed` field is a hard error** — it aborts the trade just like `false`. Always include it.</Warning>

## `POST {webhook_url}/ping`

A connectivity check you trigger yourself via [`POST /rfq/pricer/ping`](/deprecated/api-reference/rfq/registration). Novig sends a **signed** POST to `<webhook_url>/ping` and reports back how you answered — use it to confirm reachability and signature handling before any live quote flow. This endpoint is **not** on the trade path: it carries no quote content and has no latency budget.

### Request body

```json theme={"dark"}
{
    "pricer_id": "0193abcd-0000-7000-8000-000000000001",
    "timestamp": "2026-04-29T18:42:11.123Z"
}
```

| Field | Type | Notes |
| - | - | - |
| `pricer_id` | UUID string | Your pricer registration ID — the same value returned at registration. |
| `timestamp` | RFC3339 string | When Novig issued the ping. |

Header: same `X-Novig-Signature` scheme as `/quote` and `/confirm` — verify it exactly as you would on the trade path.

### Response

Return **any 2xx** status. There is no required body; Novig only reports whether the call reached you and what status you returned (as `ok`/`status` in the [ping result](/deprecated/api-reference/rfq/registration)). A non-2xx, a bad signature you rejected, or an unreachable host all surface as a failed ping so you can fix the wiring before going live.

## Type & encoding notes

* **Decimal numbers (`max_wager`, `wager`, `price` on `/confirm`) are JSON strings**, not numbers.
* **`price` on `/quote` response is a JSON number** in `(0, 1)` decimal probability.
* **UUIDs are lowercase strings** with hyphens.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.