"""E-value readout for the live trackers (docs/m20_evalues_preregistration.md). Descriptive only: never changes a
tracker's registered verdict.

  python scripts/evalues.py    writes docs/evalues_2026.md
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nflbet.execution import evalues as V  # noqa: E402

LIVE = ROOT / "data" / "live"
START = 10  # the official readout starts the product at 1 with week 10's bets
TRACKERS = {"ATS tracker": "ats_record_2026.csv", "ATS tracker, your venues": "ats_yv_record_2026.csv",
            "S1": "s1_record_2026.csv", "S1 (ParlayAPI)": "s1pa_record_2026.csv",
            "S1, your venues": "s1_yv_record_2026.csv", "Props mix": "mix_record_2026.csv"}


def kickoff(r: dict) -> str:
    return r.get("start_time") or r.get("kickoff_utc") or r.get("run_utc") or ""


def done(r: dict) -> bool:
    status = r.get("result_ats") or r.get("result") or ""
    return status not in ("", "pending") and r.get("units") not in (None, "")


def graded(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        rows = [r for r in csv.DictReader(f) if done(r) and r.get("week")]
    if path.name.startswith("ats_"):
        rows = [r for r in rows if r.get("label") == "Bet Now"]  # the ATS tracker is judged on Bet Now games only
    return sorted(rows, key=lambda r: (kickoff(r), r.get("game_id") or r.get("an_game_id") or ""))


def wind_rows() -> tuple[list[dict], str]:
    try:
        spec = importlib.util.spec_from_file_location("wind_live", ROOT / "scripts" / "wind_live.py")
        wl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wl)
        games = {g["game_id"]: g for g in wl.schedule()}
        rows = [r for r in wl.grade_rows(wl.W.official(wl.read_records()), games)
                if r["pick"] == "under" and r["result"] in ("W", "L", "P")]
        return sorted(rows, key=kickoff), ""
    except Exception as e:  # noqa: BLE001 - the readout must still be written without the wind source
        return [], f"wind unders left out: {type(e).__name__}"


def main() -> None:
    data = {name: graded(LIVE / f) for name, f in TRACKERS.items()}
    w, note = wind_rows()
    data["Wind unders"] = w
    k = len(data)
    lines = ["# E-value readout, 2026 (descriptive)", "",
             "Method: docs/m20_evalues_preregistration.md. E is how far the running record is from 'no edge' in a way "
             "that may be read every week: if a tracker has no edge, the chance its E ever reaches 20 is at most 5%. "
             f"Read together ({k} trackers), the bar is {20 * k}. This page never changes a tracker's own verdict.", ""]
    for title, keep in ((f"From week {START} (official readout)", lambda r: int(float(r["week"])) >= START),
                        (f"Weeks 1-{START - 1} (descriptive)", lambda r: int(float(r["week"])) < START)):
        lines += [f"## {title}", "", "| Tracker | Bets | Units | E now | E max | Reached 20 | Reached " + str(20 * k) + " |",
                  "|---|---|---|---|---|---|---|"]
        for name, rows in data.items():
            u = [float(r["units"]) for r in rows if keep(r)]
            s = V.summary(u)
            lines.append(f"| {name} | {s['bets']} | {s['units']:+.2f} | {s['e']:.2f} | {s['e_max']:.2f} | "
                         f"{'yes' if s['e_max'] >= 20 else 'no'} | {'yes' if s['e_max'] >= 20 * k else 'no'} |")
        lines.append("")
    if note:
        lines += [f"Note: {note}.", ""]
    (ROOT / "docs" / "evalues_2026.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
