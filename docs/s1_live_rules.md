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
