"""On-time starts for the scheduled workflows. GitHub starts `schedule:` runs late (hours, sometimes never), so an
outside cron service (cron-job.org) calls .github/workflows/scheduler.yml every 5 minutes, and this script starts
every workflow whose own `schedule:` cron came due in the last LOOKBACK minutes and that has not run since.

The times are read from each workflow file's `schedule:` block, so the workflow files stay the one place a time is
set. Inputs for a dispatched run reproduce what the schedule would have done (INPUTS). Display and records are the
workflows' own; this script only starts them.

  python scripts/scheduler.py              start what is due (needs GITHUB_TOKEN with actions: write)
  python scripts/scheduler.py --dry-run    print what would start now, start nothing
  python scripts/scheduler.py --day        print every start on the current UTC day, start nothing
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
REPO = "wbblanck/nfl-betting-model"
LOOKBACK = 30          # minutes: a cron time is started at the first call within this window after it
SKIP = {"scheduler.yml"}

# Inputs a dispatched run needs to do what the scheduled run at that cron does (the workflows pick the step from
# github.event.schedule when scheduled, from inputs.step when dispatched).
GRADE = {"live-s1.yml": {"7 14 * * 1", "33 15 * * 2", "7 14 * * 3"}, "wind-live.yml": {"17 15 * * 2"}}
INPUTS = {"live-s1.yml": lambda c: {"step": "grade" if c in GRADE["live-s1.yml"] else "run"},
          "wind-live.yml": lambda c: {"step": "grade" if c in GRADE["wind-live.yml"] else "record"},
          "novig-books.yml": lambda c: {"hours": "6"},
          "fetch-props.yml": lambda c: {"season": "2026"}}


def field(spec: str, value: int, lo: int) -> bool:
    """One cron field: *, */n, a-b, a-b/n, n, and comma lists. lo is the field's lowest value (0, or 1 for days)."""
    for part in spec.split(","):
        rng, _, step = part.partition("/")
        step = int(step) if step else 1
        if rng == "*":
            a, b = lo, 10 ** 6
        elif "-" in rng:
            a, b = map(int, rng.split("-"))
        else:
            a = b = int(rng)
            if step > 1:
                b = 10 ** 6
        if a <= value <= b and (value - a) % step == 0:
            return True
    return False


def matches(cron: str, t: dt.datetime) -> bool:
    """Five-field cron (UTC, as GitHub reads it) against a minute. Day of week: 0 = Sunday (7 also Sunday)."""
    mi, ho, dom, mon, dow = cron.split()
    wd = (t.weekday() + 1) % 7
    dow_ok = field(dow, wd, 0) or (wd == 0 and field(dow, 7, 0))
    return field(mi, t.minute, 0) and field(ho, t.hour, 0) and field(dom, t.day, 1) and field(mon, t.month, 1) and dow_ok


def schedules() -> dict[str, list[str]]:
    """workflow file -> its schedule crons, for workflows that can be dispatched."""
    out = {}
    for f in sorted(WF.glob("*.yml")):
        if f.name in SKIP:
            continue
        d = yaml.safe_load(f.read_text())
        on = d.get(True, d.get("on")) or {}
        if isinstance(on, dict) and "schedule" in on and "workflow_dispatch" in on:
            out[f.name] = [s["cron"] for s in on["schedule"]]
    return out


def due(now: dt.datetime, sched: dict[str, list[str]], lookback: int = LOOKBACK) -> list[tuple[str, str, dt.datetime]]:
    """(workflow, cron, scheduled minute) for the latest scheduled minute of each workflow in (now - lookback, now]."""
    now = now.replace(second=0, microsecond=0)
    out = {}
    for m in range(lookback):
        t = now - dt.timedelta(minutes=m)
        for wf, crons in sched.items():
            for c in crons:
                if wf not in out and matches(c, t):
                    out[wf] = (wf, c, t)
    return sorted(out.values(), key=lambda x: x[2])


def _api(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                          "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return r.status, (json.loads(raw) if raw else {})


def ran_since(wf: str, t: dt.datetime) -> bool:
    """Any run of the workflow (scheduled, dispatched or otherwise) created at or after t."""
    _, d = _api("GET", f"actions/workflows/{wf}/runs?per_page=1&branch=main&created=%3E%3D{t.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    return d.get("total_count", 0) > 0


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    sched = schedules()
    if "--day" in sys.argv:
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for m in range(24 * 60):
            t = day + dt.timedelta(minutes=m)
            for wf, crons in sched.items():
                for c in crons:
                    if matches(c, t):
                        print(f"{t:%H:%M} UTC  {wf}  {c}  {INPUTS.get(wf, lambda _: {})(c)}")
        return 0
    rc = 0
    for wf, c, t in due(now, sched):
        inputs = INPUTS.get(wf, lambda _: {})(c)
        if "--dry-run" in sys.argv:
            print(f"would start {wf} for {c} ({t:%H:%M} UTC) with {inputs}")
            continue
        if ran_since(wf, t):
            print(f"skip {wf} for {c}: already ran since {t:%H:%M} UTC")
            continue
        status, _ = _api("POST", f"actions/workflows/{wf}/dispatches", {"ref": "main", "inputs": inputs})
        print(f"started {wf} for {c} ({t:%H:%M} UTC) with {inputs}: HTTP {status}")
        rc = rc or (0 if status == 204 else 1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
