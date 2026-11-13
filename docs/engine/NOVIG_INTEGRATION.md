# Novig integration

Facts below come from the saved docs and probes (`docs/evidence/novig_docs/`, `novig_probe/`, `novig_spread_probe/`)
and the reader in `src/nflbet/sources/venues.py`. Everything is read-only through the public catalog; no key is used.

## Recording (`scripts/fetch/novig_books.py`, workflow `novig-books.yml`)
- Each run saves `data/live/novig_books/<UTC stamp>/`:
  - `events.json.gz`, `markets.json.gz`: this week's NFL events and every market of the registry's Novig types plus
    MONEY, SPREAD, TOTAL and TEAM_TOTAL, exactly as returned. A market row carries each outcome's best resting bid
    and quantity, its fee record, void rule, status, volume and open interest.
  - `books.jsonl.gz`: for open prop markets with a bid whose game starts within 6 hours, the book at depth 20
    (Novig's maximum), one per line with the time it was fetched and Novig's `seq`.
  - `summary.json`: counts by type, books wanted and saved, errors by kind.
- The run goes red if the catalog cannot be read, returns no markets, or more than half the wanted books fail.
- Scheduled runs fire only from `main`, and GitHub starts them late. The first two (Thursday 2026-11-12, set for
  21:40 and 23:10 UTC) started at 02:08 and 03:23, after kickoff, and saved no books; that night's books exist only
  because of a manual run at 22:57. Each game window now has two runs, about 6 h and 3.5 h before kickoff, with a
  6-hour book window, so the early run still lands before kickoff when it is 4.5 h late. A game's books can still be
  missed if both runs are later than that.
- Size: the one-game Thursday snapshot was about 420 KB of catalog plus 255 KB of books. A nine-game Sunday window
  will be several times that per run; repo growth is to be watched.
- Limits to state plainly: these are snapshots minutes to days apart, not a tick history; the catalog row and a
  book are read at different moments (both times are saved); a quote seen is not a fill.
- Novig's daily `trades.csv` / `markets.csv` files named in the blueprint are not fetched yet; their location was
  not in the saved docs. Add once located.

## On-time runs from an outside cron service (Will's choice, 2026-11-13)
GitHub's schedule is late, and a Claude scheduled task that starts a fresh session has no GitHub access (tried once
on 2026-11-13: it could not start the workflow). So an outside cron service starts the recorder on time by calling
GitHub's workflow-dispatch endpoint. Will sets this up; the token is never committed or shared.
- Token: fine-grained, repository `wbblanck/nfl-betting-model` only, permission Actions: read and write.
- Request: `POST https://api.github.com/repos/wbblanck/nfl-betting-model/actions/workflows/novig-books.yml/dispatches`
  with headers `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`,
  `X-GitHub-Api-Version: 2022-11-28`, `Content-Type: application/json` and body
  `{"ref":"main","inputs":{"hours":"4"}}`. Success is HTTP 204.
- Jobs, Eastern time, about 2.5 hours before kickoff: Thursday and Monday 17:45; Sunday 10:30, 13:35 and 17:50.
  Thanksgiving, Saturday and London games need one-off jobs.
- GitHub's own schedule stays as the backup until the outside jobs are confirmed, then its game-window runs are trimmed.

## Contract identity (`engine/contracts.py`)
A Novig market becomes a `Contract` only if all of these hold; otherwise it is recorded with the reason and never priced:
- its `marketType` is in `config/markets.yaml`;
- its event is in the same snapshot and reads `Away @ Home` with two known teams;
- its description reads exactly `Player <line> <TYPE>` with the same type (this rejects partial-game text and
  combined-stat look-alikes);
- `strike` equals the line in the description, and the line ends in .5 (push handling on whole lines is unconfirmed);
- it has exactly two outcomes, `Over <line>` and `Under <line>`.
The player is resolved against that week's roster for the game's two teams: full normalized name, else last name +
first initial, and a tie at either step is "ambiguous" and stays unmatched (CLAUDE.md: never guess).
Not yet verified, so stated as open: Novig's overtime treatment for player props, and how `voids: FMV` (settle at
fair market value) should be graded when a player is inactive. Until verified, FMV-voided contracts are excluded
from any result rather than graded.

## Cost (`engine/pricing.py`)
- Every Novig order buys an outcome. A resting order at price q on Under is an offer of Over at 1 - q. So the cost
  of Over is read from the Under side of the book, and the bid shown on Over is not a price Over can be bought at.
- `take(other_side_orders, contracts, limit)` walks levels cheapest first, reports partial fills and the worst
  level, and never crosses the limit. Prices are integer mills; one contract pays 1 cent.
- Fee: `coefficient x P x (1 - P)` per $1 of payout from the market's own `fee` record (`charged`: `ALWAYS`, or
  `WHEN_LIVE` = only once the game is in play). An unknown rule raises. Maker credit is recorded, not modelled.
- EV per $1 of payout = model probability - cost - fee; as a return on the outlay it is that over (cost + fee).
  The blueprint's 3% threshold is on the return, at the cost for the intended size, not at the top of book.

## Not built
Authentication, order placement, cancellation, fills, positions, RFQ parlays. The saved docs describe them; none is
implemented, and `tests/test_engine.py` fails if a POST/PUT/DELETE call or an execution path appears in the engine.
Parlays: the joint probability can come from the simulator; the blueprint's own fee note says API parlays cannot be
taken, so parlays stay a modelling output only.
