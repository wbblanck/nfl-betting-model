> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Events

> Retrieve and filter events

The Events resource provides access to event data. Events contain one or more markets and represent the underlying question or competition being predicted.

## Methods

| Method | Endpoint | Description |
| - | - | - |
| `list(params?)` | `GET /v1/events` | List events with filtering |
| `retrieve(id)` | `GET /v1/events/{id}` | Get event by ID |
| `retrieve_by_slug(slug)` | `GET /v1/events/slug/{slug}` | Get event by URL slug |

***

## list

Fetch a paginated list of events with optional filters.

```python theme={null}
events = client.events.list({
    "limit": 10,
    "offset": 0,
    "active": True,
    "categories": ["sports", "crypto"],
})

for event in events["events"]:
    print(f"{event['title']} - {len(event.get('markets', []))} markets")
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `limit` | int | Maximum results to return (default: 100) |
| `offset` | int | Number of results to skip for pagination |
| `active` | bool | Filter by active events |
| `closed` | bool | Filter by closed events |
| `archived` | bool | Filter by archived events |
| `featured` | bool | Filter featured events only |
| `categories` | list\[str] | Filter by category slugs |
| `seriesId` | list\[int] | Filter by series IDs |
| `live` | bool | Filter live sports events |
| `ended` | bool | Filter ended sports events |

### Response Fields

| Field | Type | Description |
| - | - | - |
| `id` | int | Unique event identifier |
| `slug` | str | URL-friendly identifier |
| `title` | str | Event title |
| `description` | str | Event description |
| `category` | str | Primary category |
| `active` | bool | Whether event is active for trading |
| `closed` | bool | Whether event is closed |
| `markets` | list | Associated markets |

***

## retrieve

Get a single event by its numeric ID.

```python theme={null}
event = client.events.retrieve(12345)

print(f"Title: {event['title']}")
print(f"Category: {event['category']}")
print(f"Markets: {len(event.get('markets', []))}")
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `id` | int | Event ID |

***

## retrieve\_by\_slug

Get an event by its URL slug. Useful when you have the slug from a URL or API response.

```python theme={null}
event = client.events.retrieve_by_slug("super-bowl-2025")

print(f"Title: {event['title']}")
for market in event.get("markets", []):
    print(f"  - {market['title']}: {market['slug']}")
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `slug` | str | Event URL slug |

***

## Sports Event Fields

Sports events include additional real-time data:

| Field | Type | Description |
| - | - | - |
| `gameId` | str | Sports provider game ID |
| `live` | bool | Whether game is in progress |
| `ended` | bool | Whether game has ended |
| `score` | object | Current score |
| `period` | str | Current period/quarter/half |
| `participants` | list | Teams or players |

```python theme={null}
events = client.events.list({"live": True, "categories": ["sports"]})

for event in events["events"]:
    if event.get("live"):
        score = event.get("score", {})
        print(f"{event['title']}: {score}")
```


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.