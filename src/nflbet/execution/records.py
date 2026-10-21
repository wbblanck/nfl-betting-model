"""Run and record files shared by the live trackers (data/live/*.csv): every value is stored as text, appended run
by run, and a game's official row is the last run that evaluated it before kickoff."""
from pathlib import Path

import polars as pl

from nflbet.execution.clock import parse_ts


def append(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size:
        old = pl.read_csv(path, infer_schema_length=0)
        df = pl.concat([old, df.select([pl.col(c).cast(pl.Utf8) for c in df.columns])], how="diagonal_relaxed")
    df.write_csv(path)


def before_kickoff(runs: pl.DataFrame) -> pl.DataFrame:
    """Rows whose run_utc is strictly before the game's start_time."""
    return runs.filter(pl.col("run_utc").map_elements(parse_ts, return_dtype=pl.Datetime("us", "UTC"))
                       < pl.col("start_time").map_elements(parse_ts, return_dtype=pl.Datetime("us", "UTC")))
