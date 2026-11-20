"""Known-answer checks for the outliers tracker (docs/outliers_live_rules.md)."""
import datetime as dt
import importlib.util
from pathlib import Path

import polars as pl

spec = importlib.util.spec_from_file_location("ol", Path(__file__).resolve().parents[1] / "scripts" / "outliers_live.py")
O = importlib.util.module_from_spec(spec)
spec.loader.exec_module(O)
UTC = dt.timezone.utc


def t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=UTC)


def test_cadence_and_cap():
    now = t("2026-11-22T16:00:00")                      # 11 AM ET, 1 PM kickoff in 2 h -> 15-minute polls
    k = [t("2026-11-22T18:00:00")]
    assert O.due(now, k, [t("2026-11-22T15:50:00")])[0] is False          # 10 min ago
    assert O.due(now, k, [t("2026-11-22T15:45:00")])[0] is True           # 15 min ago
    far = [t("2026-11-23T01:20:00")]                    # only SNF, 9 h away -> hourly
    assert O.due(now, far, [t("2026-11-22T15:30:00")])[0] is False
    assert O.due(now, far, [t("2026-11-22T15:00:00")])[0] is True
    assert O.due(t("2026-11-22T09:00:00"), far, [])[0] is False           # 4 AM ET, nothing near
    cap = [t("2026-11-22T00:00:00") + dt.timedelta(minutes=i) for i in range(O.DAILY_CAP)]
    assert O.due(now, k, cap) == (False, f"daily cap reached ({O.DAILY_CAP} calls today)")


def rowdf(**kw):
    base = dict(side_id="A @ B|Spread|B -3", starts="2026-11-22T18:00:00Z", kind="Spread", game="A @ B", side="B -3",
                venue="Novig", best_cost=0.45, best_depth=100.0, gap_next=0.08, venues="Novig +122", pin_price=2.0,
                pin_other=1.9, pin_hold=0.0263, fair_mult=0.4872, fair_power=0.4870, edge_mult=0.0827, edge_power=0.0822,
                move_pp=0.0)
    return pl.DataFrame([base | kw])


def test_qualify_and_record_then_grade():
    now = t("2026-11-22T17:00:00")
    d = rowdf()
    assert O.qualify(d, now).height == 1
    assert O.qualify(rowdf(gap_next=0.04), now).height == 0                    # under 5% better than next
    assert O.qualify(rowdf(edge_power=0.02), now).height == 0                  # under 3% on one method
    assert O.qualify(rowdf(starts="2026-11-22T17:05:00Z"), now).height == 0    # kicks off within 10 min
    rec = O.update_records(pl.DataFrame(), d, O.qualify(d, now), now, 11)
    assert rec.height == 1 and rec["status"][0] == "open"
    later = t("2026-11-22T17:45:00")                                            # close quote 15 min before kickoff
    rec = O.update_records(rec, rowdf(pin_price=1.8, pin_other=2.1), rowdf(pin_price=1.8, pin_other=2.1), later, 11)
    assert rec.height == 1 and rec["last_pin_price"][0] == "1.8"               # no second row, quote refreshed
    g = O.grade_rows(rec, t("2026-11-22T18:30:00"))
    fp = O.S.devig_power(1.8, 2.1)
    assert g["status"][0] == "graded" and abs(float(g["clv_power"][0]) - (fp / 0.45 - 1)) < 1e-6


def test_no_close_when_last_quote_too_early():
    now = t("2026-11-22T16:00:00")
    rec = O.update_records(pl.DataFrame(), rowdf(), rowdf(), now, 11)          # last quote 2 h before kickoff
    assert O.grade_rows(rec, t("2026-11-22T19:00:00"))["status"][0] == "no close"


def test_outliers_tab_renders_empty_and_graded():
    from nflbet import dashboard as D
    assert "No poll yet" in D.outliers_section({}, None)
    s = {"recorded": 3, "graded": 2, "no_close": 1, "open": 0, "mean_clv": 0.012, "share_pos": 0.5, "ci": [-0.01, 0.03],
         "by_week": {"11": {"n": 1, "mean_clv": 0.02, "share_pos": 1.0}, "12": {"n": 1, "mean_clv": 0.004, "share_pos": 0.0}}}
    h = D.outliers_section({"out_sum": s, "out_cur": pl.DataFrame({"poll_utc": ["2026-11-20T01:00:00Z"]})}, None)
    assert "Nothing qualifies" in h and "+1.2%" in h and "-1.0% to +3.0%" in h
