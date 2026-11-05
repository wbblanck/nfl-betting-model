"""Signal E, sharp vs soft prices (docs/five_signals_preregistration.md): exchange (Kalshi, ProphetX, BettorEdge)
no-vig P(side) minus DraftKings no-vig P(side), from the same capture run, last run before kickoff; bet the side at
DraftKings' price. `explore` = 2026 weeks 5-8 grid; `confirm` = frozen rules on weeks 9-18.

    python scripts/sharp_soft.py explore      # writes docs/sharp_soft_explore.txt
    python scripts/sharp_soft.py confirm      # after week 18, rules from docs/sharp_soft_confirm.md
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.quant.odds import no_vig_over
from nflbet.sources import parlay
from nflbet.sources.ids import TEAMS, game_key, norm_name

LIVE = config.ROOT / "data" / "live"
SEASON = 2026
VENUES = ["kalshi", "prophetx", "bettoredge"]
GRID_T = [3, 5, 8, 12]
GRID_SIZE = [0, 20]
STAT = {"rec": "receptions", "rec_yds": "receiving_yards", "rush_yds": "rushing_yards", "rush_att": "carries",
        "pass_yds": "passing_yards", "pass_att": "attempts", "pass_cmp": "completions"}


def _run_time(name: str) -> dt.datetime:
    return dt.datetime.strptime(name[:14], "%Y%m%dT%H%MZ").replace(tzinfo=dt.timezone.utc)


def _profit(odds: float) -> float:
    return odds / 100 if odds > 0 else 100 / -odds


def candidates(weeks: range) -> pl.DataFrame:
    """One row per (venue, game, player, market, line): the last same-run pair before kickoff."""
    rows = []
    for f in sorted((LIVE / "openmarkets").glob("*.csv.gz")):
        wk = int(f.name.split("_w")[1].split(".")[0])
        pf = LIVE / "parlay" / f.name.replace(".csv.gz", ".json.gz")
        if wk not in weeks or not pf.exists():
            continue
        t = _run_time(f.name)
        raw = json.loads(gzip.open(pf).read())
        kick = {}
        for r in raw:
            h, a = TEAMS.get(r.get("home_team")), TEAMS.get(r.get("away_team"))
            if h and a and r.get("commence_time"):
                kick[game_key(h, a)] = dt.datetime.fromisoformat(r["commence_time"].replace("Z", "+00:00"))
        dk = parlay.parse(raw).filter(pl.col("book") == "dk")
        om = pl.read_csv(f).filter(pl.col("p_over").is_not_null(), pl.col("p_under").is_not_null(),
                                   pl.col("venue").is_in(VENUES))
        j = dk.join(om, on=["game", "nkey", "market", "line"], how="inner")
        for r in j.iter_rows(named=True):
            k = kick.get(r["game"])
            if k is None or t >= k:
                continue
            ex = r["p_over"] / (r["p_over"] + r["p_under"])
            book = no_vig_over(r["over"], r["under"])
            gap = (ex - book) * 100
            side = "over" if gap > 0 else "under"
            rows.append({"run": t, "week": wk, "venue": r["venue"], "game": r["game"], "nkey": r["nkey"], "market": r["market"],
                         "line": r["line"], "side": side, "gap": abs(gap), "odds": r["over"] if side == "over" else r["under"],
                         "avail": r["avail_over"] if side == "over" else r["avail_under"]})
    d = pl.DataFrame(rows)
    return d.sort("run").group_by("venue", "game", "nkey", "market", "line", maintain_order=True).last()


def grade(c: pl.DataFrame) -> pl.DataFrame:
    """Actual from nflverse 2026 player stats by normalized name + team in the game; no stat row but offensive
    snaps = 0; neither = void (dropped)."""
    import nflreadpy as nfl

    st = nfl.load_player_stats(seasons=[SEASON]).filter(pl.col("season_type") == "REG")
    st = st.with_columns(pl.col("player_display_name").map_elements(norm_name, return_dtype=pl.Utf8).alias("nkey"))
    sn = nfl.load_snap_counts(seasons=[SEASON]).filter(pl.col("game_type") == "REG", pl.col("offense_snaps") > 0)
    sn = sn.with_columns(pl.col("player").map_elements(norm_name, return_dtype=pl.Utf8).alias("nkey"))
    out = []
    for r in c.iter_rows(named=True):
        teams = r["game"].split("|")
        s = st.filter(pl.col("week") == r["week"], pl.col("nkey") == r["nkey"], pl.col("team").is_in(teams))
        if s.height == 1:
            v = float(s[STAT[r["market"]]][0] or 0)
        elif s.height == 0 and sn.filter(pl.col("week") == r["week"], pl.col("nkey") == r["nkey"],
                                         pl.col("team").is_in(teams)).height:
            v = 0.0
        else:
            continue
        res = "push" if v == r["line"] else ("win" if (v > r["line"]) == (r["side"] == "over") else "loss")
        out.append({**r, "actual": v, "result": res,
                    "units": 0.0 if res == "push" else (_profit(r["odds"]) if res == "win" else -1.0)})
    return pl.DataFrame(out)


def roi_ci(b: pl.DataFrame, level: float, n=4000, seed=7) -> tuple[float, float, float]:
    u, w = b["units"].to_numpy(), b["week"].to_numpy()
    ids = np.unique(w)
    idx = [np.where(w == i)[0] for i in ids]
    rng = np.random.default_rng(seed)
    bs = [u[np.concatenate([idx[j] for j in rng.integers(0, len(ids), len(ids))])].mean() for _ in range(n)]
    return float(u.mean()), float(np.quantile(bs, level)), float(np.quantile(bs, 1 - level))


def select(g: pl.DataFrame, venue: str, t: float, size: float) -> pl.DataFrame:
    x = g.filter(pl.col("gap") >= t, pl.col("avail") >= size)
    if venue != "any":
        return x.filter(pl.col("venue") == venue)
    # one bet per prop: the largest gap across venues
    return x.sort("gap", descending=True).unique(["game", "nkey", "market", "line"], keep="first")


def explore() -> None:
    g = grade(candidates(range(5, 9)))
    L = [f"Sharp vs soft, explore 2026 weeks 5-8 (docs/five_signals_preregistration.md). Graded candidates: {g.height}; "
         f"pushes {g.filter(pl.col('result') == 'push').height}. ROI per bet; interval week-clustered 95% (descriptive).", ""]
    L.append(f"{'venue':<11}{'T':>4}{'size':>6}{'bets':>7}{'weeks':>7}{'won':>8}{'ROI':>9}   interval")
    for v in [*VENUES, "any"]:
        for t in GRID_T:
            for s in GRID_SIZE:
                b = select(g, v, t, s).filter(pl.col("result") != "push")
                if b.height < 5:
                    L.append(f"{v:<11}{t:>4}{s:>6}{b.height:>7}")
                    continue
                m, lo, hi = roi_ci(b, 0.025)
                L.append(f"{v:<11}{t:>4}{s:>6}{b.height:>7}{b['week'].n_unique():>7}{(b['result'] == 'win').mean():>8.3f}"
                         f"{m:>+9.3f}   {lo:+.3f} to {hi:+.3f}")
    (config.ROOT / "docs" / "sharp_soft_explore.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


RULES = [("E1_kalshi_gap3_size20", "kalshi", 3, 20), ("E2_bettoredge_gap3", "bettoredge", 3, 0)]   # docs/sharp_soft_confirm.md


def confirm(interim: bool = False) -> None:
    """Weeks 9-18 with the frozen RULES. PASS: n >= 30 in >= 5 weeks and the week-clustered ROI interval
    (one-sided 0.025 / len(RULES)) has its lower end above 0. With interim=True the table is descriptive."""
    g = grade(candidates(range(9, 19)))
    L = [f"# Sharp vs soft: {'INTERIM (descriptive only)' if interim else 'confirm'} 2026 weeks 9-18", "",
         "Rules frozen in docs/sharp_soft_confirm.md. Interval: week-clustered, one-sided 0.025/2.", "",
         "| Rule | Bets | Weeks | Won | ROI | Interval | Verdict |", "|---|---|---|---|---|---|---|"]
    for name, v, t, size in RULES:
        b = select(g, v, t, size).filter(pl.col("result") != "push") if g.height else g
        if b.height < 2:
            L.append(f"| {name} | {b.height} | | | | | |")
            continue
        m, lo, hi = roi_ci(b, 0.025 / len(RULES))
        ok = b.height >= 30 and b["week"].n_unique() >= 5 and lo > 0
        L.append(f"| {name} | {b.height} | {b['week'].n_unique()} | {(b['result'] == 'win').mean():.1%} | {m:+.1%} | "
                 f"{lo:+.1%} to {hi:+.1%} | {'' if interim else ('**PASS**' if ok else '**FAIL**')} |")
    (config.ROOT / "docs" / "sharp_soft_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"explore": explore, "confirm": confirm, "interim": lambda: confirm(True)}[sys.argv[1]]()
