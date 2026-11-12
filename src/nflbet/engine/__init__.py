"""Player-prop engine (docs/engine/README.md): two independent prediction engines, one pricing layer, one audit trail.

Rules, each enforced by tests/test_engine.py:
- engine/replication and engine/challenger never import each other.
- Neither prediction engine imports a price: not engine.pricing, engine.contracts or engine.novig_capture, and not a
  line or quote reader from nflbet.sources (PRICE_SOURCES below).
- Pricing reads predictions; it never writes them.
- Nothing here places an order. There is no order code in this package, and LIVE_EXECUTION stays False.
"""
LIVE_EXECUTION = False

# nflbet.sources modules that carry sportsbook or exchange prices. A prediction engine may not import them.
PRICE_SOURCES = frozenset({"venues", "parlay", "openmarkets", "gc_props", "espn", "sbro", "asb"})
PRICE_LAYERS = frozenset({"pricing", "contracts", "novig_capture"})
