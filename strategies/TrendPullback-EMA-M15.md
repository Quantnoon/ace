# TrendPullback-EMA-M15

Kind: member
Primary timeframe: M15 entry / H1 context
Provenance: AI-generated hypothesis (Ace), 2026-11-03,
derived from read-only MT5 assessment of this Deriv-Demo terminal (H1 bars
2026-08-01..2026-11-03). Frozen before execution; no post-result tuning.

## Rules

- Long only when H1 EMA50 > H1 EMA200 (uptrend context) and the M15 bar's low touches or
  undercuts M15 EMA20, the close is above M15 EMA50, the bar is bullish and closes above
  M15 EMA20.
- Short is the mirror: H1 EMA50 < H1 EMA200, high touches M15 EMA20, close below M15 EMA50,
  bearish bar closing below M15 EMA20.
- Entry at the next M15 bar open.
- Stop = lowest low of the last 3 M15 bars minus 0.5*ATR(14) for longs (mirror for shorts).
- Target = 2.0 x entry-to-stop distance. Maximum hold 96 M15 bars, then exit at close.
- One position per symbol at a time.
