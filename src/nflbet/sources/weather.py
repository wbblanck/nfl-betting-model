"""Game-time wind from the Open-Meteo historical archive (ERA5 reanalysis). docs/wind_totals_preregistration.md.

Kickoff: nflverse `gameday` + `gametime` are America/New_York local time. Wind for a game is the mean of the hourly
10 m wind speed (knots) at the kickoff hour (UTC, rounded down) and the next three hours. The sandbox cannot reach
Open-Meteo; fetching runs in GitHub Actions (scripts/fetch/game_wind.py).
"""
from __future__ import annotations

import datetime as dt
import time
import urllib.error
import urllib.parse
from zoneinfo import ZoneInfo

from nflbet.sources.http import RESEARCH_UA, get_json

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
ET = ZoneInfo("America/New_York")
WINDOW_HOURS = 4  # kickoff hour and the next three


def kickoff_utc(gameday: str, gametime: str) -> dt.datetime:
    """'2014-10-26', '13:00' (Eastern local) -> aware UTC datetime."""
    d = dt.date.fromisoformat(gameday)
    hh, mm = (int(x) for x in gametime.split(":")[:2])
    return dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).astimezone(dt.timezone.utc)


def window_mean(hourly: dict[str, float], kickoff: dt.datetime) -> float | None:
    """hourly: {'YYYY-MM-DDTHH:00' (UTC): knots}. Mean over the kickoff hour (rounded down) and the next three hours;
    None if any of the four is missing."""
    start = kickoff.astimezone(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    vals = []
    for i in range(WINDOW_HOURS):
        v = hourly.get((start + dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00"))
        if v is None:
            return None
        vals.append(float(v))
    return sum(vals) / len(vals)


def fetch_hourly_wind(lat: float, lon: float, start: dt.date, end: dt.date) -> dict[str, float]:
    """Hourly 10 m wind speed in knots, UTC timestamps, inclusive date range."""
    q = urllib.parse.urlencode({"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "start_date": start.isoformat(),
                                "end_date": end.isoformat(), "hourly": "wind_speed_10m", "wind_speed_unit": "kn",
                                "timezone": "UTC"})
    for attempt in range(6):  # network timeouts and 5xx: retry with backoff; anything else raises
        try:
            js = get_json(f"{ARCHIVE}?{q}", {"User-Agent": RESEARCH_UA}, timeout=120, pace=0.5, retries_429=5,
                          backoff=10)
            break
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 5:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 5:
                raise
        time.sleep(5 * 2 ** attempt)
    h = js["hourly"]
    return {t: v for t, v in zip(h["time"], h["wind_speed_10m"]) if v is not None}
