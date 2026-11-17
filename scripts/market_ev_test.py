"""Rules M1 / M2 on 2025 Action Network props (docs/market_ev_preregistration.md, Part B).

python scripts/market_ev_test.py run   -> docs/market_ev_report.md (run once)
"""
import sys
from statistics import NormalDist

import polars as pl

from nflbet import config
from nflbet.props import core, market_ev as M

OUT = config.ROOT / "docs" / "market_ev_report.md"
ALPHA = 0.025


def min_detectable(n: int, alpha: float = 0.0125, power: float = 0.8, sd: float = 0.95) -> float:
    z = NormalDist().inv_cdf
    return (z(1 - alpha) + z(power)) * sd / n ** 0.5


def main() -> None:
    lines = core.load_lines(2025).filter(pl.col("week").is_between(1, 18))
    joined = core.join(lines, core.load_stats(2025), core.load_snaps(2025))
    d = M.screened(joined)
    cand = M.bets(d)
    res = {}
    for rule in M.RULES:
        g = M.units(M.select(cand, rule))
        n, weeks = g.height, g["week"].n_unique() if g.height else 0
        roi, p, lo, hi = M.week_bootstrap(g) if n else (None, 1.0, None, None)
        wins = int((g["units"] > 0).sum()) if n else 0
        res[rule] = dict(n=n, weeks=weeks, wins=wins, roi=roi, p=p, lo=lo, hi=hi,
                         ev=float(g["ev"].mean()) if n else None, books=float(g["n_books"].mean()) if n else None)
    order = sorted(res, key=lambda r: res[r]["p"])                   # Holm: smallest p first
    thresholds = {r: ALPHA / (len(order) - i) for i, r in enumerate(order)}
    still = True
    for r in order:
        x = res[r]
        ok = still and x["n"] >= 30 and x["weeks"] >= 5 and x["p"] < thresholds[r]
        x["pass"], x["thr"] = ok, thresholds[r]
        still = still and ok
    pct = lambda v: "–" if v is None else f"{v * 100:+.1f}%"
    rows = "\n".join(
        f"| {r} | {'EV > 0' if r == 'M1' else 'EV >= 3%'} | {x['n']:,} | {x['weeks']} | {x['wins']:,} | {pct(x['ev'])} | {pct(x['roi'])} "
        f"| {pct(x['lo'])} to {pct(x['hi'])} | {x['p']:.4f} | {x['thr']:.4f} | {'**PASS**' if x['pass'] else 'fail'} "
        f"| {pct(min_detectable(x['n'])) if x['n'] else '–'} |" for r, x in res.items())
    n_props = cand.height
    OUT.write_text(
        "# Market EV on 2025 props: report\n\n"
        "Pre-registration: [market_ev_preregistration.md](market_ev_preregistration.md), committed before this run. "
        "Run once with `python scripts/market_ev_test.py run`.\n\n"
        f"**Sample:** {n_props:,} props with 3+ screened books (weeks 1-18, 2025, Action Network). "
        f"{joined.height:,} book quotes before the screen, {d.height:,} after it. One candidate side per prop.\n\n"
        "| Rule | Bet when | Graded bets | Weeks | Wins | Mean EV at bet | ROI at best book | 95% week-bootstrap | p | Holm threshold | Verdict | Smallest ROI detectable (80% power) |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        f"{rows}\n\n"
        "ROI is per 1 unit at the best book's price. The p-value is the share of 10,000 week-resampled ROIs at or below 0 "
        "(seed 7). Action Network lines carry no timestamps, so a best price may not have been live alongside the others: "
        "a pass would be an upper bound (pre-registration, \"Known bias\").\n")
    print(OUT.read_text())


if __name__ == "__main__":
    if sys.argv[1:] != ["run"]:
        sys.exit("usage: python scripts/market_ev_test.py run")
    main()
