"""Known-answer checks for the S1 live tracker's grading."""
import polars as pl

from nflbet import live as Lv


def _picks():
    base = {"season": "2026", "week": "4", "home": "GB", "away": "CHI", "team": "GB", "p_over_dk": "0.5", "proj": "1",
            "p_sim": "0.4", "v_disagree": "-1", "v_proj": "-1", "v_sim": "-1", "v_price": "-1"}
    rows = [
        # game 1 (kickoff 17:00): two runs before kickoff, one after -> the 16:00 run is official
        dict(base, run_utc="2026-10-04T12:45:00Z", an_game_id="1", start_time="2026-10-04T17:00:00.000Z", player="A", player_id="a",
             market="rec_yds", side="under", line="50.5", odds="-110"),
        dict(base, run_utc="2026-10-04T16:00:00Z", an_game_id="1", start_time="2026-10-04T17:00:00.000Z", player="B", player_id="b",
             market="rec_yds", side="under", line="50.5", odds="-120"),
        dict(base, run_utc="2026-10-04T16:00:00Z", an_game_id="1", start_time="2026-10-04T17:00:00.000Z", player="C", player_id="c",
             market="rec", side="over", line="4.0", odds="+100"),
        dict(base, run_utc="2026-10-04T16:00:00Z", an_game_id="1", start_time="2026-10-04T17:00:00.000Z", player="D", player_id="d",
             market="rush_yds", side="under", line="30.5", odds="-110"),
        dict(base, run_utc="2026-10-04T16:00:00Z", an_game_id="1", start_time="2026-10-04T17:00:00.000Z", player="E", player_id="e",
             market="rush_yds", side="under", line="30.5", odds="-110"),
        # game 2 (Monday, not final yet)
        dict(base, run_utc="2026-10-04T16:00:00Z", an_game_id="2", start_time="2026-10-06T00:15:00.000Z", player="F", player_id="f",
             market="rec", side="over", line="3.5", odds="-110"),
    ]
    runs = pl.DataFrame([{"run_utc": t, "an_game_id": g, "start_time": s}
                         for t, g, s in [("2026-10-04T12:45:00Z", "1", "2026-10-04T17:00:00.000Z"),
                                         ("2026-10-04T16:00:00Z", "1", "2026-10-04T17:00:00.000Z"),
                                         ("2026-10-04T17:30:00Z", "1", "2026-10-04T17:00:00.000Z"),   # after kickoff: ignored
                                         ("2026-10-04T16:00:00Z", "2", "2026-10-06T00:15:00.000Z")]])
    return pl.DataFrame(rows), runs


def test_official_is_last_run_before_kickoff():
    picks, runs = _picks()
    off = Lv.official(picks, runs)
    assert sorted(off["player"].to_list()) == ["B", "C", "D", "E", "F"]          # A's 12:45 run was superseded


def test_settle_results_and_units():
    picks, runs = _picks()
    off = Lv.official(picks, runs)
    stats = pl.DataFrame({"player_id": ["b", "c", "d"], "week": [4, 4, 4], "market": ["rec_yds", "rec", "rush_yds"],
                          "actual": [40.0, 4.0, 31.0]})
    d = Lv.settle(off, stats, played={("e", 4)}, final_games={"1"})
    got = dict(zip(d["player"].to_list(), d["result"].to_list()))
    # B under 50.5 with 40 -> W; C over 4.0 with 4 -> push; D under 30.5 with 31 -> L; E played, no stat row -> 0 -> W;
    # F's game not final -> pending
    assert got == {"B": "W", "C": "P", "D": "L", "E": "W", "F": "pending"}
    r = Lv.record(d)
    assert (r["W"], r["L"], r["P"], r["pending"]) == (2, 1, 1, 1)
    assert abs(r["units"] - (100 / 120 + 100 / 110 - 1)) < 1e-9
