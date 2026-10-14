> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Combos FAQs

> Frequently asked questions about how combos work and how they settle on Polymarket US

## Basics

### What is a combo?

A combo combines 2 to 10 markets into a single position. Each market you add is a leg, and each leg carries the side you took on it, buy or sell. Every leg has to resolve the way you took it for the combo to pay.

A combo is a single position that settles once, at a single value.

### Why does a combo pay more than a single market?

Because all of the legs have to come in together. A combo pays more than any one of those legs would on its own, and it carries correspondingly more risk.

### Does being part of a combo change what a leg is worth?

No. A leg settles inside a combo exactly as it would settle on its own.

## Payouts

### How is a combo payout calculated?

Your payout is the full potential payout multiplied by the value of every leg:

* A leg that resolves the way you took it is worth \$1.00
* A leg that resolves against you is worth \$0.00
* A leg that cannot resolve at all is worth its last fair market price (LFMP)

On an ordinary market, a winning Contract settles at \$1.00 and a losing one at \$0.00. A combo works the same way, except that its value depends on all of its legs at once.

### What happens if every leg wins?

The multipliers are all \$1.00 and you receive the full potential payout. On a \$10 combo quoted to pay \$80, that is \$80.

### What happens if one leg resolves against me?

That leg is worth \$0.00 and the combo pays \$0.00. This holds however the other legs turn out. One leg going against you is enough, and the remaining legs cannot make up for it.

## When a leg cannot resolve

### What does it mean for a leg to be unable to resolve?

Occasionally a leg cannot resolve to Yes or No at all. The usual reasons are that a match is walked over or cancelled before it begins, a listed player does not take part, or an event is postponed and not replayed.

### What happens to that leg?

It settles at its last fair market price (LFMP). The leg is not removed from your combo. It is assigned a fair price, and your payout is multiplied by that price.

### What is last fair market price?

Last fair market price is the prevailing fair market price on the exchange at a specified moment in time, typically the moment an official announcement is made, such as a cancellation, walkover, or no-contest.

### Who decides the price?

That price is determined by the Settlement Committee. Its decisions are final.

### Can a leg at LFMP rescue a combo that already has a losing leg?

No. A leg at LFMP reduces the payout rather than voiding the combo, and it never rescues a combo that already has a losing leg in it.

### How does the payout work out in practice?

Take a \$10 combo with 3 legs that would pay \$80:

| Outcome | Calculation | Payout |
| - | - | - |
| All three legs win | \$80 × 1.00 × 1.00 × 1.00 | \$80.00 |
| Two legs win, third goes to LFMP at \$0.60 | \$80 × 1.00 × 1.00 × 0.60 | \$48.00 |
| One leg wins, other two go to LFMP at \$0.60 and \$0.25 | \$80 × 1.00 × 0.60 × 0.25 | \$12.00 |
| Any leg resolves against you | Whatever happened to the other legs | \$0.00 |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.