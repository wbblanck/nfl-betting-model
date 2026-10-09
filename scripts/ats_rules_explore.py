"""Exploration of narrower ATS rules on 2014-2024 opening lines with prices (ASB: Pinnacle 2014-17, bet365 2018-24).
These seasons were already used in docs/ats_clv*.md, so everything here is a hypothesis. Writes docs/ats_rules_explore.txt.
Candidate rules (all: the rating's side at the opening number and opening price, weeks 2-18):
  G1.5 / G2 / G3   |fair - open| >= 1.5 / 2 / 3 points
  KEY              the opening number and the fair line sit on opposite sides of 3 or 7 (the bet side gets a key number)
  KEY+G1           KEY and |fair - open| >= 1
  PRICE            G1.5 and the side's opening price is -110 or better
  DOG / FAV        G1.5 and the bet side is the underdog / favorite at the open
  SOFT             G1.5, bet365 era only (2018-24) vs Pinnacle era (2014-17) shown separately"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import ats_clv2 as C2  # noqa: E402

from nflbet import config, props as P  # noqa: E402


def crosses_key(o, f, home):
    """True if the bet side's number is on the better side of 3 or 7 relative to the fair line."""
    # express from the bet side: its number s (points it gets; positive = underdog), fair f_s
    s, fs = (-o, -f) if home else (o, f)
    for k in (3, 7):
        for sign in (1, -1):
            kk = sign * k
            if s > kk > fs or s > kk and fs == kk:   # bet side's number above a key the fair line is at or below
                return True
    return False


def grade(x, mask):
    z = x.filter(pl.Series(mask))
    if not z.height:
        return {"n": 0}
    o, f, m = z["home_open"].to_numpy(), z["fair"].to_numpy(), z["result"].to_numpy()
    home = f > o
    px = np.where(home, z["home_open_odds"].to_numpy(), z["away_open_odds"].to_numpy()).astype(float)
    won = np.where(home, m > o, m < o)
    push = m == o
    pnl = np.where(push, 0.0, P.profit(px, won.astype(float)))
    return {"n": z.height, "weeks": int(z.select(pl.col("season") * 100 + pl.col("week")).n_unique()),
            "cover": float(won[~push].mean()), "roi": float(pnl.mean()), "units": float(pnl.sum())}


def main():
    k = json.loads((config.ROOT / "data" / "backtests" / "ats_constants.json").read_text())
    x = C2.frame(list(range(2014, 2025)), k)
    o, f = x["home_open"].to_numpy(), x["fair"].to_numpy()
    home = f > o
    gap = np.abs(f - o)
    side_px = np.where(home, x["home_open_odds"].to_numpy(), x["away_open_odds"].to_numpy()).astype(float)
    dog = np.where(home, o < 0, o > 0)
    key = np.array([crosses_key(a, b, h) for a, b, h in zip(o, f, home)])
    era = x["season"].to_numpy()
    rules = {"G1.5": gap >= 1.5, "G2": gap >= 2, "G3": gap >= 3, "KEY": key, "KEY+G1": key & (gap >= 1),
             "PRICE": (gap >= 1.5) & (side_px >= -110), "DOG": (gap >= 1.5) & dog, "FAV": (gap >= 1.5) & ~dog & (o != 0)}
    L = [f"Exploration 2014-2024: {x.height} games with opening line and prices (hypotheses only)", "",
         "rule      | era        |    n | cover |   ROI  | units"]
    for name, msk in rules.items():
        for lab, emask in (("2014-2024", np.ones_like(msk)), ("Pinnacle14-17", era <= 2017), ("bet365 18-24", era >= 2018)):
            r = grade(x, msk & emask)
            L.append(f"{name:9s} | {lab:13s} | {r['n']:4d} | {r.get('cover', 0):.3f} | {r.get('roi', 0):+.3f} | {r.get('units', 0):+.1f}")
    (config.ROOT / "docs" / "ats_rules_explore.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
