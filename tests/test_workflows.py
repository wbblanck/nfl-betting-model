"""Workflows that run on pushes to working branches must skip merge commits: merging main into a branch re-touches
their watched paths, and on 2026-11-05 that re-ran the EndzoneAPI probes twice (about 90 of 500 monthly credits)."""
import pathlib

import yaml

GUARD = "github.event_name != 'push' || !startsWith(github.event.head_commit.message, 'Merge ')"


def test_branch_push_workflows_skip_merge_commits():
    found = 0
    for f in sorted(pathlib.Path(".github/workflows").glob("*.yml")):
        d = yaml.safe_load(f.read_text())
        on = d.get(True, d.get("on")) or {}          # YAML 1.1 reads the bare key `on` as True
        push = on.get("push") if isinstance(on, dict) else None
        if not (isinstance(push, dict) and "branches-ignore" in push):
            continue
        found += 1
        for name, job in d["jobs"].items():
            assert job.get("if", "").startswith(GUARD), f"{f.name}: job {name} runs on merge commits"
    assert found >= 30
