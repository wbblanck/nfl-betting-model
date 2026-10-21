"""Run clock. Every tracker timestamp is UTC ISO 8601 with a Z suffix."""
import datetime as dt


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
