# Goals And Progress

These instructions govern real account goals during trading onboarding in [AGENTS.md](../AGENTS.md). Strategy research, backtest review, and account execution authority are covered in [Strategy Catalogue And Backtesting](strategy.md). Simulated backtest profit never counts toward an account goal.

## Goal Setup

After connection verification and risk-input collection, ask for the user's goal before listing/selecting strategies. Interpret the goal as additional net realized trading profit after costs, not turnover, a desired ending balance, deposits, or unrealized gains.

Ask one focused question for a positive finite target in account-currency money or percent. Record `goal_unit` as `money` or `pct` and `goal_value` as a numeric amount/percentage without unit symbols. A percent target may exceed `100`; it is not a drawdown limit. Confirm ambiguous units, decimal conventions, or currency. Money must use the verified account currency; do not assume a dollar sign means that currency or invent an FX conversion. If the user means an ending balance or equity-growth target, clarify the supported net realized-profit interpretation before acceptance.

Save a target draft without pretending trading has started. At final approval, confirm and freeze verified positive `goal_start_equity`, exact `goal_started_at_utc` and broker history/start watermark, `goal_id`, and any carry-in accounting rule. Reconfirm materially changed approval baselines before activation. A new target requires explicit approval; do not silently reset it when reached, missed, or made inconvenient.

Once the target draft is valid, proceed to listing available strategies and user selection under [strategy instructions](strategy.md). Reuse unchanged verified completed results before proposing new tests; a different goal does not authorize reruns, new trading rules, or increased risk. After per-strategy results, wait for final explicit chosen-result/account authorization, then verify protection and execution gates before orders. Test-setup approval or a research result alone never starts the goal or trading.

```text
if goal_unit == money:
    goal_amount = goal_value
if goal_unit == pct:
    goal_amount = goal_start_equity * goal_value / 100

realized_profit_pct = 100 * realized_net / goal_start_equity
progress_pct = 100 * realized_net / goal_amount
remaining_amount = max(0, goal_amount - realized_net)
```

The denominator and converted `goal_amount` remain fixed after approval, including after deposits/withdrawals, equity changes, day rollover, restarts, or first attainment. Do not clamp negative progress to zero or progress above `100` to `100`. Show remaining money and percentage progress in the report; a loss increases the remaining amount.

These goals have no promised completion date. A user deadline never permits greater risk, forced trades, or invented returns. If the approved strategy has no signal or cannot fit current risk headroom, report that constraint and wait for a compliant signal.

## Realized-Profit Accounting

Use verified MT5/broker deal history as authority, not a cached CSV number, account balance change, AI estimate, or open-position mark. Confirm whether broker fields are gross or already net and their fee/sign/booking semantics before summing them.

```text
realized_net = sum(in-scope realized trading profit)
             + sum(in-scope signed realized commission, swap, and fees)
```

Include closed-volume profit and attributable realized trading charges exactly once. Costs booked on an in-scope opening deal reduce net progress when realized even if the position remains open; do not deduct the same entry cost again at partial/final closure. Exclude unclosed price gains/losses from this realized metric and report them separately. If costs are already netted into profit, do not add/subtract them twice. Distinguish capitalized/unrealized swap from actually booked swap using the documented broker semantics.

- Exclude deposits, withdrawals, transfers, nontrading capital credits, and earlier out-of-scope realized outcomes. Classification must match the risk cash-flow ledger; ambiguous events must be resolved, not counted as profit or relabeled to hide loss.
- Preserve the original goal-start boundary alongside the latest reconciled cursor. Use unique broker deal/event IDs, reliable time/ordering semantics, overlapping reads and deduplication where needed; multiple fills or shared timestamps must not disappear or be counted twice.
- Reconcile partial closes, entry/exit costs, financing, later corrections, and deferred cost postings against the applicable goal scope. Do not advance the checkpoint past unaccounted/unknown events or claim exact attainment while required cost/history evidence is missing.
- Distinguish subsequent real losses from corrections to earlier outcomes or late charges attributable to an earlier crossing. If corrected history invalidates a recorded crossing, preserve its prior evidence/reason in an ignored checkpoint backup and the accounting audit, recompute the earliest valid crossing, and replace or clear `goal_first_reached_at_utc` accordingly. Report the earlier attainment as invalidated/unconfirmed, not a still-valid historical success. Retain a valid crossing when later independent trades lose money.
- If existing positions, pending orders, or unresolved/deferred costs overlap goal approval, disclose them and ask for an explicit carry-in attribution rule. Explain full later closed outcomes versus incremental outcomes from verified goal-start marks/cost allocation if applicable. Record the complete user-approved rule and required baseline/IDs in `goal_carry_in_rule` and the checkpoint. If reliable attribution cannot be implemented from available broker data, block activation rather than guess.
- Use `goal_carry_in_rule = none` only when a verified flat/clean boundary has no carry-in attribution issues. Do not automatically flatten an account just to create a goal boundary; that requires separate authorized action.
- Persist `goal_realized_net` only after successful reconciliation. If history is stale or unavailable, retain the last verified checkpoint with its timestamp, mark current progress unavailable, and block new exposure as required by risk instructions. Never turn missing history into zero profit.

## Attainment And Progress

When fully reconciled `realized_net >= goal_amount`, record the earliest valid `goal_first_reached_at_utc` using verified event/broker ordering evidence. Preserve that valid crossing through subsequent trading losses; reconcile and audit any corrections invalidating it under the accounting rules above. On delayed history recovery, recover the earliest verifiable attainment; do not fabricate a historical timestamp. If it cannot be established, report that uncertainty rather than pretending the first crossing occurred at the current read.

Attainment is informational: continue under the unchanged approved risk policy and strategy when all gates and a valid signal allow. Do not automatically stop, flatten, create a new goal, rebase the denominator, loosen stops, or increase size. If profit later falls below the target, preserve the first attainment record and show both "previously reached" and the current shortfall. A risk breach still triggers account-wide flattening regardless of progress.

Every trading response, including setup questions, errors, blocked actions, and post-attainment updates, must return this compact report with actual values or explicitly marked unavailable fields:

```text
As Of: <verified UTC timestamp, broker day, and any stale source timestamps>
Connection / Account / Guard: <status; login+server; demo/live; currency; health>
Goal: <money or pct, fixed start equity, account-currency target, approval status>
Realized Net: <net profit after costs; source verified or unavailable>
Progress / Remaining: <current percent, remaining account-currency money>
Unrealized P&L: <separate open price P&L/costs with broker semantics identified>
Risk: <daily used/limit; trailing used/limit; monetary headroom; latch/status>
Backtests / Selection: <available/selected strategies; run IDs, reused/new evidence, evaluation dates/timeframes, setup/result review states>
Strategy / Authority: <chosen completed specification and source/rules fingerprints; pinned reviewed run; named-account approval or missing requirement>
Outcome: <verified action result, no signal, blocked reason, or unresolved exposure>
Next Permitted Step: <compliant action, requested input, or waiting condition>
Attainment: <not yet reached, reached, previously reached/currently below, or prior crossing invalidated/unconfirmed>
```

Do not expose tokens or hide stale data behind a fresh report timestamp. During incomplete setup, report the known draft target/limits and mark unverified metrics unavailable, not zero. State completion progress, limits, outstanding blockers, and the permitted next step honestly; never guarantee returns, fabricate successful orders/flattening, or imply perpetual monitoring by the AI. Independent guard coverage is not a claim that the AI keeps running or will send reports while inactive.

At the strategy-results stage, supplement this account report with per-selected-strategy results showing all six metrics for every symbol and its shared-capital portfolio, dates/timeframes, reused/new evidence, and limitations. Keep cached research timestamps historical and account telemetry timestamps distinct. Simulated return/total return never fills `Realized Net` or goal progress. Comparing results does not approve all strategies; the final complete summary must explicitly request approval of the chosen result and autonomous authority on the named account before execution.

## Arithmetic Checks

These are fictional validation cases, not a real account, goal, or strategy.

| Case | Expected Report |
| --- | --- |
| Goal-start equity `10000`, target `2%`, realized net `50` | Target `200`, profit `0.5%` of start equity, progress `25%`, remaining `150`. |
| Same target, realized net `250` | Progress `125%`, remaining `0`; record first attainment, continue only within approved risk/strategy. |
| Previously attained, current realized net `190` | Current progress `95%`, remaining `10`, historical attainment preserved. |
| Same target, realized net `-50` | Progress `-25%`, remaining `250`; do not hide the loss. |
| Money target `500`, realized net `50` | Progress `10%`, remaining `450`, both in verified account currency. |
| A deposit increases equity during the goal | No realized-profit credit or target-denominator reset from the deposit. |
| Closed gross profit `60`, signed fees/commission `-10` | Net `50`, not `60`; do not subtract already netted costs again. |
| Repeated reads/partial closes with the same deal IDs | Each outcome/cost counted once; checkpoint and source timestamps remain verifiable. |
| A broker correction removes the original crossing above target | Preserve the invalidated record in the audit; recompute valid attainment or report no confirmed historical crossing, without resetting the goal. |
