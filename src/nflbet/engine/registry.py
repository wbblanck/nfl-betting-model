"""Market registry: the one place that says what each engine market is and how it is graded (config/markets.yaml)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from nflbet.config import ROOT

PATH = ROOT / "config" / "markets.yaml"
FAMILIES = {"yardage", "count", "rare_event", "extreme_value", "binary", "joint"}
POSITIONS = {"QB", "RB", "WR", "TE"}
ALWAYS_SHADOW = {"rare_event", "extreme_value", "binary"}      # modelled and scored, never priced for a record


@dataclass(frozen=True)
class Market:
    key: str
    positions: tuple[str, ...]
    family: str
    distribution: str
    stat: tuple[str, ...] | None
    components: tuple[str, ...]
    bounded_by: str | None
    novig_type: str | None
    shadow: bool


def parse(doc: dict) -> dict[str, Market]:
    """Validate a registry document and return its markets. Raises ValueError naming the first problem."""
    out: dict[str, Market] = {}
    for key, m in (doc.get("markets") or {}).items():
        unknown = set(m) - {"positions", "family", "distribution", "stat", "components", "bounded_by", "novig_type", "shadow"}
        if unknown:
            raise ValueError(f"{key}: unknown fields {sorted(unknown)}")
        if m.get("family") not in FAMILIES:
            raise ValueError(f"{key}: family {m.get('family')!r}")
        if not m.get("positions") or set(m["positions"]) - POSITIONS:
            raise ValueError(f"{key}: positions {m.get('positions')!r}")
        if not m.get("distribution") or not isinstance(m.get("shadow"), bool):
            raise ValueError(f"{key}: distribution and shadow are required")
        if m["family"] in ALWAYS_SHADOW and not m["shadow"]:
            raise ValueError(f"{key}: {m['family']} markets are shadow-only")
        out[key] = Market(key, tuple(m["positions"]), m["family"], m["distribution"],
                          tuple(m["stat"]) if m.get("stat") else None, tuple(m.get("components") or ()),
                          m.get("bounded_by"), m.get("novig_type"), m["shadow"])
    for k, m in out.items():
        for ref in (*m.components, *([m.bounded_by] if m.bounded_by else [])):
            if ref not in out:
                raise ValueError(f"{k}: refers to unknown market {ref!r}")
        if m.shadow is False and any(out[c].shadow for c in m.components):
            raise ValueError(f"{k}: built from a shadow market, so it must be shadow")
    types = [m.novig_type for m in out.values() if m.novig_type]
    if len(types) != len(set(types)):
        raise ValueError("a Novig market type is mapped to two markets")
    return out


@lru_cache(maxsize=1)
def load(path: Path = PATH) -> dict[str, Market]:
    return parse(yaml.safe_load(path.read_text()))


def by_novig_type() -> dict[str, Market]:
    return {m.novig_type: m for m in load().values() if m.novig_type}
