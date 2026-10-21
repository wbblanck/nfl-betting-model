"""Known-answer checks for the ParlayAPI second price record (src/nflbet/sources/parlay.py)."""
import polars as pl

from nflbet.sources import parlay as Pa


def _row(**k):
    base = {"bookmaker": "draftkings", "market_key": "player_receiving_yards", "home_team": "Dallas Cowboys",
            "away_team": "Tampa Bay Buccaneers", "period": "FULL", "player": "CeeDee Lamb", "line": 82.5,
            "over_price": -113, "under_price": -111, "last_update": "2026-10-08T05:00:00Z"}
    return {**base, **k}


def test_parse_keeps_two_sided_full_game_s1_rows():
    rows = [_row(),
            _row(bookmaker="fanduel", market_key="player_rec_yds", line=81.5, over_price=-110, under_price=-114),
            _row(under_price=None),                                   # one-sided
            _row(period="1H"),                                        # partial game
            _row(market_key="player_receiving_yards_milestones"),     # not an S1 market
            _row(bookmaker="pinnacle"),                               # not requested
            _row(home_team="Nowhere FC"),                             # unknown team
            _row(line=83.5, last_update="2026-10-07T00:00:00Z")]      # older duplicate of the first row
    d = Pa.parse(rows)
    assert d.height == 2
    dk = d.filter(pl.col("book") == "dk").row(0, named=True)
    assert (dk["market"], dk["line"], dk["game"], dk["nkey"]) == ("rec_yds", 82.5, "DAL|TB", "ceedee lamb")
    assert d.filter(pl.col("book") == "fd")["market"].item() == "rec_yds"


def test_game_key_ignores_home_away_order():
    assert Pa.game_key("PHI", "JAX") == Pa.game_key("JAX", "PHI")


def test_compare_identical_sources_have_zero_gap():
    d = Pa.parse([_row(), _row(player="Dak Prescott", market_key="player_passing_yards", line=266.5, over_price=-112, under_price=-112)])
    c = {r["book"]: r for r in Pa.compare(d, d)}
    assert c["dk"] == {"book": "dk", "n_parlay": 2, "n_an": 2, "n_both": 2, "same_line": 2, "mean_p_gap_pts": 0.0}
    assert c["fd"]["n_both"] == 0 and c["fd"]["mean_p_gap_pts"] is None


def test_compare_counts_line_differences_and_price_gap():
    pa = Pa.parse([_row(), _row(player="Dak Prescott", market_key="player_passing_yards", line=266.5)])
    an = Pa.parse([_row(over_price=-130, under_price=110), _row(player="Dak Prescott", market_key="player_passing_yards", line=265.5)])
    c = {r["book"]: r for r in Pa.compare(pa, an)}["dk"]
    assert (c["n_both"], c["same_line"]) == (2, 1)
    # -113/-111: .5305/(.5305+.5261) = .5021; -130/+110: .5652/(.5652+.4762) = .5427 -> 4.06 points
    assert abs(c["mean_p_gap_pts"] - 4.06) < 0.01


def test_an_lines_reads_dk_and_fanduel(tmp_path):
    f = tmp_path / "an.csv"
    pl.DataFrame({"home": ["DAL", "DAL", "DAL"], "away": ["TB", "TB", "TB"], "player": ["CeeDee Lamb"] * 3,
                  "market": ["rec_yds"] * 3, "book": ["DK NJ", "FanDuel NJ", "BetMGM NJ"], "line": ["82.5", "81.5", "80.5"],
                  "over_odds": ["-113", "-110", "-110"], "under_odds": ["-111", "", "-110"]}).write_csv(f)
    d = Pa.an_lines(f)
    assert d.select("book", "game", "nkey", "line").rows() == [("dk", "DAL|TB", "ceedee lamb", 82.5)]   # FanDuel one-sided


def test_attach_takes_the_picks_side():
    pa = Pa.parse([_row(), _row(bookmaker="fanduel", market_key="player_rec_yds", line=81.5, over_price=-110, under_price=-114)])
    picks = pl.DataFrame({"home": ["DAL", "LA"], "away": ["TB", "BUF"], "player": ["CeeDee Lamb", "Puka Nacua"],
                          "market": ["rec_yds", "rec_yds"], "side": ["under", "over"]})
    out = Pa.attach(picks, pa)
    assert out.row(0, named=True) | {} == {"home": "DAL", "away": "TB", "player": "CeeDee Lamb", "market": "rec_yds", "side": "under",
                                          "pa_dk_line": 82.5, "pa_dk_odds": -111.0, "pa_fd_line": 81.5, "pa_fd_odds": -114.0}
    assert out.row(1, named=True)["pa_dk_line"] is None
    assert Pa.attach(picks, None)["pa_dk_odds"].null_count() == 2
