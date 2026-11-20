import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import scheduler as S  # noqa: E402

U = dt.timezone.utc


def t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=U)


def test_cron_fields():
    assert S.matches("15 19 * * 4", t("2026-11-19T19:15"))          # Thursday
    assert not S.matches("15 19 * * 4", t("2026-11-20T19:15"))
    assert S.matches("*/30 11-23 * * *", t("2026-11-19T23:30"))
    assert not S.matches("*/30 11-23 * * *", t("2026-11-19T10:30"))
    assert S.matches("30 9 * * 0", t("2026-11-22T09:30"))           # Sunday as 0
    assert S.matches("30 9 * * 7", t("2026-11-22T09:30"))           # and as 7


def test_due_takes_latest_per_workflow_within_lookback():
    sch = {"a.yml": ["30 12 * * 0", "50 12 * * 0"], "b.yml": ["0 10 * * 0"]}
    d = S.due(t("2026-11-22T12:55"), sch)
    assert [(w, c) for w, c, _ in d] == [("a.yml", "50 12 * * 0")]  # b is past the lookback


def test_every_scheduled_workflow_can_be_dispatched_with_its_inputs():
    sch = S.schedules()
    assert "live-s1.yml" in sch and "novig-books.yml" in sch and "scheduler.yml" not in sch
    assert S.INPUTS["live-s1.yml"]("33 15 * * 2") == {"step": "grade"}
    assert S.INPUTS["live-s1.yml"]("0 20 * * 4") == {"step": "run"}
    assert S.INPUTS["wind-live.yml"]("17 15 * * 2") == {"step": "grade"}
