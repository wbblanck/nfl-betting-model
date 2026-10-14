> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# API Changelog

> This changelog is specific to our API users and EMM's

<Update label="October 15, 2026 - Live Taker Fee Rises to 0.06">
  On Thursday, October 15, 2026, the live taker fee coefficient will rise from `0.03` to `0.06` on every straight contract, including NFL. The fee is still charged only while the event is in-game, and pregame trading stays free. The Maker Credit stays at 50% of the taker fee, so makers earn twice as much per in-game fill. See [Trading fees](/api/concepts/fees) and the [Maker Credit Program](/maker-credit-program).
</Update>

<Update label="October 14, 2026 - Soccer Team Totals and 1H Totals">
  **New soccer totals.** Every soccer match now lists team totals (`TEAM_TOTAL`) and first-half totals (`TOTAL_1H`).

  These go live with our production release on October 14. If your client filters by market type, add `TEAM_TOTAL` and `TOTAL_1H` to see these markets.
</Update>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.