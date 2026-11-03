# Monetary Risk And Account State

## Inputs And Authority

After read-only MT5 account verification, collect a positive monetary **budget** and **target**, in the verified account currency. These are the only user-supplied trading settings. Accept both together; ask one focused question only for missing or ambiguous amounts/currency. No percentage-risk, daily-limit, per-trade-cap, capital-allocation or routine symbol-selection questionnaire. There are no monetary defaults. A dollar sign does not necessarily mean USD.

The budget is a fixed-money trailing-loss allowance over the whole connected account, not segregated capital, a per-trade allowance, or a cumulative sum of losing trades. The account may contain much more equity. All manual/other-origin positions, pending orders, floating P&L and costs count. Ace chooses sizing and the number of qualifying orders, subject to actual broker affordability and remaining headroom, and spreads risk across several independent orders instead of committing the budget to one trade. An unaffordable minimum lot means no trade, not a larger budget.

Save supplied values through `draft` only after verifying their account binding. Drafts do not approve a goal, replace an active policy, reset its peak or release a stop. Reuse existing valid drafts as drafts and actual approval only after verifying its provenance. Analysis-only sessions, connection-only checks and instruction maintenance must not create account state.

The one final named-account approval must cover login/server/demo-live type/currency; both monetary amounts; observed-only trailing behavior; exact policy/goal baselines and source timestamps; the approved broker symbol universe; the current market read and its invalidation conditions; normal management permissions; and cancellation/closure of **all account exposure including manual trades** at either trigger. Disclose inactivity, missed peaks/breaches, execution delays and overshoots. Supplying amounts, an example or a stored boolean is not approval.

After that approval, an eligible action passing the checks below may be submitted through the actual MT5 MCP tool without another per-trade confirmation. Client tool permissions still apply. The helper neither grants those permissions nor places an order.

## Observed Trailing Arithmetic

Use actual equity, not balance alone. Equity already reflects the broker's current floating valuation and booked costs; do not deduct them twice. External cash flows are signed deposits/withdrawals/nontrading transfers under verified broker semantics, never commissions, swaps, fees or trading losses. Unknown classifications or incoherent history block additions.

```text
B = approved monetary budget
T = approved monetary target
E = current broker equity
C_policy = external cash flows since the policy anchor
C_goal = external cash flows since the goal anchor
A = E - C_policy
H = max(previous observed adjusted-equity peak, A)
drawdown = H - A
remaining_risk = B - drawdown
adjusted_stop_floor = H - B
current_account_stop_floor = H - B + C_policy

estimated_goal_gain = E - C_goal - goal_start_equity - remaining_close_costs
loss_trigger = drawdown >= B
target_trigger = estimated_goal_gain >= T

entry_fits = existing_stressed_risk + proposed_stressed_risk
             + additional_safety_margin < remaining_risk
```

Initialize `H` only at a genuinely approved new policy baseline. It follows the highest equity **actually observed** after cash-flow adjustment; do not invent unseen peaks or reconstruct continuous equity from closed deals. There is no midnight reset. Deposits/withdrawals do not create profit, drawdown or a new adjusted peak. Policy and goal anchors may differ; keep their cash-flow windows separate.

Equality breaches the loss budget, and equality in prospective allocation is unaffordable. Do not round comparisons to display precision, clamp negative headroom, or enlarge the budget after gains. `H >= A`, so remaining headroom never exceeds `B`. Use full-precision decimal arithmetic.

At either observed trigger, latch off new risk, cancel all pending entries and close all account positions under the approved mandate. Keep protective orders until their positions are safely closed, then reconcile orphan orders and late fills. Loss-stop handling takes precedence if both triggers apply. A submitted close is not verified flat exposure.

The target estimate deducts only incremental closing charges/slippage not already in equity. Once triggered, it stays latched even if final verified liquidation profit is below target. Report the trigger, pending closure, final net result and shortfall separately under [Goals And Progress](goals.md). Never automatically trade again to recover a shortfall.

## Before Each Risk Increase

1. Reverify the account, real approval provenance, the approved instrument universe, current market data, exposure ownership and unresolved intents. Use actual MCP schemas and broker permissions. A cached helper report or an earlier session's analysis is insufficient.
2. Read current equity/balance, all positions and pending orders, quotes/economics, margins and complete relevant history through MCP. Include manual exposure. Reconcile cash-flow coverage to the account snapshot; a deposit visible in equity but missing from lagging history must not become profit or a new peak.
3. Verify broker-side stops for existing exposure and protective stops in each entry request. Missing/unprotected exposure, unknown conversion or costs, and unexplained pending orders are not zero risk. Do not modify manual stops without authority.
4. Calculate conservative account-currency loss from **current marks to stressed stops** for open positions, including reversal of floating gains. Calculate pending/proposed entry-to-stop risk under stressed fills. Include incremental spread, commission, swap/fees, conversion and slippage/gap assumptions exactly once. Assume compatible pending orders can fill; do not net unverified hedges/correlations or anticipated profits/cancellations.
5. Size down to the broker lot step; verify minimum/maximum volume, stop/freeze distances, margin/free margin and actual trading availability. Use `R_existing + R_proposed + safety_margin < remaining_risk`. For an approved risk-increasing modification, the proposal includes all additional risk without assuming the old exposure has disappeared. Stop widening and loss-chasing remain prohibited.
6. Run `prepare` with a fresh coherent snapshot and the exact intended action. Only a successful `may_dispatch: true` for that recorded action permits proceeding to its actual MCP call under the approved mandate. Dispatch promptly with the same account/tool/parameters/action identity; a prior `check`, an old preparation, or exit code zero is not reusable order permission.
7. Read back actual fills, remaining volume/orders and protective stops. Use `resolve` with authoritative outcome evidence and a later snapshot. Missing/incorrect protection blocks additions; use the approved correction or reduction response, never a wider stop. A timeout or missing immediate order is not nonexecution and must not prompt a blind retry under a new ID.

There is no fixed trade-count cap. One unresolved dispatch at a time is a local recovery safeguard, not a limit on the number of verified open positions or subsequent qualifying trades. Normal actions retain their original management rules; no-entry regimes do not prevent already authorized reductions. Missing helper/state must not delay identity-verified, previously approved emergency reductions through MCP.

## Helper Boundary And CLI

[`scripts/account_check.py`](../scripts/account_check.py) uses Python's standard library only. It has no MT5 library, networking, credentials, order sender, scheduler or background loop. The agent obtains real MCP facts and executes actual MCP orders. A passing local check cannot fence manual traders, copied repositories, account switches or a change between check and dispatch. There is no independent continuous guard or guaranteed monetary cap/return.

Invoke `python scripts/account_check.py <command>`, supplying a JSON object through standard input or `--input <private-json-file>`. `status` needs no input. The default database is repository-root `ace_state.sqlite3`, independent of working directory; `--db <path>` exists for isolated tests or an explicitly managed location, not parallel trading ledgers. Do not initialize a real database to test the helper.

JSON money is preferably decimal strings; JSON integers/decimals are also parsed exactly. Booleans, binary Python floats, nonfinite numbers, currency symbols and grouped numbers are invalid money. Supported inputs have at most 28 significant digits, magnitude below `1e19`, and no more than 12 decimal places. Comparisons use 64-digit decimal context; SQLite never stores money as `REAL`. Times are actual ISO-8601 UTC strings ending in `Z`, including a `T`, not invented times copied from examples.

Exit code `0` means the request was processed, including blocked/stop decisions; read `decision`, `reason_codes` and **`may_dispatch`**. Only `prepare` can return a true dispatch flag. Contract/input/state errors return code `2` with `ok: false` and `may_dispatch: false`; CLI syntax errors use normal usage output. No error or successful calculation means an order was sent.

All mutating requests include `owner_id` (the verified single local writer identifier) and integer `expected_revision` from the previous result or `status`; the initial revision is `0`. Do not guess or blindly replay after a revision mismatch. Most processed checks, including blocked checks, advance the revision. Source/receipt references are nonsecret references to actual tool or user evidence, not tokens or fabricated verification.

| Command | Exact Additional Request Fields |
| --- | --- |
| `draft` | `account`, `source_ref`, supplied `budget` and/or `target`, and optionally the complete agent-prepared `mandate` proposal. Creates the database only during actual onboarding. Updates pending drafts, not active authority. Save the full proposed mandate before requesting final approval. |
| `activate` | `mode`, `mandate`, fresh `snapshot`, `approval_ref`, `approved_at`; reviewed approved `baseline` for `start`, `new_goal` and `replace_policy`; `reset_reason` for `replace_policy`, `takeover_ref` when changing `owner_id`. Except unchanged `resume`, both money amounts and the exactly matching mandate must already be saved as a draft. |
| `check` | `snapshot`. Records an actual observation, computes limits and latches; does not prepare an order. Call on every active decision cycle, even without an entry signal. |
| `prepare` | `snapshot`, `action`. Rechecks and transactionally records the exact action and its entry-risk reservation before MCP dispatch. |
| `resolve` | `snapshot`, `intent_id`, `outcome`, `evidence_ref`; `readback_verified: true` for settled outcomes and nonempty `broker_tickets` for `completed`. |
| `status` | No JSON required. Read-only cached state, revision and outstanding intent details; absent database means unconfigured and does not create a file. |

### Account And Snapshot

`account` is an object with exact string fields `login`, `server`, `type` (`demo` or `live`) and `currency`. Preserve login text, including leading zeros. Every snapshot repeats the same binding. A differently bound database is a blocker, not permission to overwrite the prior account or open another active ledger.

| Snapshot Field | Meaning / Type |
| --- | --- |
| `id`, `source_ref` | Nonempty identifiers for this actual observation and its MCP evidence. Do not relabel a cached observation as a new read. |
| `account`, `as_of` | Verified binding and coherent account observation time. Reject future/stale or out-of-order observations under the mandate's maximum age. |
| `history_anchor` | Immutable UTC ledger boundary. For `start` or explicit `replace_policy`, it equals the approved **baseline** snapshot's `as_of`, where `cashflows` is empty. The fresh activation snapshot includes all later flows from that same boundary. Subsequent checks and same-policy goals retain it. |
| `history_cursor`, `history_through`, `history_complete` | Nonempty current broker history watermark; verified coverage at least through `as_of` and not into the future; literal `true` only after reconciliation. Coverage time is not merely the last deal's timestamp. Retain the original start watermark separately. |
| `cashflows` | Complete list of external-flow objects since the ledger boundary, each with unique string `id`, UTC `at`, and signed monetary `amount`. Repeated full lists are not accumulated again. Include empty `[]` only for verified no flows. |
| `balance`, `equity` | Actual broker money values. Negative equity is valid loss evidence, not an acceptable activation baseline. |
| `positions` | Complete array of open-position objects described below, or unavailable. Do not omit manual positions. |
| `pending_orders` | Complete array of pending-order objects described below, or unavailable. Pending fills and protective/orphan orders must be reconciled. |
| `free_margin`, `trading_enabled` | Verified account-currency free margin and actual boolean permission/availability for additions. Unknown values block additions. |
| `remaining_close_costs` | Nonnegative incremental estimated liquidation costs not already included in equity; unavailable is not zero. |
| `costs_final` | Literal `true` only when costs and final accounting are reconciled. With verified flat/no pending exposure, zero remaining close costs and no outstanding intent, a stopped account may report its final result. |

Each position needs string `ticket`, string `symbol`, boolean `protected`, and nonnegative stressed current-mark-to-stop `risk`. Each pending entry needs those fields plus `kind: "entry"`, with stressed entry-to-stop risk. Ticket uniqueness is checked separately for positions and orders because broker namespaces may overlap.

A separate protective pending order uses `kind: "protective"`, `reduce_only: true`, and `position_ticket` referencing the protected open position. Its risk is already counted in the position, so do not count it twice or mislabel an entry/reversal as protective. Native SL/TP attached to a position is represented by that position's protection/risk, not a fictitious separate order. Preserve journal-backed original goal ownership outside these arithmetic fields when managing exposure.

The helper validates the accounting core before moving a peak. It rejects duplicate flows, removed/changed prior events, newly inserted events at/before a previously accepted complete snapshot, conflicting reuse of snapshot identity/time, and incoherent windows. Backdated corrections could change old adjusted peaks, so do not apply them only to current equity. Resolve corrections with authoritative evidence; never patch the database or silently drop prior flows to obtain headroom. A blocked correction leaves policy history/latches intact; an explicit replacement policy is required if the original ledger cannot be reconciled.

Missing proposal, exposure, margin or exit-cost inputs do not suppress a separately verified account loss trigger. A valid target estimate can latch even when existing exposure is unprotected. Unknown history/equity cannot establish a new monetary trigger, but cannot release a prior latch or invalidate already-authorized emergency reduction authority.

### Mandate And Activation

`mandate` is the complete agent-prepared specification, not extra user risk settings:

| Field | Meaning |
| --- | --- |
| `symbols` | Nonempty unique list of approved broker symbols discovered through MCP. No automatic expansion from newer analysis or unapproved instruments. |
| `max_snapshot_age_seconds` | Positive integer technical freshness limit chosen by Ace and disclosed in final approval; not a claim that observations occur continuously. |
| `safety_margin` | Positive monetary contingency additional to modeled costs/stress counted in exposure. Ace derives it; the user need not supply another risk setting. |
| `allow_entries`, `allow_management` | Requested permissions in an unapproved proposal; at activation, `true` only when real approval permits entries and normal management. |
| `close_all_on_loss`, `close_all_on_target` | Proposed whole-account cancellation/closure permissions, including manual exposure; at activation, `true` only when actual approval grants them. |
| `accept_observed_only` | The proposal discloses active-snapshot-only checks and possible missed peaks/breaches/overshoots. At activation, `true` requires actual acceptance of that disclosed limitation. A draft flag is never acceptance. |

For a new policy/goal, present a real current `baseline` snapshot and the stored complete proposal before the final approval. `baseline` has the same fields as a snapshot. `approved_at` must be at or after that baseline and not in the future. Do not change the reviewed baseline merely because the user takes time to answer.

After approval, obtain a separate fresh `snapshot`, with `as_of` at/after approval and a coherent full cash-flow ledger from the original boundary. The reviewed baseline may now be older than the live freshness limit; only that explicitly reviewed baseline receives this exception. The current snapshot must still be fresh. Activation preserves the reviewed starting equities/times and then observes the current equity/flows, so intervening gains/losses may immediately latch a stop rather than quietly rebase it away. Changing the actual reviewed baseline/specification needs new approval; an ordinary confirmation delay does not. The helper cannot authenticate JSON assertions, identify a real user, read receipts, or interpret market analysis; the agent must verify those facts.

| `mode` | State Transition |
| --- | --- |
| `start` | Only when no active policy exists. Create policy/goal IDs and positive equity/flow anchors from the reviewed `baseline`, then check the fresh `snapshot`. No CSV import or old approval reuse. |
| `resume` | Reverify existing authority/ownership and fresh data. Use the unchanged active budget, target and mandate, not pending drafts. Preserve IDs, anchors, peaks and both latches. Verified owner handoff may retain unresolved intents for recovery, but entries stay blocked. |
| `reauthorize` | Explicitly approve a newly saved full mandate/permission proposal with unchanged active budget/target, settled exposure/intents/costs and fresh post-approval data. Preserve both monetary baselines, IDs, ledger, peak and latches; new market authority does not reset financial history. No new `baseline`. |
| `new_goal` | Explicitly approve a new target/baseline, with unchanged budget/mandate and no loss latch. Old exposure/intents/costs must be settled at both baseline and fresh observation. Preserve risk policy/peak/ledger; give the goal its reviewed equity/cash-flow anchor, then observe current data. |
| `replace_policy` | Explicit approval of a new policy and baseline reset, a nonempty `reset_reason`, settled exposure/intents/costs at both observations. Archive old state, establish new IDs/anchors from `baseline`, then observe the fresh snapshot and all intervening flows. Never automatically release a loss stop. |

`takeover_ref` records actual evidence that the prior writer has stopped and the new owner is authorized. A new string does not fence an old process. Ownership-only `resume` may hand off unresolved intents without releasing them or changing their original identities; the new verified owner can then resolve them. Unresolved intents block other activation modes and new entries. Do not automatically flatten exposure merely to change a goal/policy: use existing approved exits or obtain applicable closure authority.

### Action And Outcome

Every `action` includes string `id` (unique durable action/correlation ID), `kind` (`entry` or `reduce`), actual MCP `tool`, exact nonempty `parameters` object, `authority_ref`, current `policy_id` and `goal_id`, and `tool_permission: true` only when actually available. Use the real schema rather than invented universal order fields. MCP parameter numbers remain JSON numbers, not monetary strings; numbers that cannot round-trip through the tool's ordinary JSON-number representation are rejected, not rounded. Accounting remains decimal. No credentials in parameters/records; recognized credential keys are rejected rather than journaled.

An `entry` also supplies the approved `symbol`, unique `signal_id`, nonempty `analysis_ref` identifying the market read that justified it, positive proposed stressed `risk`, nonnegative required `margin`, and true verified attestations `broker_checks_passed` and `protective_stop_in_request`. These checks also apply to risk-increasing modifications, not just new market orders. The helper compares money/scope and records a local reservation; the agent must independently verify the facts behind every attestation.

A `reduce` supplies `reason` (`management`, `protection_failure`, `loss`, or `target`), nonempty unique `tickets` from current exposure, and `reduction_verified: true`. `loss`/`target` require the corresponding observed latch. The agent must verify actual authority, original management rules, remaining volume and documented reducing semantics; an opposite entry is not necessarily a close. Never widen a stop, remove a still-needed protective order, alter manual exposure under an ordinary position-management claim, or treat a risk increase as a reduction. Safety reductions remain eligible during no-entry states; overlapping unresolved reductions on the same tickets are blocked.

After a successful preparation, send the exact recorded action through MCP and then resolve it:

- `outcome: "completed"` means the broker request is authoritatively settled and its result/remaining exposure/protection are verified. It can include an accepted pending order or a terminal partial fill; it does not mean the account is flat. Supply actual `broker_tickets` and genuine post-dispatch readback. Its snapshot must be later than both the preparation's source observation and its local `created_at`, not merely newer than an older pre-dispatch quote.
- `outcome: "not_executed"` needs authoritative terminal nonexecution evidence and later verified readback. An empty order list, timeout or failed connection is insufficient. Do not invent a rejection to release a reservation.
- `outcome: "unknown"` retains the original intent and reservation. Store available response/status evidence and reconcile through MCP. `status.outstanding_intents` exposes original action, status and available outcome/evidence for recovery. Do not resubmit the same action with a replacement ID.

Distinct action IDs are never reused, including after rejection. A repeated symbol/signal within a goal is also rejected. Local status must not be interpreted as server-side deduplication or exactly-once execution. Invalid/stale data or a failed `prepare` cannot authorize a pending order later.

## SQLite And Recovery

`ace_state.sqlite3` is the sole local account checkpoint. Its sidecars/backups are private and Git-ignored. Root `risk_management.csv` and `risk_management.csv.*` records are retired and discarded without import: do not create, detect, read, migrate, depend on, or ask about them in future onboarding.

The helper uses `PRAGMA user_version = 1` and three tables: singleton `state` (`id`, `revision`, JSON `payload`), append-only `events` (`id`, `at`, `command`, JSON `detail`, `state_sha256`), and `intents` (`id`, unique `signal_key`, `status`, JSON `payload`, JSON `outcome`). It uses parameterized SQL and `BEGIN IMMEDIATE` for local check/reserve/write serialization. A state/audit digest detects mismatched local edits, not authentic human approval or malicious modification of the whole database.

State retains account/owner binding; pending drafts; policy/goal IDs and immutable approval/baseline/flow references; the full mandate; observed peak; independent loss/target latch timestamps; last snapshot, calculations and result; and original history boundary/cursor. Events preserve replaced mandates and observations; intents preserve exact action parameters and uncertain outcomes. Never edit SQL/JSON to manufacture approval or clear a latch, reservation or peak.

Import, help, tests and absent `status` do not create a production database. Only an explicit valid `draft` initializes a new checkpoint; `activate` needs that draft. Missing, corrupt, unsupported, busy or unreliable state blocks new risk, not an assumed zero exposure or a reset policy. Keep last source timestamps; `status` is cached, not current account verification.

On reconnection, read `status`, verify original approval provenance and single-writer ownership, get actual MCP account/exposure/history, and reconcile every outstanding intent before risk increases. Do not demand unseen equity peaks or midnight history. Preserve same-policy peaks and both stop latches across reconnects, equity recovery, new days, accounting corrections and goal drafts. Unknown costs/history or discarded/missing real approval is unavailable, not permission.

## Synthetic Checks

These are arithmetic fixtures, never settings, approvals or real account facts. Automated tests are in [`tests/test_account_check.py`](../tests/test_account_check.py); run `python -m unittest discover -s tests -v` with isolated temporary databases and no MCP. `ACE_TEST_TMPDIR` may select a permitted temporary parent.

| Fixture | Expected Result |
| --- | --- |
| Budget `5`, start equity `100`; observe `110`, then `108` | Peak `110`, stop floor `105`, remaining risk `3`. At `105`, latch the loss stop. |
| Remaining risk `3`, existing risk `1`, proposal `1.5`, extra buffer `0.5` | Reject equality; no trade-count reset or alternative budget. |
| Equity `300` after an external deposit `200` from a `100` start | Adjusted equity `100`, no artificial profit/peak. Repeated full ledger reads count the deposit once. |
| Target `15`, start equity `100`, current equity `115`, remaining close costs `0.5` | Estimated gain `14.5`, not yet reached. At equity `115.5`, trigger cancellation/closure. |
| Target triggered, later verified flat net gain `14.7` | Remain stopped; report final shortfall `0.3`, not an automatic recovery trade. |
| Eligible approved signal, fresh verified inputs, affordable proposal and MCP permission | `prepare` records the exact action and permits real MCP dispatch; a later qualifying trade needs no separate account reapproval. |
