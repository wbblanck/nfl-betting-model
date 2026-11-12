"""Append-only, hash-chained record file: predictions, quotes, paper decisions and grades are written once.

Each line is a JSON object {"seq", "prev", "record", "hash"} where hash = sha256(prev + canonical JSON of record) and
prev is the previous line's hash. Changing, removing or reordering any earlier line breaks verify(). A correction is
a new record that names the one it corrects; nothing is edited in place. Floats are refused: probabilities and
prices are written as strings or integers so the same record always hashes the same.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def _canon(record: dict) -> str:
    def check(x):
        if isinstance(x, float):
            raise TypeError("floats are not allowed in ledger records; write a string or an integer")
        if isinstance(x, dict):
            [check(v) for v in x.values()]
        elif isinstance(x, (list, tuple)):
            [check(v) for v in x]
    check(record)
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(prev: str, record: dict) -> str:
    return hashlib.sha256((prev + _canon(record)).encode()).hexdigest()


def verify(path: Path) -> tuple[int, str]:
    """(number of records, hash of the last one). Raises ValueError at the first line that breaks the chain."""
    prev, n = GENESIS, 0
    if path.exists():
        for i, line in enumerate(path.read_text().splitlines()):
            row = json.loads(line)
            if row.get("seq") != i or row.get("prev") != prev or row.get("hash") != _hash(prev, row["record"]):
                raise ValueError(f"{path.name}: chain broken at line {i + 1}")
            prev, n = row["hash"], i + 1
    return n, prev


def append(path: Path, record: dict) -> str:
    """Verify the file, then add one record. Returns the new record's hash."""
    n, prev = verify(path)
    h = _hash(prev, record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({"seq": n, "prev": prev, "record": record, "hash": h}, sort_keys=True) + "\n")
    return h
