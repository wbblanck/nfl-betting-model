> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# RFQ Overview

> How Liquidity Providers respond to Novig parlay RFQs

## What is an RFQ?

A **Request for Quote (RFQ)** is the mechanism Novig uses to source parlay prices from Liquidity Providers. When a Novig user requests a parlay, Novig fans the request out to every active LP pricer, picks the winning quote deterministically, and asks the winning quoter to confirm before executing the trade.

This page is the entry point for **LPs who want to receive RFQs and respond with prices**. If you're an existing LP trading single-leg orders through `/nbx/v2`, RFQs are an opt-in addition — registering does not affect your order-book activity.

<Note>
  Currently, RFQs are only generated for **multi-leg parlays**. Single-outcome bets settle through the order book, not RFQs.
  For which markets and leagues can be combined, see [RFQ Eligibility](/deprecated/api-reference/rfq/eligibility).
</Note>

## End-to-end flow

<Steps>
  <Step title="A user requests a parlay">
    A Novig client posts a list of `outcomeIds` to Novig. Novig validates the outcomes, allocates an `rfq_id`, and persists the RFQ.
  </Step>

  <Step title="Novig fans out to every active pricer">
    Novig sends the RFQ to each registered pricer over the transport it registered: a signed `POST {webhook_url}/quote`, a `rfq_created` event on its socket, or both. Novig waits **up to 3 seconds total** for responses.
  </Step>

  <Step title="You return a price (or don't)">
    Your pricer returns a price and a maximum wager. Malformed answers, a `max_wager` at or below zero, and anything that misses the 3-second window are dropped.
  </Step>

  <Step title="Novig picks a winner">
    The winner is the best price for the user. Ties are broken by larger `max_wager`.
  </Step>

  <Step title="Novig asks the winning LP to confirm">
    Once the user accepts the quote, Novig asks the winning pricer to confirm the actual wager and the selected price, over the transport that carried the winning quote. You have a fixed **1-second window** to answer. Confirming in time executes the trade. Rejecting or missing the window rejects it.
  </Step>

  <Step title="The parlay settles">
    Once every leg grades, the parlay settles as a single position. Any leg that pushes or settles at fair market value returns the stake — see [Parlay Settlement](/deprecated/api-reference/rfq/settlement).
  </Step>
</Steps>

## Choosing a transport

You price over a **WebSocket**, over **webhooks**, or over both.

| Transport | You operate | Novig authenticates | Available |
| - | - | - | - |
| [WebSocket](/deprecated/api-reference/rfq/websocket) | One outbound connection. No public endpoint. | Your bearer token, once, at connect. | **QA only** (preview) |
| [Webhooks](/deprecated/api-reference/rfq/webhooks) | A public HTTPS service with three POST endpoints. | A signature on every request, which you verify. | QA and Production |

Both carry the same rounds under the same 3-second auction and 1-second last look. The WebSocket suits a pricer that cannot expose a public endpoint; webhooks suit one that already runs a service.

Registering a webhook and connecting a socket are independent. Do both and **both legs receive every RFQ**. Your first quote wins the round, and Novig confirms on whichever leg carried it.

## What you implement for webhooks

You stand up an HTTP service with **three POST endpoints** under a single base URL:

| Endpoint | Purpose |
| - | - |
| `POST {base_url}/quote` | Return a price for an RFQ |
| `POST {base_url}/confirm` | Approve or reject the wager before it executes |
| `POST {base_url}/ping` | Answer Novig's signed connectivity check (return any 2xx) |

Novig appends `/quote`, `/confirm`, and `/ping` to whatever base URL you register, so the base may include path segments (e.g. `https://pricer.example.com/novig`).

All three receive an `X-Novig-Signature` header — see [Webhook Signing](/deprecated/api-reference/rfq/signing) for verification.

## Getting started

Registration is **self-serve**, and every transport needs it: `POST /rfq/pricer` creates the pricer the socket authenticates against and the webhook Novig calls. Registering a `webhookUrl` mints your shared secret in the response; omitting it registers you for the socket alone. Verify webhook wiring end-to-end with `POST /rfq/pricer/ping` before live flow. See [Registration](/deprecated/api-reference/rfq/registration).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.