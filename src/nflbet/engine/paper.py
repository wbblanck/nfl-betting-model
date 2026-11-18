"""Engine paper fills at Novig (docs/engine/paper_rules.md; CLAUDE.md fifth exception). Paper only: no order is
placed and nothing here can place one. Reads an engine's P(over) and a recorded book's costs; writes a record.
"""
from __future__ import annotations

EDGE_MIN = 0.03          # $ per $1 of payout, frozen in the rules before any comparison
SIZE = 1_000             # contracts: $10 of payout
PAYOUT = SIZE / 100      # dollars paid on a win


def choose(over: dict, under: dict, p_over: float) -> dict | None:
    """over / under: quotes.side_quote rows at SIZE for one contract's book. Returns the fill or None.
    A side counts only if all SIZE contracts fill; the side with the larger edge is taken if edge >= EDGE_MIN."""
    best = None
    for q, p in ((over, p_over), (under, 1.0 - p_over)):
        if q is None or q.get("unfilled") != 0 or q.get("all_in") is None or q.get("size") != SIZE or p != p:
            continue
        edge = p - q["all_in"]
        if best is None or edge > best["edge"]:
            best = {"side": q["side"], "p": p, "all_in": q["all_in"], "edge": edge, "cost": q["all_in"] * PAYOUT}
    return best if best is not None and best["edge"] >= EDGE_MIN else None


def settle(side: str, line: float, y: int | None, cost: float) -> tuple[str, float]:
    """(result, profit in dollars). y None = the player did not play: void, cost returned."""
    if y is None:
        return "void", 0.0
    won = (y > line) if side == "Over" else (y < line)
    return ("win", PAYOUT - cost) if won else ("loss", -cost)
