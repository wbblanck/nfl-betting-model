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
