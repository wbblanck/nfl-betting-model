"""Build data/external/team_pass_participation_2016_2025.csv and team_ftn_<years>.csv (src/nflbet/sources/teamstats.py)."""
from __future__ import annotations

import datetime as dt

from nflbet import config
from nflbet.sources import teamstats as T


def main() -> None:
    out = config.ROOT / "data" / "external"
    p = T.participation(list(range(2016, 2026)))
    p.write_csv(out / "team_pass_participation_2016_2025.csv")
    print("participation", p.height, p.group_by("season").agg(p.columns and __import__("polars").col("def_pressure_rate").mean()).sort("season").rows())
    year = dt.date.today().year if dt.date.today().month >= 8 else dt.date.today().year - 1
    f = T.ftn(list(range(2022, year + 1)))
    f.write_csv(out / f"team_ftn_2022_{year}.csv")
    print("ftn", f.height, f.group_by("season").len().sort("season").rows())


if __name__ == "__main__":
    main()
