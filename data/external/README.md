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

`coverage_fantasypoints_2026_w1-9.csv`: the same two tables for 2026 weeks 1-9, transcribed by hand from two images
Will provided on 2026-11-12 (@fball_insights; sources named on them as before). `all_plays` is the first table of the
post; `expected_pass_situations` is the reply, which defines it as expected pass 70% or more from down, distance, score
and time left. Both carry EPA per dropback here. Listed shares sum to 92.3-98.6% (all plays) and 89.7-98.4% (expected
pass) per team. The expected-pass image was a small phone screenshot, so single digits may be misread; not verified.
Same rule: context for week 10 onward, never a pre-game model input, and not used by the player-prop engine.
The S1 picks page uses the newest table that ends before the pick's week; the weekly recap uses the newest table.

## Team pass-rush and coverage stats (built 2026-10-09, `scripts/build_team_stats.py`, `src/nflbet/teamstats.py`)
- `team_pass_participation_2016_2025.csv`: nflverse participation joined to play-by-play dropbacks; per team-game
  pressure rate generated / allowed, time to throw, man vs zone share, coverage shells (Cover 0/1/2/2-man/3/4/6/9,
  combo), mean pass rushers, 5+ rusher rate, box count. Coverage fields are partial before 2022 and absent in 2016.
  nflverse publishes a season's participation only after it ends, so there is no 2026 file yet.
- `team_ftn_2022_2026.csv`: FTN charting via nflverse (CC-BY-SA 4.0, credit FTN Data via nflverse), current season
  included; per team-game blitz rate, pass rushers, box count (dropbacks) and offensive play-action, motion, screen
  and no-huddle rates. Check: on 2024 the two sources' mean pass rushers per team-game correlate 0.999 (4.25 vs 4.26).
- Live coverage (man / zone, shells) for 2026 still comes only from Will's hand-supplied tables.
