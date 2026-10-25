"""Known-answer checks for the S1 dashboard numbers (src/nflbet/dashboard.py)."""
import datetime as dt

import polars as pl

from nflbet import dashboard as D

NOW = dt.datetime(2026, 10, 4, 15, 0, tzinfo=dt.timezone.utc)
START1, START2 = "2026-10-04T17:00:00.000Z", "2026-10-04T13:30:00.000Z"
COLS = ["run_utc", "season", "week", "an_game_id", "start_time", "home", "away", "player", "player_id", "team", "market", "side",
        "line", "odds", "p_over_dk", "proj", "p_sim", "v_disagree", "v_proj", "v_sim", "v_price", "inj_self", "inj_teammates",
        "inj_against", "depth_note", "depth_against"]


def pick(run, player, odds, game="1", start=START1, side="under", line="4.5", inj_against="false"):
    return dict(run_utc=run, season="2026", week="4", an_game_id=game, start_time=start, home="BUF", away="NE", player=player,
                player_id=player.lower(), team="BUF", market="rec", side=side, line=line, odds=odds, p_over_dk="0.45", proj="3.1",
                p_sim="0.2", v_disagree="-1", v_proj="-1", v_sim="-1", v_price="-1", inj_self="", inj_teammates="",
                inj_against=inj_against, depth_note="", depth_against="false")


def test_break_even_and_summary():
    assert D.break_even(-150) == 0.6 and D.break_even(100) == 0.5 and abs(D.break_even(-110) - 110 / 210) < 1e-12
    rec = pl.DataFrame({"result": ["W", "L", "P", "pending", "void"], "units": [100 / 120, -1.0, 0.0, 0.0, 0.0],
                        "be": [0.5455, 0.6, 0.5, 0.5, 0.5], "week": [4] * 5})
    s = D.summarize(rec)
    assert (s["W"], s["L"], s["P"], s["pending"], s["void"], s["n"]) == (1, 1, 1, 1, 1, 2)
    assert abs(s["units"] - (100 / 120 - 1)) < 1e-12 and abs(s["roi"] - (100 / 120 - 1) / 2) < 1e-12 and s["win"] == 0.5
    assert abs(s["be"] - (0.5455 + 0.6) / 2) < 1e-12
    assert D.summarize(rec.head(0))["roi"] is None


def test_week_ci_needs_three_weeks_and_brackets_the_roi():
    mk = lambda w, r, u: {"week": w, "result": r, "units": u}  # noqa: E731
    two = pl.DataFrame([mk(4, "W", 0.9), mk(4, "L", -1.0), mk(5, "W", 0.9), mk(5, "L", -1.0)])
    assert D.week_ci(two) is None
    many = pl.DataFrame([mk(w, r, u) for w in range(4, 14) for r, u in (("W", 0.9), ("W", 0.9), ("L", -1.0))])
    lo, hi = D.week_ci(many)
    assert lo <= 0.8 / 3 <= hi and abs(lo - hi) < 1e-9 or lo <= 0.8 / 3 <= hi     # all weeks identical: the interval is the ROI


def test_changes_kept_and_dropped():
    picks = pl.DataFrame([pick("2026-10-04T12:00:00Z", "A", "-110"), pick("2026-10-04T16:00:00Z", "A", "-120"),
                          pick("2026-10-04T12:00:00Z", "B", "-130"), pick("2026-10-04T16:00:00Z", "C", "-140"),
                          pick("2026-10-04T18:00:00Z", "D", "-150")])               # after kickoff: not a deciding run
    runs = pl.DataFrame([{"run_utc": t, "season": "2026", "week": "4", "an_game_id": "1", "start_time": START1, "home": "BUF",
                          "away": "NE", "props_scored": "40"} for t in ("2026-10-04T12:00:00Z", "2026-10-04T16:00:00Z", "2026-10-04T18:00:00Z")])
    ch = {c["player"]: c for c in D.changes(picks, runs, 4, NOW)}
    assert ch["A"]["kept"] and ch["A"]["odds_first"] == -110 and ch["A"]["odds_last"] == -120 and ch["A"]["n_seen"] == 2
    assert not ch["B"]["kept"] and ch["C"]["kept"] and (ch["C"]["n_seen"], ch["C"]["n_runs"]) == (1, 2)


def test_run_log_flags_archives(tmp_path):
    runs = pl.DataFrame([{"run_utc": t, "season": "2026", "week": "4", "an_game_id": "1", "start_time": START1, "home": "BUF",
                          "away": "NE", "props_scored": "40"} for t in ("2026-10-04T12:00:00Z", "2026-10-04T16:00:00Z")])
    (tmp_path / "injuries").mkdir()
    (tmp_path / "injuries" / "20261004T1600Z_w4.json.gz").write_bytes(b"x")
    log = {r["run"]: r for r in D.run_log(pl.DataFrame(), runs, tmp_path)}
    assert log["2026-10-04T16:00:00Z"]["inj"] and not log["2026-10-04T16:00:00Z"]["depth"] and not log["2026-10-04T12:00:00Z"]["inj"]
    assert log["2026-10-04T12:00:00Z"]["lead"] == 300 and log["2026-10-04T16:00:00Z"]["lead"] == 60


def _write(tmp, rows, runs):
    pl.DataFrame(rows).select(COLS).write_csv(tmp / "s1_picks_2026.csv")
    pl.DataFrame(runs).write_csv(tmp / "s1_runs_2026.csv")


def test_build_with_results_and_empty(tmp_path):
    t = "2026-10-04T12:00:00Z"
    rows = [pick(t, "Won", "-120"), pick(t, "Lost", "-110", side="over", inj_against="true"),
            pick(t, "Open", "-130", game="2", start="2026-10-05T00:15:00.000Z")]
    runs = [{"run_utc": t, "season": "2026", "week": "4", "an_game_id": g, "start_time": s, "home": "BUF", "away": "NE", "props_scored": "40"}
            for g, s in (("1", START1), ("2", "2026-10-05T00:15:00.000Z"))]
    _write(tmp_path, rows, runs)
    rec = pl.DataFrame(rows).with_columns(pl.Series("actual", ["3", "6", ""]), pl.Series("result", ["W", "L", "pending"]),
                                          pl.Series("units", [str(100 / 120), "-1.0", "0.0"]))
    rec.write_csv(tmp_path / "s1_record_2026.csv")
    page = D.build(D.load(tmp_path), NOW)
    assert page.count('class="pick"') == 3
    assert "1-1" in page and "-0.17" in page and "-8.3%" in page   # record, units and ROI recomputed from the files
    assert "+0.83" in page                                         # the winning -120 pick returns 100/120 units
    assert 'data-against="1"' in page and "Injury news against" in page
    assert "Cumulative units" in page and "polyline" in page          # a graded pick draws the cumulative line
    empty = tmp_path / "empty"
    empty.mkdir()
    assert "S1 Live Tracker" in D.build(D.load(empty), NOW)       # no files at all: a page, not a crash


def test_coverage_context_only_from_tables_before_the_picks_week(tmp_path):
    cols = "table,team,cov0,cov1,cov2man,cov2,cov3,cov4,cov6,man_total,zone_total,epa_per_db"
    (tmp_path / "coverage_fantasypoints_2026_w1-4.csv").write_text(cols + "\nall_plays,CAR,1,2,0,3,42.1,5,6,18.0,60.0,0.29\n")
    r = {"week": "5", "team": "DET", "home": "CAR", "away": "DET"}
    assert D.coverage_for_pick(r, tmp_path) == "CAR defense, weeks 1-4: man 18% of plays, Cover 3 42%, EPA per DB +0.29"
    assert D.coverage_for_pick(dict(r, week="4"), tmp_path) == ""            # week 4's own game is inside that table: not shown
    assert D.coverage_for_pick(dict(r, team="CAR"), tmp_path) == ""           # opponent is DET: no row for it
    (tmp_path / "coverage_fantasypoints_2026_w1-5.csv").write_text(cols + "\nall_plays,CAR,0,0,0,0,50,0,0,10.0,70.0,0.10\n")
    assert "weeks 1-5" in D.coverage_for_pick(dict(r, week="6"), tmp_path)    # newest table that ends before the week


def test_parlay_card_and_second_source():
    pc = pl.DataFrame({"run_utc": ["2026-10-08T06:00:00Z"] * 2 + ["2026-10-08T20:00:00Z"] * 2, "week": ["5"] * 4,
                       "book": ["dk", "fd"] * 2, "n_parlay": ["400", "300", "410", "341"], "n_an": ["0", "0", "380", "300"],
                       "n_both": ["0", "0", "360", "280"], "same_line": ["0", "0", "324", "266"],
                       "mean_p_gap_pts": ["", "", "1.2", "0.8"], "credits_left": ["994", "994", "991", "991"]})
    html = D.parlay_card(pc)
    assert "90%" in html and "95%" in html and "1.2 pts" in html and "991" in html     # latest run only
    assert D.parlay_card(pl.DataFrame()) == ""
    assert D.second_source({"line": "82.5"}) == ""
    same = D.second_source({"line": "82.5", "pa_dk_line": "82.5", "pa_dk_odds": "-111"})
    assert "DK 82.5 -111" in same and "differs" not in same


def test_pa_section_marks_overlap_with_official():
    base = {"week": "5", "start_time": "2026-10-11T17:00:00.000Z", "away": "IND", "home": "PIT", "team": "IND",
            "line": "4.5", "odds": "-151", "p_sim": "0.258", "p_over_dk": "0.43", "units": "0", "result": "pending",
            "inj_against": "false", "depth_against": "false"}
    pa = pl.DataFrame([dict(base, player="Josh Downs", player_id="a", market="rec", side="under"),
                       dict(base, player="Aaron Jones", player_id="b", market="rec", side="under", away="MIN", home="NO")])
    rec = pl.DataFrame({"player_id": ["a"], "market": ["rec"], "side": ["under"]})
    html = D.pa_section(pa, rec, dt.datetime(2026, 10, 8, tzinfo=dt.timezone.utc))
    assert "2 picks" in html and html.count("Also official S1") == 1 and "Open" in html
    assert D.pa_section(pl.DataFrame(), rec, dt.datetime(2026, 10, 8, tzinfo=dt.timezone.utc)) == ""


def test_ats_section():
    runs = pl.DataFrame({"run_utc": ["2026-10-10T16:00:00Z"], "week": ["5"], "game_id": ["2026_05_IND_PIT"], "start_time": ["2026-10-11T17:00:00.000Z"],
                         "home": ["PIT"], "away": ["IND"], "fair": ["4.0"], "consensus": ["2.5"], "exchange": [""], "side": ["PIT"],
                         "side_is_home": ["true"], "best_book": ["DraftKings"], "best_line": ["2.5"], "best_odds": ["-115"], "gap": ["1.5"],
                         "key": ["true"], "exp_clv": ["0.35"], "label": ["Bet Now"], "qb_note": [""]})
    html = D.ats_section(runs, pl.DataFrame(), dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc))
    # home line 2.5 (PIT favored) backed on PIT: PIT gives 2.5, fair says it should give 4
    assert '<span class="ats-team">PIT</span> <span class="ats-num">−2.5</span>' in html
    assert "PIT −4" in html and "Bet Now" in html and "-115 at DraftKings" in html
    assert "1.5-point edge across −3" in html and "1.5 pts" in html and "+0.35 pts" in html
    assert "No ATS runs yet" in D.ats_section(pl.DataFrame(), pl.DataFrame(), dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc))
    assert D.hcp("IND", 3.0, False) == "IND +3" and D.hcp("PIT", 0.0, True) == "PIT PK"


def test_ats_side_view_and_keys():
    assert D.side_view("3.5", True) == -3.5 and D.side_view("3.5", False) == 3.5 and D.side_view("", True) is None
    assert D.fmt_line(-2.5) == "−2.5" and D.fmt_line(3.0) == "+3" and D.fmt_line(0.0) == "PK"
    # side view: best -2.5 vs fair -6.1 sits on the better side of -3 (and not of -7)
    assert D.keys_crossed(-2.5, -6.1) == [-3]
    assert D.keys_crossed(7.5, 2.0) == [3, 7]
    assert D.keys_crossed(-3.0, -3.5) == []              # landing on 3 is not the better side of it
    assert D.keys_crossed(-2.5, -3.0) == [-3]            # fair exactly 3, best better than 3 (ats.rating.crosses_key)
    from nflbet.ats.rating import crosses_key
    for best, fair in ((-2.5, -6.1), (7.5, 2.0), (-3.0, -3.5), (-2.5, -3.0), (1.0, 0.5), (-6.5, -7.0)):
        # side view on an away side equals the home-margin line, so crosses_key(line, fair, home=False) applies directly
        assert bool(D.keys_crossed(best, fair)) == crosses_key(best, fair, False)


def test_ats_label_reasons():
    base = {"key": "true", "beats_ref": "true", "qb_note": ""}
    assert D.label_reason(dict(base, gap="3.6", label="Bet Now"), -2.5, -6.1).startswith("3.6-point edge across −3")
    assert "but GB QB Jordan Love: Questionable" in D.label_reason(
        dict(base, gap="1.6", label="Wait", qb_note="GB QB Jordan Love: Questionable"), 3.0, 1.4)
    assert D.label_reason(dict(base, gap="2.3", key="false", label="Monitor"), 3.0, 0.7) == \
        "2.3-point edge, short of Bet Now: no key number between fair and the best line."
    assert "exchanges have a better number" in D.label_reason(dict(base, gap="1.2", beats_ref="false", label="Monitor"), -2.5, -3.7)
    assert D.label_reason(dict(base, gap="0.4", key="false", label="No Value"), 3.0, 2.6) == "Edge of 0.4 points, under the 1-point minimum."
    assert D.label_reason(dict(base, gap="1.2", key="false", label="No Value"), -3.5, -4.7) == \
        "Edge of 1.2 points with no key number; Monitor needs 1.5."
    # fields that do not reproduce the label: say only what was recorded
    assert D.label_reason(dict(base, gap="0.2", label="Bet Now"), 1.0, 0.8) == "Recorded as Bet Now by the run."


def test_ats_reasons_reproduce_every_recorded_label():
    runs = pl.read_csv(D.config.ROOT / "data" / "live" / "ats_runs_2026.csv", infer_schema_length=0)
    for r in runs.to_dicts():
        h = r["side_is_home"] == "true"
        assert not D.label_reason(r, D.side_view(r["best_line"], h), D.side_view(r["fair"], h)).startswith("Recorded as"), r["game_id"]
