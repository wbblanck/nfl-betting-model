"""Rules D1-D2 on DraftKings / FanDuel prices (docs/dkfd_rules_preregistration.md), 2026 weeks 9-18.

    python scripts/dkfd_rules.py interim     # descriptive, any time
    python scripts/dkfd_rules.py confirm     # after week 18
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sharp_soft as SS  # noqa: E402  (run-time parsing and grading shared with signal E)

from nflbet import config  # noqa: E402
from nflbet.quant.odds import implied, no_vig_over  # noqa: E402
from nflbet.sources import parlay  # noqa: E402
from nflbet.sources.ids import TEAMS, game_key, norm_name  # noqa: E402

WEEKS = range(9, 19)
GAP = 0.10            # P1's projection gap
MAX_REL = 0.30        # line gap at most 30% of the lower line (docs/selective_props_confirm.md)
UNDER_MAX = -120      # D2: under priced below -120
MARKETS = list(SS.STAT)


def screen(q: pl.DataFrame) -> pl.DataFrame:
    """Junk-quote screen (CLAUDE.md): de-vigged P(over) 0.35-0.65 and hold under 10%."""
    rows = []
    for r in q.iter_rows(named=True):
        p = no_vig_over(r["over"], r["under"])
        hold = implied(r["over"]) + implied(r["under"]) - 1
        if 0.35 <= p <= 0.65 and hold < 0.10:
            rows.append(r)
    return pl.DataFrame(rows, schema=q.schema)


def pairs(weeks=WEEKS) -> pl.DataFrame:
    """One row per prop: DK and FD quotes from the last run before kickoff in which both quote it (screened)."""
    out = []
    for f in sorted((SS.LIVE / "parlay").glob("*.json.gz")):
        wk = int(f.name.split("_w")[1].split(".")[0])
        if wk not in weeks:
            continue
        t = SS._run_time(f.name)
        raw = json.loads(gzip.open(f).read())
        kick = {}
        for r in raw:
            h, a = TEAMS.get(r.get("home_team")), TEAMS.get(r.get("away_team"))
            if h and a and r.get("commence_time"):
                kick[game_key(h, a)] = dt.datetime.fromisoformat(r["commence_time"].replace("Z", "+00:00"))
        q = parlay.parse(raw).filter(pl.col("market").is_in(MARKETS))
        q = q.filter(pl.col("game").map_elements(lambda g: g in kick and t < kick[g], return_dtype=pl.Boolean))
        q = screen(q)
        k = ["game", "nkey", "market"]
        dk = q.filter(pl.col("book") == "dk").select(*k, pl.col("line").alias("dk_line"), pl.col("over").alias("dk_over"),
                                                    pl.col("under").alias("dk_under"))
        fd = q.filter(pl.col("book") == "fd").select(*k, pl.col("line").alias("fd_line"), pl.col("over").alias("fd_over"),
                                                    pl.col("under").alias("fd_under"))
        j = dk.join(fd, on=k)
        if j.height:
            out.append(j.with_columns(pl.lit(t).alias("run"), pl.lit(wk).alias("week")))
    if not out:
        return pl.DataFrame()
    d = pl.concat(out).sort("run")
    return d.group_by("game", "nkey", "market", maintain_order=True).last()


def disagree(p: pl.DataFrame) -> pl.DataFrame:
    lo = pl.min_horizontal("dk_line", "fd_line")
    return p.filter(pl.col("dk_line") != pl.col("fd_line"),
                    (pl.max_horizontal("dk_line", "fd_line") - lo) / lo.abs().clip(lower_bound=1) <= MAX_REL)


def rule_d2(p: pl.DataFrame) -> pl.DataFrame:
    """Under at the higher of the two lines, at that book's price, when that under is priced below -120."""
    d = disagree(p).with_columns(
        pl.when(pl.col("dk_line") > pl.col("fd_line")).then(pl.col("dk_line")).otherwise(pl.col("fd_line")).alias("line"),
        pl.when(pl.col("dk_line") > pl.col("fd_line")).then(pl.col("dk_under")).otherwise(pl.col("fd_under")).alias("odds"))
    return d.filter(pl.col("odds") < UNDER_MAX).with_columns(pl.lit("under").alias("side"))


def rule_d1(p: pl.DataFrame, proj: pl.DataFrame) -> pl.DataFrame:
    """P1 on two books: DK's line is the higher and at least GAP above the projection; under at DK's price.
    proj: week, nkey, market, team, proj (projection rows exist only for players with a 2026 stat row that week)."""
    d = disagree(p).filter(pl.col("dk_line") > pl.col("fd_line"))
    d = d.with_columns(pl.col("game").str.split("|").alias("_t")).explode("_t").rename({"_t": "team"})
    d = d.join(proj, on=["week", "nkey", "market", "team"], how="inner").drop("team")
    d = d.filter((pl.col("dk_line") - pl.col("proj")) / pl.col("dk_line").abs().clip(lower_bound=1) >= GAP)
    return d.with_columns(pl.col("dk_line").alias("line"), pl.col("dk_under").alias("odds"), pl.lit("under").alias("side"))


def projections() -> pl.DataFrame:
    import nflreadpy as nfl

    from nflbet.props import projection as R

    pr = R.projections(SS.SEASON).select("player_id", "week", "market", "proj")
    names = nfl.load_player_stats(seasons=[SS.SEASON]).filter(pl.col("season_type") == "REG") \
        .select("player_id", "week", "team", pl.col("player_display_name").map_elements(norm_name, return_dtype=pl.Utf8).alias("nkey"))
    return pr.join(names, on=["player_id", "week"]).select("week", "nkey", "market", "team", "proj")


def report(interim: bool) -> None:
    p = pairs()
    sets = {"D1_p1_on_dk_fd": rule_d1(p, projections()) if p.height else p, "D2_under_below_-120_high_line": rule_d2(p) if p.height else p}
    L = [f"# DK/FD prop rules: {'INTERIM (descriptive only)' if interim else 'confirm'} 2026 weeks 9-18", "",
         f"Pre-registration: docs/dkfd_rules_preregistration.md. Props with both books quoting: {p.height}. "
         "Interval: week-clustered, one-sided 0.025/2.", "", "| Rule | Bets | Weeks | Under won | ROI | Interval | Verdict |",
         "|---|---|---|---|---|---|---|"]
    for name, x in sets.items():
        g = SS.grade(x.select("week", "game", "nkey", "market", "line", "side", "odds")) if x.height else x
        b = g.filter(pl.col("result") != "push") if g.height else g
        if b.height < 2:
            L.append(f"| {name} | {b.height} | | | | | |")
            continue
        m, lo, hi = SS.roi_ci(b, 0.025 / 2)
        ok = b.height >= 30 and b["week"].n_unique() >= 5 and lo > 0
        L.append(f"| {name} | {b.height} | {b['week'].n_unique()} | {(b['result'] == 'win').mean():.1%} | {m:+.1%} | "
                 f"{lo:+.1%} to {hi:+.1%} | {'' if interim else ('**PASS**' if ok else '**FAIL**')} |")
    (config.ROOT / "docs" / "dkfd_rules_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"interim": lambda: report(True), "confirm": lambda: report(False)}[sys.argv[1]]()
