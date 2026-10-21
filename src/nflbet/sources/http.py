"""One JSON-over-HTTPS client for every live feed. Read-only GETs; callers pass their own headers, pacing and retry
policy so each feed keeps the limits it was tuned to."""
import json
import time
import urllib.error
import urllib.request

BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
RESEARCH_UA = "nfl-betting-model/1.0 (read-only research)"


def get_json(url: str, headers: dict, timeout: float = 60, pace: float = 0.0, retries_429: int = 0,
             backoff: float = 1.0):
    """GET url and parse JSON. pace: seconds slept before every attempt. On HTTP 429, retry up to retries_429 times,
    sleeping backoff x 2^attempt first; any other error is raised."""
    for i in range(retries_429 + 1):
        try:
            if pace:
                time.sleep(pace)
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries_429:
                time.sleep(backoff * 2 ** i)
                continue
            raise
