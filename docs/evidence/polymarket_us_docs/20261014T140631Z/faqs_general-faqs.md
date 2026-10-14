> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# General FAQs

> Frequently asked questions about trading on Polymarket US

### What are the trading hours?

Polymarket US operates nearly 24/7, with a recurring weekly maintenance window every Thursday from 6am–8am ET. Specific markets may have different trading hours based on the underlying event.

### How do I fund my account?

Deposit via debit card or bank transfer (ACH) through the Polymarket US app. See the app's funding section for deposit limits and processing times.

### How do I get support?

Email [support@polymarket.us](mailto:support@polymarket.us) or use the in-app chat.

### Where can I check system status?

View live system status, incidents, and scheduled maintenance at [status.polymarketexchange.com](https://status.polymarketexchange.com).

### When are maintenance windows?

Every Thursday, 6am–8am ET is the recurring weekly maintenance window, effective September 24, 2026. Previously, the window was every Thursday, 2am–4am ET.

### What happens to open orders during maintenance?

All open orders are canceled before maintenance begins. Leaving resting orders on the book during maintenance would expose traders to stale fills when the book reopens.

### What happens to connections during maintenance?

All API requests return **503 Service Unavailable** during maintenance. An explicit rejection is preferable to leaving connections open but non-functional.

### When do markets reopen?

Connections are re-enabled first, then markets move from SUSPENDED to OPEN. Order books reopen empty since all orders were cancelled before maintenance. The state change signals that maintenance is complete.

### What are `fractionalQtyScale` and `priceScale`, and how do I convert quantities and prices?

On the Institutional REST and gRPC APIs, quantities and prices are transmitted as **integers**. To convert them into whole shares and whole dollars, divide by the instrument's scale factors:

* **Quantities** — divide by `fractionalQtyScale`. For example, with `fractionalQtyScale = 100`, an integer quantity of `100` is `1` whole share, and `1` is `0.01` of a share (1% of a contract).
* **Prices** — divide by `priceScale`. For example, with `priceScale = 100`, an integer price of `50` is `$0.50`.

Both `fractionalQtyScale` and `priceScale` are returned per instrument in [reference data](/institutional/refdata/overview). Always read them from the instrument before submitting or interpreting orders — do not assume a fixed scale across instruments. Note that `int64` fields like `priceScale` and `fractionalQtyScale` are serialized as **strings** in JSON, so parse them as numbers in your client.

<Info>
  **On FIX, prices and quantities are pre-scaled.** FIX messages carry decimal values directly, so you do **not** apply `priceScale` or `fractionalQtyScale` to them. Scaling only applies to the integer values on the REST and gRPC APIs.
</Info>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.