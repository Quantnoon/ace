# RangeReversion-Bollinger-M15

Kind: member
Primary timeframe: M15 entry / H1 ADX filter
Provenance: AI-generated hypothesis (Ace), 2026-11-03,
derived from read-only MT5 assessment of this Deriv-Demo terminal (H1 bars
2026-08-01..2026-11-03). Frozen before execution; no post-result tuning.

## Rules

- Trade only when H1 ADX(14) < 20 (range regime) and the H1 context is not stale.
- Long when the M15 close is below the lower Bollinger(20,2) band; short when it is above the
  upper band. Entry at the next M15 bar open.
- Stop = 1.5 x ATR(14) from entry.
- Exit when price touches the middle band, or on the stop, or after 96 M15 bars at close.
- One position per symbol at a time.
