# SportsGameOdds post-game closes (record only)

Written 2026-11-19, before any SGO close was compared with our own snapshots. Will approved building the recorder in
the project thread the same day.

## What it records
- `scripts/fetch/sgo_closes.py run` (workflow `sgo-closes.yml`, daily) fetches finalized 2026 NFL games from
  SportsGameOdds (secret `SPORTSGAMEODDS`, free Amateur tier: 2,500 objects a month, 10 requests a minute; one game =
  one object with every market) with `includeOpenCloseOdds=true`.
- One gzipped CSV per game in `data/live/sgo/2026/`: every full-game market side at each of the free tier's 9 books
  (DraftKings, FanDuel, ESPN BET, Bovada, Caesars, BetMGM, PointsBet, Unibet, William Hill) with open, close (the
  book's price at the event's start time, per SGO's docs), last seen price and time, and SGO's result value.
  Our nine prop markets carry `market` and `nkey` so they join to ParlayAPI rows. Index: `data/live/sgo/events_2026.csv`.
- No Pinnacle, no exchanges on this tier. 2025 games carry no open/close (probe, docs/evidence/sgo_probe/README.md).

## What it is not
Record only and unvalidated. It feeds no tracker, pick, paper fill or pre-registered test (D1/D2, mix rule K/Mo,
Test M, props CLV); using it in any of them needs a dated amendment first. It never stores the account usage answer,
which contains the account email.

## Check (fixed before running)
`scripts/sgo_check.py` compares SGO's DK and FanDuel close (over side, our nine markets) with the same prop in our
latest ParlayAPI snapshot taken before kickoff, by how long before kickoff that snapshot was.
SGO's close counts as usable for DK/FanDuel only if, among props whose snapshot was 0-30 minutes before kickoff
(0-2 hours if that bucket has fewer than 100 props), at least 90% have the same line and at least 80% have the same
line with the over price within 10 cents. Otherwise it is labeled unreliable in this file and the dashboard never
shows it. Re-run once the props-close job's ~6-minute DK/FD snapshots (`data/live/close/books_2026.csv`) exist.

## Results
Backfill 2026-11-19 (run 44640767769): 150 games, 2026-09-10 to 2026-11-17 (weeks 1-10). Every game has a close on
at least 98.5% of its rows, so SGO's closes go back to week 1.

Check (`docs/sgo_close_check.md`), 0-30 minute bucket (408 DK and 443 FanDuel props, so the 2-hour fallback is not
used): DraftKings 76.7% same line, 72.5% same line with price within 10 cents; FanDuel 95.9% and 95.5%.
**The criterion is not met as a whole: DraftKings fails both thresholds. FanDuel alone meets both.** Agreement falls
as the snapshot gets older for both books, which fits late line moves; whether DK's gap is SGO's fault or DK moving
in the last minutes (or ParlayAPI's DK feed lagging) is not known. SGO's DK close stays labeled unreliable; re-run the
check once the ~6-minute props-close snapshots exist.

Disclosure: while building the check (2026-11-19, before this file was committed) I ran it on the one probe game
(WAS @ NYG, 2026-11-13) to make sure it worked. With snapshots 27 minutes before kickoff, FanDuel matched 32 of 34
lines and DraftKings 29 of 41; DK's misses were mostly 1-point moves. The criterion above was written before that
run and was not changed after it. Only snapshots from the 7 days before kickoff are used (that run had matched a
snapshot from an earlier meeting of the same teams, which this rule removes).
