"""S1 variants backtest on 2024-2025 (docs/variants_preregistration.md). Writes docs/variants_backtest.md and
data/backtests/variants_backtest.json. Exploration: a pass is a hypothesis for a 2026 live record, not a rule."""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import polars as pl

from nflbet import config, props as P, props_confirm as C, props_projection as R, props_selective as S, screener as Sc
from nflbet.sim import Simulator

FAMILY = 12
LEVEL = 0.025 / FAMILY


def scored_full(season: int, sim: Simulator, weeks: tuple[int, int] | None = None) -> pl.DataFrame:
    """screener.scored plus FanDuel's line per prop (for V9) and raw gaps for threshold variants."""
    lines = P.load_lines(season)
    if weeks:
        lines = lines.filter(pl.col("week").is_between(*weeks))
    g = P.graded(P.join(lines, P.load_stats(season), P.load_snaps(season)))
    s = C.screened(g).filter(pl.col("result") != "push", pl.col("market").is_in(Sc.MARKETS))
    out = sim.run(season, keep=set(zip(s["player_id"].to_list(), s["week"].to_list())))
    d = Sc.score(s, R.projections(season), out)
    fd = s.filter(pl.col("book") == "FanDuel NJ").unique(subset=C.KEY).select(*C.KEY, pl.col("line").alias("fd_line"))
    d = d.join(fd, on=C.KEY, how="left")
    gap = (pl.col("line") - pl.col("proj")) / pl.col("line").abs().clip(lower_bound=1)
    return d.with_columns(gap.alias("gap"), (pl.col("p_sim") - pl.col("p_over")).alias("edge"))


def vote(under, over):
    return pl.when(under).then(-1).when(over).then(1).otherwise(0)


def variants(d: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """{id: bets with a `side` column (-1 under, +1 over)}."""
    B, J, M, Pz = pl.col("v_disagree"), pl.col("v_proj"), pl.col("v_sim"), pl.col("v_price")
    j15 = vote(pl.col("gap") >= 0.15, pl.col("gap") <= -0.15).fill_null(0)
    m8 = vote(pl.col("edge") <= -0.08, pl.col("edge") >= 0.08).fill_null(0)
    p110 = vote(pl.col("under_odds") < -110, pl.col("over_odds") < -110)
    p130 = vote(pl.col("under_odds") < -130, pl.col("over_odds") < -130)
    bfd = vote(pl.col("fd_line").is_not_null() & (pl.col("line") > pl.col("fd_line")),
               pl.col("fd_line").is_not_null() & (pl.col("line") < pl.col("fd_line")))
    side_odds = pl.when(B < 0).then(pl.col("under_odds")).otherwise(pl.col("over_odds"))
    tot = B + J + M + Pz
    against = ((B * tot) < 0) | ((J * tot) < 0) | ((M * tot) < 0) | ((Pz * tot) < 0)

    def all_agree(*vs):
        e = (vs[0] != 0)
        for v in vs[1:]:
            e = e & (v == vs[0])
        return e

    sel = {
        "V1": (all_agree(B, J, M, Pz), B),
        "V2": ((tot.abs() >= 3) & ~against, tot.sign()),
        "V3": (all_agree(B, J, M) & (Pz == 0), B),
        "V4": (all_agree(J, M, Pz) & (B == 0), J),
        "V5": (all_agree(B, j15, M, Pz), B),
        "V6": (all_agree(B, J, m8, Pz), B),
        "V7": (all_agree(B, J, M, p110), B),
        "V8": (all_agree(B, J, M, p130), B),
        "V9": (all_agree(bfd, J, M, Pz), bfd),
        "V10": (all_agree(B, J, M, Pz) & (B < 0), B),
        "V11": ((tot.abs() >= 3) & ~against & (tot < 0), tot.sign()),
        "V12": (all_agree(B, J, M) & (side_odds >= -120), B),
        "V13": (all_agree(B, J, M), B),
    }
    return {k: d.with_columns(side.alias("votes")).filter(cond) for k, (cond, side) in sel.items()}


def grade(x: pl.DataFrame) -> dict:
    if not x.height:
        return {"n": 0}
    b = Sc.bets_frame(x)
    r = S.evaluate(b, level=LEVEL)
    be = np.mean([-o / (-o + 100) if o < 0 else 100 / (o + 100) for o in b["under_odds"].to_list()])
    return {**r, "win": r["under_rate"], "break_even": float(be)}


OOS = ["V1", "V5", "V6", "V7", "V10", "V11", "V13"]


def oos(season: int, weeks: tuple[int, int]) -> None:
    """Addendum: descriptive out-of-sample look (docs/variants_preregistration.md)."""
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, season - 1, season])
    d = scored_full(season, sim, weeks)
    v = variants(d)
    res = {k: grade(v[k].with_columns(pl.lit(season).alias("season"))) for k in OOS}
    L = [f"\n## Out-of-sample look: {season} weeks {weeks[0]}-{weeks[1]} (descriptive, addendum)", "",
         f"{d.height} DraftKings props scored.", "",
         "| ID | Bets | Weeks | Win | Break-even | ROI | Units |", "|---|---|---|---|---|---|---|"]
    for k, r in res.items():
        if not r.get("n"):
            L.append(f"| {k} | 0 | | | | | |")
            continue
        L.append(f"| {k} | {r['n']} | {r['weeks']} | {r['win']:.1%} | {r['break_even']:.1%} | {r['roi']:+.1%} | {r['roi'] * r['n']:+.2f} |")
    with open(config.ROOT / "docs" / "variants_backtest.md", "a") as f:
        f.write("\n".join(L) + "\n")
    j = config.ROOT / "data" / "backtests" / "variants_backtest.json"
    out = json.loads(j.read_text())
    out[f"oos_{season}_w{weeks[0]}-{weeks[1]}"] = res
    j.write_text(json.dumps(out, indent=1, default=str))
    print("\n".join(L))


def main() -> None:
    import sys
    if "--season" in sys.argv:
        a, b = sys.argv[sys.argv.index("--weeks") + 1].split("-")
        return oos(int(sys.argv[sys.argv.index("--season") + 1]), (int(a), int(b)))
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, 2025])
    res = {}
    for season in (2024, 2025):
        d = scored_full(season, sim)
        for k, x in variants(d).items():
            res.setdefault(k, {})[season] = grade(x.with_columns(pl.lit(season).alias("season")) if "season" not in x.columns else x)
    verdict = {}
    for k, r in res.items():
        a, b = r[2025], r[2024]
        ok25 = a.get("n", 0) >= 30 and a.get("weeks", 0) >= 10 and a["roi_ci"][0] > 0 if a.get("n") else False
        ok24 = b.get("n", 0) < 30 or b["roi"] >= 0
        verdict[k] = "reference" if k == "V1" else ("PASS (hypothesis)" if ok25 and ok24 else "fail")
    out = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "level_one_sided": LEVEL, "results": res, "verdict": verdict}
    (config.ROOT / "data" / "backtests" / "variants_backtest.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["# S1 variants backtest, 2024-2025 (exploration)", "",
         "Pre-registration: docs/variants_preregistration.md. Interval: week-clustered, one-sided 0.025/12 per end. "
         "2025 is the primary season (simulator and projection fitted on 2024). A pass is a hypothesis for a 2026 live record.", "",
         "| ID | Season | Bets | Weeks | Win | Break-even | ROI | Interval | Verdict |", "|---|---|---|---|---|---|---|---|---|"]
    for k in res:
        for season in (2025, 2024):
            r = res[k][season]
            if not r.get("n"):
                L.append(f"| {k} | {season} | 0 | | | | | | {verdict[k] if season == 2025 else ''} |")
                continue
            L.append(f"| {k} | {season} | {r['n']} | {r['weeks']} | {r['win']:.1%} | {r['break_even']:.1%} | {r['roi']:+.1%} | "
                     f"{r['roi_ci'][0]:+.1%} to {r['roi_ci'][1]:+.1%} | {verdict[k] if season == 2025 else ''} |")
    (config.ROOT / "docs" / "variants_backtest.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
