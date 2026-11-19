# SportsGameOdds probe (2026-11-19)

Evidence only. Run 44583345933 of `sgo-probe.yml`, secret `SPORTSGAMEODDS`, 5 objects used of 2,500.

| Check | Result |
|---|---|
| Plan (`/account/usage`) | `tier: amateur`: 10 requests/min, 2,500 objects/month. Each event returned = 1 object, all markets included; an empty answer still counts 1. Usage calls did not count. |
| Books on this key (NFL) | draftkings, fanduel, espnbet, bovada, caesars, betmgm, pointsbet, unibet, williamhill. No pinnacle, kalshi, polymarket. Every answer carried a `notice` that thousands of bookmaker odds were withheld (5,624 on the upcoming game). |
| Upcoming game (IND @ HOU, 2026-11-20) | 1,692 oddIDs, 1,421 player props; `openOdds`/`openOverUnder` per book; no close yet. |
| Finalized 2026 game (WAS @ NYG, 2026-11-13) | `includeOpenCloseOdds=true` gives per-book `closeOdds`/`closeOverUnder` on 2,837 of 2,844 quotes; all 98 DK passing/rushing/receiving yards O/U quotes have a close. Docs: close = "odds at event start time at this book". Result `score` per market. |
| Finalized 2025 game (LV @ DEN, 2025-11-06) | 902 props but no open/close fields; 257 of 1,933 quotes last updated before kickoff, so `odds` is not a close. |
| Finalized 2024 game (CIN @ BAL, 2024-11-07) | 68 book quotes in all, none updated before kickoff. |
| 2022 window | no events. |

Docs (llms-full.txt, saved here): "Historical data from 2024+ is included in all plans. Extended historical data
(2020+) available on Pro/AllStar plans." Pro is $499/month; Rookie $149/month (77 books). No line-history endpoint:
only current, open and close per book; streaming is AllStar only. The docs do not say which plan includes Pinnacle.

Not yet known: from which 2026 week close fields exist; whether SGO's close matches our own ~6-minute pre-kickoff
DK/FD snapshots (`props-close.yml`).
