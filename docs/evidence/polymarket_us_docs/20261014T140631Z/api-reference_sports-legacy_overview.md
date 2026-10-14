> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Sports API Overview (Legacy)

> Legacy v1 sports data endpoints

# Sports API (Legacy)

The v1 Sports API provides access to sports configuration, player and team information, and sports events. The players lookup remains supported and is not deprecated despite this section's legacy label; it has no standalone v2 replacement.

## Endpoints

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v1/sports` | Get all sports |
| `GET` | `/v1/sports/{seriesId}/events` | Get events for a series |
| `GET` | `/v1/sports/teams` | Get sports teams |
| `GET` | `/v1/sports/teams/provider` | Get teams by provider |
| `GET` | `/v1/sports/players` | List players or look up players by internal ID, team, or provider ID |

## Get Sports Players

Retrieve player reference data without loading an event. Use `filters.id` for a specific player or `filters.teamId` for players on a team. See [Players Endpoint](/data-guide/sports-data#players-endpoint) for all filters, provider lookup behavior, pagination, response fields, and curl examples.

## Get Sports

Retrieve available sports and their configuration:

```bash theme={null}
GET /v1/sports
```

### Sport Fields

| Field | Type | Description |
| - | - | - |
| `sport` | string | Sport name |
| `image` | string | Sport image URL |
| `resolution` | string | Resolution configuration |
| `ordering` | string | Display ordering |
| `tags` | string | Associated tags |
| `series` | string | Associated series |
| `isOperational` | boolean | Whether sport is operational |
| `automaticResolution` | boolean | Whether automatic resolution is enabled |

## Get Sports Events

Retrieve events for a specific series:

```bash theme={null}
GET /v1/sports/{seriesId}/events
```

### Path Parameters

| Parameter | Type | Description |
| - | - | - |
| `seriesId` | integer | Series ID |

## Get Sports Teams

Retrieve all sports teams:

```bash theme={null}
GET /v1/sports/teams
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `teamIds` | array | Filter by team IDs |

## Get Teams by Provider

Retrieve team information from a specific data provider:

```bash theme={null}
GET /v1/sports/teams/provider?provider=PROVIDER_SPORTRADAR&league=NFL
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `teamIds` | array | Filter by team IDs |
| `provider` | string | Data provider (`PROVIDER_SPORTSDATAIO` or `PROVIDER_SPORTRADAR`) |
| `league` | string | League name (e.g., NFL, NBA, MLB) |

### Team Fields

| Field | Type | Description |
| - | - | - |
| `id` | integer | Team identifier |
| `name` | string | Team name |
| `abbreviation` | string | Team abbreviation |
| `displayAbbreviation` | string | Display abbreviation |
| `league` | string | League name |
| `record` | string | Team record |
| `logo` | string | Logo URL |
| `alias` | string | Team alias |
| `safeName` | string | Safe name for URLs |
| `homeIcon` | string | Home icon URL |
| `awayIcon` | string | Away icon URL |
| `colorPrimary` | string | Primary team color |
| `ranking` | integer | Team ranking |
| `conference` | string | Conference name |
| `providerIds` | array | Provider ID mappings |

## Data Providers

| Provider | Description |
| - | - |
| `PROVIDER_SPORTSDATAIO` | SportsData.io |
| `PROVIDER_SPORTRADAR` | Sportradar |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.