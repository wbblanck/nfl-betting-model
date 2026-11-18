"""Save the frozen engines' fitted parameters so later runs load them instead of refitting (Test M amendment of
2026-11-18). Refitting needs the nflverse warehouse exactly as it stood at the freeze, and nflverse revises its
players and schedule tables daily, so a refit elsewhere moves the numbers and the frozen-record check refuses.

Refits A-1.0 and B-1.0 from the local warehouse, refuses unless both match their frozen records, and writes
data/backtests/engine_A-1.0_params.pkl.gz and engine_B-1.0_params.pkl.gz plus their SHA-256 in
data/backtests/engine_params_sha256.json. engine.forecast loads them only if the file hashes match that record and
the loaded parameters reproduce the frozen records.
"""
import gzip
import hashlib
import json
import pickle
import sys

import engine_a_tune as TA
import engine_test_s as SA
import engine_test_s_b as SB
from nflbet.config import ROOT

DIR = ROOT / "data" / "backtests"


def main() -> int:
    PA, tab, pools = TA.fitted()
    fa = SA.fingerprint_of(PA, pools)
    fb, PB = SB.fingerprint()
    ok_a = all(json.loads(SA.FROZEN.read_text())[k] == fa[k] for k in fa)
    ok_b = all(json.loads(SB.FROZEN.read_text())[k] == fb[k] for k in fb)
    if not (ok_a and ok_b):
        print(f"REFUSED: frozen record matches A={ok_a} B={ok_b}")
        return 1
    shas = {}
    for name, obj in (("engine_A-1.0_params.pkl.gz", {"P": PA, "tab": tab, "pools": pools}), ("engine_B-1.0_params.pkl.gz", {"P": PB})):
        with gzip.GzipFile(DIR / name, "wb", mtime=0) as f:
            pickle.dump(obj, f, protocol=5)
        shas[name] = hashlib.sha256((DIR / name).read_bytes()).hexdigest()
    (DIR / "engine_params_sha256.json").write_text(json.dumps(shas, indent=1, sort_keys=True) + "\n")
    print(json.dumps(shas, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
