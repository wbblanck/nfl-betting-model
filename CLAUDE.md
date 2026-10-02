# nfl-betting-model: NFL player-prop research

Owner: Will. Analysis only: ROI, CLV and log loss in backtests are fine; no pick lists or "bet this", with one
exception Will asked for (2026-10-02): the S1 live tracker (docs/s1_live_rules.md) records rule S1's picks before
kickoff and grades them, labeled as unvalidated. No other pick list.

## Standing rules
- Never state a number that was not computed or looked up in the same session; recompute from committed files.
- Pre-register every test (rules, sample, pass criteria) and commit it before the data it runs on is fetched or
  read. Exploration only on a season declared in advance; anything found there is a hypothesis until confirmed
  once on a held-out season, with Bonferroni over the rules taken forward. "Nothing survives" is a valid result.
- Never add a hypothesis because a held-out result looked interesting. Interim looks are descriptive.
- Validate new analysis code on known answers first (hand cases; planted signal found, noise not).
- Season roles so far: 2024 and 2025 explored; 2026 is the test season for R1-R3 and P1 (README).

## Data traps (each already caused a bug)
- **Partial-game props:** from 2025 week 13 Action Network files first-half/quarter props under the same market
  type. The fetch keeps `period == "event"` only, and `props.load_lines` refuses a file where a book has two
  two-sided lines for one prop. Do not remove either.
- **No timestamps:** Action Network lines carry none; two books' lines may not have been live at the same time.
  Book 15 (Consensus) and 30 (Open) are not books.
- **Junk quotes:** some BetMGM prices are implausible pregame (e.g. 1.5 passing TDs at +220/−300 vs DK −115/−115).
  Screen: de-vigged P(over) 0.35-0.65, hold < 10%.
- **NFL scoreboard ignores `date`:** use `season=&week=`.
- **Players who played without a stat row** are missing from nflverse player stats: graded 0 via snap counts;
  no snaps = void (as books grade).
- **Blank player team** in Action Network: match against both teams in the game; name match, else last name +
  first initial; never guess.
- Sandbox cannot reach Action Network; fetch in GitHub Actions. Scheduled workflows run only from `main`.

## Agent team rules
- Teammates (`.claude/agents/`: ux, backend on Sonnet at medium effort in their own worktrees; adversary on
  Fable) claim subtasks from the team's shared task list and settle contracts with each other directly.
- Teammates must request a security review from the `adversary` teammate, and address or answer every finding,
  before opening a pull request for the lead session.
