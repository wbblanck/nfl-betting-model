# Australia Sports Betting NFL file (supplied by Will, 2026-10-09)

`nfl.xlsx`: downloaded by Will from https://www.aussportsbetting.com/data/ (the site blocks automated downloads).
**Terms: personal use only; do not make this data available on another website.** This repository is private; do
not publish the file or its rows (dashboards, artifacts, public repos). Link to the source instead.

Per the file's notes: Pinnacle 2014 to February 2018, bet365 September 2018 to February 2025, betr from September
2025, footballlocks.com before 2014. Decimal odds (converted to American by `nflbet.asb`).

`../asb_nfl_games.csv`: parsed and matched to nflverse by `nflbet.asb.games()` (2026-10-09): 5,423 games, all
matched; final scores agree on 99.96%; opening/closing spread prices from 2014. Closing spread within 0.5 of
nflverse's: Pinnacle era 98.8%, bet365 era 92.3%, **betr era (2025-26) 58.5% with 8.5% more than 2 points off**:
betr "closing" lines look like post-kickoff or another market and are not used as closing lines.
