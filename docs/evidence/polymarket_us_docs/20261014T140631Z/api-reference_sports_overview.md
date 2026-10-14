> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Sports API Overview

> Sports event data by league and sport, plus direct player lookup

# Sports API

The Sports API provides access to sporting events organized by league or sport, plus player reference data.

## Endpoints

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v2/leagues/{slug}/events` | Get events by league slug |
| `GET` | `/v2/sports/{slug}/events` | Get events by sport slug |
| `GET` | `/v1/sports/players` | List players or look up players by internal ID, team, or provider ID |

## Players

Use `/v1/sports/players?filters.id=781` to retrieve a specific player directly, or `filters.teamId` to list players on a team. This public endpoint is supported and is not deprecated; there is no standalone v2 players lookup endpoint. See [Players Endpoint](/data-guide/sports-data#players-endpoint) for filters, pagination, response fields, and examples for player props and combos.

## Get League Events

Retrieve events for a specific league:

```bash theme={null}
GET /v2/leagues/nfl/events
```

### Path Parameters

| Parameter | Type | Description |
| - | - | - |
| `slug` | string | League slug (e.g., `nfl`, `nba`, `mlb`) |

### Query Parameters

| Parameter | Type | Description |
| - | - | - |
| `limit` | integer | Pagination limit |
| `offset` | integer | Pagination offset |
| `excludeEventId` | array | Event IDs to exclude |
| `type` | string | Type: `sport` (default) or `futures` |
| `section` | string | Section: `general` (default) or `trending` |

## Get Sport Events

Retrieve events for all leagues under a sport:

```bash theme={null}
GET /v2/sports/football/events
```

### Path Parameters

| Parameter | Type | Description |
| - | - | - |
| `slug` | string | Sport slug (e.g., `football`, `basketball`) |

### Query Parameters

| Parameter | Type | Description |
| - | - | - |
| `limit` | integer | Pagination limit |
| `offset` | integer | Pagination offset |
| `excludeEventId` | array | Event IDs to exclude |
| `type` | string | Type: `sport` (default) or `futures` |
| `section` | string | Section: `general` (default) or `trending` |

## Teams

For fetching team information, use the [Sports (Legacy) API](/api-reference/sports-legacy/overview).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.