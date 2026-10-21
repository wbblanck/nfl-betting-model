"""Write the weekly recap: python scripts/recap.py [week]   (default: the latest week whose official picks are all graded)"""
import sys

import polars as pl

from nflbet.props import live as Lv
from nflbet.props import recap

if __name__ == "__main__":
    rec = pl.read_csv(Lv.LIVE / "s1_record_2026.csv", infer_schema_length=0)
    if len(sys.argv) > 1:
        week = int(sys.argv[1])
    else:
        done = [int(w) for (w,), x in rec.group_by("week") if not (x["result"] == "pending").any()]
        if not done:
            print("no fully graded week yet"); sys.exit(0)
        week = max(done)
    print(*recap.write(week), sep="\n")
