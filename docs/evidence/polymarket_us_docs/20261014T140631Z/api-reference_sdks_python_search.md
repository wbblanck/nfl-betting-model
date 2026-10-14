> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Search

> Search for events and markets

The Search resource provides full-text search across events and markets.

## Methods

| Method | Endpoint | Description |
| - | - | - |
| `query(params?)` | `GET /v1/search` | Search events and markets |

***

## query

Search for events and markets by text query.

```python theme={null}
results = client.search.query({
    "query": "bitcoin",
    "limit": 10,
})

for event in results["events"]:
    print(f"{event['title']}")
    for market in event.get("markets", []):
        print(f"  - {market['question']}")
```

### Parameters

| Parameter | Type | Description |
| - | - | - |
| `query` | str | Search query text |
| `limit` | int | Maximum results to return |
| `page` | int | Page number for pagination |
| `seriesIds` | list\[int] | Filter by series IDs |
| `marketType` | list\[str] | Filter by market types |
| `status` | str | Filter by status |

### Response

Returns events with their associated markets that match the search query:

```python theme={null}
{
    "events": [
        {
            "id": 123,
            "title": "Bitcoin Price Markets",
            "slug": "bitcoin-price",
            "markets": [
                {
                    "id": 456,
                    "question": "Will Bitcoin reach $100k?",
                    "slug": "btc-100k-2025"
                }
            ]
        }
    ]
}
```


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.