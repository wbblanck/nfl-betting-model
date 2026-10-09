# Historical NFL game odds

- `sbro/nfl_<start year>.csv`: Sportsbook Review Online's NFL odds archive pages, 2007-08 to 2021-22, every table
  row as published (fetched by `scripts/fetch/sbro_odds.py` in GitHub Actions, 2026-10-09). Source:
  https://www.sportsbookreviewsonline.com/scoresoddsarchives/nfl/nfloddsarchives.htm (no longer updated).
- `sbro_nfl_games.csv`: the same games parsed and matched to nflverse (`nflbet.sbro.games`): home opening and
  closing spread (positive = home favored, nflverse's convention), opening and closing totals, nflverse's closing
  spread for comparison, `score_check` (SBRO final score equals nflverse's) and `sign_flag` (a stray minus sign in
  the archive cell).

Checks (2026-10-09): 4,025 games, all matched to nflverse; final scores agree on 99.98%; regular-season closing
spread equal to nflverse's on 59%, within 0.5 on 89%, within 1 on 96.5%; 12 games with a stray sign. Large
disagreements: SEA-GB 2012 week 3 (SBRO sign looks wrong), KC-NE 2020 week 4 (game postponed, line moved),
CHI-BAL 2021 week 11 (late QB news).

Caveat: the archive does not say which book's opener it shows. An "Open" number may not have been bettable
(CLAUDE.md: Action Network's "Open" matched no checked book), so CLV measured from it is notional.
