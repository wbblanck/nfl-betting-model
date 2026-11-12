"""Executable price and expected value against a Novig order book. Reads predictions; never changes them.

Units: a Novig price is a decimal string in dollars per $1 of payout ('0.685'); here it is an integer number of
mills (685). A resting order's qty is in contracts and one contract pays 1 cent (nflbet.sources.venues). Every Novig
order buys an outcome, so buying Over takes the resting orders on Under: an Under order at price q sells Over at
1000 - q mills. Money stays in integers or Fractions until the final EV, which is a float because the model
probability is.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

MILLS = 1000


def mills(price) -> int:
    """'0.685' -> 685. Refuses a price that is not a whole number of mills strictly between 0 and 1."""
    d = Decimal(str(price)) * MILLS
    if d != d.to_integral_value() or not 0 < d < MILLS:
        raise ValueError(f"price {price!r} is not a whole number of mills in (0, 1)")
    return int(d)


@dataclass(frozen=True)
class Fill:
    filled: int               # contracts bought
    unfilled: int             # contracts wanted but not available within the limit
    cost: Fraction | None     # average price paid per $1 of payout, before fees; None when nothing filled
    worst: int | None         # worst price level taken, mills
    levels: tuple[tuple[int, int], ...]     # (price in mills, contracts) per level taken


def take(other_side_orders: list[dict], contracts: int, limit_mills: int | None = None) -> Fill:
    """Buy `contracts` of an outcome against the other outcome's resting orders ({'price', 'qty'}, any order).
    Levels are taken cheapest first and never above limit_mills. A partial fill is reported, not hidden."""
    if contracts <= 0:
        raise ValueError("contracts must be positive")
    asks: dict[int, int] = {}
    for o in other_side_orders:
        qty = int(o["qty"])
        if qty <= 0:
            raise ValueError("resting order with no quantity")
        a = MILLS - mills(o["price"])
        asks[a] = asks.get(a, 0) + qty
    left, taken = contracts, []
    for a in sorted(asks):
        if left == 0 or (limit_mills is not None and a > limit_mills):
            break
        q = min(left, asks[a])
        taken.append((a, q))
        left -= q
    filled = contracts - left
    cost = Fraction(sum(a * q for a, q in taken), filled * MILLS) if filled else None
    return Fill(filled, left, cost, taken[-1][0] if taken else None, tuple(taken))


def taker_fee(fee: dict | None, price: Fraction, live: bool) -> Fraction:
    """Novig taker fee per $1 of payout at `price`, from the market's own fee record as saved with the quote:
    coefficient x P x (1 - P), charged always or only while the game is live. Unknown rules raise."""
    f = fee or {}
    charged = f.get("charged")
    if charged not in ("ALWAYS", "WHEN_LIVE"):
        raise ValueError(f"unknown fee rule {charged!r}")
    if charged == "WHEN_LIVE" and not live:
        return Fraction(0)
    return Fraction(Decimal(str(f["coefficient"]))) * price * (1 - price)


def ev(p_model: float, cost: Fraction, fee: Fraction = Fraction(0)) -> tuple[float, float]:
    """(expected profit per $1 of payout, the same as a return on the money put up).
    A contract pays 1 with probability p and costs cost + fee either way: EV = p - cost - fee."""
    if not 0 <= p_model <= 1:
        raise ValueError("p_model must be a probability")
    outlay = cost + fee
    if not 0 < outlay < 1:
        raise ValueError("cost + fee must be strictly between 0 and 1")
    e = p_model - float(outlay)
    return e, e / float(outlay)


def mc_se(p: float, n: int) -> float:
    """Standard error of a simulated probability from n independent runs. Sampling error only: it says nothing
    about whether the model behind the runs is right."""
    return math.sqrt(p * (1 - p) / n)
