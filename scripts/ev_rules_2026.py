"""Rules K (market EV > 0) and Mo (model EV > 0) on 2026 weeks 11-18 props mix picks
(docs/ev_rules_2026_preregistration.md).

python scripts/ev_rules_2026.py interim   -> docs/ev_rules_2026_report.md, descriptive only, no verdict
python scripts/ev_rules_2026.py confirm   -> the same file with the verdict; run once after week 18 is graded
"""
import sys

import polars as pl

from nflbet import config
from nflbet.gamesim import mix_live as Mx
from nflbet.props import market_ev as M

OUT = config.ROOT / "docs" / "ev_rules_2026_report.md"
ALPHA = 0.025


def _read(p):
    return pl.read_csv(p, infer_schema_length=0) if p.exists() and p.stat().st_size else pl.DataFrame()


def table(rows: pl.DataFrame, verdict: bool) -> str:
    res = {}
    for rule, col in M.FORWARD_RULES.items():
        g = rows.filter(pl.col(col) > 0) if rows.height else rows
        n = g.height
        weeks = g["week"].n_unique() if n else 0
        roi, p, lo, hi = M.week_bootstrap(g) if n else (None, 1.0, None, None)
        roi_dk = float(g["units_dk"].sum()) / n if n else None
        res[rule] = dict(n=n, weeks=weeks, w=int((g["units"] > 0).sum()) if n else 0, roi=roi, roi_dk=roi_dk, p=p, lo=lo, hi=hi,
                         u=float(g["units"].sum()) if n else 0.0)
    order = sorted(res, key=lambda r: res[r]["p"])
    still = True
    for i, r in enumerate(order):
        x = res[r]
        x["thr"] = ALPHA / (len(order) - i)
        x["pass"] = still and x["n"] >= 30 and x["weeks"] >= 5 and x["p"] < x["thr"]
        still = still and x["pass"]
    pct = lambda v: "–" if v is None else f"{v * 100:+.1f}%"
    head = "| Rule | Bet when | Bets | Weeks | Record | Units (best price) | ROI best price | ROI at DK | 95% week bootstrap | p |"
    if verdict:
        head += " Holm threshold | Verdict |"
    lines = [head, "|" + " --- |" * (head.count("|") - 1)]
    for r, x in res.items():
        line = (f"| {r} | {'market EV > 0' if r == 'K' else 'model EV > 0'} | {x['n']} | {x['weeks']} | {x['w']}-{x['n'] - x['w']} | "
                f"{x['u']:+.2f} | {pct(x['roi'])} | {pct(x['roi_dk'])} | {pct(x['lo'])} to {pct(x['hi'])} | {x['p']:.4f} |")
        if verdict:
            line += f" {x['thr']:.4f} | {'**PASS**' if x['pass'] else 'fail'} |"
        lines.append(line)
    return "\n".join(lines)


def main(mode: str) -> None:
    rows = M.forward_rows(_read(Mx.RECORD), _read(Mx.BEST))
    verdict = mode == "confirm"
    wk = sorted(rows["week"].unique().to_list()) if rows.height else []
    OUT.write_text(
        "# Market EV vs model EV, 2026 weeks 11-18: " + ("result" if verdict else "interim (descriptive, no verdict)") + "\n\n"
        "Pre-registration: [ev_rules_2026_preregistration.md](ev_rules_2026_preregistration.md). "
        f"Graded weeks so far: {', '.join(map(str, wk)) or 'none'}.\n\n" + table(rows, verdict) + "\n\n"
        "1 unit per pick at the pick's best price (fees included); ROI at DraftKings' price shown alongside. "
        + ("" if verdict else "Interim numbers are descriptive; the verdict is computed once after week 18.") + "\n")
    print(OUT.read_text())


if __name__ == "__main__":
    if sys.argv[1:] not in (["interim"], ["confirm"]):
        sys.exit("usage: python scripts/ev_rules_2026.py interim|confirm")
    main(sys.argv[1])
