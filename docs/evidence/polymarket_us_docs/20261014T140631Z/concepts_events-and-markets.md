> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Events & Markets

> Understanding how prediction markets are structured on Polymarket US.

Every prediction on Polymarket US is structured around three levels: **series**, **events**, and **markets**. Understanding how they relate is essential for finding what you want to trade.

## Series

A series is a broad grouping of related events — like a sports league or a season. Think of it as a folder that contains many games or occurrences.

**Examples:** NFL 2025-26 Season, NBA 2025-26 Season, March Madness 2026

## Events

An event is a specific occurrence within a series — usually a single game, match, or contest. Each event has a start time, participants, and one or more markets attached to it.

**Examples:** Chiefs vs Eagles — Feb 9, 2026, Lakers vs Celtics — Jan 15, 2026

## Markets

A market is the actual thing you trade. It's a single yes/no question about an event. Each market settles at \$1.00 if the outcome happens and \$0.00 if it doesn't.

One event can have multiple markets. For example, a single NFL game might have:

| Market type | Question | Example |
| - | - | - |
| **Moneyline** | Who wins? | Will the Chiefs win? |
| **Spread** | Will they win by more than X points? | Chiefs -3.5 |
| **Total** | Will the combined score be over/under X? | Total points over 47.5 |
| **Prop** | Will a specific thing happen in the game? | Mahomes over 2.5 TDs |

```
Series: NFL 2025-26 Season
  └── Event: Chiefs vs Eagles — Feb 9, 2026
        ├── Market: Will the Chiefs win? (moneyline)
        ├── Market: Chiefs -3.5 (spread)
        └── Market: Total points over 47.5 (total)
```

## Crypto price markets

Crypto price markets follow the same three levels, but the event is a time window or an expiry rather than a game. A series groups one asset, one market family and one cadence (for example `btc-updown-15m`); an Up/Down event holds a single market for one window, while an Above/Below or Price Range event holds one market per strike or bucket, all expiring at the same instant.

```
Series: btc-strike-daily
  └── Event: btc-above-day-2026-09-21 (expires 5:00 PM ET)
        ├── Market: $73,500 or above
        ├── Market: $74,000 or above
        └── Market: $74,500 or above
```

Each market carries a typed `assetPriceTerms` object with the window, strike or range bounds, the reference price to beat and, once settled, the settlement price. See [Crypto Price Market Fields](/api-reference/market/overview#crypto-price-market-fields).

## Market slugs

Every market has a **slug** — a URL-friendly identifier like `aec-nfl-kc-phi-2026-02-09`. This is what you use everywhere: placing orders, fetching order books, subscribing to WebSocket streams.

You can find slugs by searching or browsing markets through the API.

## Live sports data

For sports events that are in progress, you get real-time metadata like the current score, period, and whether the game has ended. This is useful if you're building applications that react to live game state.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.