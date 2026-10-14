> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Sports

> Sports configuration and team data

The Sports resource provides access to sports configuration and team information from data providers.

## Methods

| Method | Endpoint | Description |
| - | - | - |
| `list()` | `GET /v1/sports` | List all sports |
| `teams(params?)` | `GET /v1/sports/teams/provider` | Get teams by provider |

***

## list

Get all available sports and their configuration.

```python theme={null}
sports = client.sports.list()

for sport in sports["sports"]:
    print(f"{sport['sport']} - Operational: {sport['isOperational']}")
```

### Response Fields

| Field | Type | Description |
| - | - | - |
| `sport` | str | Sport name |
| `image` | str | Sport image URL |
| `isOperational` | bool | Whether sport is operational |
| `automaticResolution` | bool | Whether automatic resolution is enabled |
| `ordering` | str | Display ordering |

***

## teams

Get team information from a specific data provider.

```python theme={null}
teams = client.sports.teams({
    "provider": "PROVIDER_SPORTRADAR",
    "league": "NFL",
})

for team in teams["teams"]:
    print(f"{team['name']} ({team['abbreviation']})")
    print(f"  Conference: {team['conference']}")
    print(f"  Record: {team['record']}")
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `provider` | str | Data provider (see below) |
| `league` | str | League name (NFL, NBA, MLB, etc.) |
| `teamIds` | list\[int] | Filter by specific team IDs |

### Data Providers

| Provider | Description |
| - | - |
| `PROVIDER_SPORTRADAR` | Sportradar |
| `PROVIDER_SPORTSDATAIO` | SportsData.io |

### Team Fields

| Field | Type | Description |
| - | - | - |
| `id` | int | Team identifier |
| `name` | str | Team name |
| `abbreviation` | str | Team abbreviation |
| `league` | str | League name |
| `conference` | str | Conference name |
| `record` | str | Team record |
| `ranking` | int | Team ranking |
| `logo` | str | Logo URL |
| `colorPrimary` | str | Primary team color |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.