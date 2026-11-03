# Adaptive-Regime-FX-M15

Kind: composite
Primary timeframe: M15 entry / H1 regime selector
Provenance: AI-generated hypothesis (Ace), 2026-11-03,
derived from read-only MT5 assessment of this Deriv-Demo terminal (H1 bars
2026-08-01..2026-11-03). Frozen before execution; no post-result tuning.

## Rules

Selector Adaptive-Regime-Selector v1, evaluated on every M15 bar from the last completed H1 bar:
- H1 ADX(14) > 25 AND efficiency ratio > 0.15  -> trend regime, only TrendPullback-EMA-M15
  entry rules are eligible.
- H1 ADX(14) < 20                              -> range regime, only
  RangeReversion-Bollinger-M15 entry rules are eligible.
- Any other value, or stale H1 context         -> no trade.
- Allocation: one shared equity pool, one position per symbol across both members, no
  simultaneous conflicting member ownership of a symbol.
- Existing positions keep their original member's exits; a regime change never reassigns or
  re-opens them.
- Deterministic priority: a symbol is checked by the single eligible member only, so no
  cross-member tie-break is required.
