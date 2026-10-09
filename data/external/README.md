# External snapshots

`coverage_fantasypoints_2026_w1-4.csv` — defensive coverage usage by team, 2026 weeks 1-4, transcribed by hand from two
tables posted by @fball_insights (sources named on the images: Fantasy Points Data Suite, nflfastR). Provided by Will on
2026-10-07; not fetched by any script and not independently verified.

- `expected_pass_situations`: coverage shares on expected pass plays. `all_plays`: shares on all plays, plus `epa_per_db`.
- Columns are percentages: man = cov0, cov1, cov2man; zone = cov2, cov3, cov4, cov6.
- The seven listed shares sum to 85-98% per team, not 100%: the tables show only these coverages. `man_total` and
  `zone_total` are sums of the listed columns only.
- A single season-to-date snapshot, so it includes the games being reviewed. Use as recap context only; it is not a
  pre-game input (the repo rule on look-ahead applies).

## Team pass-rush and coverage stats (built 2026-10-09, `scripts/build_team_stats.py`, `src/nflbet/teamstats.py`)
- `team_pass_participation_2016_2025.csv`: nflverse participation joined to play-by-play dropbacks; per team-game
  pressure rate generated / allowed, time to throw, man vs zone share, coverage shells (Cover 0/1/2/2-man/3/4/6/9,
  combo), mean pass rushers, 5+ rusher rate, box count. Coverage fields are partial before 2022 and absent in 2016.
  nflverse publishes a season's participation only after it ends, so there is no 2026 file yet.
- `team_ftn_2022_2026.csv`: FTN charting via nflverse (CC-BY-SA 4.0, credit FTN Data via nflverse), current season
  included; per team-game blitz rate, pass rushers, box count (dropbacks) and offensive play-action, motion, screen
  and no-huddle rates. Check: on 2024 the two sources' mean pass rushers per team-game correlate 0.999 (4.25 vs 4.26).
- Live coverage (man / zone, shells) for 2026 still comes only from Will's hand-supplied tables.
