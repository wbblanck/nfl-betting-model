"""Phase 7 summary: calibration and A versus B, read only from the committed Test S results
(data/backtests/engine_test_s_*.json). No 2024-2025 outcome is read again and nothing is tested here.
Writes docs/engine/verification.md."""
import json
import sys

from nflbet.config import ROOT

VERSIONS = ("A-1.0", "B-1.0")
OUT = ROOT / "docs" / "engine" / "verification.md"


def main() -> int:
    R = {v: json.loads((ROOT / "data" / "backtests" / f"engine_test_s_{v}.json").read_text()) for v in VERSIONS}
    L = ["# Engine verification summary (phase 7)", "",
         "Written by `scripts/engine_verification.py` from the committed Test S results only (each run once on 2024-2025,",
         "Will's go-ahead). Nothing here is a new test or a new look at the test seasons' outcomes.", "",
         "## Test S verdicts", "", "| Market | Rows | A verdict | B verdict | A CRPS | B CRPS | B minus A |", "|---|---|---|---|---|---|---|"]
    for m in R["A-1.0"]["markets"]:
        a, b = R["A-1.0"]["markets"][m], R["B-1.0"]["markets"][m]
        L.append(f"| {m} | {a['n']:,} | {a['verdict']} | {b['verdict']} | {a['engine_crps']:.3f} | {b['engine_crps']:.3f} | "
                 f"{b['engine_crps'] - a['engine_crps']:+.3f} |")
    L += ["", "B minus A is reported, not tested (no interval was pre-registered for it).", "",
          "## Calibration: interval coverage, actual minus what an exactly right forecast would show", "",
          "Whole-number stats cover more than the nominal level even when right, so each band is compared with the share",
          "the engine's own runs would cover (Test S's 'coverage if right'). Positive = too wide; negative = too narrow.", "",
          "| Market | A 50% | A 80% | A 90% | B 50% | B 80% | B 90% | A mean bias | B mean bias |", "|---|---|---|---|---|---|---|---|---|"]
    for m in R["A-1.0"]["markets"]:
        row = [m]
        for v in VERSIONS:
            r = R[v]["markets"][m]
            row += [f"{100 * (r['coverage'][k] - r['coverage_if_right'][k]):+.1f}" for k in ("0.5", "0.8", "0.9")]
        row += [f"{R[v]['markets'][m]['mean_bias']:+.2f}" for v in VERSIONS]
        L.append("| " + " | ".join(row) + " |")
    L += ["", "Coverage gaps are in percentage points; mean bias is runs' mean minus outcomes' mean in the stat's units.",
          "Neither engine has been compared with a market price: that is Test M (2026 weeks 11-18, frozen 2026-11-17)."]
    OUT.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
