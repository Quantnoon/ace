# Risk Management Instructions

## Inputs And Authority

During onboarding, after authenticated read-only MT5 account verification, ask the first outstanding risk question in the same response that reports the connection. Ask one focused question at a time in the following order. All four inputs are percentages, not fractions, money, or leverage; there are no numeric defaults.

1. `daily_drawdown_pct`: "What daily drawdown limit, as a percentage of broker day-start equity, should Ace use for this account?"
2. `max_drawdown_pct`: "What maximum trailing drawdown limit, as a percentage of the continuous cash-flow-adjusted equity high-water mark since policy approval, should Ace use?"
3. `risk_per_trade_pct`: "What maximum risk per trade, as a percentage of current account equity, should Ace use?"
4. `max_aggregate_risk_pct`: "What maximum aggregate risk across all open positions and pending orders, as a percentage of current account equity, should Ace use?"

Read and validate the root CSV before reusing or updating saved inputs. Reuse valid, verified same-account inputs, including user-supplied drafts that remain unapproved, and accept unambiguous valid inputs supplied together in the current request. Skip inputs already supplied and ask only for the first missing input or a focused clarification/correction. Corrupt or differently bound saved state requires the persistence/recovery rules below, not silent replacement with new answers. Verify approval provenance separately; reusing numeric inputs does not grant trading authority. Once all four are valid, continue to the next incomplete onboarding step in `AGENTS.md`, with the target before strategy, rather than asking for them again.

Normalize an unambiguous input such as `0.5%` to the numeric CSV value `0.5`; confirm ambiguous units instead of guessing. Each value must be finite and satisfy `0 < value < 100`. Per-trade risk must not exceed aggregate risk. Ask for a correction to invalid or incompatible inputs; never choose a replacement value or automatically adjust either limit. Account equity, policy/day baselines, and the high-water mark must be positive for risk sizing. Do not round comparisons to the display precision.

Daily drawdown is cash-flow-adjusted loss from broker day-start equity, not an intraday trailing peak. Maximum drawdown trails the continuous, cash-flow-adjusted equity high-water mark since policy approval. Both include floating P&L and trading costs. Confirm midnight resets in the verified broker-server timezone, including DST rules.

Save each accepted input as an unapproved draft using validated complete writes and readback under the CSV contract below. Keep draft approval fields empty; do not populate approval timestamps from this document or sample values. If persistence is unavailable, report the blocker without claiming inputs were saved, and keep entries blocked. When resuming an existing policy, preserve its approval evidence, anchors, peaks, and latches; changed limits must follow the replacement-policy rules below, not overwrite the active policy or reset history. Final approval must identify the exact account/server and demo/live type, rules, baseline evidence, strategy, target, and autonomous authority including cancellation/closure of all account exposure, even manual trades.

## Root CSV Contract

The sole active checkpoint is `risk_management.csv` at the repository root. It is local-only and ignored by Git, as are `/risk_management.csv.*` backups/temporary files. Do not commit filled account, strategy, target, or financial state. Never store access tokens in any column.

Use schema version `1`, the exact ordered header below, and zero or one logical data row. Header-only means unconfigured and blocked, not default risk or approval. On a fresh checkout, create this header if absent. If a missing file might represent lost existing policy/history, recover from verified guard/broker evidence before allowing trading; do not bootstrap a new peak to bypass lost state.

```csv
schema_version,account_login,broker_server,account_type,account_currency,policy_id,policy_approved_at_utc,broker_timezone,daily_drawdown_pct,max_drawdown_pct,risk_per_trade_pct,max_aggregate_risk_pct,policy_start_equity,net_cashflow_since_policy_start,broker_day,day_start_equity,net_cashflow_since_broker_day_start,adjusted_equity_high_watermark,daily_breach_day,max_breach_at_utc,risk_state,guard_reference,guard_verified_at_utc,goal_id,goal_unit,goal_value,goal_start_equity,goal_started_at_utc,goal_carry_in_rule,goal_history_cursor,goal_realized_net,goal_first_reached_at_utc,strategy_spec,strategy_approved_at_utc,account_authorized_at_utc,last_verified_at_utc
```

Use RFC 4180 CSV quoting, a UTF-8 file, decimal points without thousands separators, and numeric percentages without `%`. Double embedded quotes; quote cells containing commas, quotes, or newlines. `strategy_spec` may be multiline but still belongs to one logical row. Never split CSV by comma/newline naively or evaluate cell content as code/formulas.

| Column | Meaning |
| --- | --- |
| `schema_version` | `1` for a populated supported row; other versions block execution. |
| `account_login` | Verified account identifier stored as text, without changing leading zeros. |
| `broker_server` | Verified broker server; together with login uniquely binds the account. |
| `account_type` | Verified `demo` or `live`, explicitly included in user approval. |
| `account_currency` | Verified account currency for equity, profits, costs, and monetary caps. |
| `policy_id` | Unique nonsecret identifier of the exact approved risk policy, or blank in a draft. |
| `policy_approved_at_utc` | Immutable UTC anchor of that policy's approval and cash-flow/peak tracking. |
| `broker_timezone` | Verified timezone with its DST rules, or verified offset plus documented offset-change schedule; never an assumed host timezone. |
| `daily_drawdown_pct` | Approved positive daily loss percentage. |
| `max_drawdown_pct` | Approved positive trailing maximum-drawdown percentage. |
| `risk_per_trade_pct` | Approved positive proposed-trade loss cap as a percentage of current equity. |
| `max_aggregate_risk_pct` | Approved positive total open-plus-pending stressed-stop-risk cap as a percentage of current equity. |
| `policy_start_equity` | Verified equity at the immutable policy approval anchor. |
| `net_cashflow_since_policy_start` | Signed verified external capital flows since that anchor. |
| `broker_day` | Verified broker-local date `YYYY-MM-DD` for the daily baseline. |
| `day_start_equity` | Actual verified account equity at that broker day's midnight. |
| `net_cashflow_since_broker_day_start` | Signed verified external flows since that midnight, including flows before a mid-day onboarding. |
| `adjusted_equity_high_watermark` | Guard-maintained continuous peak of equity minus policy-window external flows. |
| `daily_breach_day` | Broker-local date of a latched daily breach; empty only when no applicable latch exists. |
| `max_breach_at_utc` | UTC timestamp of a latched maximum breach; never cleared merely by recovery/restart/midnight. |
| `risk_state` | One of the states below; not sufficient evidence of authority on its own. |
| `guard_reference` | Nonsecret guard/account/policy, execution-journal and verifiable audit/ownership references; not an access secret or invented guard ID. |
| `guard_verified_at_utc` | Time of the last actually verified healthy/armed guard evidence; do not make stale telemetry fresh by writing the current time. |
| `goal_id` | Identifier of the user's current approved goal; empty in an unapproved draft. |
| `goal_unit` | `money` or `pct`, explicitly confirmed with the user. |
| `goal_value` | Positive finite amount in account currency, or percentage points. |
| `goal_start_equity` | Positive equity fixed at goal approval; never rebased after deposits, losses, or attainment. |
| `goal_started_at_utc` | Immutable approved goal-start boundary timestamp. |
| `goal_carry_in_rule` | Exact approved carry-in profit/cost attribution and required baseline evidence; `none` only when verified no carry-in exposure/attribution issues exist. |
| `goal_history_cursor` | Verifiable accounting checkpoint; preserve the original start watermark and carry-in baselines when advancing the last reconciled cursor. Use actual broker cursor semantics or quoted structured checkpoint data. |
| `goal_realized_net` | Reconciled net realized goal profit cache, possibly negative; broker records remain authoritative. |
| `goal_first_reached_at_utc` | First valid verified attainment timestamp; retained after subsequent actual losses. Corrections invalidating that crossing require audited recomputation, not a false retained attainment. |
| `strategy_spec` | Exact user-supplied, approved executable rules and parameters, not a name or AI-invented summary. |
| `strategy_approved_at_utc` | Actual user approval timestamp of the stored specification. |
| `account_authorized_at_utc` | Actual authorization for autonomous trading and account-wide emergency reductions under the specified policy/goal/strategy. |
| `last_verified_at_utc` | Time of the last fully reconciled account/history check; also report underlying data timestamps rather than concealing stale sources. |

UTC timestamp values use ISO 8601 with `Z`. Preserve actual broker ordering/watermarks when multiple deals share a timestamp. Missing values are empty cells, not zero, `NaN`, fabricated timestamps, or sample data. Approval/goal identifiers and start timestamps stay empty until real user approval and verified activation evidence exist.

## Persistence And Recovery

- Read and validate the complete CSV before updates: exact header/version, at most one logical row, identity/currency binding, finite numeric values, timestamps, latches, approval provenance, and internal consistency. Invalid or unreconciled data blocks entries; do not overwrite corruption with permissive defaults.
- Keep a single writer for the active account. Verify exclusive trading ownership with the guard; another client/session/worktree must not trade the same account concurrently. Do not switch accounts while prior exposure or protection is unresolved. A different account requires separate approval and recovery of its own existing guard history, not reuse of the current row's peaks.
- Write validated complete state using atomic replacement or an equivalently reliable client-supported method, then read it back before risk-increasing actions. Preserve the prior row in a local ignored backup when replacing a policy/account. If persistence or ownership is unreliable, block entries. CSV failure must not delay identity-verified, previously approved emergency reductions; the independent guard must retain the latch.
- Reconcile the CSV with current broker exposure, full cash-flow/deal history, continuous guard peaks/latches, armed policy, every unresolved durable mutation intent, and actual user approval provenance after restart/reconnection or any manual edit. The CSV is a checkpoint, not permission to override the guard or broker; absence of a visible order is not proof that an old request cannot still execute.
- Never lower a peak, clear a current daily/max breach, move an approval anchor, relabel trading losses as capital flows, or initialize an unknown day-start value to current equity to create headroom. Recover verified values or report unavailable and remain blocked.
- A goal or strategy change does not reset risk history. Renewing account authorization under the same risk policy must not alter `policy_approved_at_utc`, `policy_start_equity`, its cash-flow window, or peak. A replacement risk policy requires explicit approval of its changed rules and any proposed baseline reset, a new policy ID, preserved old history, and verified guard installation; never auto-replace a breached policy.

## Drawdown Calculations

Use full-precision verified values in the account currency. External capital flows are signed: deposits positive, withdrawals negative. Classify transfers/credits/adjustments using documented broker semantics; trading commission, swap, fees, and losses are not external capital flows. Ambiguous classifications block new exposure.

The daily and policy windows differ. At mid-day setup, the daily cash-flow window already includes movements earlier that day, while the newly approved policy window starts at zero.

```text
E = current account equity, including floating P&L and costs
C_policy = net external cash flows since policy approval
C_day = net external cash flows since broker midnight
A_policy = E - C_policy
A_day = E - C_day
D = actual equity at broker midnight
H = highest continuously verified A_policy since policy approval

daily_drawdown_pct_used = 100 * max(0, D - A_day) / D
max_drawdown_pct_used = 100 * (H - A_policy) / H
daily_floor = D * (1 - daily_drawdown_pct / 100)
trailing_floor = H * (1 - max_drawdown_pct / 100)
daily_allowance = A_day - daily_floor
trailing_allowance = A_policy - trailing_floor
remaining_loss_allowance = min(daily_allowance, trailing_allowance)
per_trade_cap = E * risk_per_trade_pct / 100
aggregate_cap = E * max_aggregate_risk_pct / 100
```

Initialize policy `C_policy = 0` and `H = policy_start_equity` only at a verified new approved policy anchor. Thereafter reconcile `H` with the guard's continuous maximum; a chat-sampled peak is insufficient. If verified `H < A_policy`, obtain fresh consistent guard evidence rather than silently repairing a stale peak locally. Nonpositive/unknown baselines prevent sizing; authorized safety actions are still allowed on the confirmed account.

A breach occurs at equality: `daily_drawdown_pct_used >= daily_drawdown_pct` or `max_drawdown_pct_used >= max_drawdown_pct`, equivalently the matching adjusted equity at/below its floor. Do not trade against a displayed rounding difference, and do not clamp negative headroom to disguise a breach.

At verified broker midnight, record actual new `D`, new `broker_day`, and `C_day = 0`, then reconcile any later flows. Release only the prior day's daily latch when the guard confirms the rollover and the new day is not breached. Do not reset `C_policy`, `H`, or the maximum latch. Require authoritative timezone/DST, midnight equity, and continuous breach history; history of closed trades alone cannot reconstruct floating midnight equity or missed equity peaks. Unknown day-start/history means no entries.

## Continuous Guard Gate

Prompt instructions are not an always-on risk engine. Autonomous entries require an independent, already implemented MT5/MCP-side guard that remains operating while the AI is inactive, disconnected, restarting, or denied tool access. Building/installing such a service is outside this repository's instructions-only scope.

Verify through documented guard operations/status readback that it:

- Is armed for this exact account/server, approved policy ID/anchor, timezone, all four limits, and the formulas above, with cash-flow/cost handling matching the broker.
- Continuously observes equity and all account exposure, including manual positions and pending orders, and enforces account-wide risk/admission budgets and exclusive execution ownership, not merely an alert to the AI.
- Atomically binds mutation/admission to the expected account and execution fencing generation, supports durable pre-dispatch intent/correlation records and crash-safe result recovery, and coordinates its own liquidation with the agent so only one authorized dispatcher acts on an outstanding operation.
- Persistently maintains the policy high-water mark, daily baselines, cash-flow windows, and daily/maximum breach latches through restarts/day changes.
- Can cancel all pending orders and liquidate all account positions under the approved mandate without needing the AI to stay active, and blocks new exposure when halted.
- Has verifiably current heartbeat/feed health under its documented cadence/timeouts and maintains protection under relevant connection failures. Unknown health or undocumented freshness behavior is not proof of continuous coverage.

A user assertion, CSV `ready` flag, broker-side individual stop, or status label without matching policy/readback is insufficient. Configure/arm a supported existing guard only after explicit approval. Missing, stale, unhealthy, mismatched, or unverifiable guard/ownership evidence blocks entries, but does not prohibit approved identity-verified safety reductions. Setup, target recording, strategy collection, and honest reporting may still proceed while execution is blocked.

Even a continuous guard and stops cannot guarantee losses stay within limits: gaps, slippage, stale broker feeds, outages, market closure, rejected liquidation, and permissions may exceed them. Never promise a hard cap or guaranteed return.

## Pre-Order Risk Gate

Before any entry, pending order, added volume, or other risk increase:

1. Reverify the account, approvals, persisted state, exclusive ownership/fencing, source freshness, armed guard, and resolution of every prior mutation intent. Require server-side account-bound dispatch, not merely a pre-call identity check. A `ready` checkpoint is not a substitute for this check.
2. Refresh all open/manual positions and pending orders. Require valid protective stops submitted with new orders and confirmed by readback; if the API cannot attach protection at entry or existing exposure has unknown/unprotected stop risk, do not add exposure. Do not alter manual stops without appropriate explicit authority.
3. Calculate conservative account-currency stressed-stop loss using real tick/contract values, prices, conversion, direction and broker rules. Existing-position loss is from current mark to stop, including the possible reversal of floating gains, not just entry-to-stop risk. Pending/proposed loss is from its stressed entry to stop. Include incremental commission, swap/fees, spread where not already counted, and a defensible slippage/gap allowance without double-counting costs already in equity. This is a stress estimate, not a guaranteed worst loss.
4. Assume all compatible pending/proposed exposure can fill. Do not net risks with unverified hedge/correlation offsets, positive take-profit outcomes, or presumed order cancellation. Include external/manual exposure in the aggregate.
5. Let `R_existing` be stressed-stop risk of all current open/pending exposure and `R_new` the proposal's risk. Require `R_new <= per_trade_cap` and `R_existing + R_new < min(aggregate_cap, remaining_loss_allowance)` with a conservative additional safety margin. Unknown necessary cost/stress assumptions must be resolved before execution, not set to zero.
6. Round volume down to the actual broker lot step, then recalculate risk, minimum/maximum lot, stop/freeze distances, margin/free margin, market availability, and trading permissions. If even the minimum lot does not fit, skip the trade. Do not round risk up into a limit.
7. Durably journal the account/policy/owner, unique approved signal/action ID, and parameters before dispatch. Execute only that approved strategy signal through actual documented account-fenced MCP semantics, verify fills/stops/remaining volume, then finalize the journal outcome and reconcile guard/CSV/history. An uncertain acknowledgment invokes the connection file's recovery rules, not blind retries or a replacement intent ID.

If an accepted fill or modification has missing/incorrect protection or unexpected volume, halt entries, set `reconciliation_required`, notify the guard, and follow the explicitly approved protection-failure response. Restore only the intended approved protection or reduce/close affected exposure through coordinated account-bound safety operations; never widen the stop to fit broker restrictions or leave the failure unreported while waiting for another signal. Obtain appropriate authority for manual-position changes rather than assuming it from the ability to read them.

Do not widen stops or increase leverage/risk allocations to chase a target or recover a loss. A risk-compliant position size is a ceiling, not an instruction to use all remaining headroom. No signal means no trade.

## Breaches And State

Risk latches are independent of the display state. A max latch survives all other status changes; a daily latch survives recovery within its broker day.

| `risk_state` | Meaning |
| --- | --- |
| `setup_incomplete` | A required input, strategy, target, or real approval is missing; header-only has this effective state. |
| `ready` | All prerequisites are currently verified, with no applicable breach; entries still require the pre-order gate and strategy signal. |
| `daily_halted` | Current broker day's daily latch is active, even if equity later recovers. |
| `max_halted` | A maximum breach is latched; takes precedence over all other display states. |
| `guard_unavailable` | Guard health/policy/ownership cannot be verified; retain any separate breach latches. |
| `reconciliation_required` | History, identity, source consistency, CSV, or mutation result is unresolved; retain separate latches. |

On a confirmed breach, halt risk increases immediately and record the appropriate latch in guard/local state as reliably as possible. Under the already approved account-wide mandate, cancel all pending orders and close all open positions, including manual trades, using true documented cancellation/position-close semantics. Do not wait for another goal question or for a failed CSV write to succeed.

Coordinate with the guard's liquidation ownership/journal and read back actual orders/positions and remaining volume; do not duplicate a close the guard is already dispatching. Reconcile uncertain results before any bounded retry, respect hedging/netting behavior, and report unresolved exposure/permission failures without claiming successful flattening. If the account cannot be positively identified and atomically bound or tools are disconnected, do not blindly mutate another account; rely on the independent guard and escalate the unresolved protection status.

Daily trading may resume only after a verified new broker day, recovered midnight equity/cash flows, released daily guard latch, and all remaining gates. Maximum trading may resume only after explicit user reapproval, verified guard-authorized latch release, and confirmation that the retained policy is no longer breached or that a replacement policy/baseline was explicitly approved. Recovery alone is not reapproval.

## Arithmetic Checks

These are fictional validation cases, not default settings or authorization.

| Case | Expected Result |
| --- | --- |
| `D = 10000`, daily limit `2%`, `H = 10500`, maximum limit `5%`, no intervening flows | Floors `9800` and `9975`; trailing allowance is binding. At equity `9975`, maximum drawdown is exactly `5%`: halt/flatten. |
| Same limits; verified `H` rises to `10600` | Trailing floor tightens to `10070`; do not retain the old lower floor. |
| Same-day post-approval deposit `2000`, equity `12000`, both cash-flow windows `2000` | Both adjusted equities `10000`; no profit, new peak, or loss from the deposit itself. |
| Same-day post-approval withdrawal `500`, equity `9500`, both windows `-500` | Both adjusted equities `10000`; no false drawdown from the withdrawal itself. |
| Day-start equity `10000`, deposit `2000` before mid-day policy approval at equity `12000` | `C_day = 2000`, `C_policy = 0`, `A_day = 10000`, `A_policy = H = 12000`; daily loss remains zero. |
| Prior-day post-policy deposit `2000`, new midnight equity `12000`, policy peak `10000` | New `D = 12000`, `C_day = 0`, `C_policy = 2000`, `A_policy = 10000`; daily baseline resets but the policy peak/window do not. |
| Daily breach followed by same-day recovery | Keep the daily latch; no entries until verified new day and the other gates. |
| Maximum breach followed by recovery/restart/midnight | Keep the maximum latch; require explicit reapproval and verified release. |
