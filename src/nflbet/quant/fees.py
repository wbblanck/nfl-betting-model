"""Exchange taker fees per $1 of payout at price p. Venue coefficients and when they apply live with each venue's
reader (nflbet.sources.venues); this is only the shared formula."""


def taker_fee(coef: float, p: float) -> float:
    """coef x p x (1 - p): the form Polymarket US, Kalshi and Novig all use."""
    return coef * p * (1 - p)
