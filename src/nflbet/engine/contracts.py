"""Canonical contract identity and strict matching of a Novig market to an engine market and a player.

A contract is matched only when every part of its identity is read from Novig's own fields and agrees with every
other part. Anything else is returned as (None, reason) and is never priced. Names are never guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from nflbet.engine.registry import Market
from nflbet.sources.ids import TEAMS, game_key, last_name, norm_name

DESC = re.compile(r"^(.+?) (\d+(?:\.\d+)?) ([A-Z0-9_]+)$")          # 'Keenan Allen 6.5 RECEPTIONS'
SIDE = re.compile(r"^(Over|Under) (\d+(?:\.\d+)?)$")


@dataclass(frozen=True)
class Contract:
    venue: str
    event_id: str
    market_id: str
    game: str                 # nflverse codes, alphabetical: 'BUF|NYJ'
    home: str
    away: str
    starts_ms: int | None
    player_name: str          # as the venue writes it
    player_key: str           # ids.norm_name(player_name)
    market: str               # registry key
    line: Decimal
    period: str               # 'game' (full game, overtime included); nothing else is matched
    voids: str | None         # venue's void rule, kept verbatim ('FMV' at Novig)
    over_id: str
    under_id: str


def match_novig(m: dict, event: dict | None, by_type: dict[str, Market]) -> tuple[Contract | None, str]:
    """Novig catalog market (+ its event) -> (Contract, 'ok') or (None, reason)."""
    mk = by_type.get(m.get("marketType"))
    if mk is None:
        return None, "market type not in registry"
    if not event or event.get("eventId") != m.get("eventId"):
        return None, "event missing"
    parts = (event.get("description") or "").split(" @ ")
    if len(parts) != 2:
        return None, "event description not 'Away @ Home'"
    away, home = (TEAMS.get(x.strip()) for x in parts)
    if not away or not home:
        return None, "unknown team"
    d = DESC.match(m.get("description") or "")
    if not d or d.group(3) != m["marketType"]:
        return None, "description does not read 'Player line TYPE'"     # also rejects '... 1H' style partial-game text
    try:
        line = Decimal(d.group(2))
        strike = Decimal(str(m["strike"])) if m.get("strike") not in (None, "") else None
    except InvalidOperation:
        return None, "line not a number"
    if strike is None or strike != line:
        return None, "strike and description disagree"
    if line % 1 != Decimal("0.5"):
        return None, "whole-number line (push rules not confirmed)"
    sides = {}
    for o in m.get("outcomes") or []:
        s = SIDE.match(o.get("name") or "")
        if not s or Decimal(s.group(2)) != line or s.group(1) in sides:
            return None, "outcomes are not one Over and one Under at the line"
        sides[s.group(1)] = o.get("outcomeId")
    if set(sides) != {"Over", "Under"} or not all(sides.values()) or len(m.get("outcomes") or []) != 2:
        return None, "outcomes are not one Over and one Under at the line"
    name = d.group(1).strip()
    return Contract("novig", m["eventId"], m["marketId"], game_key(away, home), home, away, m.get("startsTs"), name,
                    norm_name(name), mk.key, line, "game", m.get("voids"), sides["Over"], sides["Under"]), "ok"


def resolve_player(c: Contract, roster: list[dict]) -> tuple[str | None, str]:
    """Contract -> (player_id, how). roster rows: {'player_id', 'name', 'team', 'position'} for one week.
    Only the game's two teams are searched. Full normalized name first, else last name + first initial; a tie at
    either step is 'ambiguous' and no player is returned."""
    pool = [r for r in roster if r.get("team") in (c.home, c.away)]
    for how, key, val in (("name", norm_name, c.player_key), ("last+initial", last_name, last_name(c.player_name))):
        hits = {r["player_id"] for r in pool if key(r["name"]) == val}
        if len(hits) == 1:
            return hits.pop(), how
        if len(hits) > 1:
            return None, f"ambiguous ({how})"
    return None, "not on either roster"
