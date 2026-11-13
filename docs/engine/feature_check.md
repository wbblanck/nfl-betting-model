# Feature leakage check (engine phase 2 gate)

Written by `scripts/engine_feature_check.py` from the local warehouse. For each cut-off, every raw row of every
game kicking off at or after it is scrambled (player stats, snap counts, play-by-play, participation), the whole
pipeline is rebuilt, and the feature rows up to the cut-off are compared with the originals.

Feature table: 121,882 player-games (97,410 played, the rest on the game-day active list without playing), 208 columns, seasons 2010-2025; contents hash `69e60144acf4eea5`.

| Cut-off kickoff | Games scrambled | Rows up to cut-off | Identical | Later rows changed |
|---|---|---|---|---|
| 2019-10-13 13:00 | 1,791 | 72,316 | yes | yes |
| 2023-11-12 13:00 | 678 | 103,309 | yes | yes |
| 2025-12-25 13:00 | 32 | 121,026 | yes | yes |

Rows at the cut-off kickoff itself are among those compared: their own game is scrambled and their features do not move.
'Later rows changed' confirms the scramble was real.

Result: **PASS**
