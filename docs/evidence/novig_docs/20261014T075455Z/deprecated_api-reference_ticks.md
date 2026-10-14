> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Tick Table

## Overview

Not all prices are valid for order submission. Novig uses a **non-uniform tick table** that defines the exact set of prices at which orders can be placed. Any order submitted at a price not in the tick table will be rejected.

<Warning>
  **Do not hardcode the tick table.** The tick table may change in the future. Always fetch it dynamically using the `GET /nbx/v2/emm/ticks` endpoint to ensure your integration stays up to date.
</Warning>

## Fetching the Tick Table

Retrieve the current tick table via the REST API. See the full endpoint reference at [`GET /nbx/v2/emm/ticks`](/deprecated/api-reference/markets/get-ticks).

The response is an array of valid price ticks as floating-point numbers:

```json theme={"dark"}
[0.001, 0.002, 0.003, ..., 0.998, 0.999]
```

## Tick Spacing

The current tick table is **symmetric around 0.50** and uses two spacing tiers: **0.001 increments** from 0.001 to 0.050, and **0.005 increments** from 0.055 to 0.495. The upper half mirrors the lower half around the 0.500 midpoint. The API endpoint is always the source of truth.

## Best Practices

* **Fetch on startup:** Load the tick table when your application starts and cache it locally.
* **Refresh periodically:** Re-fetch the tick table at a reasonable interval to pick up any future changes.
* **Snap prices to ticks:** Before submitting an order, round your desired price to the nearest valid tick.
* **Never hardcode:** The tick table may be updated over time. Always use the `GET /nbx/v2/emm/ticks` endpoint as the source of truth.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.