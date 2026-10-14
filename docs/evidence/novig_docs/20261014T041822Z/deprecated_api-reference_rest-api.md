> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Rate Limits & URL's

> HTTP REST API for order management and market data

**PROD URL:** `https://api.novig.com/nbx/v2`

**QA URL:** `https://api-qa.novig.us/nbx/v2`

## Rate Limits

| Endpoint | Interval | Limit |
| - | - | - |
| `POST emm/orders/place` (Single-order placement) | 1 s | 2048 |
| `POST emm/orders/batch` (Batch placement) | 1 s | 64 |
| `POST emm/strike-requests`, `GET emm/account/dashboard` | 1 s | 64 |
| `DELETE emm/orders/*` (Order cancellation, single and bulk) | 1 s | 2048 |
| `emm/kill` (Kill switch) | 30 s | 1 |
| `emm/fills/all`, `emm/orders/all`, `emm/transactions` (User history) | 1 s burst / 60 s sustained | 32 burst / 512 sustained |
| `emm/events`, `emm/events/{eventId}`, `emm/events/getMarketsByEvent/{eventId}` (Event screener) | 1 s | 1024 |
| All other EMM reads | 1 s | 256 |

Each limit is per route and per method. A row that lists several routes gives
each of them its own budget at that limit: every cancel route has its own 2048
requests per second, and single-order placement no longer competes with batch
placement.

User history endpoints support a maximum `limit` of **1024 items per request** for `/orders` and **256 items per request** for `/fills` and `/transactions` (default 100).

### Rate limit responses

When a limit is exceeded the API responds with **HTTP `429 Too Many Requests`**. Every response (both `2xx` and `429`) carries rate-limit headers:

| Header | Meaning |
| - | - |
| `X-RateLimit-Limit` | Max requests allowed in the current window |
| `X-RateLimit-Remaining` | Requests remaining in the current window |
| `X-RateLimit-Reset` | Time until the current window resets |
| `Retry-After` | Time to wait before retrying (present on `429`) |

<Warning>
  `Retry-After` and `X-RateLimit-Reset` are reported in **milliseconds**, not seconds. A value of `73` means wait **73 ms**, not 73 seconds. Do not feed these values into helpers that assume the HTTP-standard seconds unit.
</Warning>

Endpoints with a two-tier `burst` + `sustained` policy (the user-history endpoints) emit a separate set of headers per tier, suffixed with the tier name — e.g. `X-RateLimit-Remaining-burst` and `X-RateLimit-Remaining-sustained`. Honor whichever tier is closest to its limit.

We recommend retrying on `429` after the `Retry-After` delay with exponential backoff.

**Timeout:** 5 seconds

## Features

* Place, cancel, and query orders
* Retrieve market data and positions


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.