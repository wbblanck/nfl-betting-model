> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Maker WebSocket

> Receive RFQs and answer them over a single persistent socket

export const feature_0 = "The maker WebSocket"

export const production_0 = "Connecting on Production returns 404 until we enable it there."

<Warning>
  **Preview.** {feature_0} is available on **QA** only. {production_0} Contact Novig to start testing.
</Warning>

The maker WebSocket is the second way to price RFQs. You hold one connection open, Novig pushes each quote round to you, and you answer on the same socket. It replaces the inbound HTTP server that the [webhook transport](/deprecated/api-reference/rfq/webhooks) requires.

Pick it when you want to price without operating a public endpoint. You need no TLS certificate, no public hostname, and no signature verification. The connection authenticates once, at connect.

The trade path is unchanged: a **3-second** auction, a **1-second** last look, and a rejected trade when the last look goes unanswered.

## Connect

| Environment | URL | Status |
| - | - | - |
| QA | `wss://api-qa.novig.us/rfq/ws` | Available. Test here. |
| Production | `wss://api.novig.com/rfq/ws` | Not yet enabled. Returns `404` today. |

Send your OAuth 2.0 access token as a bearer token on the upgrade request. It is the same token the REST API uses. See [Authentication](/deprecated/api-reference/authentication).

```bash theme={"dark"}
Authorization: Bearer YOUR_ACCESS_TOKEN
```

The token identifies your LP trader, so the socket carries no pricer ID and no signature.

### Register a pricer first

The handshake refuses the upgrade when your trader has no pricer registration. Register once with an **empty body**: a socket pricer needs no webhook and gets no shared secret. Your registration outlives every connection, so reconnecting does not re-register.

Register on **QA** while the socket is in preview. See [Registration](/deprecated/api-reference/rfq/registration).

### Handshake failures

Authentication fails **before** the upgrade, as a plain HTTP status code.

| Status | Cause | Retry |
| - | - | - |
| `403` | The token is not an LP token, or you have no live pricer registration. | No. Fix the registration. |
| `404` | The maker socket is not enabled in this environment. | No. Ask Novig to enable it. |
| `500` | Novig could not read your registration. | Yes, with backoff. |

<Note>
  `price`, `max_wager`, and `wager` are **JSON strings** in both directions. This differs from the webhook `/quote` response,
  where `price` is a JSON number.
</Note>

## Channels

Subscriptions are per-connection. A reconnect carries none of them.

| Channel | Delivered to | Carries |
| - | - | - |
| `rfq` | Every pricer | `rfq_created`, `rfq_closed`, `rfq_executed` |
| `quotes` | You only | `quote_created`, `quote_accepted`, `quote_executed`, `quote_dropped` |

<Warning>
  Subscribe to **both** channels to trade. `rfq` delivers the rounds you price; `quotes` delivers the `quote_accepted` last
  look you must answer. A maker subscribed only to `rfq` never hears that it won, and every trade it wins is rejected.
</Warning>

## Round lifecycle

<Steps>
  <Step title="Novig opens a round">
    `rfq_created` arrives on the `rfq` channel with the legs, the wager floor, and the deadline.
  </Step>

  <Step title="You answer">
    Send `create_quote` with your price and maximum wager, or `decline` to pass. Answer before `expires_at`.
  </Step>

  <Step title="Novig closes the auction">
    `rfq_closed` arrives. Stop pricing that round.
  </Step>

  <Step title="You win, and confirm">
    `quote_accepted` arrives on the `quotes` channel. Answer with `confirm` inside **1 second**.
  </Step>
</Steps>

## <Icon icon="circle-arrow-up" color="#28b1ff" /> Client messages

Messages you send to Novig. Novig acks every one.

<div className="ws-msg ws-send">
  <AccordionGroup>
    <Accordion title="`subscribe`" icon="circle-arrow-up" description="Start receiving a channel's events">
      The `data` is a bare channel string, not an object. Acked with `subscribed`.

      ```json theme={"dark"}
      { "event": "subscribe", "data": "rfq" }
      ```

      <ParamField body="data" type="string" required>
        `"rfq"` or `"quotes"`.
      </ParamField>
    </Accordion>

    <Accordion title="`unsubscribe`" icon="circle-arrow-up" description="Stop receiving a channel's events">
      Acked with `unsubscribed`.

      ```json theme={"dark"}
      { "event": "unsubscribe", "data": "quotes" }
      ```

      <ParamField body="data" type="string" required>
        `"rfq"` or `"quotes"`.
      </ParamField>
    </Accordion>

    <Accordion title="`create_quote`" icon="circle-arrow-up" description="Answer an open round">
      Acked with `quote_submitted`.

      ```json theme={"dark"}
      {
          "event": "create_quote",
          "data": {
              "rfq_id": "0193abcd-0000-7000-8000-000000000001",
              "price": "0.45",
              "max_wager": "250",
              "quote_id": "mm-1"
          }
      }
      ```

      <ParamField body="rfq_id" type="UUID string" required>
        The round, from `rfq_created`.
      </ParamField>

      <ParamField body="price" type="decimal string" required>
        Decimal probability in `(0, 1)`. `"0.45"` means `$0.45` stake per `$1.00` payout. Resolved on a 0.001 grid.
      </ParamField>

      <ParamField body="max_wager" type="decimal string" required>
        Largest taker stake this quote covers, in Novig Cash. Must be positive.
      </ParamField>

      <ParamField body="quote_id" type="string">
        **Your own** reference, at most 256 characters. Returned to you as `external_flag`. Omit it when you don't need one.
      </ParamField>

      <Warning>
        **One quote per round.** Your first quote stands. A second quote for the same `rfq_id` is dropped and acked with
        `quote_superseded`. To change a price, wait for the next round.
      </Warning>
    </Accordion>

    <Accordion title="`decline`" icon="circle-arrow-up" description="Pass on an open round">
      Acked with `quote_declined`.

      ```json theme={"dark"}
      { "event": "decline", "data": { "rfq_id": "0193abcd-0000-7000-8000-000000000001" } }
      ```

      <ParamField body="rfq_id" type="UUID string" required>
        The round, from `rfq_created`.
      </ParamField>

      Decline every round you do not quote. A decline records that you saw the round and passed; silence is indistinguishable from a pricer that is down or lagging.
    </Accordion>

    <Accordion title="`confirm`" icon="circle-arrow-up" description="Answer the last look on your accepted quote">
      Acked with `confirm_recorded`.

      ```json theme={"dark"}
      {
          "event": "confirm",
          "data": {
              "rfq_id": "0193abcd-0000-7000-8000-000000000001",
              "quote_id": "0193abcd-0000-7000-8000-00000000000a",
              "confirmed": true
          }
      }
      ```

      <ParamField body="rfq_id" type="UUID string" required>
        From `quote_accepted`.
      </ParamField>

      <ParamField body="quote_id" type="UUID string" required>
        From `quote_accepted`. Novig's UUID, not your `external_flag`.
      </ParamField>

      <ParamField body="confirmed" type="boolean" required>
        `true` fills the trade at your quoted price. `false` rejects it.
      </ParamField>

      <Warning>
        **You have 1 second, and the last look fails closed.** A confirm that misses the window rejects the trade, exactly as
        `false` does. A dropped connection between `quote_accepted` and your answer also rejects the trade.
      </Warning>

      The first answer wins. A second answer returns `CONFIRM_ALREADY_DECIDED`, or `NO_CONFIRM_WINDOW` once the window is gone.
    </Accordion>
  </AccordionGroup>
</div>

## <Icon icon="circle-arrow-down" color="#16a34a" /> Server events

Events Novig sends you. Subscribe to a channel to receive its events.

Every frame Novig sends carries `timestamp`: when Novig emitted it. An instant that means anything else is a named field inside `data` — `expires_at` is when the auction closes, `executed_at` is when the trade filled.

<div className="ws-msg ws-recv">
  <AccordionGroup>
    <Accordion title="`rfq_created`" icon="circle-arrow-down" description="A round opened (rfq channel)">
      Price it before `expires_at`.

      ```json theme={"dark"}
      {
          "event": "rfq_created",
          "data": {
              "rfq_id": "0193abcd-0000-7000-8000-000000000001",
              "outcome_ids": ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"],
              "expires_at": "2026-01-01T00:00:03Z",
              "min_wager": "15"
          },
          "timestamp": "2026-01-01T00:00:00.123Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"rfq_created"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round. Name it on every message you send about this round.
      </ResponseField>

      <ResponseField name="data.outcome_ids" type="array of UUID strings" required>
        The legs, in request order. `GET /rfq/executions` returns the same legs sorted by outcome ID. See [Outcome IDs](/deprecated/api-reference/outcome-ids).
      </ResponseField>

      <ResponseField name="data.expires_at" type="ISO-8601 string" required>
        When the auction closes, 3 seconds after Novig created the round.
      </ResponseField>

      <ResponseField name="data.min_wager" type="decimal string" required>
        The round's wager floor: the taker's minimum or the venue minimum of `10.00`, whichever is higher. A quote whose
        `max_wager` cannot cover it is dropped as `below_min_wager`.
      </ResponseField>
    </Accordion>

    <Accordion title="`rfq_closed`" icon="circle-arrow-down" description="The auction closed (rfq channel)">
      Stop pricing the round. A `create_quote` that arrives after this is rejected with `RFQ_CLOSED`.

      ```json theme={"dark"}
      {
          "event": "rfq_closed",
          "data": {
              "rfq_id": "0193abcd-0000-7000-8000-000000000001"
          },
          "timestamp": "2026-01-01T00:00:03.001Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"rfq_closed"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round that closed.
      </ResponseField>
    </Accordion>

    <Accordion title="`rfq_executed`" icon="circle-arrow-down" description="A trade filled, with no counterparty named (rfq channel)">
      Every pricer sees this print, so it carries no identity.

      ```json theme={"dark"}
      {
          "event": "rfq_executed",
          "data": {
              "rfq_id": "0193abcd-0000-7000-8000-000000000001",
              "wager": "50",
              "price": "0.5",
              "executed_at": "2023-11-14T22:13:20Z"
          },
          "timestamp": "2023-11-14T22:13:20.050Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"rfq_executed"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round.
      </ResponseField>

      <ResponseField name="data.wager" type="decimal string" required>
        Amount staked.
      </ResponseField>

      <ResponseField name="data.price" type="decimal string" required>
        Execution price.
      </ResponseField>

      <ResponseField name="data.executed_at" type="ISO-8601 string" required>
        When the trade filled.
      </ResponseField>
    </Accordion>

    <Accordion title="`quote_created`" icon="circle-arrow-down" description="Your quote was recorded (quotes channel)">
      Novig recorded your quote at auction close.

      ```json theme={"dark"}
      {
          "event": "quote_created",
          "data": {
              "quote_id": "0193abcd-0000-7000-8000-00000000000a",
              "rfq_id": "0193abcd-0000-7000-8000-000000000001",
              "pricer_trader_id": "0193abcd-0000-7000-8000-0000000000ff"
          },
          "timestamp": "2026-01-01T00:00:03.001Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"quote_created"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.quote_id" type="UUID string" required>
        Novig's identifier for your quote.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round.
      </ResponseField>

      <ResponseField name="data.pricer_trader_id" type="UUID string" required>
        Your pricer.
      </ResponseField>
    </Accordion>

    <Accordion title="`quote_accepted`" icon="circle-arrow-down" description="You won. Confirm within 1 second (quotes channel)">
      The taker is executing against your quote.

      ```json theme={"dark"}
      {
          "event": "quote_accepted",
          "data": {
              "quote_id": "0193abcd-0000-7000-8000-00000000000a",
              "rfq_id": "0193abcd-0000-7000-8000-000000000001",
              "pricer_trader_id": "0193abcd-0000-7000-8000-0000000000ff",
              "wager": "50",
              "price": "0.55",
              "external_flag": "mm-1"
          },
          "timestamp": "2026-01-01T00:00:05.250Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"quote_accepted"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.quote_id" type="UUID string" required>
        **Novig's** identifier for your quote. Send this back on `confirm`.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round.
      </ResponseField>

      <ResponseField name="data.pricer_trader_id" type="UUID string" required>
        Your pricer.
      </ResponseField>

      <ResponseField name="data.wager" type="decimal string" required>
        The taker's stake. Always at or below the `max_wager` you quoted.
      </ResponseField>

      <ResponseField name="data.price" type="decimal string" required>
        The price you quoted.
      </ResponseField>

      <ResponseField name="data.external_flag" type="string or null" required>
        The `quote_id` **you** sent on `create_quote`. `null` when you sent none.
      </ResponseField>

      <Warning>
        **Two different fields are named `quote_id`.** The one you send on `create_quote` is your own free-form string; it returns
        to you as `external_flag`. The one on `quote_accepted` is a Novig UUID, and it is the one `confirm` requires.
      </Warning>
    </Accordion>

    <Accordion title="`quote_executed`" icon="circle-arrow-down" description="Your quote filled (quotes channel)">
      Carries the pricer identity the public print omits.

      ```json theme={"dark"}
      {
          "event": "quote_executed",
          "data": {
              "quote_id": "0193abcd-0000-7000-8000-00000000000a",
              "rfq_id": "0193abcd-0000-7000-8000-000000000001",
              "pricer_trader_id": "0193abcd-0000-7000-8000-0000000000ff",
              "wager": "50",
              "price": "0.55",
              "executed_at": "2023-11-14T22:13:20Z"
          },
          "timestamp": "2023-11-14T22:13:20.050Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"quote_executed"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.quote_id" type="UUID string" required>
        Novig's identifier for your quote.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round.
      </ResponseField>

      <ResponseField name="data.pricer_trader_id" type="UUID string" required>
        Your pricer.
      </ResponseField>

      <ResponseField name="data.wager" type="decimal string" required>
        Amount staked.
      </ResponseField>

      <ResponseField name="data.price" type="decimal string" required>
        Execution price.
      </ResponseField>

      <ResponseField name="data.executed_at" type="ISO-8601 string" required>
        When the trade filled.
      </ResponseField>
    </Accordion>

    <Accordion title="`quote_dropped`" icon="circle-arrow-down" description="Your quote was dropped for a fixable reason (quotes channel)">
      Novig sends this **only for actionable drops**. Losing on price is silent.

      ```json theme={"dark"}
      {
          "event": "quote_dropped",
          "data": {
              "quote_id": "0193abcd-0000-7000-8000-00000000000a",
              "rfq_id": "0193abcd-0000-7000-8000-000000000001",
              "pricer_trader_id": "0193abcd-0000-7000-8000-0000000000ff",
              "reason": "below_min_wager",
              "min_wager": "15"
          },
          "timestamp": "2026-01-01T00:00:03.001Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"quote_dropped"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.quote_id" type="UUID string" required>
        Novig's identifier for your quote.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round.
      </ResponseField>

      <ResponseField name="data.pricer_trader_id" type="UUID string" required>
        Your pricer.
      </ResponseField>

      <ResponseField name="data.reason" type="string" required>
        `below_min_wager` or `unbacked`. Each reason carries one extra field naming the number you must beat.
      </ResponseField>

      | `reason` | Extra field | Meaning |
      | - | - | - |
      | `below_min_wager` | `min_wager` | Your `max_wager` is under the round's floor: the taker's minimum or the venue minimum, whichever is higher. |
      | `unbacked` | `required_collateral` | Your free balance does not cover the quote's collateral. |
    </Accordion>
  </AccordionGroup>
</div>

## <Icon icon="circle-arrow-down" color="#16a34a" /> Acks

Novig answers every client message with an ack.

<div className="ws-msg ws-recv">
  <AccordionGroup>
    <Accordion title="`subscribed`" icon="circle-arrow-down" description="The subscription is active">
      Answers your `subscribe`.

      ```json theme={"dark"}
      {
          "event": "subscribed",
          "data": {
              "channel": "rfq"
          },
          "timestamp": "2026-01-01T00:00:00.123Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"subscribed"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.channel" type="string" required>
        `"rfq"` or `"quotes"`.
      </ResponseField>
    </Accordion>

    <Accordion title="`unsubscribed`" icon="circle-arrow-down" description="The subscription is removed">
      Answers your `unsubscribe`.

      ```json theme={"dark"}
      {
          "event": "unsubscribed",
          "data": {
              "channel": "quotes"
          },
          "timestamp": "2026-01-01T00:00:00.123Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"unsubscribed"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.channel" type="string" required>
        `"rfq"` or `"quotes"`.
      </ResponseField>
    </Accordion>

    <Accordion title="`quote_submitted`" icon="circle-arrow-down" description="Your quote entered the auction">
      Answers your `create_quote`.

      ```json theme={"dark"}
      {
          "event": "quote_submitted",
          "data": {
              "rfq_id": "0193abcd-0000-7000-8000-000000000001"
          },
          "timestamp": "2026-01-01T00:00:01.500Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"quote_submitted"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round your message named.
      </ResponseField>
    </Accordion>

    <Accordion title="`quote_superseded`" icon="circle-arrow-down" description="Your first quote stands. This one was dropped">
      Answers your `create_quote`.

      ```json theme={"dark"}
      {
          "event": "quote_superseded",
          "data": {
              "rfq_id": "0193abcd-0000-7000-8000-000000000001"
          },
          "timestamp": "2026-01-01T00:00:01.800Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"quote_superseded"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round your message named.
      </ResponseField>
    </Accordion>

    <Accordion title="`quote_declined`" icon="circle-arrow-down" description="Your pass was recorded">
      Answers your `decline`.

      ```json theme={"dark"}
      {
          "event": "quote_declined",
          "data": {
              "rfq_id": "0193abcd-0000-7000-8000-000000000001"
          },
          "timestamp": "2026-01-01T00:00:01.500Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"quote_declined"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round your message named.
      </ResponseField>
    </Accordion>

    <Accordion title="`confirm_recorded`" icon="circle-arrow-down" description="Your last-look answer was recorded">
      Answers your `confirm`.

      ```json theme={"dark"}
      {
          "event": "confirm_recorded",
          "data": {
              "rfq_id": "0193abcd-0000-7000-8000-000000000001",
              "quote_id": "0193abcd-0000-7000-8000-00000000000a"
          },
          "timestamp": "2026-01-01T00:00:05.400Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"confirm_recorded"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string" required>
        The round your message named.
      </ResponseField>

      <ResponseField name="data.quote_id" type="UUID string" required>
        The quote your answer decided.
      </ResponseField>
    </Accordion>
  </AccordionGroup>
</div>

## Errors

<div className="ws-msg ws-err">
  <AccordionGroup>
    <Accordion title="`error`" icon="circle-exclamation" description="Your message failed">
      ```json theme={"dark"}
      {
          "event": "error",
          "data": {
              "code": "RFQ_CLOSED",
              "message": "The quote round has already closed.",
              "rfq_id": "0193abcd-0000-7000-8000-000000000001"
          },
          "timestamp": "2026-01-01T00:00:03.100Z"
      }
      ```

      <ResponseField name="event" type="string" required>
        `"error"`.
      </ResponseField>

      <ResponseField name="timestamp" type="ISO-8601 string" required>
        When Novig emitted the frame.
      </ResponseField>

      <ResponseField name="data.code" type="string" required>
        Stable, machine-matchable. Match on this, not on `message`.
      </ResponseField>

      <ResponseField name="data.message" type="string" required>
        Human-readable description.
      </ResponseField>

      <ResponseField name="data.channel" type="string">
        The channel the failing request named. Omitted when absent.
      </ResponseField>

      <ResponseField name="data.rfq_id" type="UUID string">
        The round the failing request named. Omitted when absent.
      </ResponseField>
    </Accordion>
  </AccordionGroup>
</div>

Every code Novig sends, and what causes it:

| Code | Cause |
| - | - |
| `MALFORMED_REQUEST` | The message did not parse: bad JSON, an unknown `event`, a wrong `data` shape, or a binary frame. |
| `INVALID_QUOTE` | The quote's terms failed validation. See the limits table below. |
| `RFQ_CLOSED` | The auction already closed. The quote was dropped. |
| `FORBIDDEN` | You have no active pricer registration, or your account is restricted from RFQ quoting. |
| `RATE_LIMITED` | Too many actions. Retry later. |
| `NO_CONFIRM_WINDOW` | No last look is open for that quote. The answer was dropped. |
| `CONFIRM_ALREADY_DECIDED` | The last look already has an answer. This one was dropped. |
| `INTERNAL` | Novig failed to process the message. |

<Note>
  **An error never closes the socket.** Novig answers with a frame and the connection stays up. Handle an error and keep
  trading; do not reconnect in response to one.
</Note>

Novig checks your eligibility on **every action**, not at connect. A pricer deregistered or restricted mid-session keeps its socket and learns on its next `create_quote`, as a `FORBIDDEN` frame.

## Timing and limits

| Limit | Value | On breach |
| - | - | - |
| Auction window | 3 seconds | `RFQ_CLOSED`. The quote is dropped. |
| Last look | 1 second | The trade is rejected. |
| Server ping interval | 15 seconds | A missed pong disconnects the socket. |
| Actions per trader | 600 per 60 seconds | `RATE_LIMITED`. `confirm` is exempt. |
| Outbound queue per socket | 256 frames | Event frames drop. Acks and errors never drop. |
| `price` | `(0, 1)`, 0.001 grid | `INVALID_QUOTE`. |
| `max_wager` | Greater than zero | `INVALID_QUOTE`. |
| `quote_id` | 256 characters | `INVALID_QUOTE`. |

## Keepalive

The server sends a WebSocket protocol **Ping** every 15 seconds. Answer with a protocol **Pong**; standard clients do this automatically. A client that misses a ping interval is disconnected.

There is no JSON ping message and no idle timeout. A socket that answers its Pings stays open indefinitely.

## Reconnecting

<Warning>
  **Re-subscribe after every reconnect.** Subscriptions live on the connection. A new socket carries none of them, and Novig
  sends no events until you subscribe again.
</Warning>

The socket has **no replay and no backfill**. It starts at the live edge, so anything sent while you were disconnected is lost. Recover missed executions from the [executions feed](/deprecated/api-reference/rfq/executions).

Novig closes a socket without a status code, so do not read meaning into a close frame. Reconnect with backoff, then re-subscribe.

Event frames drop when your client cannot keep up, rather than blocking the server. Read promptly: a slow consumer silently misses quote rounds.

## Running both transports

The webhook is a capability, not a mode. Registering a `webhookUrl` and connecting the socket are independent choices, and you may do both.

| Your setup | What happens |
| - | - |
| Webhook only | Novig POSTs every round to `{webhook_url}/quote` and confirms over `{webhook_url}/confirm`. |
| Socket only | Novig pushes every round to the socket and confirms over the socket. |
| Both | **Both legs receive every round.** Your first quote wins; the other is dropped as `quote_superseded`. |

With both configured, Novig confirms on whichever leg carried the winning quote. A round your webhook won is confirmed over HTTP; a round your socket won arrives as `quote_accepted`. Implement both confirm paths, or run one transport.

Register with no `webhookUrl` to make the socket your only path. See [Registration](/deprecated/api-reference/rfq/registration).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.