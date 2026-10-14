> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# RFQ Eligibility

> Which markets and leagues can appear together in a parlay RFQ

There is **no restricted list of leagues or market types**. Every market listed on the exchange — mainlines, player props, and futures, across every league, pregame or live — is combo-eligible. A parlay generates an RFQ unless it breaks one of these rules:

* **2–20 legs.** Single legs route to the order book, never to RFQ.
* Every leg's event must be **open** (pregame or in-game).
* No special/custom promo markets, and no NO side of yes/no futures.
* **Same game** is allowed, except pairs that collapse into one position (e.g. spread + moneyline, total + total).
* **Same player**: blocked when one stat contains the other (e.g. PRA + Points) or the market type is identical.
* **Different games** can't share a team.
* **Futures** combine with anything outside their own league only.

<Note>
  The blocked-pair lists are tuned over time — the examples are illustrative, not exhaustive. Your pricer sees the resolved
  legs on `/quote` and can decline any request with a 204.
</Note>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.