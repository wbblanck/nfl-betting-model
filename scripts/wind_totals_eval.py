"""Moderate wind and game-total unders: the one pre-registered run (docs/wind_totals_preregistration.md).

Needs data/weather/game_wind.csv (scripts/fetch/game_wind.py). Writes docs/wind_totals_report.md. Runs in GitHub
Actions (nflverse is not reachable from the sandbox).
"""
from __future__ import annotations

import math
import sys

import polars as pl

from nflbet import config

BREAKEVEN = 110 / 210
ALPHA = 0.05
MIN_N = 150
LO, HI = 8.0, 15.0          # knots, [LO, HI)
KN_TO_MPH = 1.15078
CONFIRM = range(2000, 2015)  # 1999 dropped by amendment 2026-11-05 (no kickoff times)
PUBLISHED = range(2015, 2026)
FORWARD = 2026
MIN_WIND_CORR = 0.3


def side(total: float, line: float) -> str:
    return "under" if total < line else "over" if total > line else "push"


def bucket(w: float) -> str:
    return "calm <8" if w < LO else "moderate 8-15" if w < HI else "strong 15+"


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k), X ~ Binomial(n, p), summed in log space."""
    if k <= 0:
        return 1.0
    lp, lq = math.log(p), math.log1p(-p)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq
             for i in range(k, n + 1)]
    m = max(terms)
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in terms))


def verdict(unders: int, n: int) -> tuple[str, float]:
    if n < MIN_N:
        return "UNDERPOWERED", float("nan")
    p = binom_sf(unders, n, BREAKEVEN)
    return ("PASS" if p < ALPHA else "FAIL"), p


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sxy / (sx * sy)


def summarize(df: pl.DataFrame, by: str) -> pl.DataFrame:
    """Under rate (pushes dropped) and mean total - line per group."""
    d = df.filter(pl.col("side") != "push")
    return (d.group_by(by).agg(pl.len().alias("n"), (pl.col("side") == "under").sum().alias("unders"),
                               (pl.col("total") - pl.col("total_line")).mean().round(2).alias("total_minus_line"))
            .with_columns((pl.col("unders") / pl.col("n")).round(3).alias("under_rate")).sort(by))


def load() -> pl.DataFrame:
    import nflreadpy as nfl
    wind = pl.read_csv(config.ROOT / "data" / "weather" / "game_wind.csv")
    s = nfl.load_schedules(seasons=list(range(1999, FORWARD + 1)))
    s = s.filter(pl.col("game_type") == "REG", pl.col("location") != "Neutral",
                 pl.col("roof").is_in(["outdoors", "open"]))
    s = s.select("game_id", "season", "roof", "total_line", "home_score", "away_score",
                 pl.col("wind").cast(pl.Float64).alias("nflverse_wind_mph"))
    df = s.join(wind.select("game_id", "wind_kn"), on="game_id", how="left")
    return df


def table(t: pl.DataFrame) -> str:
    cols = t.columns
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in r) + " |" for r in t.iter_rows()]
    return "\n".join(lines)


def main() -> None:
    df = load()
    conf = df.filter(pl.col("season").is_in(list(CONFIRM)), pl.col("total_line").is_not_null(),
                     pl.col("home_score").is_not_null(), pl.col("away_score").is_not_null())
    out = ["# Moderate Wind and Game-Total Unders: Report", "",
           "Pre-registration: docs/wind_totals_preregistration.md. One run. Lines are nflverse `total_line`, "
           "graded at -110 (break-even 0.5238).", ""]

    # Gate 1: every confirm game has a wind value.
    miss = conf.filter(pl.col("wind_kn").is_null())
    if miss.height:
        sys.exit(f"GATE 1 FAIL: {miss.height} confirm games without wind, e.g. {miss['game_id'].head(5).to_list()}")
    # Gate 2: ERA5 wind vs nflverse recorded wind.
    both = conf.filter(pl.col("nflverse_wind_mph").is_not_null())
    r = pearson(both["wind_kn"].to_list(), both["nflverse_wind_mph"].to_list())
    out += [f"**Gate 1 (wind for every game):** pass, {conf.height} confirm games.",
            f"**Gate 2 (ERA5 vs nflverse recorded wind):** Pearson r = {r:.3f} on {both.height} games "
            f"(needs >= {MIN_WIND_CORR}).", ""]
    if r < MIN_WIND_CORR:
        (config.ROOT / "docs" / "wind_totals_report.md").write_text("\n".join(out + ["**STOPPED at gate 2.**"]))
        sys.exit("GATE 2 FAIL")

    df = df.with_columns((pl.col("home_score") + pl.col("away_score")).alias("total"))
    df = df.filter(pl.col("total").is_not_null(), pl.col("total_line").is_not_null(), pl.col("wind_kn").is_not_null())
    df = df.with_columns(pl.struct("total", "total_line").map_elements(
        lambda x: side(x["total"], x["total_line"]), return_dtype=pl.String).alias("side"),
        pl.col("wind_kn").map_elements(bucket, return_dtype=pl.String).alias("bucket"))
    c = df.filter(pl.col("season").is_in(list(CONFIRM)))
    prim = c.filter(pl.col("bucket") == "moderate 8-15", pl.col("side") != "push")
    n, u = prim.height, int((prim["side"] == "under").sum())
    v, p = verdict(u, n)
    out += ["## Primary test (2000-2014, 8 <= w < 15 knots)", "",
            f"Unders {u} of {n} (pushes dropped) = **{u / n:.3f}** vs break-even 0.524. "
            f"One-sided exact binomial p = {p:.4f}. **{v}**", "",
            "## Descriptive only (not verdicts)", "", "### 2000-2014 by wind bucket", "", table(summarize(c, "bucket")),
            "", "### 2000-2014 moderate bucket by season", "",
            table(summarize(c.filter(pl.col("bucket") == "moderate 8-15"), "season")), ""]
    rec = c.filter(pl.col("nflverse_wind_mph").is_not_null()).with_columns(
        pl.col("nflverse_wind_mph").is_between(LO * KN_TO_MPH, HI * KN_TO_MPH, closed="left").alias("moderate_mph"))
    out += ["### 2000-2014 using nflverse recorded wind (9.2 to 17.3 mph)", "", table(summarize(rec, "moderate_mph")),
            "", "### 2015-2025: outside work already reported these seasons, not a test", "",
            table(summarize(df.filter(pl.col("season").is_in(list(PUBLISHED))), "bucket")), "",
            f"### {FORWARD} games played so far (forward look)", "",
            table(summarize(df.filter(pl.col("season") == FORWARD), "bucket")), ""]
    (config.ROOT / "docs" / "wind_totals_report.md").write_text("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
