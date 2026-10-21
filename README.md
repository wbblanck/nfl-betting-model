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
- `src/nflbet/` one package in layers; each layer imports only the ones above it (`tests/test_foundation.py`):
  - `quant/` shared odds and fee arithmetic (implied probability, de-vig, American/decimal, profit, taker fee)
  - `execution/` shared run clock and run/record files for the live trackers (runs pipelines; places no bets)
  - `sources/` one reader per feed (Action Network archives, ParlayAPI, OpenMarkets, Polymarket US, Novig, Kalshi,
    ESPN, nflverse team stats, SBRO and ASB odds files), the HTTP client, and team/name keys (`ids.py`)
  - `props/` player-prop research and the S1 tracker: `core.py` joins lines to nflverse outcomes; `confirm.py`,
    `selective.py`, `projection.py` the rules; `player_proj.py`, `sim.py`, `screener.py`; `live.py` (S1),
    `bestprice.py`, `explain.py`, `recap.py`
  - `ats/` spread rating (`rating.py`) and the live ATS tracker (`live.py`)
  - `dashboard.py` the tracker page, built from both trackers' records
- Pre-registrations and reports written before 2026-10-21 name modules by their old flat paths
  (`src/nflbet/props.py` is now `props/core.py`, `props_confirm.py` is `props/confirm.py`, and so on); the
  commit that moved them keeps each file's history (`git log --follow`).
- `scripts/grade_2026.py` grades R1-R3 and P1
- `docs/` pre-registrations, exploration output, reports; `docs/PROVENANCE.md` for where and when each was committed

```bash
pip install -e ".[dev]" && pytest -q
python scripts/grade_2026.py
```
