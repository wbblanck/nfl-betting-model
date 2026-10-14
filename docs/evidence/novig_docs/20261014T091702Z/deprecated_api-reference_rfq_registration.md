> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Registering Your Pricer

> Register your pricer webhook and verify it end-to-end, self-serve

Registration is **self-serve**. A single authenticated call to `POST /rfq/pricer` creates your pricer; Novig mints your shared secret and hands it back in the response. Once registered, `POST /rfq/pricer/ping` lets you verify reachability and signature handling before any live quote flow.

Register whichever transport you price over. Registration creates the pricer that the [WebSocket](/deprecated/api-reference/rfq/websocket) authenticates against **and** the [webhook](/deprecated/api-reference/rfq/webhooks) Novig calls. The socket refuses a connection from a trader with no pricer.

## Authentication

Both endpoints use the same OAuth 2.0 Client Credentials token as the rest of the API — see [Authentication](/deprecated/api-reference/authentication). Send it as a bearer token:

```bash theme={"dark"}
Authorization: Bearer YOUR_ACCESS_TOKEN
```

The token identifies your LP trader, so **no trader ID goes in the body** — your registration is linked to the account the token belongs to.

| Environment | Base URL |
| - | - |
| Production | `https://api.novig.com` |
| QA | `https://api-qa.novig.us` |

## Prerequisites

<Steps>
  <Step title="You're onboarded as an LP">
    You must already be an LP. If you aren't, email [developers@novig.com](mailto:developers@novig.com) first. Registration links to that LP
    account via your access token.
  </Step>

  <Step title="Your webhook is reachable (webhook pricers only)">
    The base URL you register must be reachable from the public internet. For local development, terminate `https` at a tunnel
    like ngrok and register the public URL. A socket-only pricer skips this: it needs no public endpoint.
  </Step>
</Steps>

## `POST /rfq/pricer` — register or re-point your webhook

Register your pricer, or re-point an existing registration at a new URL.

* **First call** creates your pricer. A call carrying a `webhookUrl` mints a fresh 32-byte shared secret.
* **Later calls** re-point the URL and **keep the existing secret** — the secret only ever changes on first registration.

The response carries the secret whenever one exists, so you can (re)configure signature verification at any time.

### Request body

```json theme={"dark"}
{
    "webhookUrl": "https://pricer.example.com/novig"
}
```

| Field | Type | Notes |
| - | - | - |
| `webhookUrl` | string, optional | Absolute `http`/`https` base URL your pricer listens on. Path segments are allowed (e.g. `…/novig`). Novig appends `/quote`, `/confirm`, and `/ping` to it. Any other field is rejected. |

Omit `webhookUrl` on a **first** call to register for the [WebSocket](/deprecated/api-reference/rfq/websocket) alone, with no webhook and no shared secret. Omit it on a **later** call to leave the existing registration unchanged. Omitting it never removes a webhook you already registered.

<Note>
  A registration must leave Novig some way to reach you. A first call with no `webhookUrl` returns `400` when the maker socket
  is not enabled in that environment, because it would strand the pricer with no webhook to call and no socket to wait on.

  While the [maker WebSocket](/deprecated/api-reference/rfq/websocket) is in preview, that means **QA accepts a socket-only registration
  and Production returns `400`**. Register a `webhookUrl` on Production.
</Note>

```bash theme={"dark"}
curl https://api.novig.com/rfq/pricer \
  --header "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"webhookUrl": "https://pricer.example.com/novig"}'
```

A socket-only registration sends an empty body. It returns `null` for both `webhookUrl` and `sharedSecret`.

```bash theme={"dark"}
curl https://api-qa.novig.us/rfq/pricer \
  --header "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{}'
```

### Response

`200 OK`:

```json theme={"dark"}
{
    "pricerId": "0193abcd-0000-7000-8000-000000000001",
    "webhookUrl": "https://pricer.example.com/novig",
    "sharedSecret": "3b1f...<64 hex chars>...9e0a"
}
```

| Field | Type | Notes |
| - | - | - |
| `pricerId` | UUID string | Identifier of your pricer registration. |
| `webhookUrl` | string or `null` | The base URL webhook requests are now POSTed to. `null` on a socket-only registration. |
| `sharedSecret` | string or `null` | Hex-encoded 32-byte signing key (64 lowercase characters). Used to verify `X-Novig-Signature`. See [Signing](/deprecated/api-reference/rfq/signing). `null` on a socket-only registration. |

<Warning>
  The `sharedSecret` is returned **in full on every call** that has one, but Novig never shows it anywhere else. Store it
  securely on receipt. Re-pointing your URL keeps the same secret, so a routine URL change won't rotate the value your verifier
  depends on.
</Warning>

## Your shared secret

**Novig mints the shared secret server-side** on the first registration that carries a `webhookUrl`. The key is 32 bytes, hex-encoded as 64 lowercase characters. The same value lives on both sides: Novig signs every webhook body with it, and your pricer verifies. You never choose or upload it; you read it from the registration response.

A socket-only pricer has no shared secret. The socket authenticates with your bearer token at connect and signs nothing.

## `POST /rfq/pricer/ping` — verify connectivity

Ask Novig to send a **signed test request** to your registered webhook and report how it answered. Use it to confirm reachability and that your signature verification works — before any live quote flow depends on it.

Novig reads your pricer straight from the database rather than a cached snapshot, so a registration made seconds ago is immediately pingable. The signed request lands at `<webhookUrl>/ping` — see [Webhook Signing](/deprecated/api-reference/rfq/signing) and the [`/ping` handler](/deprecated/api-reference/rfq/webhooks) you implement.

```bash theme={"dark"}
curl https://api.novig.com/rfq/pricer/ping \
  --header "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Response

`200 OK`:

```json theme={"dark"}
{
    "url": "https://pricer.example.com/novig/ping",
    "ok": true,
    "status": 200,
    "error": null
}
```

| Field | Type | Notes |
| - | - | - |
| `url` | string | The URL the ping was POSTed to (`<webhookUrl>/ping`). |
| `ok` | boolean | `true` when your webhook answered with a 2xx status. |
| `status` | integer or `null` | The HTTP status your webhook returned. `null` when the request never completed (connection failure or timeout). |
| `error` | string or `null` | Why the request failed to complete, when no response was received. `null` on success. |

<Note>
  A `404` from this endpoint means the calling LP has no registered pricer yet — register with `POST /rfq/pricer` first.
</Note>

QA and Production registrations are independent — register in QA first, exercise the full lifecycle, then register in Production.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.