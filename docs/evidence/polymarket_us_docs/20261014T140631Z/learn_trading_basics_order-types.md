> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Order Types

> Learn how market and limit orders execute and how fills work

Polymarket US offers two order types in the app and on the web: **market orders**, which fill right away at the best available prices, and **limit orders**, which let you set your price.

## How It Works

1. A market order fills right away against the order book at the best available prices, within a price limit based on the price you were quoted.
2. When you buy, if there isn't enough available for your full amount, you'll see a warning before you confirm, and only what's available is filled.
3. If prices move and the order can no longer fill within the price limit, a buy or a sale of a set dollar amount is canceled. A cash out sells what it can and cancels the rest. A market order never leaves an open order on the book.
4. A limit order fills at your limit price or better. If there isn't enough size at that price, you receive a **partial fill**.
5. Unless you choose Immediate or cancel, any unfilled portion of a limit order stays on the order book as an **open order** until it is filled, canceled, or expires. You choose the expiry when you place the order: Good 'til canceled, 12am PT, Start of game (for games that haven't started), or Immediate or cancel, which cancels any unfilled portion right away.

Execution is always based on available liquidity and standard time-and-price priority within the central limit order book (CLOB).

## Example

You place a Good 'til canceled limit order to buy 1,000 Yes contracts at \$0.52, the current best ask:

* If at least 1,000 contracts are available at \$0.52 or better, the entire order is filled immediately.
* If only 600 contracts are available at \$0.52, you receive a partial fill for 600 contracts.
* The remaining 400 stay on the order book at \$0.52 as an open order until they are filled or canceled.
* Your execution price reflects only the portion that filled.

## Key Points

* **Price protection**: A limit order never fills at a worse price than your limit price. A market order only fills within a price limit based on the price you were quoted.
* **Partial fills**: A limit order can fill in part, and unless you chose Immediate or cancel, the rest stays on the book as an open order. A market order never leaves an open order on the book.
* **Dynamic markets**: Prices and available size may change while your order is being filled, but a limit order only fills at your limit price or better.
* **Priority**: Orders match using standard time-and-price priority within the CLOB.
* **Compliance**: All orders are handled in accordance with applicable law and Polymarket US platform rules to ensure fair and orderly trading.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.