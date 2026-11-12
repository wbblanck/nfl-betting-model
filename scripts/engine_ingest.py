"""Engine phase 1: pull nflverse 2010-2025 into data/cache/engine/ (docs/engine/IMPLEMENTATION_PLAN.md)."""
import sys

from nflbet.engine.data import nflverse

if __name__ == "__main__":
    lo, hi = (int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "2010-2025").split("-"))
    man = nflverse.ingest(range(lo, hi + 1))
    bad = sorted(k for k, v in man.items() if v["status"] != "ok")
    print(f"{len(man) - len(bad)} ok, {len(bad)} unavailable")
