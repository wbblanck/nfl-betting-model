# S1 Live Tracker: Rules

Requested by Will on 2026-10-02: run rule S1 live for the 2026 season and track its record week by week.

- **What runs:** rule S1 exactly as registered (docs/simulator_confirm.md, `screener.score`): DraftKings props where
  all four signals agree, scored from lines fetched at run time (all real books at the same moment), with the
  simulator and projection built from each player's games before the run.
- **When:** `.github/workflows/live-s1.yml` runs before every game window (Thursday afternoon, Saturday morning,
  Sunday before the London, 1 PM, late-afternoon and night games, Monday afternoon); only games that have not
  started are scored. Each run's picks and the games it scored are committed with a timestamp
  (`data/live/s1_picks_2026.csv`, `data/live/s1_runs_2026.csv`; the fetched lines in `data/live/lines/`).
- **Official pick:** for each game, the picks of the last run that scored it before kickoff. Earlier runs stay in
  the files but do not count. Nothing is edited after kickoff.
- **Grading:** every Tuesday (`grade` step) against nflverse stats: W / L / push; a player with no snaps is void (as
  books grade it); 1 unit per pick at the recorded DraftKings price. `docs/s1_live.md` shows the season record,
  each week's W-L, units and ROI, and every pick.
- **What it is not:** S1 is not validated. Its 2025 exploration was 61 bets, +5.2%, interval −16% to +27%. The
  formal verdict is the season-end test in docs/simulator_confirm.md (graded on final lines); this tracker shows
  the same rule at prices that were actually available before kickoff.
- **Injury flag (added 2026-10-03, after week 4's first run):** the model cannot see injury news; it projects from
  each player's past usage. Breece Hall was listed Out on ESPN at 15:26 UTC on 2026-10-02 and the 18:00 run still
  picked Braelon Allen's rush attempts under 14.5 (model 5.2 carries, built from Hall's weeks as the starter). Each
  run now fetches ESPN's injury statuses (archived in `data/live/injuries/`) and marks a pick **against** when it is
  an under whose teammate at the same position (QB / RB / WR+TE, played in the team's last 3 weeks) is Out,
  Doubtful or on IR, or an over whose player is himself listed. Descriptive only: S1 is unchanged, flagged picks
  are still recorded and graded, and `docs/s1_live.md` shows the record with and without them. A rule that drops
  flagged picks would be a new hypothesis and needs its own pre-registration before it is judged.
- **Depth-chart flag (added 2026-10-03):** QB and RB only. Each run fetches every team's ESPN depth chart
  (archived in `data/live/depth/`). A team has a role change when its listed starter (highest-ranked player not
  Out / Doubtful / IR) differs from the player who led it in attempts (QB) or carries (RB) over its last 3 weeks,
  and that leader is healthy (an injured leader is the injury flag's case). A pick is **against** when it is an
  under on the new starter or an over on the old leader in that position's markets; receiving picks on a team whose
  QB changed get a note. WRs and TEs are left out: TE order often reflects blocking roles. Probe and reasoning:
  `src/nflbet/depth.py`, `docs/evidence/espn_depth/`. Descriptive only, like the injury flag.
- **Start times (from 2026-10-03):** GitHub started the Saturday 14:00 UTC run at 17:46, so Claude routines
  dispatch `live-s1.yml` on time (America/New_York): Sun/Sat 8:50 AM and 11:50 AM (London and 1 PM games), 3:05 PM
  and 7:05 PM (late afternoon and night games), Thu 11:05 AM and 7:05 PM, Mon 6:05 PM and 7:05 PM. Each lands after
  the inactives list (~90 min before kickoff) and before kickoff. The workflow's own cron stays as a fallback; a
  duplicate run is harmless (the last run before kickoff is the official one).
