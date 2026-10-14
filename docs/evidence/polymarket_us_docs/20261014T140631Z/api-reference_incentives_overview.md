> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Incentives API Overview

> View incentive programs and your earned rewards

# Incentives API

The Incentives API exposes the active incentive programs and the rewards you have earned. For background on how programs work and their reward formulas, see the [Incentive Programs overview](/incentives/overview); for how liquidity programs score — Target Size, Discount Factor, and Max Spread — see the [Liquidity Incentive Program](/incentives/liquidity) page.

## Base URL

```
https://api.polymarket.us
```

<Note>
  **Field casing.** Query parameters are `snake_case` (e.g. `page_size`). Response bodies are `lowerCamelCase` (e.g. `marketSlug`). Sending a camelCase query parameter (e.g. `pageSize`) is silently ignored and the default is used.
</Note>

## Endpoints

| Method | Endpoint | Auth | Description |
| - | - | - | - |
| `GET` | `/v1/incentives` | Required | Get incentive programs |
| `GET` | `/v1/incentives/earnings` | Required | Get your incentive earnings |

<Warning>
  **Authentication**

  Both endpoints require API key authentication — see the [Authentication guide](/api-reference/authentication).
</Warning>

## Get Incentive Programs

Returns active and historical incentive programs grouped by market.

```bash theme={null}
GET /v1/incentives?page_size=10&symbols=aec-nba-bos-nyk-2026-04-01
```

### Query Parameters

| Parameter | Type | Required | Description |
| - | - | - | - |
| `page_size` | integer | No | Number of markets per page. Use with `page_token` for pagination. |
| `page_token` | string | No | Pagination token from a previous response's `nextPageToken`. |
| `symbols` | string\[] | No | Filter by market symbols. |
| `order_by` | string | No | Sort field. Defaults to `created_at`. |
| `order_direction` | string | No | Sort direction: `asc` or `desc`. Defaults to `desc`. |
| `statuses` | string\[] | No | Filter by status: `active`, `closed`, or `pending`. |
| `program_type` | string | No | Filter by program type, such as `liquidityProgram` or `volumeProgram`. |
| `query` | string | No | Case-insensitive substring match on market slug. |
| `instrument_states` | string\[] | No | Filter by instrument lifecycle state. |
| `category` | string | No | Filter by exact event category. |
| `subcategory` | string | No | Filter by exact event subcategory. |

### Response

```json theme={null}
{
  "programs": [
    {
      "marketSlug": "aec-nba-bos-nyk-2026-04-01",
      "instrumentState": "INSTRUMENT_STATE_OPEN",
      "category": "sports",
      "subcategory": "basketball",
      "eventStartTime": "2026-04-01T23:30:00Z",
      "instrumentProduct": "moneyline",
      "timePeriods": [
        {
          "programId": "nba_t1_ml_early",
          "programType": "liquidityProgram",
          "start": "2026-03-28T04:00:00Z",
          "end": "2026-04-01T21:00:00Z",
          "rewardPool": 3000.0,
          "status": "closed",
          "discountFactor": 0.40,
          "targetSize": 20000,
          "period": "early",
          "createdAt": "2026-03-28T01:00:00Z",
          "maxSpread": 0.035
        },
        {
          "programId": "nba_t1_ml_day_of",
          "programType": "volumeProgram",
          "start": "2026-04-01T21:00:00Z",
          "rewardPool": 3000.0,
          "status": "active",
          "minTakerNotional": 100,
          "period": "day_of",
          "createdAt": "2026-03-28T01:00:00Z"
        }
      ]
    }
  ],
  "nextPageToken": "abc123"
}
```

<Note>
  Ongoing programs omit `end` until an end time is set.
</Note>

### IncentiveProgram Fields

| Field | Type | Description |
| - | - | - |
| `marketSlug` | string | Market identifier |
| `timePeriods` | TimePeriod\[] | Incentive periods for this market |
| `instrumentState` | string | Exchange lifecycle state of the instrument |
| `category` | string | Event category from instrument metadata |
| `subcategory` | string | Event subcategory from instrument metadata |
| `eventStartTime` | string | Event start time from instrument metadata |
| `instrumentProduct` | string | Product from instrument metadata |

### TimePeriod Fields

| Field | Type | Description |
| - | - | - |
| `programId` | string | Unique program period identifier |
| `programType` | string | Program type (e.g. `liquidityProgram`) |
| `start` | string | ISO 8601 start timestamp |
| `end` | string | ISO 8601 end timestamp (optional; omitted for ongoing programs) |
| `rewardPool` | number | Total reward pool for this period in USD |
| `status` | string | `active`, `closed`, or `pending` |
| `discountFactor` | number | Discount factor for scoring (optional; omitted if unset) |
| `targetSize` | integer | Liquidity programs: minimum aggregate resting size, in contracts, on a side of the book for that side to qualify (optional; omitted if unset) |
| `maxSpread` | number | Liquidity programs only. Optional **half-width** in price dollars (`0.035` = 3.5¢ from mid, so a 7¢ gap). Where set, a second pays only if both sides of the book reach `targetSize` with each size-adjusted price within `maxSpread` of the midpoint. Omitted (never `0`) when the program has no Max Spread. See the note below |
| `period` | string | Reward period type: `early`, `day_of`, `live`, etc. |
| `createdAt` | string | ISO 8601 timestamp when the program was created |
| `minTakerNotional` | integer | Minimum taker notional for volume programs (optional) |

<Note>
  **Reading `maxSpread`.** A liquidity program may carry a maximum spread from the midpoint. Where it does:

  * **Units.** `maxSpread` is in price dollars of a \$1 contract (`0.035` = 3.5¢). The docs pages and polymarket.us/rewards quote the same value in cents; the API always returns dollars. It is a **half-width**: the two sides may be up to 2 × `maxSpread` apart (3.5¢ from the midpoint = a 7¢ gap).
  * **What is compared.** Once per sampled second, each side of the book is walked from its best price outward, one whole price level at a time, until the resting size on that side (all participants combined) reaches `targetSize`. The price level that gets there is that side's *size-adjusted price*. The midpoint is halfway between the two size-adjusted prices — not the best-bid/best-offer midpoint. A small order at the best price counts toward that side's depth like any other order; it moves the size-adjusted price only when it is what carries the side to `targetSize`.
  * **Pass / fail.** This is a test of the book, not of each trader: you do not have to quote both sides yourself. The second is scored as usual (every order from the best price through the size-adjusted price qualifies, weighted by its distance from that side's best price and by its size) when both sides reach `targetSize` and each size-adjusted price is no more than `maxSpread` from the midpoint — a gap of exactly 2 × `maxSpread` passes. If either side never reaches `targetSize`, or the gap is wider than 2 × `maxSpread`, **nobody is paid for that second**, including makers quoting tightly and including a side that did reach `targetSize`. Once a second qualifies, a one-sided quote still earns on the side it rests on. A failed second still counts toward the period's total, so its share of `rewardPool` is forfeited, not shifted to other seconds or other makers.
  * **Tick size.** The check is in dollars, so a given `maxSpread` means the same thing on 1¢-tick and 0.1¢-tick markets.
  * **Omission.** The key is absent (never `0`) when a program has no Max Spread; it is a `liquidityProgram` field. Programs without a Max Spread score each side independently, as before.
  * **Scope.** The value applies to every scored second of that `timePeriods[]` entry. Parameters can differ between time periods of the same market, so read `maxSpread` per entry rather than per market.

  Full explanation and worked example: [What is Max Spread?](/incentives/liquidity#what-is-max-spread).
</Note>

## Get Incentive Earnings

Returns rewards earned by the authenticated caller. Each entry sums all payouts for a single `(market, date)` pair, where `date` is in Eastern Time.

```bash theme={null}
GET /v1/incentives/earnings?start_date=2026-03-21&market_slug=aec-nba-bos-nyk-2026-04-01
```

### Query Parameters

| Parameter | Type | Required | Description |
| - | - | - | - |
| `start_date` | string | No | Start date filter (`YYYY-MM-DD`). Defaults to program launch. |
| `end_date` | string | No | End date filter (`YYYY-MM-DD`). Omit for through-today. |
| `market_slug` | string | No | Filter by market slug. |
| `program_type` | string | No | Filter by program type (e.g. `liquidityProgram`). |

### Response

```json theme={null}
{
  "rewards": [
    {
      "reward": 1828.62,
      "programType": "liquidityProgram",
      "marketSlug": "tsc-nba-ny-okc-2026-03-29-223pt5",
      "date": "2026-03-30",
      "status": "PAID"
    },
    {
      "reward": 325.97,
      "programType": "liquidityProgram",
      "marketSlug": "aec-cbb-cabap-kan-2026-03-20",
      "date": "2026-03-29",
      "status": "PENDING"
    }
  ]
}
```

<Note>
  Each daily entry represents rewards earned from midnight-to-midnight ET. Callers with no rewards receive `{"rewards":[]}`.
</Note>

### UserReward Fields

| Field | Type | Description |
| - | - | - |
| `reward` | number | Reward amount in USD (sum of all payouts for this market on this date) |
| `programType` | string | Program type (e.g. `liquidityProgram`) |
| `marketSlug` | string | Market identifier |
| `date` | string | Reward date in Eastern Time (`YYYY-MM-DD`) |
| `status` | string | Payout disposition: `PAID`, `PENDING`, or `SKIPPED` |

## Rate Limits

| Endpoint | Rate Limit |
| - | - |
| `GET /v1/incentives` | 5 requests / second |
| `GET /v1/incentives/earnings` | 5 requests / second |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.