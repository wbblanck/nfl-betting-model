# ESPN BET Props: Declaration

Committed 2026-10-02 before any ESPN prop file was fetched in full (only the probe sample in
`docs/evidence/espn/` exists: 3 records per game for 4 games).

- ESPN's core API holds ESPN BET (provider 58) player props for 2024 and 2025 with an opening and a final line
  and price. Both seasons are already exploration seasons here; anything found with these files is a
  hypothesis.
- Before any use, the final line must be shown to be pregame: compare it with Action Network's lines for the
  same player-game-market, and check it is not closer to the actual result than those lines are (an in-game
  line would be).
- 2026 has no ESPN BET props (ESPN's book is now DraftKings; its propBets returned 404 for 2026 week 5), so the
  four rules registered for 2026 are unaffected and are not changed on account of this data.
