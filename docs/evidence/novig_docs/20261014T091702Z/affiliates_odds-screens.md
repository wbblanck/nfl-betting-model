> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Odds Screens

> Display Novig odds using the REST catalog and order book

export const BOOK_DEPTH_DEFAULT = 20;

export const BOOK_DEPTH_MAX = 20;

export const BOOK_DEPTH_MIN = 1;

export const HOST_VAR = "NOVIG_HOST";

export const PROD_HOST = "https://api.novig.com";

## Overview

You can show Novig prices on your odds screen with our REST API.
You list a league's markets from the catalog, then read each market's order book to get its prices.

Every example reads the host from <code>{HOST_VAR}</code>. On Production that is <code>{PROD_HOST}</code>.

```bash theme={"dark"}
export NOVIG_HOST=https://api.novig.com
```

## Get a key

The catalog accepts a `trading` or `trading::read` key, and you sign every request.
A `trading::read` key can read but can't place orders, so it fits a read-only integration.

* [Get a key](/api/api-keys) shows how to create each kind of key.
* [Sign a request](/api/signing) explains the three signature headers in the examples below.
* [Location checks](/api/api-keys#location-checks) explains why a signed route can return `451`.

## Routes

| Route | Returns |
| - | - |
| `GET /v3/types/leagues` | The league names you can filter on |
| `GET /v3/catalog/events` | Events, with their start time and status |
| `GET /v3/catalog/markets` | Markets, with their outcome IDs |
| `GET /v3/catalog/markets/{id}/book` | Resting orders by outcome |
| `GET /v3/catalog/markets/{id}/trades` | Executions, newest first |

Each route spends the `read` throttle. [Throttling](/api/throttling) explains how to pace your requests.

## List a league's markets

A market leaves the catalog when it closes, so the catalog lists only markets you can still trade.

<Tabs>
  <Tab title="Request">
    ```bash theme={"dark"}
    curl -s "$NOVIG_HOST/v3/catalog/markets?league=NFL" \
      -H "Novig-Key-Id: $TRADING_KEY_ID" \
      -H "Novig-Timestamp: $TS" \
      -H "Novig-Signature: $SIG"
    ```
  </Tab>

  <Tab title="200">
    ```json theme={"dark"}
    {
    "items": [
    {
      "marketId": "6f9619ff-…",
      "eventId": "110e8400-…",
      "marketType": "MONEY",
      "status": "OPEN",
      "description": "Kansas City Chiefs at Buffalo Bills — Moneyline",
      "startsTs": 1758400800000,
      "fee": {
        "coefficient": "0.03",
        "makerCredit": "0.5",
        "charged": "WHEN_LIVE"
      },
      "outcomes": [
        {
          "outcomeId": "3f2504e0-…",
          "name": "Kansas City Chiefs",
          "status": "TBD"
        },
        {
          "outcomeId": "5a1c9e73-…",
          "name": "Buffalo Bills",
          "status": "TBD"
        }
      ]
    }
    ],
    "next": "eyJvIjoxNzU4NDAwODAwMDAwfQ"
    }
    ```
  </Tab>
</Tabs>

| Field | Meaning |
| - | - |
| `marketId` | The ID you pass to the book route |
| `eventId` | The event the market belongs to |
| `marketType` | The question, like `MONEY` or `TOTAL` |
| `strike` | The line, on a market that has one |
| `description` | Display text. Don't parse it |
| `startsTs` | Scheduled start, in Unix milliseconds |
| `outcomes` | Each answer's `outcomeId` and `name` |

To read the next page, pass the reply's `next` as `after`.
[Catalog](/api/catalog#filters) lists every filter, including `marketType`, `startsAfter`, and `startsBefore`.

For each event's name, start time, and status, call `GET /v3/catalog/events?league=NFL` and match on `eventId`.

<Note>
  Build on IDs, not on `description`. An outcome ID stays stable for the life of its market.
</Note>

## Read the order book

<Tabs>
  <Tab title="Request">
    ```bash theme={"dark"}
    curl -s "$NOVIG_HOST/v3/catalog/markets/$MARKET_ID/book" \
      -H "Novig-Key-Id: $TRADING_KEY_ID" \
      -H "Novig-Timestamp: $TS" \
      -H "Novig-Signature: $SIG"
    ```
  </Tab>

  <Tab title="200">
    ```json theme={"dark"}
    {
    "marketId": "6f9619ff-…",
    "seq": 48120,
    "orders": {
    "3f2504e0-…": [
      {
        "orderId": "7c9e6679-…",
        "price": "0.665",
        "qty": 110
      },
      {
        "orderId": "1b4e28ba-…",
        "price": "0.660",
        "qty": 250
      }
    ],
    "5a1c9e73-…": [
      {
        "orderId": "6ba7b810-…",
        "price": "0.330",
        "qty": 180
      }
    ]
    }
    }
    ```
  </Tab>
</Tabs>

Each key in `orders` is an outcome ID.
Each outcome's array lists the best price first. Within a price, it lists the earlier order first.

`depth` sets how many price levels you get per outcome, from {BOOK_DEPTH_MIN} to {BOOK_DEPTH_MAX}. It defaults to {BOOK_DEPTH_DEFAULT}.

To skip an unchanged book, send the previous reply's `ETag` in `If-None-Match`. An unchanged book returns `304`.

## Turn the book into prices

Every order on the book is a bid: an offer to buy one outcome at a price.
A price is a probability, written as a decimal string.

A bid resting at `0.665` on one outcome is liquidity for the other outcome.
A taker on the other outcome trades against it at `0.335`.

So the price you show for an outcome is 1 minus the best bid on the other outcome.
The size you show is the `qty` of that bid, in contracts.

Using the book above:

| Best bid | Price to show | Size |
| - | - | - |
| Chiefs at `0.665` | Bills at `0.335` | 110 contracts |
| Bills at `0.330` | Chiefs at `0.670` | 180 contracts |

[Monetary representations](/api/concepts/money) explains prices, quantities, and the price grid.

<Warning>
  The `outcomes` array has no fixed order. Find the other outcome by its `outcomeId`, never by its position.
</Warning>

A three-way moneyline is three separate Yes / No markets, not one market with three outcomes.
[Three-way moneylines](/api/concepts/universe-model#three-way-moneylines) explains how to read them.

When an event goes live, we void every resting order on its markets, so its books start empty in-game.
[Event lifecycle](/api/concepts/event-lifecycle) lists each event status.

## Show the last traded price

`GET /v3/catalog/markets/{id}/trades` lists a market's executions, newest first.
Each trade carries its `outcomeId`, `price`, `qty`, and `ts`.

## Get live updates

Each book request spends from your `read` throttle.
To follow prices live, subscribe to the [book channel](/api/streaming/book) on the websocket. It reports every change to a market's book.

The REST book's `seq` is the book's sequence number at that snapshot. The next `book` delta on the websocket follows it.

## Supported leagues

Read the current list of leagues from `GET /v3/types/leagues`.
Pass one or more of its names to `league`, separated by commas.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.