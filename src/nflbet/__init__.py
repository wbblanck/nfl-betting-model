"""NFL betting-market research: player props (Action Network lines, nflverse outcomes) and spreads.

Layers, each importing only those above it (enforced by tests/test_foundation.py):
  quant      odds and fee arithmetic, no project imports
  execution  run clock and tracker record files (runs pipelines; places no bets)
  sources    one reader per data feed, the HTTP client, team and name keys
  props, ats the two research areas and their live trackers; neither imports the other
  dashboard  the tracker page, built from both
"""
