"""Shared keys for joining feeds: team abbreviations, Action Network ids that are not books, normalized player
names, and the game key. Every feed is matched to nflverse through these."""
import re
import unicodedata

NON_BOOKS = {"15", "30"}                    # Action Network "Consensus" and "Open"
# Action Network abbreviations that differ from nflverse
TEAM_FIX = {"JAC": "JAX", "LAR": "LA", "WSH": "WAS"}
TEAMS = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "Seattle Seahawks": "SEA",
    "San Francisco 49ers": "SF", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


def norm_name(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[.'`\-]", " ", s)
    parts = [p for p in s.split() if p not in ("jr", "sr", "ii", "iii", "iv", "v")]
    out: list[str] = []
    for p in parts:                          # "d j moore" -> "dj moore", so D.J. and DJ agree
        if len(p) == 1 and out and len(out[-1]) >= 1 and out[-1].isalpha() and len(out[-1]) <= 2 \
                and all(len(x) == 1 for x in out[-1]):
            out[-1] += p
        else:
            out.append(p)
    return " ".join(out)


def last_name(s: str) -> str:
    """Last name plus first initial ("garrett wilson" -> "wilson g"), so a fallback never pairs M. Wilson
    with Garrett Wilson."""
    p = norm_name(s).split()
    return f"{p[-1]} {p[0][0]}" if len(p) >= 2 else (p[0] if p else "")


def game_key(a: str, b: str) -> str:
    """Teams in sorted order: neutral-site games may list home and away differently by source."""
    return "|".join(sorted((a, b)))
