> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Fractional Contracts

> Learn how fractional contracts work on Polymarket US

Most markets on Polymarket US support fractional contracts, so you can buy or sell part of a contract. These markets trade in steps of **0.01 contracts** (1% of a contract). A small number of markets, mostly futures, still trade in **whole contracts** only.

## How It Works

When you buy using a dollar amount, the system purchases as many contracts as that amount can cover at the current market price, rounded down to the market's step size: 0.01 contracts on most markets, or 1 contract on whole-contract markets. The amount you enter also covers the trading fee.

Any amount left over stays in your cash balance.

## Example

You want to spend 100 dollars to buy Yes contracts priced at **\$0.65**. To keep the math simple, this example leaves out the trading fee:

* Each contract costs **\$0.65**
* 100 ÷ 0.65 = **153.846...** contracts
* On a market that trades in 0.01-contract steps, that rounds down to **153.84 contracts**
* On a whole-contract market, it rounds down to **153 contracts**

In practice, part of your \$100 pays the trading fee, so you receive slightly fewer contracts. See the [Fee Schedule](/fees) for how the fee is calculated.

## Key Points

* Most markets support fractional contracts in steps of **0.01 contracts**; a small number still trade in **whole contracts** only
* When buying with a dollar amount, you receive the most contracts that amount can cover at the current price, after the trading fee, in the market's step size
* Any amount left over stays in your cash balance


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.