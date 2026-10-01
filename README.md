# nfl-betting-model

Research on NFL player props: pre-registered tests of betting rules against Action Network's historical lines
(DraftKings, FanDuel, BetRivers, BetMGM; 2024 onward), graded with nflverse player stats. Analysis only; no
pick lists.

## Status

| Test | Seasons | Result |
|---|---|---|
| Under at the highest line when books disagree | explore 2024, confirm 2025 | **Fail**: +2.3% ROI (−0.2% to +4.8%), 3,198 bets (`docs/props_confirm_report.md`) |
| R1 three+ books quote the prop | explore 2025 (+4.5%), test 2026 | pending, judged after the 2026 regular season |
| R2 high line's under priced below −120 | explore 2025 (+7.3%), test 2026 | pending |
| R3 high line at BetRivers or BetMGM | explore 2025 (+7.1%), test 2026 | pending |
| P1 projection ≥ 10% under DraftKings' high line, books disagree | fit 2024, check 2025 (+5.9%), test 2026 | pending |

Interim 2026 numbers (descriptive only): `docs/grade_2026.md`, refreshed every Tuesday by `fetch-props.yml`.

## Layout

- `scripts/fetch/an_props.py` fetch one season (refuses held-out seasons without a pre-registration)
- `src/nflbet/props.py` join lines to nflverse outcomes; data checks
- `src/nflbet/props_confirm.py`, `props_selective.py`, `props_projection.py` the rules
- `src/nflbet/player_proj.py` pre-game projection (usage, implied team points, opponent allowance)
- `scripts/grade_2026.py` grades R1-R3 and P1
- `docs/` pre-registrations, exploration output, reports; `docs/PROVENANCE.md` for where and when each was committed

```bash
pip install -e ".[dev]" && pytest -q
python scripts/grade_2026.py
```
