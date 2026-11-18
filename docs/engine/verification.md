# Engine verification summary (phase 7)

Written by `scripts/engine_verification.py` from the committed Test S results only (each run once on 2024-2025,
Will's go-ahead). Nothing here is a new test or a new look at the test seasons' outcomes.

## Test S verdicts

| Market | Rows | A verdict | B verdict | A CRPS | B CRPS | B minus A |
|---|---|---|---|---|---|---|
| pass_att | 1,115 | PASS | PASS | 5.367 | 5.200 | -0.166 |
| pass_yds | 1,115 | PASS | PASS | 45.100 | 41.841 | -3.259 |
| rush_att | 2,059 | PASS | PASS | 2.720 | 2.648 | -0.072 |
| rush_yds | 2,059 | PASS | PASS | 16.661 | 16.436 | -0.225 |
| rec | 4,637 | PASS | PASS | 1.190 | 1.161 | -0.029 |
| rec_yds | 4,637 | PASS | PASS | 16.200 | 15.888 | -0.312 |

B minus A is reported, not tested (no interval was pre-registered for it).

## Calibration: interval coverage, actual minus what an exactly right forecast would show

Whole-number stats cover more than the nominal level even when right, so each band is compared with the share
the engine's own runs would cover (Test S's 'coverage if right'). Positive = too wide; negative = too narrow.

| Market | A 50% | A 80% | A 90% | B 50% | B 80% | B 90% | A mean bias | B mean bias |
|---|---|---|---|---|---|---|---|---|
| pass_att | -0.5 | -3.4 | -3.1 | +3.0 | +1.7 | +0.4 | -0.03 | +0.62 |
| pass_yds | +2.3 | -0.1 | -2.2 | +2.3 | +3.0 | +2.1 | +3.62 | +5.62 |
| rush_att | +1.7 | -0.3 | +0.5 | +1.4 | +2.8 | +1.9 | -0.14 | +0.21 |
| rush_yds | -3.1 | -3.1 | -0.7 | +2.5 | +0.8 | +0.7 | -0.78 | +0.70 |
| rec | +2.7 | +2.1 | +1.2 | +1.2 | +0.1 | +0.0 | +0.10 | +0.06 |
| rec_yds | +2.2 | +2.7 | +0.8 | +3.4 | +1.0 | +0.0 | +1.48 | +0.72 |

Coverage gaps are in percentage points; mean bias is runs' mean minus outcomes' mean in the stat's units.
Neither engine has been compared with a market price: that is Test M (2026 weeks 11-18, frozen 2026-11-17).
