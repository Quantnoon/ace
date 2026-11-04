# Goals And Progress

These instructions govern real account goals under [AGENTS.md](../AGENTS.md). Analysis alone never counts toward account progress. Maintenance is not account setup, a monetary goal or trading approval.

## Budget And Target

The only user-supplied trading settings are a positive monetary trailing-loss **budget** and a positive monetary **target** in the verified account currency. Accept them together, for example "risk only 5 USD and make an extra 15 USD". Ask only for missing/ambiguous amounts or currency, not percentages, allocated capital or routine symbol choices. Account facts come from actual MT5 MCP responses.

The target is additional cash-flow-adjusted account equity gain from the approved goal baseline, including floating P&L and estimated incremental closing costs. It is not turnover, deposits, starting capital, a desired ending balance, or a sum of closed-trade profits that ignores open losses. The allowance does not create a virtual subaccount. All manual and other-origin exposure/costs count.

Save inputs as unapproved `draft` state through the [helper contract](risk-management.md). During onboarding, Ace verifies instrument economics, current market conditions, costs and affordability, and plans orders across independent trade ideas rather than one all-in trade. Winner additions remain within their original idea allocation, not extra diversification. That analysis is read-only until the named-account approval below; it never authorizes orders by itself.

Present one final named-account confirmation of the account identity, amounts, baseline values/source timestamps, observed-only trailing definition, approved symbol universe, current market read, [Active Order Management](risk-management.md#active-order-management) and account-wide cancellation/closure at either trigger. Explicitly include Ace-only adaptive cost-aware breakeven/trailing stops, early invalidation exits, cancellation of invalid pending entries and protect-first winner additions within the original idea allocation; routine management does not adopt manual trades. Disclose that only active AI snapshots check monetary limits or adjust stops; missed peaks/breaches, gaps and delayed closes can overshoot them. A provided target or an optimistic analysis is not that approval.

After real approval, activate/reconcile using the reviewed baseline plus a separate fresh post-approval snapshot. Preserve the baseline while the user reviews it; intervening equity/cash-flow changes are checked, not silently rebased. Handle latches and required existing-position/pending-order management before new exposure. An eligible approved order with a successful fresh preparation may be placed through MT5 MCP without per-trade confirmation, subject to actual client/broker permissions. No compliant signal or affordable minimum lot means no trade. There is no target deadline, forced trade volume, automatic risk increase or promised return.

## Equity-Based Progress

```text
E = current broker account equity, including floating valuation and booked costs
E0 = fixed verified equity at goal approval/activation
C_goal = net external capital flows since this goal's anchor
K = estimated incremental closing charges/slippage not already reflected in E

estimated_net_gain = E - C_goal - E0 - K
progress_pct = 100 * estimated_net_gain / target
remaining_amount = max(0, target - estimated_net_gain)
target_trigger = estimated_net_gain >= target
```

Keep `E0`, target and original history boundary fixed for that approved goal. A same-policy new goal gets its own goal/cash-flow anchor without resetting the risk policy's peak or loss latch. Do not clamp negative progress or progress above 100%; do not hide losses behind display rounding.

Obtain account equity/balance and complete relevant broker history from MCP. Classify external deposits/withdrawals/credits using actual broker semantics, paginate/deduplicate events and reconcile coverage with the account observation. Booked commission, spread valuation, swaps and fees already included in equity are not subtracted again. Unknown costs, missing conversion/history or a deposit not yet represented in the flow ledger make current progress unavailable, not zero or a verified crossing.

Existing floating profit at goal activation is already inside `E0`; it is not extra goal profit merely because the position later closes. The fixed interpretation is incremental whole-account mark-to-market gain from that baseline, not a new user carry-in accounting questionnaire. Preserve actual start marks/watermark and deferred-cost evidence; if that accounting cannot be verified, block additions rather than invent attribution.

The Python helper stores a full deduplicated external-flow ledger from an immutable history anchor and separate cash-flow anchors for policy and goal. Follow its exact JSON contract; do not populate extra undocumented fields or interpret a CSV/SQLite flag as approval. `status` retains historical timestamps and is not a current MT5 observation.

## Trigger And Close

On the first **actually observed and verified** `estimated_net_gain >= target`, latch the target stop. Do not infer an earlier floating-equity crossing from closed deals, invent a continuous peak, or backdate enforcement. An unobserved crossing may be missed while the AI is inactive.

Under the final approved whole-account mandate:

1. Stop new entries and other risk increases immediately, including any instrument switch that would add exposure.
2. Cancel all pending entry orders, including manual/other-origin entries, using the actual documented MCP tool. Preserve necessary protective orders until their positions are safely closed.
3. Close all account positions including manual exposure using true position-close/reduce semantics. An opposite entry may hedge or reverse rather than close. Record intended actions before dispatch where the helper is available; an unavailable helper must not delay previously authorized identity-verified safety reductions.
4. Read back cancellations, partial/late fills, remaining orders, volume, stops and uncertain requests. Close remaining verified exposure under the same mandate, without blindly duplicating an uncertain close. Reconcile orphan orders only after their protection is no longer needed.
5. Verify flat positions, no pending orders, resolved intents and final costs. Report the actual final net gain and any shortfall separately from the trigger. A submitted request or accepted partial fill is not a flat account.

The stop stays latched after slippage, rejected/partial closes, equity recovery, profit falling below target, later cost corrections, new days and reconnects. Do not automatically trade to make up a shortfall. If a loss stop is also latched, loss handling takes precedence; neither latch hides the other.

Before a trigger, positions retain their original approved exits/ownership except for an explicitly approved transition; the [active management rules](risk-management.md#active-order-management) do not retroactively expand authority. No-entry regimes or target/loss latches do not prevent identity-verified, previously authorized protective management and reductions. After a whole-account trigger, that cancellation/closure mandate overrides normal position holding periods, trailing decisions and add-on plans.

## Final Result And Resume

While exposure, costs or requests remain unresolved, report target-triggered/closure-pending, not a guaranteed achieved net profit. Once verified flat with final costs, actual incremental net gain is `final_equity - C_goal - E0` and shortfall is `max(0, target - final_net_gain)`. With a normal flat cash account, final balance equals equity; verify actual broker semantics rather than summing deal profits a second time.

For example, a target of `15` may trigger on estimated liquidation gain `15`, then close at actual net `14.7`. Report trigger observed, closure verified, final net `14.7`, shortfall `0.3`, and **stopped**. Do not falsely claim the final goal was met or clear the stop because the estimate changed. Later charges/corrections update the reported result, not the existing latch.

New-goal activation requires explicit approval of that new goal and its reviewed baseline, settled previous exposure/intents/costs, fresh post-approval reconciliation and unchanged risk policy under the helper contract. It preserves the observed risk peak and original policy/flow anchor. Explicit mandate `reauthorize` changes the approved analysis/symbol authority without resetting either monetary baseline or any latch. A loss latch requires an explicitly approved replacement risk policy and baseline reset; a new target, mandate reauthorization or local flag cannot release it. Never silently replace symbols, analysis or policy limits to pursue the target.

No process is installed to run checks or close positions while the AI is inactive. Broker stop-losses remain essential but cannot guarantee the monetary cap or target. A stop failure, stale data, missing tool/permission or unresolved exposure must be reported honestly with the next safe permitted step.

## Compact Trading Report

Every trading response, including onboarding questions, errors, blocked decisions and liquidation updates, includes this compact report with actual values or `unavailable`:

```text
Account / As Of: <login + server; demo/live; currency; connection; verified source times>
Budget / Risk: <budget; observed adjusted peak; drawdown; remaining money; stop floor; loss latch>
Target / Progress: <target; goal-start equity/time; estimated net gain; incremental close costs; progress/remaining>
Authority / Analysis: <draft/approved; approved symbol universe; current market read and its invalidation conditions, or no-entry reason>
Stop / Exposure: <target/loss latch; open/pending exposure; unresolved intent; closure pending or verified>
Loop: <session id; active/interrupted/closing/closed; cycles; entry timeframe; last confirmed bar; max observed gap; end reason or next candle boundary>
Outcome / Next: <action/ticket and reason; verified stop change, cancellation/closure/fill or blocker; final net/shortfall when verified; next permitted action>
```

During a [loop session](loop.md) the `Loop` line is mandatory. Report the largest observation gap honestly: while it was open, the monetary limits were unwatched and only broker stops protected the account.

For management, keep `Outcome / Next` concise but distinguish proposed, broker-verified and unknown outcomes. Include old/new SL for a verified stop change, the invalidation/expiry reason and actual remaining exposure for a cancellation or close, or why a valid order was left unchanged. For a winner addition, identify the original idea and show its allocation/use alongside account-wide headroom; a breakeven stop is not zero give-back risk. Do not claim canceled, protected or closed on submission alone.

Do not substitute the report-generation time for stale source timestamps, invent zero balances or assume a missing database is approved. Label the last actual snapshot/check; do not imply continuing monitoring, execution or reporting while inactive.

At the final-approval stage, supplement the compact report with the approved broker symbol universe and the specific market reads that justify the planned orders: timeframes and source timestamps, direction or range, volatility, spread relative to planned stops, session, invalidation levels, instrument economics, costs and margin, planned order count, and the total stressed risk against the remaining budget. Include the original management conditions for those ideas: breakeven/trailing method, invalidation/expiry exits, whether winner additions are eligible and their fixed original idea allocation. One full question may authorize the named-account mandate only when it explicitly requests both that account and those limits; later eligible actions within it need no separate per-trade confirmation.

## Synthetic Workflow Checks

| Case | Expected Outcome |
| --- | --- |
| Baseline `100`, target `15`, equity `110`, remaining close costs `0.5` | Estimated gain `9.5`, remaining `5.5`; no realized-only shortcut. |
| Equity `115`, close costs `0.5` | Gain `14.5`; not reached. At equity `115.5`, trigger and close under the approved mandate. |
| External deposit `200` changes equity from `100` to `300` | No goal profit, denominator reset or adjusted risk peak from that deposit. |
| Manual position or late pending fill exists at the target trigger | Include it in cancellation/closure; verify the actual final account state. |
| Estimated target triggered but final net is `14.7` | Retain the latch and report final shortfall `0.3`, not automatic re-entry. |
| Disconnected during an open position | No claim of continuous helper protection; report last actual observation and broker-stop/unknown-exposure status. |
| Same-policy new goal after settlement | New goal anchor, unchanged risk-policy peak/history; loss latch cannot be released by a target change. |
