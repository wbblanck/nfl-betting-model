"""Known-answer check for the PinnRadar harvest tidier: a price change gives one row, an unchanged poll gives none."""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "fetch"))
import pinnradar_tidy as T  # noqa: E402


def game(price_home: float) -> dict:
    return {"event_id": 1, "league_name": "NFL", "home": "H", "away": "A", "starts": "2026-11-22T18:00:00Z",
            "parent_id": None, "periods": {"num_0": {"number": 0, "money_line": {"home": price_home, "away": 2.0},
                                                      "spreads": {"-3": {"hdp": -3, "home": 1.9, "away": 1.95, "max": 100}},
                                                      "meta": {"max_money_line": 50}}}}


def prop(price_over: float) -> dict:
    return {"event_id": 2, "parent_id": 1, "league_name": "NFL", "home": "H", "away": "A", "starts": "x",
            "special_category": "Player Props", "special": "P Total Receptions", "special_units": "Receptions",
            "special_markets": {"num_0": [{"type": "total", "max_risk": 250, "prices": [
                {"name": "Over", "points": 4.5, "price": price_over}, {"name": "Under", "points": 4.5, "price": 1.9}]}]}}


def test_changes_only(tmp_path, monkeypatch):
    root = tmp_path / "radar"; job = root / "20261119T000000Z"; job.mkdir(parents=True)
    with gzip.open(job / "full_20261119T000000Z.json.gz", "wt") as f:
        json.dump({"events": [game(1.8), prop(1.9)]}, f)
    with gzip.open(job / "prematch_deltas.jsonl.gz", "at") as f:
        f.write(json.dumps({"t": "20261119T000100Z", "events": [game(1.8), prop(1.9)]}) + "\n")   # unchanged
    with gzip.open(job / "prematch_deltas.jsonl.gz", "at") as f:                                   # second member
        f.write(json.dumps({"t": "20261119T000200Z", "events": [game(1.75), prop(2.05)]}) + "\n")  # ML + over move
    monkeypatch.setattr(T, "ROOT", root); monkeypatch.setattr(T, "OUT", root / "tidy")
    T.main()
    g = list(gzip.open(root / "tidy" / "game_lines.csv.gz", "rt"))[1:]
    s = list(gzip.open(root / "tidy" / "specials.csv.gz", "rt"))[1:]
    assert len(g) == 3 and g[-1].startswith("20261119T000200Z") and ",money_line,,1.75,2.0,50" in g[-1]
    assert len(s) == 3 and s[-1].startswith("20261119T000200Z") and ",Over,4.5,2.05,250" in s[-1]
