# Warehouse coverage (engine phase 1)

Written by `scripts/engine_coverage.py` from the local warehouse (`data/cache/engine/`, not in git; rebuilt by
`scripts/engine_ingest.py`). Counts and join keys only.

## Sources

| Table | Seasons held | Rows | Not published |
|---|---|---|---|
| depth_charts | 2010-2025 (16) | 1,106,729 | - |
| ftn_charting | 2022-2025 (4) | 185,215 | 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021 |
| injuries | 2010-2025 (16) | 85,931 | - |
| ngs_passing | 2016-2025 (10) | 5,933 | 2010, 2011, 2012, 2013, 2014, 2015 |
| ngs_receiving | 2016-2025 (10) | 14,731 | 2010, 2011, 2012, 2013, 2014, 2015 |
| ngs_rushing | 2016-2025 (10) | 6,059 | 2010, 2011, 2012, 2013, 2014, 2015 |
| participation | 2016-2025 (10) | 478,989 | 2010, 2011, 2012, 2013, 2014, 2015 |
| pbp | 2010-2025 (16) | 770,337 | - |
| player_stats | 2010-2025 (16) | 287,187 | - |
| players | all | 24,869 | - |
| rosters_weekly | 2010-2025 (16) | 656,941 | - |
| schedules | all | 7,548 | - |
| snap_counts | 2013-2025 (13) | 324,612 | 2010, 2011, 2012 |

## Player-week table (QB, RB, WR, TE; regular season)

Stat rows plus a zero row for anyone with offensive snaps and no stat row. Snap counts start in 2013, so
2010-2012 have stat rows only.

| Season | Stat rows | Duplicate keys | Zero rows added | Snap rows | Snap rows with no player ID match | Stat rows with no snap row | Stat rows on that week's roster | Team agrees with roster | Games vs schedule |
|---|---|---|---|---|---|---|---|---|---|
| 2010 | 5,223 | 0 | 0 | 0 | 0 | 5,223 | 100.0% | 100.0% | 256 / 256 |
| 2011 | 5,320 | 0 | 0 | 0 | 0 | 5,320 | 100.0% | 100.0% | 256 / 256 |
| 2012 | 5,320 | 0 | 0 | 0 | 0 | 5,320 | 100.0% | 100.0% | 256 / 256 |
| 2013 | 5,251 | 0 | 661 | 5,616 | 0 | 296 | 100.0% | 100.0% | 256 / 256 |
| 2014 | 5,412 | 0 | 567 | 5,736 | 5 | 248 | 100.0% | 100.0% | 256 / 256 |
| 2015 | 5,423 | 0 | 538 | 5,681 | 1 | 281 | 100.0% | 100.0% | 256 / 256 |
| 2016 | 5,413 | 0 | 581 | 5,743 | 5 | 256 | 100.0% | 100.0% | 256 / 256 |
| 2017 | 5,448 | 0 | 616 | 5,808 | 0 | 256 | 100.0% | 100.0% | 256 / 256 |
| 2018 | 5,363 | 0 | 714 | 5,864 | 0 | 213 | 100.0% | 100.0% | 256 / 256 |
| 2019 | 5,411 | 0 | 630 | 5,805 | 11 | 247 | 100.0% | 100.0% | 256 / 256 |
| 2020 | 5,543 | 0 | 762 | 6,008 | 8 | 305 | 100.0% | 100.0% | 256 / 256 |
| 2021 | 5,866 | 0 | 834 | 6,469 | 8 | 239 | 100.0% | 100.0% | 272 / 272 |
| 2022 | 5,808 | 0 | 836 | 6,403 | 1 | 242 | 100.0% | 100.0% | 271 / 271 |
| 2023 | 5,801 | 0 | 868 | 6,486 | 12 | 195 | 100.0% | 100.0% | 272 / 272 |
| 2024 | 5,864 | 0 | 835 | 6,468 | 14 | 245 | 100.0% | 100.0% | 272 / 272 |
| 2025 | 6,037 | 0 | 710 | 6,394 | 13 | 366 | 100.0% | 100.0% | 272 / 272 |

## Injury report timestamps

| Season | Rows | With `date_modified` | With a game status |
|---|---|---|---|
| 2010 | 4,491 | 98.6% | 93.9% |
| 2011 | 4,971 | 100.0% | 95.0% |
| 2012 | 5,533 | 100.0% | 96.5% |
| 2013 | 5,070 | 100.0% | 97.3% |
| 2014 | 5,078 | 100.0% | 95.6% |
| 2015 | 5,232 | 100.0% | 97.1% |
| 2016 | 5,115 | 100.0% | 60.2% |
| 2017 | 5,104 | 100.0% | 50.6% |
| 2018 | 5,133 | 100.0% | 47.3% |
| 2019 | 5,392 | 100.0% | 47.0% |
| 2020 | 5,661 | 100.0% | 44.8% |
| 2021 | 5,587 | 100.0% | 45.9% |
| 2022 | 5,682 | 100.0% | 48.3% |
| 2023 | 5,599 | 100.0% | 48.6% |
| 2024 | 6,215 | 100.0% | 45.5% |
| 2025 | 6,068 | column absent | 45.9% |

## Participation joined to play-by-play

| Season | Participation plays | Found in play-by-play | Pass plays with a route recorded |
|---|---|---|---|
| 2016 | 48,434 | 98.4% | 84.5% |
| 2017 | 47,998 | 98.4% | 83.4% |
| 2018 | 47,875 | 98.4% | 82.0% |
| 2019 | 48,034 | 98.4% | 80.6% |
| 2020 | 48,513 | 98.3% | 82.2% |
| 2021 | 50,714 | 98.4% | 81.7% |
| 2022 | 50,150 | 98.6% | 80.9% |
| 2023 | 46,168 | 100.0% | 85.3% |
| 2024 | 45,919 | 100.0% | 85.2% |
| 2025 | 45,184 | 100.0% | 85.5% |

## What this means for the build

- Snap counts start in 2013 and participation and Next Gen Stats in 2016, so snap-based role features exist
  for every fit, tune and test season (2018 on) but not for all of the 2010-2017 history window.
- Routes run per player are not in the free nflverse feeds: the participation `route` column is one value per
  pass play, and the nflverse Next Gen Stats files have no routes column. Route participation is derived from
  who was on the field on dropbacks, which overstates it for tight ends and running backs who stay in to block.
- Sumer Sports publishes routes run per player, but its terms of service (read 2026-11-13) forbid automated
  collection and use of its content to develop or train machine-learning models, so it is not used.
- Franchise codes differ between tables in older seasons (for example OAK and LV); `player_week.TEAM_ALIASES`
  maps them, and the roster agreement above is measured after mapping.
- Injury rows carry `date_modified` through 2024 but the 2025 file has no such column, and only about half the
  rows from 2016 on carry a game status. Historical availability inputs are weaker than live ones.
- A few stat rows each season have no snap row and a few snap rows have no player ID match; they are counted
  above and never matched by guessing.
