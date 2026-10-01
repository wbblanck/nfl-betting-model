# Provenance

This work was built in `wbblanck/NFL_ATS` on branch `claude/nfl-alt-markets` and moved here on 2026-10-01
without changing any rule, number or data file. The pre-registrations are copied word-for-word, so their
file paths are the old ones:

| Path in the pre-registrations | Path here |
|---|---|
| `engine/backtest/props.py`, `props_confirm.py`, `props_selective.py`, `props_projection.py` | `src/nflbet/` (same file names) |
| `engine/models/player_proj.py` | `src/nflbet/player_proj.py` |
| `docs/selective_preregistration.md` (its line-move part belongs to NFL_ATS) | `docs/selective_preregistration.md` |

The order of events is proven by the NFL_ATS commit history (UTC, 2026-10-01). Keep that branch.

| Time | Commit | Event |
|---|---|---|
| 12:21:11 | 9995f81 | 2024 declared the exploration season, before any prop line was fetched |
| 12:35:38 | ad2b478 | 2024 lines fetched |
| 12:41:32 | 73a6d95 | 2025 confirmation pre-registered (one hypothesis) |
| 12:53:19 | d985f0c | 2025 lines fetched |
| 13:01:51 | ef82940 | 2025 re-declared exploration for selective rules; 2026 = confirmation |
| 13:03:41 | b245568 | Selective rules R1-R3 pre-registered for 2026 |
| 13:11:55 | fb56976 | 2026 lines fetched (not read) |
| 13:15:41 | ac2ab78 | Projection model declared (tune 2024-25, test 2026) |
| 13:17:54 | 07d7dc4 | Fetch fixed to full-game props only (partial-game lines found in 2025 wk 13-18) |
| 13:26:48 / 13:36:13 | 04dcc67 / 49f78cf | 2024 and 2025 refetched clean |
| 13:38:05 | b46fa45 | Projection rule P1 pre-registered; R1-R3's 2025 numbers corrected (rules unchanged) |
| 13:44:58 | d502ca3 | 2026 lines refetched clean |

No 2026 prop result was computed before b46fa45. The first 2026 numbers (interim, descriptive) were produced in
this repo by `scripts/grade_2026.py`.
