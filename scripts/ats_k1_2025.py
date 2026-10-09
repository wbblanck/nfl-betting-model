"""K1 interim on 2025 betr openers (docs/ats_key_preregistration.md). Descriptive; writes docs/ats_k1.md."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import ats_clv2 as C2  # noqa: E402
import ats_rules_explore as R  # noqa: E402

from nflbet import config  # noqa: E402


def main():
    k = json.loads((config.ROOT / "data" / "backtests" / "ats_constants.json").read_text())
    x = C2.frame([2025], k)
    o, f = x["home_open"].to_numpy(), x["fair"].to_numpy()
    home = f > o
    msk = (np.abs(f - o) >= 1) & np.array([R.crosses_key(a, b, h) for a, b, h in zip(o, f, home)])
    r = R.grade(x, msk)
    L = ["# ATS rule K1: interim", "", "Pre-registration: docs/ats_key_preregistration.md. Decided only after the 2026 season (2025 + 2026 pooled).", "",
         f"- 2025 (betr openers and prices, {x.height} games with prices): K1 bets {r['n']} in {r.get('weeks', 0)} weeks, covered "
         f"{r.get('cover', 0):.1%}, ROI {r.get('roi', 0):+.1%}, units {r.get('units', 0):+.2f}. Descriptive."]
    (config.ROOT / "docs" / "ats_k1.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
