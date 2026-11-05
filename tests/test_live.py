"""Known-answer checks for the S1 live tracker's grading."""
import polars as pl

from nflbet.props import live as Lv


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
    from nflbet.props import core as P

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


def test_run_exits_cleanly_when_no_props_are_posted(tmp_path, monkeypatch, capsys):
    """2026-10-07, 2:30 PM ET: week 5 had no props yet; the early run crashed on the empty file. It must say so and stop."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("live_s1", "scripts/live_s1.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_s1"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.Lv, "LIVE", tmp_path)
    monkeypatch.setattr(mod.Lv, "current_week", lambda season: 5)

    def fake_fetch(cmd, check):          # writes a header-only lines file, as the fetch did
        out = cmd[cmd.index("--out") + 1]
        open(out, "w").write("season,week,an_game_id,start_time,home,away,market,an_player_id,player,player_team,book_id,book,line,over_odds,under_odds,yes_odds\n")

    monkeypatch.setattr(mod.subprocess, "run", fake_fetch)
    mod.do_run()
    assert "no player props posted yet" in capsys.readouterr().out
    assert not (tmp_path / "lines").exists()                              # nothing archived, nothing recorded


def test_coverage_guard_ignores_thin_runs():
    picks = pl.DataFrame([{"run_utc": "2026-10-08T22:51:23Z", "an_game_id": "g", "player": "Aaron Jones"}])
    runs = pl.DataFrame({"run_utc": ["2026-10-08T05:42:48Z", "2026-10-08T22:51:23Z", "2026-10-09T08:00:35Z"],
                         "an_game_id": ["g"] * 3, "start_time": ["2026-10-11T17:00:00.000Z"] * 3,
                         "props_scored": ["18", "20", "7"]})
    assert Lv.official(picks, runs).height == 0                          # plain rule: the thin 08:00 run (no picks) wins
    assert Lv.official(picks, runs, 0.5)["player"].to_list() == ["Aaron Jones"]   # 7 < 0.5 * 20: 08:00 does not count
    runs2 = runs.with_columns(pl.Series("props_scored", ["18", "20", "15"]))
    assert Lv.official(picks, runs2, 0.5).height == 0                    # a full run with no pick still drops it


def test_an_outage_alarm_only_when_draftkings_has_posted():
    """2026 weeks 5-8: Action Network returned 0 props while ParlayAPI had DK's, and the run called it "not posted yet"."""
    import importlib.util
    import sys

    import polars as pl

    spec = importlib.util.spec_from_file_location("live_s1", "scripts/live_s1.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_s1"] = mod
    spec.loader.exec_module(mod)
    pa = pl.DataFrame({"book": ["dk", "dk", "fd"]})
    assert mod.an_outage(8, 0, pa) == ("week 8: Action Network returned 0 player props, but ParlayAPI has 2 DraftKings props; "
                                       "official S1 cannot run")
    assert mod.an_outage(8, 120, pa) is None                       # Action Network has props: fine
    assert mod.an_outage(8, 0, pl.DataFrame({"book": ["fd"]})) is None   # nobody has DK props yet: early week
    assert mod.an_outage(8, 0, None) is None                       # ParlayAPI unavailable: no evidence of an outage


def _load_live_s1():
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("live_s1", "scripts/live_s1.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_s1"] = mod
    spec.loader.exec_module(mod)
    return mod


def _switched_env(mod, tmp_path, monkeypatch, pa):
    """Week 9 run with Action Network empty; ParlayAPI answers with `pa` (None = the call failed)."""
    monkeypatch.setattr(mod.Lv, "LIVE", tmp_path)
    for name in ("PICKS", "RUNS", "PA_PICKS", "PA_RUNS"):
        monkeypatch.setattr(mod, name, tmp_path / f"{name.lower()}.csv")
    monkeypatch.setattr(mod.Lv, "current_week", lambda season: 9)
    hdr = "season,week,an_game_id,start_time,home,away,market,an_player_id,player,player_team,book_id,book,line,over_odds,under_odds,yes_odds\n"
    monkeypatch.setattr(mod.subprocess, "run", lambda cmd, check: open(cmd[cmd.index("--out") + 1], "w").write(hdr))
    monkeypatch.setattr(mod, "parlay_record", lambda week, when, an: pa)
    monkeypatch.setattr(mod, "openmarkets_record", lambda week, when, pa, an: None)
    monkeypatch.setattr(mod, "ats_record", lambda week, when: None)
    monkeypatch.setattr(mod, "with_news", lambda frames, week, when: frames)
    seen = {}
    monkeypatch.setattr(mod, "bestprice_record", lambda picks, an_path, pa, week, when: seen.setdefault("best", picks.height))
    monkeypatch.setattr(mod.Pa, "to_an_csv", lambda pa, season, week, path: open(path, "w").write(hdr) and 1)
    pick = pl.DataFrame([{"run_utc": "2026-11-05T16:00:00Z", "week": "9", "an_game_id": "pa_2026_09_X_Y", "start_time": "2026-11-06T01:15:00.000Z",
                          "home": "Y", "away": "X", "player": "A B", "player_id": "p", "market": "rec", "side": "under",
                          "line": 4.5, "odds": -150.0, "inj_against": False, "inj_self": "", "inj_teammates": "",
                          "depth_against": False, "depth_note": ""}])
    log = pl.DataFrame([{"run_utc": "2026-11-05T16:00:00Z", "season": 2026, "week": 9, "an_game_id": "pa_2026_09_X_Y",
                         "start_time": "2026-11-06T01:15:00.000Z", "home": "Y", "away": "X", "props_scored": 40}])
    monkeypatch.setattr(mod.Lv, "run", lambda season, path, when: (pick, log))
    monkeypatch.setattr(mod.Om, "attach", lambda picks, om: picks)
    monkeypatch.setattr(mod.Pa, "attach", lambda picks, pa: picks)
    return seen


def test_week9_official_s1_is_scored_on_parlayapi(tmp_path, monkeypatch, capsys):
    """Source switch (docs/s1_live_rules.md): from week 9 ParlayAPI's DK + FanDuel lines are the official S1 input."""
    mod = _load_live_s1()
    seen = _switched_env(mod, tmp_path, monkeypatch, pl.DataFrame({"book": ["dk", "fd"]}))
    mod.do_run()
    out = capsys.readouterr().out
    assert "S1 (official, ParlayAPI DK + FanDuel), week 9" in out and "S1 on ParlayAPI (DK + FanDuel), week 9" in out
    for name in ("picks", "pa_picks"):
        assert pl.read_csv(tmp_path / f"{name}.csv")["player"].to_list() == ["A B"]
    assert pl.read_csv(tmp_path / "runs.csv")["an_game_id"].to_list() == ["pa_2026_09_X_Y"]
    assert seen["best"] == 1                                     # best-price / your-venues records get the official pick
    assert not (tmp_path / "tmp" / "ALERT").exists()             # Action Network empty is no alarm after the switch


def test_week9_parlayapi_failure_alarms_and_records_nothing(tmp_path, monkeypatch):
    mod = _load_live_s1()
    _switched_env(mod, tmp_path, monkeypatch, None)
    mod.do_run()
    assert "ParlayAPI unavailable" in (tmp_path / "tmp" / "ALERT").read_text()
    assert not (tmp_path / "picks.csv").exists()


def test_official_guard_applies_to_parlayapi_games_only():
    mod = _load_live_s1()
    runs = pl.DataFrame({"run_utc": ["2026-11-05T05:00:00Z", "2026-11-05T20:00:00Z"] * 2,
                         "an_game_id": ["290901", "290901", "pa_g", "pa_g"],
                         "start_time": ["2026-11-06T01:15:00.000Z"] * 4, "props_scored": ["20", "7", "20", "7"]})
    picks = pl.DataFrame({"run_utc": ["2026-11-05T05:00:00Z"] * 2, "an_game_id": ["290901", "pa_g"], "player": ["an", "pa"]})
    off = mod.official_mixed(picks, runs, 0.5, "pa_")
    assert off["player"].to_list() == ["pa"]                     # thin later run ignored for pa_ only; AN game keeps plain rule
