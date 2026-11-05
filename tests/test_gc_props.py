"""Known answers for reshaping the third-party 2022-2023 Action Network prop archive."""
import polars as pl

from nflbet.sources import gc_props


def raw(rows):
    cols = ["season", "week", "event_id", "bet_type", "action_network_player_id", "join_name", "team", "player_id",
            "book_id", "side", "value", "odds", "period"]
    return pl.DataFrame([dict(zip(cols, r)) for r in rows], orient="row")


def test_pairs_sides_drops_partial_games_and_conflicts():
    r = raw([
        (2023, 5, 1, "receptions", "a", "x.one", "KC", "00-1", 68, "over", 4.5, -110, "event"),
        (2023, 5, 1, "receptions", "a", "x.one", "KC", "00-1", 68, "under", 4.5, -120, "event"),
        (2023, 5, 1, "receptions", "a", "x.one", "KC", "00-1", 68, "over", 2.5, -110, "firsthalf"),   # dropped
        (2023, 5, 1, "receptions", "a", "x.one", "KC", "00-1", 68, "under", 2.5, -110, "firsthalf"),
        (2023, 5, 1, "receiving_yards", "a", "x.one", "KC", "00-1", 69, "over", 50.5, -110, "event"),  # two lines
        (2023, 5, 1, "receiving_yards", "a", "x.one", "KC", "00-1", 69, "under", 50.5, -110, "event"),
        (2023, 5, 1, "receiving_yards", "a", "x.one", "KC", "00-1", 69, "over", 60.5, 120, "event"),
        (2023, 5, 1, "receiving_yards", "a", "x.one", "KC", "00-1", 69, "under", 60.5, -150, "event"),
        (2023, 5, 1, "rushing_yards", "a", "x.one", "KC", "00-1", 79, "over", 9.5, -110, "event"),     # one-sided
        (2023, 5, 1, "anytime_touchdown_scorer", "a", "x.one", "KC", "00-1", 15, "noside", 0.0, 250, "event"),
        (2023, 5, 1, "tackles_assists", "a", "x.one", "KC", "00-1", 68, "over", 1.5, -110, "event"),   # not mapped
    ])
    out, bad = gc_props.shape(r)
    assert bad == 1
    rec = out.filter(pl.col("market") == "rec").row(0, named=True)
    assert (rec["line"], rec["over_odds"], rec["under_odds"], rec["book"]) == (4.5, -110, -120, "DK")
    assert out.filter(pl.col("market") == "rec_yds").height == 0
    assert out.filter(pl.col("market") == "rush_yds").height == 0
    td = out.filter(pl.col("market") == "anytime_td").row(0, named=True)
    assert td["yes_odds"] == 250 and td["book"] == "Consensus" and td["line"] is None
    assert out.height == 2
