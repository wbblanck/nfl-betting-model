> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Events API Overview

> Event data endpoints

# Events API

The Events API provides access to event information. For search, see the Search API.

## Endpoints

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v1/events` | Get all events with filtering |
| `GET` | `/v1/events/{id}` | Get event by ID |
| `GET` | `/v1/events/slug/{slug}` | Get event by slug |
| `GET` | `/v1/partners/{partnerKey}/events/{externalId}` | Get partner event by external ID |

## Key Event Fields

| Field | Description |
| - | - |
| `id` | Unique event identifier |
| `slug` | URL-friendly identifier |
| `title` | Event title |
| `description` | Event description |
| `category` | Event category |
| `subcategory` | Event subcategory |
| `active` | Whether event is active |
| `closed` | Whether event is closed |
| `archived` | Whether event is archived |

### Sports Event Fields

| Field | Description |
| - | - |
| `gameId` | Sports provider game ID |
| `sportradarGameId` | Sportradar game ID |
| `score` | Current event score |
| `period` | Current period |
| `live` | Whether event is live |
| `ended` | Whether event has ended |
| `eventState` | Detailed event state information |
| `participants` | Event participants (teams/players) |

### Crypto Event Fields

Crypto price events have no participants or game state. Use these fields instead:

| Field | Description |
| - | - |
| `seriesSlug` | Asset, family and cadence, e.g. `btc-updown-15m`, `btc-strike-daily`, `btc-range-hourly`, `btc-hit-monthly` |
| `tags` | Taxonomy tags such as `crypto`, `crypto-prices`, `recurring`, the family (`up-or-down`, `multi-strikes`, `neg-risk`, `hit-price`), the window (`15M`, `1H`, `daily`, `weekly`, `monthly`) and the asset (`bitcoin`) |
| `markets[].assetPriceTerms` | Typed terms of each leg; see [Crypto Price Market Fields](/api-reference/market/overview#crypto-price-market-fields) |

An Up/Down event holds one market per window; a ladder event holds one market per strike or bucket.

### Volume & Liquidity

| Field | Description |
| - | - |
| `liquidity` | Event liquidity |
| `volume` | Total trading volume |
| `volume24hr` | 24-hour volume |
| `volume1wk` | 7-day volume |
| `volume1mo` | 30-day volume |

## Filtering Events

Query events with various filters:

```bash theme={null}
GET /v1/events?active=true&categories=sports&limit=50
```

### Common Filters

| Parameter | Type | Description |
| - | - | - |
| `active` | boolean | Filter by active status |
| `closed` | boolean | Filter by closed status |
| `archived` | boolean | Filter by archived status |
| `featured` | boolean | Filter featured events |
| `categories` | array | Filter by categories |
| `seriesId` | array | Filter by series IDs |
| `gameId` | integer | Filter by game ID |
| `ended` | boolean | Filter by ended status |
| `live` | boolean | Filter live events |

### Date Filters

| Parameter | Type | Description |
| - | - | - |
| `startDateMin` | string | Minimum start date |
| `startDateMax` | string | Maximum start date |
| `startTimeMin` | string | Minimum start time |
| `startTimeMax` | string | Maximum start time |
| `eventDate` | string | Specific event date |
| `eventWeek` | integer | Event week number |

## Partner Events

Retrieve an event using a partner's external ID:

```bash theme={null}
GET /v1/partners/{partnerKey}/events/{externalId}
```

### Path Parameters

| Parameter | Type | Description |
| - | - | - |
| `partnerKey` | string | Partner key identifier |
| `externalId` | string | Partner's external event ID |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.