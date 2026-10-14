> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Series

> Browse event series

The Series resource provides access to series information. Series group related events together (e.g., NFL games, election cycles, daily crypto markets).

## Methods

| Method | Endpoint | Description |
| - | - | - |
| `list(params?)` | `GET /v1/series` | List all series |
| `retrieve(id)` | `GET /v1/series/id/{id}` | Get series by ID |

***

## list

Get a list of all series with optional filtering.

```python theme={null}
series = client.series.list({
    "active": True,
    "limit": 20,
})

for s in series["series"]:
    print(f"{s['title']} ({s['recurrence']})")
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `limit` | int | Maximum results |
| `offset` | int | Pagination offset |
| `slug` | list\[str] | Filter by slugs |
| `active` | bool | Filter by active status |
| `closed` | bool | Filter by closed status |
| `archived` | bool | Filter by archived status |
| `recurrence` | str | Filter by recurrence (daily, weekly, etc.) |

### Response Fields

| Field | Type | Description |
| - | - | - |
| `id` | int | Unique series identifier |
| `slug` | str | URL-friendly identifier |
| `title` | str | Series title |
| `subtitle` | str | Series subtitle |
| `description` | str | Series description |
| `seriesType` | str | Type of series |
| `recurrence` | str | Recurrence pattern |
| `active` | bool | Whether series is active |
| `volume` | str | Total trading volume |
| `liquidity` | str | Current liquidity |

***

## retrieve

Get a single series by ID.

```python theme={null}
series = client.series.retrieve(123)

print(f"Title: {series['title']}")
print(f"Description: {series['description']}")
print(f"Recurrence: {series['recurrence']}")
```


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.