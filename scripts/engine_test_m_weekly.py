"""Weekly Test M housekeeping (docs/engine_preregistration.md, amendment of 2026-11-17), run by
.github/workflows/engine-test-m.yml. For every sample week (2026 weeks 11-18) whose last game kicked off more than a
day ago and that has no forecasts yet: build them (scripts/engine_forecast.py, unchanged) and write the counts
(scripts/engine_test_m.py --counts). Then, per amendment 2026-11-18 (2), the interim (descriptive) statistic on the
weeks done so far (scripts/engine_test_m.py --interim) and the paper fills of every forecast week that has none yet
(scripts/engine_paper.py; docs/engine/paper_rules.md). The verdict is still the single --grade run after week 18.

  python scripts/engine_test_m_weekly.py            the due weeks
  python scripts/engine_test_m_weekly.py --dry-run  forecast week 10 (outside the sample) into a scratch folder and
                                                    check the frozen records; commits nothing
"""
import datetime as dt
import os
import sys

import nflreadpy as nr
import polars as pl

import engine_forecast as EF
import engine_paper as EP
import engine_test_m as TM
from nflbet.engine import forecast as FO


def due(now: dt.datetime) -> list[int]:
    s = nr.load_schedules([TM.SEASON]).filter(pl.col("game_type") == "REG")
    out = []
    for w in TM.WEEKS:
        g = s.filter(pl.col("week") == w)
        last = max(FO.kickoff_utc(f"{d} {t}") for d, t in zip(g["gameday"].cast(pl.Utf8), g["gametime"].fill_null("00:00")))
        if now - last > dt.timedelta(days=1) and not (TM.FC / f"{TM.SEASON}_w{w:02d}" / "manifest.json").exists():
            out.append(w)
    return out


def main() -> int:
    if "--dry-run" in sys.argv:
        os.environ.setdefault("ENGINE_FORECAST_DRY", "/tmp")
        sys.argv = ["engine_forecast.py", str(TM.SEASON), "10", "--dry-run"]
        return EF.main()
    weeks = due(dt.datetime.now(dt.timezone.utc))
    print(f"due weeks: {weeks}")
    rc = 0
    for w in weeks:
        sys.argv = ["engine_forecast.py", str(TM.SEASON), str(w)]
        r = EF.main()
        rc = rc or r
        if r == 0:
            sys.argv = ["engine_test_m.py", "--counts", str(w)]
            rc = rc or TM.main()
    if weeks:
        sys.argv = ["engine_test_m.py", "--interim"]
        rc = rc or TM.main()
    for w in TM.WEEKS:
        if (TM.FC / f"{TM.SEASON}_w{w:02d}" / "manifest.json").exists() and not (EP.OUT / f"{TM.SEASON}_w{w:02d}" / "fills.csv").exists():
            sys.argv = ["engine_paper.py", str(w)]
            rc = rc or EP.main()
    return rc


if __name__ == "__main__":
    sys.exit(main())
