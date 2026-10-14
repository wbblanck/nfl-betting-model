> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Search API Overview

> Search for events and markets

# Search API

The Search API allows you to search for events and markets by query string.

## Endpoints

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v1/search` | Search for events and markets |

## Search

Find events and markets matching a query:

```bash theme={null}
GET /v1/search?query=super+bowl&limit=10
```

### Query Parameters

| Parameter | Type | Description |
| - | - | - |
| `query` | string | Search query |
| `limit` | integer | Maximum number of results to return |
| `page` | integer | Page number for pagination |
| `seriesIds` | array | Filter by series IDs |
| `marketType` | array | Filter by market types |
| `status` | string | Filter by status |
| `startTimeMin` | string | Minimum start time filter |
| `startTimeMax` | string | Maximum start time filter |
| `closedTimeMin` | string | Minimum closed time filter |
| `closedTimeMax` | string | Maximum closed time filter |

### Response

Returns matching events with their associated markets:

```json theme={null}
{
  "events": [
    {
      "id": "123",
      "slug": "super-bowl-winner",
      "title": "Super Bowl Winner",
      "category": "sports",
      "active": true,
      "markets": [...]
    }
  ]
}
```


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.