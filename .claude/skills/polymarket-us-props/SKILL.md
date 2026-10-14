---
name: polymarket-us-props
description: Read player-prop prices from Polymarket US (any sport) and turn them into an all-in cost per $1 of payout, including the taker fee. Use when fetching, parsing, pricing or comparing Polymarket US props or game markets (gateway.polymarket.us), or when matching them to sportsbook lines. Read-only market data; not for placing orders.
---

# Polymarket US player props: reading prices and computing all-in cost

Everything below is marked **verified** (seen in our own runs or saved data, with the evidence file and date) or
**documented, untested** (stated in Polymarket US's docs, never called by us). Facts are as of 2026-10-14. Markets,
coverage and fees change: re-check anything a result depends on, and add new evidence when you do.

Polymarket US (`polymarket.us`) is a separate exchange from Polymarket's international site (`polymarket.com`).
Never use docs.polymarket.com for US facts: its fee table (Sports 0.05) does not apply here.

Working code: `src/nflbet/venues.py` (`pm_get`, `pm_slugs`, `pm_markets`, `pm_quotes`, `pm_fee`, `pm_game`). It is NFL-only
today (`PM_MAP` and `PM_PAT` match the NFL "record N+" wording); other sports need the "at least N" pattern below.

## Two APIs

| Host | Use | Key |
| - | - | - |
| `https://gateway.polymarket.us` | Public market data: events, markets, books, BBO, price history, sports, search | None (**verified**) |
| `https://api.polymarket.us` | Trading, portfolio, account; websockets `wss://api.polymarket.us/v1/ws/markets` and `/v1/ws/private` | Signed key (documented, untested) |

Source: `docs/evidence/polymarket_us_docs/20261014T140631Z/api-reference_introduction.md`, `api-reference_authentication.md`,
`api-reference_websocket_overview.md`. Authenticated requests carry `X-PM-Access-Key`, `X-PM-Timestamp` (ms, within 30 s of
server time) and `X-PM-Signature` (Ed25519 over `timestamp + method + path`). Keys come from polymarket.us/developer after
identity verification. Even the market-data websocket needs a key.

Rate limits (documented, `api-reference_rate-limits.md`): the "Retail API" allows 25 requests/s per source IP (shared across
keys on that IP); a 429 means stop, wait at least 1 s, back off exponentially. The page does not say whether the public
gateway shares this limit. Our probes paced requests 0.15-0.3 s apart and retried on 429.

## Finding a sport's games

1. **League slugs** (verified): `GET /v1/sports` returns `{"sports": [{"sport": "nfl", ...}, ...]}`; the slug is the `sport`
   key (`nfl`, `cfb`, `nba`, `wnba`, `mlb`, `nhl`, `epl`, `ucl`, `mls`, `atp`, `wta`, `ufc`, ... several hundred in all).
2. **Games in a league** (verified 2026-10-14 for 26 leagues, all HTTP 200): `GET /v2/leagues/{slug}/events?limit=50`.
   Documented params: `limit`, `offset`, `excludeEventId`, `type` (`sport` default, or `futures`), `section`.
   Events carry `slug`, `title`, `startTime`, `seriesSlug`, `markets`, `teams`, `participants`, `gameId`, `sportradarGameId`.
3. **Full game with its props** (verified): `GET /v1/events/slug/{slug}` returns `{"event": {...}}` with every market.
   Fetch each game this way.

Pitfalls (verified):
- `GET /v1/search` returns games but embeds only part of their markets and **no player props** (NFL, 2026-10-14,
  `docs/evidence/polymarket_week_probe/`). `limit=20` works; `limit=50` returned an error (code 5). Season-long markets
  crowd the 20 results. Searching by sport name misses games whose titles are not "X vs. Y".
- `GET /v1/events` without filters lists from the oldest events (2025). It ignores `seriesSlug`, `tag` and `league`
  (not documented params); `active`, `closed` and `startDateMin` do filter. Documented filters include `seriesId`,
  `tagSlug`, `startTimeMin/Max`, `sportsMarketTypes`, `gameId`, `includePopularPlayerProps` (untested).
- Props appear close to the game. On 2026-10-14 the NFL games 1-4 days out had 626-714 markets each with player props;
  games 11 days out had about 400 markets and none.

Event slugs (verified): `{league}-{team1}-{team2}-{ET date}`, e.g. `nfl-sea-den-2026-10-15`, `nhl-mon-was-2026-10-14`,
`mlb-mil-lad-2026-10-14`, `ucl-rom-rma-2026-10-14`. For the NFL, team1 is the away team (checked on week 5-6 games);
for other leagues the order is not checked. Team codes differ by place: NFL Rams `lar` in slugs but "LA Rams" in titles,
Jaguars `jax` in slugs but "JAC" in titles, Canadiens `mon` in slugs and team objects but "MTL" in titles.

## Player-prop markets

A player prop has `marketType` `props` and `sportsMarketType` `{sport}_player_{stat}`. Threshold markets have slugs like
`astatc-{event slug}-{stat}-{player code}-gte{N}` (e.g. `astatc-mlb-mil-lad-2026-10-14-ha-robgas-gte2`); first-TD markets
end without `gte` (`astatc-nfl-sea-den-2026-10-15-firsttd-adatra`). `line` holds N (MLB "at least 2" has `line` 2; NFL "4+" has `line` 4).
For an integer stat, "N or more" is the over at N - 0.5.

Coverage on 2026-10-14 (`docs/evidence/polymarket_sports_probe/20261014T141314Z/probe.json`, the soonest 3 games per league):

| League | Player-prop types seen | Question format |
| - | - | - |
| NFL | receiving yards, receptions, touchdowns, rushing yards, passing yards / TDs / attempts / completions, rushing attempts, interceptions thrown, longest reception, scrimmage yards, fantasy points (PPR), first TD, team first TD, most passing yards | `Will Bo Nix record 100+ passing yards?`; `Will Bo Nix throw 1+ interceptions?`; `Will X score the first touchdown?`; `Will X record the most passing yards?` |
| MLB | hits + runs + RBIs, total bases, hits, RBIs, home runs, pitcher strikeouts, stolen bases, hits / walks / earned runs allowed, outs | `Will Mookie Betts record at least 2 total bases in Game 3: MIL Brewers vs. LA Dodgers?` |
| NHL | points, goals, assists | `Will Nick Suzuki record at least 1 points in MTL vs WSH?` |
| Soccer (UCL, MLS) | goals | `Will Breel Embolo record at least 1 goals in MIM vs ATL?` |

No player props in that sample for CFB, NBA, WNBA, EPL, La Liga, Bundesliga, ATP, WTA, UFC, NPB,
EuroLeague, NBL, CS2, LoL; none listed for CBB, PFL, KBO, PLL. Absence on one day is not absence in general.

## Price = the side's quote (verified)

Each market is **one instrument**. Buying Yes is going long; buying No is recorded as a short of the same instrument
(documented: `learn_trading_basics_buying-yes-vs-selling-no.md`). The price to buy each side:

- **Yes** = `marketSides[description == "Yes"].quote.value` = market `bestAskQuote.value`
- **No** = `marketSides[description == "No"].quote.value` = 1 - market `bestBidQuote.value`

Checked on 1,120 of 1,120 markets with both quotes and a best bid/ask
(`docs/evidence/polymarket_compare/20261014T091724Z/polymarket_props.json.gz`). Quote Yes + quote No - 1 is the bid-ask
spread. Do **not** use `marketSides[].price`: on 2026-10-10 its Yes + No summed to a median 0.81, which is not a market.
Markets with no quote on a side have no book on that side; skip them. On 2026-10-14 the share of markets with both
sides quoted was NFL 77%, MLB 91%, NHL 69%, UCL 71%, MLS 71%.

**Size behind a price** (verified 2026-10-14 on 20 NFL prop markets, `docs/evidence/polymarket_book_probe/`):
`GET /v1/markets/{market slug}/book` returns `marketData.bids` and `marketData.offers`, each a list of
`{"px": {"value": "0.67"}, "qty": "28"}` sorted best price first (bids high to low, offers low to high). The best offer
equalled `bestAskQuote` and the best bid `bestBidQuote` on 20 of 20. One contract pays $1, so `qty` is dollars of payout:
buying Yes takes the best offer's quantity, buying No sells into the best bid's quantity. `src/nflbet/venues.py` `pm_sizes`
reads it. Sizes at the best price were often $1-$50 and spreads wide (bid 0.67, offer 0.98) four days before kickoff.

`GET /v1/markets/{slug}/bbo` (verified on the same 20) returns `bestBid`, `bestAsk`, `bidShares`, `askShares` (all levels
summed), and `longQuote` = best ask (Yes cost) and `shortQuote` = 1 - best bid (No cost). On one market its best bid
(0.47) differed from the book read a moment earlier (0.61); read the book when the size matters.

Documented, untested: `GET /v1/price-history?symbol={market slug}` with `fixedInterval` and `fidelity`, or
`timestamp.startTimestamp` / `timestamp.endTimestamp`.

## Fees (verified from the Polymarket US fee schedule)

Source: `docs/evidence/polymarket_us_docs/20261014T140631Z/fees.md` and `docs/evidence/polymarket_us/fee_schedule_20261014.md`,
effective exchange-wide from 10 AM ET, 2026-10-07.

- Taker fee per fill = Θ × C × p × (1 - p), with C contracts at price p. Θ = **0.0695** for every market except
  Table Tennis (0.10). Every market seen on 2026-10-14, in all leagues, carried `feeCoefficient` 0.0695; read that field
  per market rather than assuming it.
- Each fill's fee is rounded to the nearest $0.01 (banker's rounding), so small trades can round to $0.00.
- Makers pay no taker fee. Maker rebate: Θ = -0.0125 until 1:00 PM ET, 2026-10-19; then volume tiers (Tier 1, below
  $10,000,000 a month, gets none). Taker rebates start at $250,000 of prior-month taker volume.
- Combos (parlays): taker fee = C × p × [0.0695 × (1 - p) + 0.06 × (1 - p)^4], no maker rebate.

**All-in taker cost per $1 of payout** = p + 0.0695 × p × (1 - p). Compare it with a sportsbook's implied probability
of its American price (vig already included). `src/nflbet/venues.py` `pm_fee` and `src/nflbet/bestprice.py` do this.

## Matching to sportsbook lines

- **No player ID**: the player is only in the question text. Normalise names (`nflbet.props.norm_name` strips suffixes
  like Jr., Sr., III) and match on game + player + stat + line.
- **Teams**: map by nickname, not by the title's first word. NFL titles write both Los Angeles teams as "LA"; a
  first-word key sent every Chargers game to the Rams (fixed 2026-10-14; `venues.pm_game` maps the last word of each
  side to `parlay.TEAMS`). Each market side also carries a `team` object (`id`, `abbreviation`, `league`) that can be
  used instead.
- **Line**: "N+" / "at least N" equals the sportsbook over at N - 0.5 only for integer stats; check before matching
  stats with fractional values.

## Evidence

- `docs/evidence/polymarket_us_docs/20261014T140631Z/`: the docs (323 pages via `llms.txt`; no OpenAPI file).
- `docs/evidence/polymarket_sports_probe/20261014T141314Z/probe.json`: 26 leagues, market types, quotes, fees.
- `docs/evidence/polymarket_week_probe/`: why search misses props; slug lookup 14/14.
- `docs/evidence/polymarket_compare/`: full NFL prop markets with quotes and best bid/ask.
- `docs/evidence/polymarket_us/`: first probes (2026-10-10) and the pasted fee schedule.
- Scripts: `scripts/audit/polymarket_sports_probe.py`, `scripts/audit/polymarket_week_probe.py`,
  `scripts/audit/fetch_docs.py`, `scripts/polymarket_compare.py`. The sandbox cannot reach polymarket.us; run probes in
  GitHub Actions.
