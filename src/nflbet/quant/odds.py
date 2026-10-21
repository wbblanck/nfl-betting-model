"""Odds arithmetic shared by every record and backtest. American odds are floats (-110, +150); probabilities are the
cost of a share paying 1. Pure functions: no data, no I/O."""
import numpy as np


def implied(a: float) -> float:
    """American odds -> implied probability including the vig, i.e. the break-even win rate for that price."""
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def no_vig_over(over: float, under: float) -> float:
    """De-vigged P(over) from a two-sided American quote (multiplicative: each side's implied over their sum)."""
    io, iu = implied(over), implied(under)
    return io / (io + iu)


def american_from_prob(p: float) -> float:
    """Price as a probability -> American odds (not rounded)."""
    return -100 * p / (1 - p) if p >= 0.5 else 100 * (1 - p) / p


def american_to_decimal(a: float) -> float:
    return 1 + (a / 100 if a > 0 else 100 / -a)


def decimal_to_american(d: float) -> int | None:
    """Decimal odds -> American, rounded to whole points; None for prices at or below 1."""
    if d <= 1:
        return None
    return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))


def profit(odds: np.ndarray, won: np.ndarray) -> np.ndarray:
    """Profit per 1 unit staked at American odds; won is 1 (win), 0 (loss) or nan (push -> 0)."""
    dec = np.where(odds > 0, 1 + odds / 100, 1 + 100 / -odds)
    return np.where(np.isnan(won), 0.0, np.where(won == 1, dec - 1, -1.0))
