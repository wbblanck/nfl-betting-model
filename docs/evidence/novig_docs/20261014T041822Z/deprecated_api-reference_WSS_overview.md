> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# WebSocket Overview

> Real-time market data and order updates via WebSocket

## WebSocket API

The NBX WebSocket API provides real-time updates for market data, order books, and private trading events.

**WebSocket URL:** `wss://api.novig.com/tape`

**QA Environment:** `wss://api-qa.novig.us/tape`

### Key Features

* **Real-time order book updates** - Subscribe to public order book ticks (PLACE, CANCEL)
* **Market lifecycle events** - Get notified when markets open, close, start, or end, and when an event goes live or leaves live play
* **Private trading updates** - Receive place, fill, and cancel notifications for your orders
* **Heartbeat mechanism** - Protocol-level keepalive to ensure connection health

### Constraints

* **Keepalive:** the server sends a WebSocket protocol **Ping** every 15 seconds; a client that misses a full interval without a protocol Pong is disconnected. Standard clients respond automatically — see [Heartbeat](/deprecated/api-reference/WSS/heartbeat)

### Available Channels

| Channel | Description |
| - | - |
| `tape` | Global order book updates for all markets |
| `lifecycle` | Market lifecycle events (OPEN, END, CLOSE, START) and event liveness (EVENT\_GOLIVE, EVENT\_UNLIVE) |
| `private` | Private place, fill, and cancel updates for your orders |
| `{marketId}` | Order book updates for a specific market |

### Connection Flow

1. Establish WebSocket connection with Authorization header
2. Wait for connection to open
3. Send subscription messages for desired channels
4. Receive subscription confirmation
5. Process incoming messages (protocol Pings are answered automatically by standard clients)
6. Handle reconnection if connection drops


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.