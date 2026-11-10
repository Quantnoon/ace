# FX Entry Strategies

This file is the single source of truth for FX entry-regime screening, the four standalone entry playbooks, per-signal stop/target/trailing rules, and handling multiple signals. Read it with [MT5 Connection](mt5-connection.md), [Monetary Risk And SQLite/Helper Contract](risk-management.md), [Goals And Progress](goals.md), and [Loop Sessions](loop.md) before every trading session. These are AI-agent instructions, not a separate executable strategy engine or backtesting system.

These playbooks apply to **new FX entries**. Other eligible asset classes retain their normal analysis workflow. Never skip required monitoring or management of existing exposure because an FX pair is consolidating or fails an entry screen.

## FX Regime Gate

Before detailed setup analysis, make only a lightweight, per-pair regime classification using fresh quotes and enough confirmed closed bars on the approved entry timeframe and a higher timeframe.

- **Consolidating:** Price repeatedly rotates inside overlapping, bounded structure without sustained directional progress. Volatility compression can support this classification, but is not enough by itself.
- **Unknown:** Data is stale, missing, conflicting or inconclusive, or there is not enough confirmed evidence to classify the regime.
- **Pass:** There is clear directional structure, or a confirmed close beyond the established range with follow-through.

For a consolidating or unknown pair, stop after the regime screen: do not perform detailed direction/setup/entry analysis, do not run the four playbooks, and do not prepare an entry. Record a concise factual skip reason through existing reporting text. Do not treat the screen as proof of a signal. If no pair passes, continue observation and other permitted work without forcing a trade.

## Four Independent Playbooks

For every pair that passes the regime gate, evaluate each playbook independently on fresh MCP data and confirmed closed bars. Each playbook produces its own qualifying signal or no-signal. Do not require agreement or confluence from another playbook, combine them into a collective vote/score, or force a signal when that playbook's conditions are absent.

1. **Breakout and retest:** Identify an established range/structure boundary. Require a confirmed close beyond it, followed by a retest from the breakout side and a confirmed hold or rejection in the breakout direction. A touch, wick, or unconfirmed break alone is not a signal.
2. **Break of structure and liquidity sweep:** Identify a sweep beyond a confirmed prior swing high/low that takes visible swing liquidity, then require a confirmed close through the relevant opposing short-term structure in the proposed reversal direction. Both the sweep and structure break are required; a wick alone is neither a structure break nor a signal.
3. **Support/resistance with confirmation and liquidity sweep:** Mark support/resistance from confirmed prior structure. Require price to sweep beyond the level/zone and then close back through or reclaim it with a confirmed rejection in the proposed direction. A level touch without both sweep and confirmation is not a signal.
4. **SMC (Smart Money Concepts):** Name the concrete SMC setup rather than using the label alone. Require a confirmed structure shift/break with displacement, a clearly identified order block or fair-value-gap point of interest, and a confirmed response on retrace into that zone. Record the structure, zone and confirmation that make this playbook's signal; do not depend on another playbook to validate it.

### Separate Signals And Multiple Entries

Each qualifying playbook signal is its own trade idea. Keep its strategy name, rationale, invalidation, `signal_id`, `analysis_ref`, root entry intent and fixed original allocation separate. Use the existing exact [`action.context` contract](risk-management.md#decision-context); do not add helper fields, merge separate strategies, reuse IDs, or disguise an unchanged signal as a new one to bypass deduplication.

If several or all four playbooks signal, each may be prepared and dispatched independently. All four are permitted when each passes its own checks and the combined **account-wide stressed exposure, with applicable costs counted once, plus the safety margin, is strictly below remaining headroom**. Count all open positions, pending fills, manual exposure, same-symbol and correlated exposure; do not assume signals hedge one another or treat them as risk diversification. Dispatch signals sequentially, with at most one unresolved mutation at a time. After each broker readback and `resolve`, refresh exposure and headroom before preparing the next. Size down only when the valid broker volume step and minimum still permit it; otherwise omit the unaffordable signal. Never exceed headroom or force a trade.

## Initial Stop, Target And Trailing Stop

Apply these rules separately to every qualifying signal. Verify instrument economics, conversion, costs, margin, quote side, tick size, broker stop/freeze distances, and execution permissions. Unknown required facts block the affected entry.

- **Initial stop-loss (SL):** Place a broker-side SL beyond the price structure that invalidates that specific setup, with a justified volatility/spread buffer. Examples include beyond the failed retest boundary/swing for breakout-retest; beyond the swept extreme or invalidating structure for BOS/liquidity sweep; beyond the sweep extreme/zone for support-resistance; or beyond the point-of-interest/invalidation swing for SMC. Do not use an arbitrary fixed pip distance, tighten a valid stop just to improve the reward/risk ratio, or widen it after entry. If the structurally valid stop makes the broker's minimum size unaffordable, skip that signal.
- **R and take-profit (TP):** For this planned reward/risk check, **1R** is the proposed stressed account-currency loss from entry to the initial SL, with applicable modeled costs counted once under the [account-wide risk check](risk-management.md#before-each-risk-increase). Estimate target reward using verified contract economics/conversion and expected exit costs. Choose an objectively supported opposing structure/liquidity target whose planned **net** reward is at least 2R and no more than 5R. If a nearer valid opposing level prevents a 2R target, skip the signal. If the structural objective is beyond 5R, cap the TP at 5R only if the path to that price remains technically valid; never extend the planned TP beyond 5R. Set and verify the initial TP in the entry request. Do not double-count costs in either R or the account reservation.
- **Trailing SL:** A broker-side initial SL is required from entry. As favorable movement develops, trail behind newly confirmed higher lows/support for a long or lower highs/resistance for a short, using confirmed closed bars and a justified volatility/spread buffer. Trail when fresh structure gives a valid improvement; no fixed R activation threshold is required. A valid move only tightens protection. Never loosen, remove, or trail through noise; if no valid tighter level exists, retain the accepted SL. Preserve the original TP during SL updates and never extend it beyond 5R.

The 2R–5R requirement constrains the **planned** target, not the realized result: a trailing SL may close a trade before 2R, and gaps, slippage or delayed execution can change the result. Do not promise a return or widen protection to try to reach the TP. Record the strategy, invalidation, target basis and trailing method in the existing strategy/rationale text; keep exact initial SL/TP in the MCP action parameters and follow the existing context contract.

## Reporting And Existing Exposure

Record each playbook's signal/no-signal and material regime-screen pass/skip reasons through existing source-bound journal text, alongside actual source times and relevant market evidence. A journal is not a substitute for a fresh market read. The FX entry gate never suspends required management of existing positions or orders; continue the original authorized plan and account-wide emergency protections under [Risk Management](risk-management.md).
