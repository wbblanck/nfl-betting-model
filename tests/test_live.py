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


def test_load_lines_ignores_in_play_lines_of_started_games(tmp_path):
    """A game in progress carries several live lines per prop; the one-line-per-book guard must not stop a run that
    only scores games not yet started (2026-10-04: the 11:50 AM ET run failed on IND@WAS in-play lines)."""
    from nflbet import props as P

    cols = ["season", "week", "an_game_id", "start_time", "home", "away", "market", "an_player_id", "player", "player_team",
            "book_id", "line", "over_odds", "under_odds", "yes_odds"]
    row = lambda gid, start, line: dict(zip(cols, ["2026", "4", gid, start, "WAS", "IND", "rec", "9", "X", "IND", "68", line, "-110", "-110", ""]))  # noqa: E731
    rows = [row("1", "2026-10-04T13:30:00.000Z", "4.5"), row("1", "2026-10-04T13:30:00.000Z", "5.5"),   # started, two live lines
            row("2", "2026-10-04T17:00:00.000Z", "4.5")]
    path = tmp_path / "lines.csv"
    pl.DataFrame(rows).write_csv(path)
    try:
        P.load_lines(2026, path)
        raise AssertionError("the guard should refuse a file with two lines per book")
    except ValueError as e:
        assert "game 1" in str(e)                                  # the message names the offending prop
    not_started = pl.col("start_time").map_elements(lambda s: Lv.parse_ts(s) > Lv.parse_ts("2026-10-04T15:50:00Z"), return_dtype=pl.Boolean)
    kept = P.load_lines(2026, path, where=not_started)
    assert kept["an_game_id"].to_list() == ["2"]


def test_gradable_waits_for_published_stats():
    """2026-10-04: the schedule had IND@WAS final while nflverse had no week-4 stats for either team yet, so the
    grader called Tyler Warren's pick void. A game is gradable only once its player stats exist."""
    games = pl.DataFrame({"an_game_id": ["1", "2", "3"], "week": [4, 4, 4], "home_team": ["WAS", "HOU", "PHI"],
                          "away_team": ["IND", "DAL", "LA"]}, schema_overrides={"week": pl.Int32})
    final = pl.DataFrame({"week": [4, 4], "home_team": ["WAS", "HOU"], "away_team": ["IND", "DAL"]}, schema_overrides={"week": pl.Int32})
    assert Lv.gradable(games, final, published={(4, "CLE"), (4, "PIT")}) == set()            # final, stats not out yet
    assert Lv.gradable(games, final, published={(4, "HOU"), (4, "DAL")}) == {"2"}            # HOU@DAL has stats; PHI game not final
    assert Lv.gradable(games, final, published={(4, "WAS")}) == {"1"}
