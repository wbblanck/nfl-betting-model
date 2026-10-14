> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Parlay Settlement

> How an executed RFQ parlay grades, and how its payout is computed

<Note>
  **Effective Thursday, August 20, 2026.** Parlay payout is now a scalar of the legs' resolved values instead of refunding
  the full stake on any void.
</Note>

An executed parlay settles as a **single position** — there is no partial settlement, and RFQ parlays are **never repriced**.
A lost leg settles the parlay as a loss immediately, even while other legs are still ungraded. Otherwise, the parlay stays
open until every leg has graded.

## Payout is the product of the legs' values

Each leg resolves to a value between `0` and `1`:

* **Win** → `1`
* **Loss** → `0`
* **Void (FMV)** → the leg's **fair market value (FMV)** price, e.g. `0.5`

The parlay pays `stake × quoted price × scalar`, where the **scalar is the product of every leg's value**. The taker is paid
that amount; you (the maker) retain the remainder of your collateral.

| Example legs | Leg values | Scalar | Parlay result |
| - | - | - | - |
| Loss, other legs still ungraded | 0, —, — | **0** | Loss — settles immediately, without waiting on the other legs |
| Loss + FMV + win | 0, 0.5, 1 | **0** | Loss — a lost leg zeroes the payout even with a void elsewhere |
| Loss + win + win | 0, 1, 1 | **0** | Loss — you receive the stake plus your collateral |
| Win + FMV (0.5) + win | 1, 0.5, 1 | **0.5** | Taker paid `0.5` |
| Win + win + win | 1, 1, 1 | **1** | Full win — taker paid at the quoted price |
| No leg lost, one still ungraded | 1, —, 1 | — | Parlay stays open; nothing settles until every leg does |

<Warning>
  This replaces the previous rule, where any voided leg refunded the taker's **entire** stake regardless of how the other
  legs graded — including a parlay with a genuine losing leg. A loss elsewhere in the parlay is no longer forgiven by a
  void: the loss's `0` value zeroes the whole product, so a parlay that lost still loses and your collateral is returned to
  you as the maker.
</Warning>

## Status precedence

<Steps>
  <Step title="Any leg lost">
    The parlay settles immediately as a loss, for zero payout — even if other legs are still ungraded. You (the maker)
    receive the stake plus your collateral.
  </Step>

  <Step title="Otherwise, any leg still ungraded">
    The parlay stays open and is not settled yet.
  </Step>

  <Step title="Otherwise, compute the payout">
    Every leg has graded and none lost. Multiply every leg's win / FMV value together for the payout scalar.
  </Step>
</Steps>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.