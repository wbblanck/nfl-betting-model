> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Series API Overview

> Series data endpoints

# Series API

The Series API provides access to series information. Series group related events together (e.g., NFL games, election cycles).

## Endpoints

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v1/series` | Get all series with filtering |
| `GET` | `/v1/series/id/{id}` | Get series by ID |

## Key Series Fields

| Field | Description |
| - | - |
| `id` | Unique series identifier |
| `slug` | URL-friendly identifier |
| `title` | Series title |
| `subtitle` | Series subtitle |
| `description` | Series description |
| `seriesType` | Type of series |
| `recurrence` | Recurrence pattern (e.g., daily, weekly) |
| `active` | Whether series is active |
| `closed` | Whether series is closed |
| `archived` | Whether series is archived |

### Volume & Liquidity

| Field | Description |
| - | - |
| `liquidity` | Series liquidity |
| `volume` | Total trading volume |
| `volume24hr` | 24-hour volume |

## Filtering Series

Query series with various filters:

```bash theme={null}
GET /v1/series?active=true&recurrence=daily&limit=20
```

### Common Filters

| Parameter | Type | Description |
| - | - | - |
| `slug` | array | Filter by slugs |
| `active` | boolean | Filter by active status |
| `closed` | boolean | Filter by closed status |
| `archived` | boolean | Filter by archived status |
| `recurrence` | string | Filter by recurrence pattern |

## Pagination

| Parameter | Type | Description |
| - | - | - |
| `limit` | integer | Page size |
| `offset` | integer | Page offset |
| `orderBy` | array | Fields to order by |
| `orderDirection` | string | Order direction (asc/desc) |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.