import polars as pl

from nflbet.ui import cards as C


def test_american_prices():
    assert C.am(0.5) == "-100" and C.am(0.6) == "-150" and C.am(0.4) == "+150"


def test_nan_and_blank_are_missing():
    assert C._f("nan") is None and C._f("") is None and C._f("0.5") == 0.5


def test_ladder_positions_inside_rail_and_value_zone():
    html, text = C.ladder(0.45, 0.50, 0.55)
    assert "zone" in html and "Best +122" in text and "Pinnacle fair -122" in text
    assert all(0 <= float(x) <= 100 for x in __import__("re").findall(r"left:([\d.]+)%", html))


def test_both_keys_and_histogram_counts():
    df = pl.DataFrame({"engine": ["A", "A", "B"], "player_id": ["1", "2", "1"], "market": ["rec"] * 3,
                       "line": ["1.5"] * 3, "side": ["Under"] * 3})
    assert C.both_keys(df) == {("1", "rec", "1.5", "Under")}
    h = C.histogram({"A": [0.04, 0.04, 0.2], "B": [0.06]}, {"A": "A", "B": "B"})
    assert "3-5%: 2" not in h and "3-5% 2" in h and "15%+ 1" in h


def test_cards_escape_untrusted_text():
    r = {"kind": "Prop <b>", "venue": "Novig", "side": "<script>x</script>", "game": "a & b", "best_cost": "0.5", "gap_next": "0.06",
         "fair_power": "0.53", "edge_power": "0.04", "edge_mult": "0.04", "best_depth": "nan", "move_pp": "", "starts": ""}
    out = C.outlier_card(r, lambda s: s)
    assert "<script>" not in out and "&lt;script&gt;" in out and "$nan" not in out
