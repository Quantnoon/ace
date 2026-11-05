# Monetary Risk And Account State

## Inputs And Authority

After read-only MT5 account verification, collect a positive monetary **budget** and **target**, in the verified account currency. These are the only user-supplied trading settings. Accept both together; ask one focused question only for missing or ambiguous amounts/currency. No percentage-risk, daily-limit, per-trade-cap, capital-allocation or routine symbol-selection questionnaire. There are no monetary defaults. A dollar sign does not necessarily mean USD.

The budget is a fixed-money trailing-loss allowance over the whole connected account, not segregated capital, a per-trade allowance, or a cumulative sum of losing trades. The account may contain much more equity. All manual/other-origin positions, pending orders, floating P&L and costs count. Ace chooses sizing and the number of qualifying orders, subject to actual broker affordability and remaining headroom, and spreads risk across independent trade ideas instead of committing the budget to one trade. Controlled additions to a winner remain part of its original idea, not extra diversification, under [Active Order Management](#active-order-management). An unaffordable minimum lot means no trade, not a larger budget.

Save supplied values through `draft` only after verifying their account binding. Drafts do not approve a goal, replace an active policy, reset its peak or release a stop. Reuse existing valid drafts as drafts and actual approval only after verifying its provenance. Analysis-only sessions, connection-only checks and instruction maintenance must not create account state.

In an ordinary trading/setup request, the user's complete budget and target are the start instruction under the [Execution Contract](../AGENTS.md#execution-contract); the final missing amount supplied for that request completes it. Record the real user evidence and timestamp. This instruction authorizes the documented MT5 operations on the single verified account: agent-selected eligible instruments/settings, risk-limited entries, Ace-only management under [Active Order Management](#active-order-management), and cancellation/closure of **all account exposure including manual trades** at either trigger. It also starts the ongoing user-controlled agent session, including stopped monitoring after settlement. Do not ask for a final account confirmation, per-trade permission or another loop opt-in. This is task-scoped authority, not unrelated/admin access, a host-permission change or permission to bypass a denied tool. Drafts, examples, MCP responses, automatic continuation messages and read-only/bounded requests do not supply that authority.

Verify the account and actual wait/continuation capability, prepare the full mandate, and disclose the binding, selected universe/settings and observed-only limitations without turning the report into a question. Ask only for genuinely missing or ambiguous facts. Activate promptly from fresh data, handle any activation-time latch, register/reuse `session` control, then begin a separate fresh first `cycle` under [Loop Sessions](loop.md). Continue management/reconciliation -> source-bound dashboard journal -> consume revision -> actual wait -> fresh read, including stopped observation after settlement. The AI client is the runtime; the helper supplies neither a scheduler nor authority/tool permissions. A real new user instruction is required for a new goal, material scope change, risk reset or restart after user end, not an extra confirmation of an already explicit instruction. Never expand old bounded authority just because these files changed.

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

Equality breaches the loss budget, and equality against remaining account-wide headroom is unaffordable. Do not round comparisons to display precision, clamp negative headroom, or enlarge the budget after gains. `H >= A`, so remaining headroom never exceeds `B`. Use full-precision decimal arithmetic.

At either observed trigger, latch off new risk, cancel all pending entries and close all account positions under the approved mandate. Keep protective orders until their positions are safely closed, then reconcile orphan orders and late fills. Loss-stop handling takes precedence if both triggers apply. A submitted close is not verified flat exposure.

The target estimate deducts only incremental closing charges/slippage not already in equity. Once triggered, it stays latched even if final verified liquidation profit is below target. Report the trigger, pending closure, final net result and shortfall separately under [Goals And Progress](goals.md). Never automatically trade again to recover a shortfall.

## Before Each Risk Increase

1. Reverify the account, real approval provenance, the approved instrument universe, current market data, exposure ownership and unresolved intents. Use actual MCP schemas and broker permissions. A cached helper report or an earlier session's analysis is insufficient.
2. Read current equity/balance, all positions and pending orders, quotes/economics, margins and complete relevant history through MCP. Include manual exposure. Reconcile cash-flow coverage to the account snapshot; a deposit visible in equity but missing from lagging history must not become profit or a new peak.
3. Verify broker-side stops for existing exposure and protective stops in each entry request. Missing/unprotected exposure, unknown conversion or costs, and unexplained pending orders are not zero risk. Do not modify manual stops without authority.
4. Calculate conservative account-currency loss from **current marks to stressed stops** for open positions, including reversal of floating gains. Calculate pending/proposed entry-to-stop risk under stressed fills. Include incremental spread, commission, swap/fees, conversion and slippage/gap assumptions exactly once. Assume compatible pending orders can fill; do not net unverified hedges/correlations or anticipated profits/cancellations.
5. Size down to the broker lot step; verify minimum/maximum volume, stop/freeze distances, margin/free margin and actual trading availability. Use `R_existing + R_proposed + safety_margin < remaining_risk`. For an approved risk-increasing modification, the proposal includes all additional risk without assuming the old exposure has disappeared. Stop widening and loss-chasing remain prohibited.
6. Run `prepare` with a fresh coherent snapshot, the exact intended action and its required [decision context](#decision-context), outside MCP `parameters`. Only a successful `may_dispatch: true` for that durably recorded action permits proceeding to its actual MCP call under the approved mandate. Dispatch promptly with the same account/tool/parameters/action identity; a prior `check`, an old preparation, or exit code zero is not reusable order permission.
7. Read back actual fills, remaining volume/orders and protective stops. Use `resolve` with authoritative outcome evidence and a later snapshot. Missing/incorrect protection blocks additions; use the approved correction or reduction response, never a wider stop. A timeout or missing immediate order is not nonexecution and must not prompt a blind retry under a new ID.

There is no fixed trade-count cap. One unresolved dispatch at a time is a local recovery safeguard, not a limit on the number of verified open positions or subsequent qualifying trades. Normal actions retain their original management rules; no-entry regimes do not prevent already authorized reductions. Missing helper/state must not delay identity-verified, previously approved emergency reductions through MCP.

## Active Order Management

On each active decision cycle, obtain a fresh account/exposure/history snapshot and use `check`, or `cycle` instead during a loop session. Enforce monetary latches and authorized emergency reductions first, manage existing positions and pending entries next, and consider new exposure only after required management outcomes are verified. Position-level trailing SL does not replace the account-wide trailing budget. Neither trailing nor breakeven adjustments run while the AI is inactive; only the last accepted broker protection remains in place.

### Original Plan And Authority

Before entry, persist the original strategy and factual rationale in `action.context` through `prepare`, using the [exact decision-context fields](#decision-context). Keep initial protection in the exact MCP parameters and supporting market evidence behind `analysis_ref`/`source_refs`; an opaque reference alone no longer supplies a new entry's plan. The original entry intent ID identifies the idea, and its recorded `action.risk` is the fixed allocation. Bind the action to the named-account authority in `authority_ref`; verify actual fills, costs and ticket bindings on readback. Ace derives the plan from current structure, volatility, spread and economics, not universal pip distances or fixed R thresholds. These are not extra user settings or per-trade approval requests. Adaptive management applies the original rules to fresh data; later actions record new assessments without replacing the plan or moving a losing trade's invalidation.

Routine management applies only to verified Ace-owned exposure covered by that original authority and plan. Manual/other-origin exposure still counts in account risk and is covered by the approved whole-account loss/target closures, but must not be adopted or modified under a routine management claim. Adding these instructions does not expand an earlier approval: preserve existing exits unless they already permit this behavior, otherwise use explicit reauthorization and its settlement requirements before expanding scope. Do not flatten positions just to adopt new rules or reset any baseline, peak or latch.

On resumption use read-only [`context`](#context-recovery) to recover original entries, including completed ones, their related actions and linked journal assessments; `status.outstanding_intents` alone is insufficient. Reverify actual analysis/approval evidence, ownership and broker outcomes. Missing legacy plans stay unavailable, without automatic backfill, symbol-based adoption or inferred rules from MCP parameters. Missing ownership, original conditions or allocation blocks affected discretionary changes/additions, not separately verified, previously authorized safety reductions. The helper validates metadata and recorded links, not market reasoning, ownership or all protect-first economics. Do not edit SQL, create a second ledger or manufacture missing history.

### Running Positions

1. Review each Ace position's actual direction, remaining volume, fills, accepted SL/TP and associated protection. Use confirmed closed candles for ordinary structural decisions, with fresh quotes and verified costs for dispatch. Previously authorized, identity-verified safety reductions do not wait for a new candle or an entry signal.
2. Move to **breakeven** only after the recorded favorable-move condition is met and the market has enough room for a valid stop. Calculate the estimated net-zero exit using verified payoff/conversion, executable price-side semantics, attributable entry/exit charges, financing and stressed closing slippage. Entry price alone need not cover costs. Attributable booked charges may inform this trade-level exit estimate but must not be deducted again from account equity or goal progress. Unknown economics/costs block a guessed breakeven move; gaps, slippage and late charges mean even a cost-aware stop never guarantees zero loss.
3. **Trail** behind newly confirmed higher lows/support for a long or lower highs/resistance for a short, using the recorded method and a justified volatility/spread buffer. For both trailing and breakeven, a new long SL must be higher than the currently accepted SL; a new short SL must be lower. Never move a stronger profit-locking stop back to breakeven. Check the broker's actual trigger-price side, tick size, stop/freeze distances and modification permissions after rounding. Skip identical, noise-driven or invalid changes; choose one valid improving stop when breakeven and trailing conditions overlap. If no tighter valid level exists, retain the accepted protection, never loosen or remove it to make an update pass.
4. **Close on invalidation** when fresh evidence confirms the original exit condition. Use true position-close semantics and verify any remaining volume rather than waiting for the old SL or moving the invalidation farther away. Do not automatically reverse or re-enter after that exit. Preserve unrelated TP/protection during stop updates; this policy adds no partial-profit-taking or TP-redesign rule.

On hedging accounts, verify each affected ticket and its protection. On netting accounts, an add or SL update can affect the aggregated position: verify original deal/volume ownership, effective stop and protection of every earlier leg. Never let an add overwrite the aggregate SL with a weaker stop. If manual exposure is mixed in, or the affected ownership/protection cannot be verified without changing it, skip routine changes/additions instead of inventing isolated positions or authority. An opposite entry may hedge or reverse rather than close.

### Pending Entries

- Review every Ace pending entry's recorded validity, not only orders near the current price. Retain a still-valid setup. Cancel when confirmed structure invalidates it, its recorded expiry is reached, or its recorded session/event/economics conditions cease to hold. Mere age, distance from price, a new candle or missing data is not invented proof of invalidation. Report unavailable evidence and block affected additions; separately authorized safety cancellations still require verified targeting and authority.
- Cancel an unfilled **entry** with the documented order-cancel operation; close a resulting position with position-close semantics. Do not treat a native SL/TP or necessary protective pending order as a stale entry. Preserve protection until its position is safely closed.
- Do not re-level an order just to chase price. For a replacement, prefer cancel -> authoritative readback and `resolve` -> genuinely fresh valid setup -> new `prepare`. Do not release risk on a submitted cancellation, blindly recreate the same signal under a new ID, or assume a timeout/empty order list proves nonexecution. Reconcile partial or late fills, resulting positions and remaining orders before further risk increases, preserving their original bindings and protection.
- Cancel a dependent unfilled add when its required parent exposure closes or its thesis/protection conditions fail. If it has already filled, reconcile and manage the actual position under its original plan, not a fictitious successful cancellation. Do not stage an unchecked ladder of adds that can bypass protect-first eligibility.

### New Orders And Winner Additions

Spare headroom, a canceled order, a closed trade or a profitable position is not by itself a signal. New market/pending entries need fresh analysis within the approved universe, a genuinely distinct signal/action identity, verified stops/economics/margin and every check in [Before Each Risk Increase](#before-each-risk-increase). There is no forced replacement or target-driven turnover.

An addition to a winner also requires the original thesis to remain valid, a fresh favorable continuation setup, and **every earlier open leg of that idea to be individually profitable after attributable costs and protected by a verified cost-aware breakeven-or-better stop**. Aggregate profit must not hide a losing or unprotected leg. Verify earlier protection before preparing the add; a proposed stop move does not qualify. If the original allocation or earlier-leg bindings cannot be recovered, do not add.

Treat the original entry and every related continuation leg/pending entry as one idea. Its fixed allocation is the first entry action's recorded proposed stressed `risk`, chosen by Ace before entry. Never expand it after gains, fills, later additions, closes or reconnects, or label the same thesis independent to evade it. The following are agent admission calculations, not extra JSON budget fields, independent helper enforcement or a separate account latch:

```text
idea_limit = original entry action's recorded stressed risk
idea_open_risk + idea_pending_risk + proposed_risk <= idea_limit
all_account_existing_risk + proposed_risk + safety_margin < remaining_risk
```

Open risk is current-mark-to-stressed-stop loss, including floating-profit give-back; pending/proposed risk is stressed entry-to-stop loss. Include all compatible pending fills, costs and stress exactly once. **Breakeven does not make existing risk zero.** Do not offset correlated exposure, spend anticipated profits/cancellations or increase lot sizes to chase the target. Size each sequential add within both limits using fresh verified exposure after previous actions resolve. The idea limit gates additions; it is not authority to force a close or tighten a stop without a valid management reason.

### Dispatch And Recovery

| Intended Action | Helper Classification | Context Operation |
| --- | --- | --- |
| Verified SL tightening or breakeven move | `kind: "reduce"`, `reason: "management"`; actual reducing semantics, original authority and verified tickets. | `trail` or `breakeven`, linked to the original entry. |
| Cancel invalid Ace pending entry or close invalidated Ace position | `kind: "reduce"`, `reason: "management"`; verified entry/protection and remaining-volume semantics. | Required `cancel` or `close` context linked to the original entry. |
| New independent order or winner addition | `kind: "entry"`; fresh analysis, broker checks, protection and full stressed-risk reservation. Never disguise an increase as a reduction. | Required `entry` with original strategy, or `add` linked to that strategy's root intent. |
| Observed account loss/target stop | `kind: "reduce"`, `reason: "loss"`/`"target"`; overrides routine management and covers manual exposure too. | `close`/`cancel` may omit the root; missing context must not delay authorized emergency reductions. |

Use fresh `prepare` -> exact documented MCP action -> later broker readback -> `resolve` for each ordinary mutation. Only `may_dispatch: true` with still-applicable authority/session control permits that recorded action; `may_continue`, `check` and exit code zero do not. An intervening user stop invalidates unused routine permission. Verify actual SL/TP, tickets, fills, remaining volume/orders and cancellation/closure status, then recalculate stressed risk from the verified result. After a rejection, read back whether the old protection remains and report the result rather than claiming an improvement. Ambiguous changes, timeouts and unsettled partial outcomes retain their original unresolved intent and block additions: no blind retry, replacement identity or assumed release of headroom. Helper failure must not delay previously authorized, identity-verified emergency reductions through safely targeted MCP tools.

## Helper Boundary And CLI

[`scripts/account_check.py`](../scripts/account_check.py) uses Python's standard library only. It has no MT5 library, networking, credentials, order sender, scheduler or background loop. The agent obtains real MCP facts and executes actual MCP orders. A passing local check cannot fence manual traders, copied repositories, account switches or a change between check and dispatch. There is no independent continuous guard or guaranteed monetary cap/return. The `cycle` command records loop observations, candle evidence and a wake plan; it neither waits nor wakes itself.

Invoke `python scripts/account_check.py <command>`. Mutating commands take a JSON object through standard input or `--input <private-json-file>`; read-only `status` needs no input, and `context` takes only the [CLI options below](#context-recovery), not JSON stdin or `--input`. The default database is repository-root `ace_state.sqlite3`, independent of working directory; `--db <path>` exists for isolated tests or an explicitly managed location, not parallel trading ledgers. Do not initialize a real database to test the helper.

JSON money is preferably decimal strings; JSON integers/decimals are also parsed exactly. Booleans, binary Python floats, nonfinite numbers, currency symbols and grouped numbers are invalid money. Supported inputs have at most 28 significant digits, magnitude below `1e19`, and no more than 12 decimal places. Comparisons use 64-digit decimal context; SQLite never stores money as `REAL`. Times are actual ISO-8601 UTC strings ending in `Z`, including a `T`, not invented times copied from examples.

Exit code `0` means the request was processed, including blocked/stop decisions; read `decision`, `reason_codes` and **`may_dispatch`**. Only `prepare` can return a true dispatch flag. Contract/input/state errors return code `2` with `ok: false` and `may_dispatch: false`; CLI syntax errors use normal usage output. No error or successful calculation means an order was sent.

All mutating requests include `owner_id` (the verified single local writer identifier) and integer `expected_revision` from the previous result or `status`; the initial revision is `0`. Processed blocked helper requests, including stale-snapshot requests, may be audited and consume a revision: use the returned revision. After a revision conflict or unknown local outcome, read `status`, not a guessed revision or blind replay. A failed MCP read makes no snapshot-based helper/journal call and changes no observation. A separately recorded real user stop or unavoidable interruption is a control event, not a fabricated account read. Source/receipt references are nonsecret references to actual tool or user evidence, not tokens or fabricated verification.

| Command | Exact Additional Request Fields |
| --- | --- |
| `draft` | `account`, `source_ref`, supplied `budget` and/or `target`, and optionally the complete agent-prepared `mandate` proposal. Creates the database only during actual onboarding. Updates pending drafts, not active authority. Save the full mandate before activation; this is not a request for another human approval. |
| `activate` | `mode`, `mandate`, fresh `snapshot`, real `approval_ref` and `approved_at`; `approval_mode: "start_request"` for the user's trading-start instruction, or legacy `reviewed` when backed by an actual reviewed receipt; `baseline` for `start`, `new_goal` and `replace_policy`; `reset_reason` for `replace_policy`, `takeover_ref` when changing `owner_id`. Except unchanged `resume`, both money amounts and the exactly matching mandate must already be saved as a draft. See the timing rules below. |
| `session` | `action` (`start`, `resume`, `stop`, `interrupt`), real `evidence_ref`, and `reason`, with the common `owner_id`/`expected_revision`. Records user-controlled continuation or an actual interruption without a snapshot or financial observation; see [Agent Session Control](#agent-session-control). |
| `check` | `snapshot`. Records an actual observation, computes limits/latches and updates an existing loop's lifecycle; never starts a loop or agent session or prepares an order. Use for ordinary bounded checks, latch-only wakes and stopped-account monitoring. |
| `cycle` | `snapshot`, plus optional `timeframe`, `clock`, `bar`, `market_state`, `buffer_seconds` under [Loop Input And Results](#loop-input-and-results). Starts/continues the authorized loop, counts unique accepted observations and reports candle evidence/wake plans, even without an entry signal. |
| `prepare` | `snapshot`, `action`, including required context for entry/add and newly prepared routine management. Rechecks and transactionally records the exact action, valid decision context and entry-risk reservation before MCP dispatch; emergency metadata is optional. |
| `resolve` | `snapshot`, `intent_id`, `outcome`, `evidence_ref`; `readback_verified: true` for settled outcomes and nonempty `broker_tickets` for `completed`. |
| `journal` | `snapshot_id`, `as_of`, `activity`, `summary`, `reason`, `next_step`, plus optional display fields under [Journal Reports](#journal-reports). Saves an explanation, never an observation or dispatch permission. |
| `status` | No input required. Read-only cached state, revision, outstanding private intent details and the canonical continuation view described below. Absent database is unconfigured, without file creation. Neither observation nor execution proof. |
| `context` | Read-only `before`, `limit`, `origin_intent_id` options, with no owner/revision or account override. Returns scoped originating/related private intent records, including completed entries, linked reports and the cached continuation view; see [Context Recovery](#context-recovery). |

Successful `status`, `context` and `journal` responses project canonical `state.session` and `state.loop` as top-level `session`/`loop`, with `may_continue` and derived `loop_health`. This pure cached view calls no observation, risk report, lifecycle synchronization or wake planner. With session control, `may_continue` is true only for `active`, including financial `closed`; without it, only a saved `active`/`closing` loop yields true. Missing control objects stay null; with neither session nor loop, continuation is false. No view supplies new authority. `state.last_result` can predate a stop or resume and cannot override current control. Reads do not consume revisions; journal does. Preserve actual broker/action evidence separately, and never infer completion or a user stop from a reporting error or missing response fields.

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

A separate protective pending order uses `kind: "protective"`, `reduce_only: true`, and `position_ticket` referencing the protected open position. Its risk is already counted in the position, so do not count it twice or mislabel an entry/reversal as protective. Native SL/TP attached to a position is represented by that position's protection/risk, not a fictitious separate order. Preserve original intent/plan and verified goal/ownership evidence outside these arithmetic fields when managing exposure.

The helper validates the accounting core before moving a peak. It rejects duplicate flows, removed/changed prior events, newly inserted events at/before a previously accepted complete snapshot, conflicting reuse of snapshot identity/time, and incoherent windows. Backdated corrections could change old adjusted peaks, so do not apply them only to current equity. Resolve corrections with authoritative evidence; never patch the database or silently drop prior flows to obtain headroom. A blocked correction leaves policy history/latches intact; an explicit replacement policy is required if the original ledger cannot be reconciled.

Missing proposal, exposure, margin or exit-cost inputs do not suppress a separately verified account loss trigger. Rejected cycle bar/clock metadata likewise preserves accepted money, peaks and latches; scheduling errors must not suppress a known breach. A valid target estimate can latch even when existing exposure is unprotected. Unknown history/equity cannot establish a new monetary trigger, but cannot release a prior latch or invalidate already-authorized emergency reduction authority.

### Mandate And Activation

`mandate` is the complete agent-prepared specification, not extra user risk settings:

| Field | Meaning |
| --- | --- |
| `symbols` | Nonempty unique list of approved broker symbols discovered through MCP. No automatic expansion from newer analysis or unapproved instruments. |
| `max_snapshot_age_seconds` | Positive integer technical freshness limit chosen by Ace and disclosed at startup; not a claim that observations occur continuously. |
| `safety_margin` | Positive monetary contingency additional to modeled costs/stress counted in exposure. Ace derives it; the user need not supply another risk setting. |
| `allow_entries`, `allow_management` | At activation, `true` only when the actual start instruction or existing authority permits entries and normal management. These are verified assertions, not prompts for per-action permission. |
| `close_all_on_loss`, `close_all_on_target` | Whole-account cancellation/closure authority, including manual exposure, supplied by the documented start instruction or verified existing mandate. A draft boolean cannot grant it. |
| `accept_observed_only` | Record the start instruction's documented active-snapshot-only limits and disclose possible missed peaks/breaches/overshoots. A draft flag is not authority; do not demand a second acceptance of the same start contract. |
| `entry_timeframe` | Optional closed-candle timeframe that paces the approved [loop session](loop.md). Absent means M15; a request cannot override it. Changing it needs reauthorization, not a mid-session switch or another routine user setting. |
| `latch_check_seconds` | Optional latch-only tripwire interval; positive values add account checks from the last accepted observation's receipt time. Preserve `0`/absence as no additional periodic tripwire; never silently enable it on an existing mandate. It does not authorize entries. |

`baseline` has the same fields as a snapshot. `approval_ref` identifies the actual user instruction/receipt, never an invented assistant confirmation; `approved_at` is its real timestamp and cannot be in the future. Two timing contracts preserve existing receipts without imposing their old confirmation exchange on new starts:

- **`approval_mode: "start_request"`** is the normal new-start path. The user's complete monetary trading request delegates eligible instrument/settings selection and authorizes the documented workflow. Verify capability and save the mandate, then capture/activate a fresh baseline promptly, before discretionary trading analysis/entries. Require `approved_at <= baseline.as_of <= snapshot.as_of <= now`; both baseline and current snapshot must satisfy the mandate's freshness bound. There is no human review delay or historical-baseline exception in this mode. Never replace an accepted baseline, known peak or latch to improve the result.
- **`approval_mode: "reviewed"`** retains compatibility with real historical reviewed-baseline authority. It is the helper's default for old requests, not an instruction to ask new users for confirmation. Require `baseline.as_of <= approved_at <= snapshot.as_of <= now`. The exactly reviewed baseline may be older than the live freshness limit; the current snapshot may not. Do not reinterpret an old approval as a newer start request or change a reviewed baseline because time passed.

Use a coherent full cash-flow ledger from the original boundary in the current snapshot. Activation establishes the authorized baseline and then observes current equity/flows; intervening gains/losses may immediately latch a stop instead of being rebased away. Existing financial anchors remain fixed on `resume`. An omitted `approval_mode` on `resume` inherits the stored mode (legacy absent means `reviewed`); a resume cannot change it. New policy/goal records retain their original mode alongside authority timestamps. The helper cannot authenticate JSON assertions, identify a real user, read receipts or interpret analysis; the agent must verify those facts. A fresh baseline provided to a rejected transition can still establish a breach of the old policy, but a stale unreviewed baseline cannot ratchet that policy's peak.

Handle an activation-time latch immediately. Register/reuse the authorized agent-session control, obtain another fresh snapshot and issue the first `cycle` before normal management/entries. Do not wait for a fill or another message. Later cycles reuse that authority without repeated activation. Status, context, journal, dashboard or explicit one-shot checks never bootstrap a loop or agent session.

| `mode` | State Transition |
| --- | --- |
| `start` | Only when no active policy exists. Create policy/goal IDs and positive equity/flow anchors from the authorized `baseline`, then check the fresh `snapshot`. No CSV import or old approval reuse. |
| `resume` | Reverify existing authority/ownership and fresh data. Use unchanged active budget, target and mandate, not drafts; no routine new human approval. Preserve loop/policy/goal IDs, anchors, peak and latches. Bind legacy unbound loops prospectively under recovery below. Verified owner handoff may retain unresolved intents, but entries stay blocked pending recovery. |
| `reauthorize` | Explicitly approve a saved full mandate/permission proposal with unchanged money, settled exposure/intents/costs and fresh post-approval data. Preserve loop identity and all financial history; no new `baseline`. An approved timeframe change invalidates affected cadence/bar tracking. Symbol changes invalidate obsolete clock and all-universe closed-market evidence while retaining eligible high-water marks. These are recorded transitions, not financial resets. |
| `new_goal` | A real user instruction authorizes a new target/baseline, unchanged budget/mandate and no loss latch. Old exposure/intents/costs must be settled at both observations. Preserve risk policy/peak/ledger; give the goal its authorized anchor. Archive the prior loop and clear its active slot; the agent's automatic fresh first `cycle` creates the new bound loop only with permitted session continuation. |
| `replace_policy` | A real user instruction authorizes a new policy/baseline, nonempty `reset_reason` and settlement at both observations. Archive old state/loop, establish new IDs/anchors from `baseline`, then observe all intervening flows; with permitted active session control, the automatic fresh first `cycle` creates the new loop. Never automatically release a loss stop or restart a user-ended session. |

`takeover_ref` records actual evidence that the prior writer has stopped and the new owner is authorized. A new string does not fence an old process. Ownership-only `resume` may hand off unresolved intents without releasing them or changing their original identities; the new verified owner can then resolve them. Unresolved intents block other activation modes and new entries. Do not automatically flatten exposure merely to change a goal/policy: use existing approved exits or obtain applicable closure authority.

Failed activation does not discard the old loop. Accepted financial evidence can still update its latches/lifecycle even when other activation requirements fail. A goal/policy supersession is an approved transition, not fabricated target completion. Never insert optional defaults into an existing stored mandate to manufacture a changed approval.

### Agent Session Control

The user-controlled task is separate from the financial `loop`. Only register it for an actual ongoing start instruction; a legacy missing record, migration, copied receipt or read-only request does not create indefinite authority. Reuse an existing active record rather than starting it every candle. Initial `session start` follows activation/emergency handling and precedes the first fresh `cycle`.

The `session` request accepts exactly `owner_id`, `expected_revision`, `action`, `evidence_ref` and `reason`. `evidence_ref` is a real nonsecret opaque reference using the journal reference rule (at most 200 characters); `reason` is nonblank plain text of at most 500 characters. No `snapshot`, money, mandate, account override or fabricated approval is accepted. It requires an existing activated policy and goal and the current single writer/revision.

Phrases such as `session stop` mean command `session` with JSON `"action": "stop"`, not an additional positional CLI subcommand. Use `python scripts/account_check.py session --input <private-request.json>` or the documented JSON stdin form.

| `action` | Contract |
| --- | --- |
| `start` | From absent or `stopped` control, create a new session ID under a genuine ongoing user instruction. After a user stop it must be a genuinely new request, not an automatic wake/reconnect. Consumed session/control references and authority recorded at earlier stops cannot be reused; changing a string is not new user authority. |
| `resume` | Only from `interrupted`, after real capability, account, ownership and existing-authority recovery, with a new actual recovery-evidence reference. Keep the session ID, original request and start time. Old stop/request/recovery receipts cannot authorize this transition. No new user confirmation is needed when original authority remains applicable. |
| `stop` | Record explicit user end/revocation, including a durable stopped record for a legacy mandate with no prior session control. An unknown legacy start time/request stays null. Cancel actual queued client continuations as well; a SQLite write cannot cancel the host itself. |
| `interrupt` | Only from active control, for a real unavoidable runtime/permission limit leaving no permitted continuation. Never substitute this for a user stop, no-trade result, quiet market, scheduled wait or recoverable read retry. |

`state.session` contains `id`, `status` (`active`, `stopped`, `interrupted`), `started_at`, `updated_at`, original `request_ref`, latest `evidence_ref` and `reason`. `active` means continuation was requested, not that a process is alive. Successful control returns `decision: "session_saved"`, `may_dispatch: false`, the updated `session`, `loop`, derived `loop_health`, `may_continue`, policy/goal IDs and new revision. It saves a `session` event but preserves snapshots, observation health, metrics, `last_result`, all financial anchors/latches, and every intent/outcome. Consume its revision and current control; historical `last_result.may_continue` may predate a stop and cannot override it.

All new control transitions need their own actual evidence, not a replayed start, stop, interruption or recovery reference. Repeating the current stop with its same reference is harmless and leaves it stopped. Control timestamps retain actual local wall-clock readings; if that clock moves backward, revisions/audit order still order the controls. Do not fabricate monotonic times or make a successfully recorded stop unreadable because its timestamp precedes its recorded start. Financial source-time and freshness checks remain unchanged.

Stopping/interruption clears planned loop deadlines and blocks `cycle` advancement and new entry/routine-management preparations. Checks may still record a requested bounded observation; resolutions and separately still-authorized safety reductions remain possible, never permission to ignore user revocation. Activation, owner handoff, reauthorization, new goal and policy replacement cannot remove a stop as a side effect. Start/resume with an existing loop requests an immediate `session_check` wake, not a new observation, candle or trading permission.

A user stop after `prepare` invalidates unused routine dispatch permission. Do not send it after a wait/restart or manufacture terminal `not_executed` evidence just because the session stopped. Retain the exact intent and reconcile actual broker/in-flight outcomes. Local control cannot fence an already-sent request or a manual actor. If host cancellation prevents recording the stop/interruption, report only what actually persisted; the real user stop still applies and must be reconciled before any later work.

### Loop Input And Results

These optional `cycle` fields describe actual MCP evidence, not additional user settings:

| Field | Exact Contract |
| --- | --- |
| `timeframe` | Must match the approved `entry_timeframe`, using M15 only when that mandate field is absent. No caller override. |
| `buffer_seconds` | Integer settle buffer from 3 through 5 seconds; default 5. |
| `market_state` | `open`, `closed` or `unknown`; default `unknown`. `closed` asserts all approved and held/pending-exposure symbols are verifiably closed. One closed reference symbol or a missing bar is insufficient. |
| `clock` | Optional object with approved `symbol`, actual `source_ref`, fresh UTC `as_of`, `last_boundary_at`, `next_boundary_at`. Require `last_boundary_at <= as_of < next_boundary_at`, `as_of <= snapshot.as_of`, and `next_boundary_at` still ahead of current receipt time; expired boundaries need refresh, not extrapolation. Use documented broker timezone/DST/calendar semantics, not host-clock UTC alignment. |
| `bar` | Optional object with approved `symbol`, actual `source_ref`, UTC `open_time`, `close_time` and boolean `confirmed`. Valid confirmed closed-bar progress requires the same symbol as coherent clock evidence, `close_time == clock.last_boundary_at` and a snapshot at/after boundary plus buffer. Open precedes close; both times must be strictly newer than that symbol/timeframe's prior confirmed high-water mark. |

The helper validates assertions, not their real MCP provenance or broker calendar. Missing/invalid clock evidence is a scheduling blocker; missing/legacy incomplete, repeated, unconfirmed, in-progress, conflicting or regressing bar evidence creates no new candle progress. Confirmation/advancement flags reset on each `cycle` request; another command can return the saved last-cycle fields, never new candle progress or entry permission. Track each approved symbol/timeframe separately, never one global bar for the universe. Valid fresh financial observations still check limits and count unique cycles despite absent/invalid timing; unknown accounting cannot do so. Such errors do not undo accepted money/latches or delay authorized reductions.

`cycles` counts accepted unique `cycle` observations while work remains, not bars or trades. A fresh no-bar observation can count but cannot authorize a candle-based entry. Exact snapshot replays, rejected accounting cores, failed MCP reads, ordinary `check` and refreshes merely reconfirming a closed session neither increment it nor refresh its cycle timestamp. Legitimate reuse of an accepted snapshot by other helper commands is not a new observation. Legacy counts are retained, not rewritten as hypothetical corrected history.

Relevant observations/intent resolution synchronize the financial lifecycle using the final outstanding-intent count, including `check`, `cycle`, `prepare`, activation and `resolve`, without making those commands start a loop or count a cycle. With a user-controlled session, `may_continue` reflects its control: true while active, including financial `closed` stopped-monitoring work, and false after explicit stop/interruption. Without a session record, live results retain the legacy until-settlement behavior; cached projections reflect saved lifecycle only, never a fresh closure verification or expanded authority. Inspect current control, `required_action`, latches and `closure_verified` to select the next work. Stale/invalid requests cannot certify closure from cached state. `required_action: "none"`, `may_dispatch: false`, a financial `closed` record or a journal acknowledgement cannot end an active user-controlled session. Only fresh successful `prepare.may_dispatch` authorizes its exact action.

| Loop Field | Meaning |
| --- | --- |
| `id`, `status`, `cycles`, `timeframe` | Financial campaign identity; `active`, `closing` or `closed`; unique observation count; approved cadence. Separate from `state.session` control and actual execution. |
| `policy_id`, `goal_id`, `binding_verified_at` | Current verified financial binding and when it was established; legacy historical association is not guessed. |
| `last_cycle_at`, `gap_seconds`, `max_gap_seconds` | Local cycle time and cycle-call spacing, **not account-observation gaps**. Other observation commands can check limits between cycles. |
| `next_cycle_at` | Verified candle deadline including settle buffer, or unavailable when timing cannot be established. Do not skip an unprocessed boundary within its settling window. |
| `next_latch_check_at` | Positive approved tripwire due from the last genuinely accepted observation's receipt time; no additional periodic deadline for zero/absent interval. |
| `next_wake_at`, `wake_reason` | Earliest applicable work; reasons are `candle`, `bar_retry`, `clock_refresh`, `market_closed`, `latch_check`, `closure`, `monitor` or `session_check`. A stored deadline is not proof of scheduling/execution. |

Missing/unconfirmed due bars or timing needing refresh use about 15-second data retries. After two distinct missed verified boundaries with the whole relevant universe verifiably closed, use about five-minute market polling, still subject to an earlier risk check. Count a missed boundary once, not each retry. Accepted `check`/`prepare`/`resolve` observations refresh risk deadlines without candle progress; closure work takes priority over entry timing. Use the [canonical wait/read workflow](loop.md#cadence-and-candle-evidence).

Financial `closed` requires a monetary latch, fresh verified flat/no-pending exposure, settled intents and final costs. Repeated observations retain identity, counters, bar history and `ended_at`. With active session control, use account-only `check` at the `monitor` wake: last accepted observation receipt plus 300 seconds, or the smaller positive `latch_check_seconds`. Zero/absence does not add a trading-phase tripwire; stopped monitoring is a separate no-new-risk duty. Exact replays/journals do not postpone that wake. Closed legacy loops without active session control have no planned wake; stopped/interrupted control suppresses all loop deadlines. Fresh late exposure returns the same financial loop to `closing`, retains both latches, clears current `ended_at` and keeps prior closure in audit history. Campaign settlement never starts a new goal/policy or ends an active user-controlled task.

### Observation Health

`state.observation` records `snapshot_id`, source `as_of`, local `received_at`, `gap_seconds`, `max_gap_seconds` and `max_gap_at` for genuinely newer accepted live account observations across observation commands. Its gaps measure **source `as_of` spacing**, and `max_gap_at` is the later source timestamp of that maximum gap. Receipt time is separate and drives latch/monitor scheduling. Reviewed historical baselines, exact snapshot replays, failed reads, session-control events and journal writes do not refresh this telemetry.

Read-only `loop_health(state, now)` derives the top-level `loop_health` on loop results and cached `status`/`context`/`journal` continuation views without changing observation/deadline state or observing equity. Read-time ages can increase without a new observation:

| Health Field | Meaning |
| --- | --- |
| `last_observation_at`, `last_observation_received_at` | Last accepted source and local receipt times; legacy source may come from the cached snapshot while unknown receipt stays unavailable. |
| `observation_age_seconds` | Age of the accepted source at the current read, not time since a journal or page refresh. |
| `observation_gap_seconds`, `max_observation_gap_seconds`, `max_observation_gap_at` | Source-to-source account-observation spacing and the source time ending its maximum gap, not cycle spacing or a proven outage duration. |
| `wake_overdue_seconds` | Derived overdue time for the stored planned wake; not evidence that a wait ran or a client crashed. |
| `execution` | Always `unverified`; cached lifecycle/telemetry cannot certify client liveness, broker connection, approval or execution. |

Unavailable legacy evidence stays unavailable; never turn old maximum cycle spacing into an account gap or reconstruct unseen peaks. An abrupt exit cannot write its own interruption event. Health is display evidence, never a new trigger, dispatch grant, authority or proof of continuous protection.

### Action And Outcome

Every `action` includes string `id` (unique durable action/correlation ID), `kind` (`entry` or `reduce`), actual MCP `tool`, exact nonempty `parameters` object, `authority_ref`, current `policy_id` and `goal_id`, and `tool_permission: true` only when actually available. Use the real schema rather than invented universal order fields. MCP parameter numbers remain JSON numbers, not monetary strings; numbers that cannot round-trip through the tool's ordinary JSON-number representation are rejected, not rounded. Accounting remains decimal. No credentials in parameters/records; recognized credential keys are rejected rather than journaled.

An `entry` also supplies the approved `symbol`, unique `signal_id`, nonempty `analysis_ref` identifying the market read that justified it, positive proposed stressed `risk`, nonnegative required `margin`, required `context` below, and true verified attestations `broker_checks_passed` and `protective_stop_in_request`. These checks also apply to risk-increasing modifications, not just new market orders. The helper compares money/scope and records a local reservation; the agent must independently verify the facts behind every attestation.

A `reduce` supplies `reason` (`management`, `protection_failure`, `loss`, or `target`), nonempty unique `tickets` from current exposure, and `reduction_verified: true`. `loss`/`target` require the corresponding observed latch. The agent must verify actual authority, original management rules, remaining volume and documented reducing semantics; an opposite entry is not necessarily a close. Never widen a stop, remove a still-needed protective order, alter manual exposure under an ordinary position-management claim, or treat a risk increase as a reduction. Safety reductions remain eligible during no-entry states; overlapping unresolved reductions on the same tickets are blocked.

After a successful preparation, send the exact recorded action through MCP and then resolve it:

- `outcome: "completed"` means the broker request is authoritatively settled and its result/remaining exposure/protection are verified. It can include an accepted pending order or a terminal partial fill; it does not mean the account is flat. Supply actual `broker_tickets` and genuine post-dispatch readback. Its snapshot must be later than both the preparation's source observation and its local `created_at`, not merely newer than an older pre-dispatch quote.
- `outcome: "not_executed"` needs authoritative terminal nonexecution evidence and later verified readback. An empty order list, timeout or failed connection is insufficient. Do not invent a rejection to release a reservation.
- `outcome: "unknown"` retains the original intent and reservation. Store available response/status evidence and reconcile through MCP. `status.outstanding_intents` exposes original action, status and available outcome/evidence for recovery. Do not resubmit the same action with a replacement ID.

Distinct action IDs are never reused, including after rejection. A repeated symbol/signal within a goal is also rejected. Local status must not be interpreted as server-side deduplication or exactly-once execution. Invalid/stale data or a failed `prepare` cannot authorize a pending order later.

### Decision Context

`action.context` is local, independently versioned metadata, never an MCP parameter. Successful `prepare` saves valid context with the normalized action in the existing `intents.payload` transaction before returning dispatch permission, so recovery does not depend on a later journal. It is required for new risk increases and newly prepared `reason: "management"` reductions; the emergency exception is below. Record concise factual conclusions and nonsecret evidence references, not private chain-of-thought, credentials or invented provenance.

| Context Field | Exact Contract |
| --- | --- |
| `version` | Required integer `1`, independent of SQL schema and display/API versions. |
| `operation` | Required `entry`, `add`, `breakeven`, `trail`, `close` or `cancel`. `kind: "entry"` accepts only `entry`/`add`; `kind: "reduce"` accepts only the other four. |
| `rationale` | Required nonblank plain text, at most 2000 characters, explaining this proposed action. |
| `source_refs` | Required nonempty array of at most 64 distinct opaque references, each at most 200 characters under the journal reference rule. |
| `origin_intent_id` | Optional/null nonblank plain-text intent ID, at most 200 characters. Omission normalizes to null. The original entry has no origin; follow-up actions use its ID, not an intervening add or matching symbol. |
| `strategy` | Required exact object below for operation `entry`; omit or supply null for every follow-up operation. A replacement strategy on a follow-up is rejected. |

The whole helper-encoded context is limited to 131072 bytes. Unknown context/strategy fields invalidate context; the emergency exception does not accept or persist them. Plain text uses the same nonblank/control-character validation as journal text; `source_refs` match `[A-Za-z0-9][A-Za-z0-9_.:#@-]*`, not URLs or file paths. `origin_intent_id` is a text identifier, not constrained to that reference pattern. An action carrying valid context also needs a nonblank plain-text `action.id` of at most 200 characters so it remains recoverable through linked records.

The original `strategy` has exactly these fields; none may be missing:

| Strategy Field | Exact Contract |
| --- | --- |
| `name`, `thesis`, `invalidation` | Nonblank plain text of at most 120, 2000 and 1000 characters respectively. |
| `side` | `buy` or `sell`. |
| `timeframe` | One of helper `PERIODS`: M1, M2, M3, M4, M5, M6, M10, M12, M15, M20, M30, H1, H2, H3, H4, H6, H8, H12, D1, W1, MN1. At preparation it must match mandate `entry_timeframe` (M15 if absent). |
| `expiry_rule`, `breakeven_rule`, `trailing_rule`, `addition_rule` | Each is nonblank plain text of at most 1000 characters or literal `false` for an explicitly disabled rule. Null, omission and `true` are not rules; missing legacy evidence is unavailable, not disabled. |

Initial `entry` requires null origin and the full strategy. `add`, `breakeven` and `trail` require the root original entry ID. Every new `reason: "management"` reduction also requires context with that root, including `close`/`cancel`. Emergency `close`/`cancel` context may omit the root for whole-account/manual work. To retain a supplied origin, `prepare` requires an existing `completed` originating entry with matching recorded ID and valid original context under the same account, policy and goal; an add must also use its symbol. Verified owner handoff preserves the original record rather than rewriting its owner. A completed entry can still be an unfilled pending order, so this link check does not establish profitable/protected earlier legs, ownership or permission to add.

Existing legacy intents remain readable and resolvable without new metadata, but missing plans cannot serve as roots for new additions or routine-management preparations. Do not backfill/adopt them automatically or relabel routine management as an emergency. Context cannot replace market analysis, enforce all protect-first economics or change risk arithmetic. The original entry's plan and `action.risk` allocation remain fixed; later reasons belong to new action records or linked journal assessments.

For `reason: "loss"`, `"target"` or `"protection_failure"` reductions, context may be absent. If supplied context or its origin fails validation, the helper omits the entire context, retains only a private generated `intent.context_warning` error code, and adds `action_context_unavailable` to a successful preparation's `reason_codes`. No raw failed metadata is retained or dispatched. This output warning is not another request field or an exemption from account/authority, freshness, tool, ticket, overlap and actual reduction checks. Metadata failure alone must not delay otherwise authorized protection; helper/database failure likewise must not delay previously authorized, identity-verified emergency reductions.

### Context Recovery

Read saved current-account/policy/goal context without observing, creating or upgrading state:

```text
python scripts/account_check.py context [--before <positive-rowid>] [--limit <1..100>] [--origin-intent-id <id>] [--db <path>]
```

This read command uses CLI options, not JSON stdin or `--input`. Python callers may use `checker.run("context", {"before": cursor, "limit": 20, "origin_intent_id": root_id}, db_path=...)`, omitting unused options. These are the only request fields: no `owner_id`, `expected_revision` or account override. Default limit is 20; `before` is a positive integer SQLite rowid cursor no greater than 9223372036854775807. Use returned cursors, not timestamps or action IDs. The helper uses scoped parameterized SQLite JSON queries inside `mode=ro`/`BEGIN`; absent state is unconfigured with an empty page, never a new ledger.

The response includes `revision`, canonical `account`/`policy_id`/`goal_id`, the cached continuation view and `context: {items, next_cursor, origin}`. Each item has `intent`, `latest_action` and `latest_journal`. `intent`, `latest_action` and non-null `origin` use `{id, action, status, outcome}`: **`action` is the full private stored payload**, including exact MCP parameters and references; `outcome` is the saved outcome or null. `latest_journal` is the raw matched report or null. Like `status`, this CLI/Python response is private, not the dashboard's separately allowlisted API.

By default, `origin` is null and `items` pages originating entries newest-rowid first, including completed and legacy entries without plans. Each root's `latest_action` is its newest recorded root/related action, and `latest_journal` is the latest journal explicitly linked to one of those intents, even after unrelated wait notes replace `state.last_journal`. With `origin_intent_id`, `origin` returns that current-scope root and `items` pages the root plus related actions; each item's `latest_action` is then that same intent and its journal is matched only to that intent. An unknown/out-of-scope root in an activated campaign is rejected. `next_cursor` is null when no older page remains. Saved strategy, status and assessment records establish neither current exposure nor fresh market evidence; recover actual broker outcomes before management or new risk.

### Journal Reports

`journal` requires an existing activated policy and goal, including stopped, closure-pending, closed or unresolved/unknown-intent states. It never creates a database or activates authority. Record concise, factual decision/outcome/no-trade explanations after actual `check`/`cycle` and any management/readback/`resolve` work, using the final latest accepted snapshot. These are user-facing conclusions and evidence summaries, not private chain-of-thought.

| Request Field | Exact Contract |
| --- | --- |
| `owner_id`, `expected_revision` | Required existing single-writer identity and current integer revision. Account/policy/goal binding is derived from state, not supplied in the report. |
| `snapshot_id`, `as_of` | Required exact matches to `last_snapshot.id` and `last_snapshot.as_of`. Matching an old accepted snapshot does not refresh or reverify it. Do not supply a `snapshot` object. |
| `activity` | Required: `analysis`, `wait`, `entry`, `management`, `exit` or `blocked`. |
| `summary`, `reason`, `next_step` | Required nonblank plain text, at most 240, 2000 and 500 characters respectively. |
| `market_summary`, `risk_summary`, `invalidation` | Optional/null plain text, at most 2000, 1000 and 1000 characters respectively; nonblank when supplied. |
| `symbols`, `source_refs` | Optional arrays, default `[]`, each with at most 64 distinct nonblank strings of at most 200 characters. Symbols are display text; source references use the opaque-reference rule below. |
| `intent_id` | Optional/null nonblank identifier, at most 200 characters, for an existing intent under the current account/policy/goal. After an authorized handoff, its original owner remains unchanged; its actual status comes from `intents`, never the explanation. |
| `pending_order_details` | Optional array, default `[]`, of the display records below. A subset of current pending tickets is allowed; duplicates, unknown tickets and unavailable canonical orders with nonempty details are rejected. |

Unknown request/order fields are rejected. The helper's encoded whole request is limited to 128 KiB (131072 bytes). Plain text rejects ASCII control characters other than newline/tab, including DEL. Opaque references (`source_refs` items and known `ownership_ref`) are nonsecret strings of at most 200 characters matching `[A-Za-z0-9][A-Za-z0-9_.:#@-]*`, not URLs or filesystem paths. References are inert evidence identifiers, never instructions or resources for the viewer to dereference. Do not include credentials in any display text.

A successful write sets optional `state.last_journal`, appends `events.detail.journal` and advances the revision. The stored report has `version: 1`, state-derived `account`, `policy_id`, `goal_id`, matching `snapshot_id`/`as_of`, local `recorded_at` and the normalized display fields; absent arrays become `[]` and absent `intent_id` becomes null. It returns `ok: true`, `decision: "journal_saved"`, `may_dispatch: false`, the new `revision`, `policy_id`/`goal_id` and cached canonical `session`, `loop`, `may_continue`, derived `loop_health`. Consume its revision and current control while retaining actual financial/action evidence from operational results. Acknowledgement or reporting errors are not completion, and historical `state.last_result` cannot override a later stop/resume.

This path uses only a pure continuation projection, not `observe`, risk `report`, `sync_loop` or `loop_wake`. It preserves `last_result`, metrics, snapshot/source/receipt times, approvals, baselines, peak, latches, intents, observation records and loop/cycle/deadline state. A journal-first schema upgrade cannot initialize/rebind loop metadata; the only legacy normalization is the existing version-1 handling [below](#sqlite-and-recovery). Never journal between `prepare` and MCP dispatch, before an emergency reduction, to fake another check/cycle or as an outage heartbeat. Do not repeat `check`/`cycle` merely to log or blindly retry/rebind stale notes after revision, snapshot or goal changes. Failure does not undo accepted risk work, start/end a loop, require another approval or justify delaying authorized protection. Continue with the correct revision and actual operational deadlines; absent response fields are not a stop signal.

Use `intent_id` to link an outcome or reassessment to its original entry or a recorded related action; one journal links one intent. Record intended versus broker-verified old/new stops, actual cancellation/closure/addition results, partial/unknown outcomes and remaining work in the existing text fields, not invented extra fields. Explain unchanged valid orders and no-entry decisions too. A submitted action is not a verified fill, improved protection or flat exposure. Linked reports supplement, never replace, the original pre-dispatch plan.

### Pending Order Display Fields

Only `ticket` is required in each `pending_order_details` item. Details bind to that exact pending-order ticket in the report's current account/policy/goal/snapshot, never to a position with the same ticket.

| Field | Exact Contract |
| --- | --- |
| `ticket` | Nonblank string of at most 200 characters, preserving leading zeros; must match a current `last_snapshot.pending_orders` ticket. |
| `order_type`, `side` | Optional/null; `order_type` is nonblank text of at most 64 characters, `side` is `buy` or `sell`. |
| `volume_unit` | If supplied, only `lots`; defaults to `lots`, not account-currency money. |
| `volume_initial`, `volume_remaining` | Optional/null exact nonnegative decimal strings. When both are known, remaining must not exceed initial. |
| `entry_price`, `stop_limit_price`, `stop_loss`, `take_profit` | Optional/null exact decimal strings in the instrument's price units, not account-currency money. Prices may be signed; all number strings retain the helper's finite/precision/magnitude limits. JSON numbers are not accepted for these price or volume fields. |
| `placed_at`, `expires_at` | Optional/null ISO-8601 UTC strings ending in `Z`. Placement must be at or before the matched snapshot's `as_of`; expiry may be later. |
| `ownership`, `ownership_ref` | Ownership is `ace`, `manual`, `mixed` or `unknown` (default). A non-unknown classification requires an opaque `ownership_ref` backed by actual evidence; the reference is not retained for `unknown`. |
| `unset_fields` | Optional distinct array drawn only from `stop_limit_price`, `stop_loss`, `take_profit`, `expires_at`. Each corresponding normalized value must be null (omission normalizes to null). |

For nullable fields, omission/null means unknown unless explicitly named in `unset_fields` as verified absent. Missing enrichment remains unavailable. These fields stay outside core risk snapshot normalization/equality checks: they cannot override canonical symbol, entry/protective `kind`, protection, stressed risk or account binding. A matching ticket, explanation or ownership label is not independent verified ownership, approval or execution evidence, especially for mixed netting exposure. Include actual manual and protective pending orders; do not invent rows for attached native SL/TP or local prepared/unknown intentions. Only a verified empty canonical order array means no pending orders.

### Display Events

New ordinary helper events carry an allowlisted `detail.display` envelope with `version: 1`. Successful activation and `check`, `cycle`, `prepare`, `resolve` observations use the finalized command result, including post-resolution closure metrics. An accepted accounting observation may still block exposure or have individual unavailable metrics. Events without accepted result metrics, including drafts, session controls or rejected observations, have null `snapshot_id`, `as_of` and `metrics`; they never copy last-good metrics into a new saved target observation. A `journal` event is a report, not an observation. Session events expose only control ID/status/times/reason with execution unverified; they create neither financial progress points nor failed-read markers and do not expose request/evidence/authority references or previous-state payloads.

The envelope contains `account`, `policy_id`, `goal_id`, `snapshot_id`, source `as_of`, local `recorded_at`, `metrics`, `decision`, `reason_codes`, `loss_latched_at`, `target_latched_at`, `closure_verified`, `required_action` and `intent_id` (or null). Its metric allowlist is:

- `budget`, `target`, `balance`, `equity`, `peak`, `drawdown`, `remaining_risk`, `adjusted_stop_floor`, `account_stop_floor`.
- `policy_cashflows`, `goal_cashflows`, `estimated_goal_gain`, `progress_pct`, `remaining_target`, `remaining_close_costs`.
- `existing_risk`, `free_margin`, `final_net`, `final_shortfall`.

Values come from the finalized result, not display prose or browser input. There is no historical `may_dispatch` permission in this envelope. Factual helper/intent events remain available even without an explanation; a completed intent means a settled request, not necessarily a fill or verified flat exposure.

The [local dashboard](../README.md#local-dashboard) is a separate read-only projection, using these saved results for the current goal only and deduplicating by account/policy/goal and snapshot identity/time. Do not backfill events, reconstruct unseen peaks or invent continuous performance. An older current checkpoint has at most one timestamped cached observation; missing history/prose is unavailable. Browser refresh, journal `recorded_at` and an active loop record do not refresh source `as_of`, establish MCP connectivity or promise a running guard. Optional unsupported/malformed display metadata is unavailable, not a reason to repair canonical state or treat the prose as authority.

## SQLite And Recovery

`ace_state.sqlite3` is the sole local account checkpoint. Its sidecars/backups are private and Git-ignored. Root `risk_management.csv` and `risk_management.csv.*` records are retired and discarded without import: do not create, detect, read, migrate, depend on, or ask about them in future onboarding.

The helper uses `PRAGMA user_version = 5` and the same three tables: singleton `state` (`id`, `revision`, JSON `payload`), append-only `events` (`id`, `at`, `command`, JSON `detail`, `state_sha256`), and `intents` (`id`, unique `signal_key`, `status`, JSON `payload`, JSON `outcome`). It uses parameterized SQL and `BEGIN IMMEDIATE` for local check/reserve/write serialization. A state/audit digest detects mismatched local edits, not authentic human approval or malicious modification of the whole database.

SQL versions 1, 2, 3, 4 and 5 are explicitly readable. Preserve version-1 missing-`loop` normalization to `null`; no loader initializes/rebinds a loop or creates agent-session authority. The next successful authorized write upgrades atomically to version 5, preserving approvals, drafts, IDs, financial anchors, peak, both latches, every intent/outcome, `last_journal` and all display/report history. Absent session/approval-mode/context fields stay absent on reads and journal-first upgrades: no authority expansion or invented strategy backfill. Malformed present session control fails closed, not back to legacy behavior. Read-only `status`, `context` and dashboard reads never upgrade. Journal/display/API envelopes remain version 1; action context has its own version 1. No new tables or historical plan reconstruction. A journal-first upgrade preserves existing loop fields exactly and defers operational metadata recovery.

An unbound legacy loop's historical policy/goal association is unverified, not inferred from current state. Preserve its original metadata in the migration/activation audit. Verified unchanged `activate resume` binds it prospectively, records `binding_verified_at` and retains its ID/counters/history, using real existing authority rather than another routine human approval. Normalize an old unapproved request-timeframe override to the already-approved cadence and reset only affected timing/bar tracking, not financial history. Block new risk until reconciled, not already-authorized safely targeted reductions. Known approved goal/policy replacements follow the explicit transitions above.

Deploy the helper and reader/viewer together before a version-5 write; older writers must reject the upgraded schema rather than omit/drop required entry/management context or downgrade it. Follow the [loaded-build compatibility contract](../README.md#local-dashboard): increment the corresponding embedded `READER_BUILD`/`VIEWER_BUILD` for behavior changes even at the same schema. Database-free health freezes loaded identity/capability at server construction; on-disk `VERSION` is not loaded-code evidence, and health does not prove checkpoint readability/freshness or broker/agent execution.

Repository maintenance never migrates production state. An explicit viewer-repair request permits only an identity-verified viewer restart after a successful current-reader read-only check, through its original owning client's verified, permitted tracked process controls on the same workspace/checkpoint/port. No auto-kill, hot reload, alternate port/checkpoint, HTTP shutdown, state repair or trading/continuation interruption. Without those controls, leave the service untouched and report dashboard-only recovery as blocked; continue otherwise permitted work and protection without extra trading approval.

State retains account/owner binding; pending drafts; policy/goal IDs and immutable approval/baseline/flow references; the full mandate; observed peak; independent loss/target latch timestamps; last snapshot, calculations and result; original history boundary/cursor; loop, observation and optional session-control metadata; and optional latest display report. Events preserve replaced mandates/loops, session controls, observations and reports; intents preserve exact action parameters, original strategy/allocation, linked action reasons and uncertain outcomes. Never edit SQL/JSON to manufacture authority, backfill a plan or clear a latch, user stop, reservation or peak.

Import, help, tests and absent `status`/`context` reads do not create a production database. Only an explicit valid `draft` initializes a new checkpoint; `activate` needs that draft. Missing, corrupt, unsupported, busy or unreliable state blocks new risk, not an assumed zero exposure or a reset policy. Keep last source timestamps; read-only recovery is cached, not current account verification.

On authorized reconnection, read `status` and current canonical session control, recover original/related records through `context`, verify approval provenance and single-writer ownership, get actual MCP account/exposure/history, and reconcile every outstanding intent before risk increases. Read-only lookup does not change original owner identities after handoff or turn old strategies into current signals. Use one fresh read after a long gap, not replayed missed candles or reconstructed unseen peaks/midnight history. Unchanged resume retains the loop ID and actual authority; never resume against an explicit user stop or expand a bounded task. Preserve same-policy peaks and both stop latches across reconnects, recovery, new days, corrections and drafts. Unknown costs/history or missing real approval is unavailable, not permission.

## Synthetic Checks

These are arithmetic fixtures, never settings, approvals or real account facts. Automated tests are in [`tests/test_account_check.py`](../tests/test_account_check.py); run `python -m unittest discover -s tests -v` with isolated temporary databases and no MCP. `ACE_TEST_TMPDIR` may select a permitted temporary parent.

| Fixture | Expected Result |
| --- | --- |
| Budget `5`, start equity `100`; observe `110`, then `108` | Peak `110`, stop floor `105`, remaining risk `3`. At `105`, latch the loss stop. |
| Remaining risk `3`, existing risk `1`, proposal `1.5`, extra buffer `0.5` | Reject equality; no trade-count reset or alternative budget. |
| Equity `300` after an external deposit `200` from a `100` start | Adjusted equity `100`, no artificial profit/peak. Repeated full ledger reads count the deposit once. |
| Target `15`, start equity `100`, current equity `115`, remaining close costs `0.5` | Estimated gain `14.5`, not yet reached. At equity `115.5`, trigger cancellation/closure. |
| Target triggered, later verified flat net gain `14.7` | Remain stopped; report final shortfall `0.3`, not an automatic recovery trade. |
| Eligible approved signal, fresh verified inputs, affordable proposal, complete context and MCP permission | `prepare` records exact parameters plus separate strategy/rationale before permitting dispatch; a later qualifying trade needs no separate account reapproval. |
| Restart after preparation before any journal, or recover a completed origin after later wait notes | `status` retains unresolved requests; bounded `context` recovers original plan/allocation and linked actions/reports, without assuming execution or generating a new action ID. |
| Journal/status/context after session stop/resume with older `last_result` | Canonical control wins; cached projection moves no observations/deadlines and journal alone consumes its normal revision. Missing/error fields never imply completion. |
| Read SQL versions 1-5, including legacy missing plans | No read-time write/backfill; the next authorized write upgrades to 5 with anchors/latches/stops/intents intact. Resolve old intents normally; new adds/management cannot invent a legacy root plan. |

### Management Scenarios

These are synthetic agent-workflow checks, not real account settings or automated broker tests. The existing Python tests verify the local contract, not independent enforcement of market-management judgments.

| Scenario | Expected Action |
| --- | --- |
| Confirmed long higher low permits a higher SL, or short lower high permits a lower SL; all broker constraints pass | Prepare the authorized improvement with `trail`/`breakeven` rationale and root link, preserve TP/protection, verify the accepted stop and resolve; never widen on a later candle. |
| SL equals entry price but attributable charges remain | Do not call it net breakeven; use verified cost-aware economics, without subtracting booked costs from account equity again. |
| Candidate SL violates stop/freeze distance or the broker rejects it | Retain/read back existing protection, report the blocker, and do not widen, claim success or fund an add from the proposed change. |
| Pending setup remains valid despite age or distance from price | Leave it unchanged unless its recorded expiry/other invalidation condition actually applies. |
| Recorded pending-entry invalidation is confirmed, or its recorded expiry is reached without a new bar | Cancel the Ace entry without inventing a candle, preserve protective orders and verify outcome; a loop-session new entry still needs its own confirmed candle and fresh setup. |
| Recorded open-position invalidation is confirmed before SL | Close under original management authority, reconcile remaining volume, and do not automatically reverse. |
| Cancellation times out or races a partial/late fill | Retain uncertainty, reconcile the original intent, resulting position and remainder, and block further additions until settled. |
| All earlier legs profitable and protected; idea limit `3`, related/all-account existing risk `1`, proposal `1`, safety margin `0.5`, remaining risk `3` | Both `2 <= 3` and `2.5 < 3` pass; a fresh continuation signal and successful `prepare` are still required. |
| One earlier leg is losing/unprotected, its breakeven move is unverified, or its original evidence is unavailable | No winner addition; aggregate profit or spare account headroom does not override the gate. |
| Original idea limit `3`, related existing risk already `3` | No positive add fits; a second signal, realized gain or reconnect cannot reset the original allocation. |
| Two independent ideas use one symbol, or an add points to another account/goal | Keep separate root intent IDs; reject mismatched root scope instead of merging ideas by symbol or replacing the original strategy. |
| Newly prepared routine management omits context or cannot recover a completed valid root | Block that discretionary preparation; reading/resolving legacy records remains supported without invented metadata. |
| Positions have breakeven stops, but existing give-back risk `2` + proposal `0.5` + safety margin `0.5` equals remaining risk `3` | Reject the account-wide equality; breakeven risk is not zero. |
| Netting position mixes Ace and manual exposure or an add would weaken aggregate SL | Skip routine modification/addition; do not invent isolated legs or manual-management authority. |
| Loss/target latch appears while trailing or an add is being considered | Whole-account cancellation/closure takes priority, including manual exposure; no new entry or automatic target-shortfall recovery. |
| Emergency reduction supplies unusable context or an invalid/legacy origin | Drop the context with private `context_warning` and `action_context_unavailable` on successful preparation, retaining every canonical safety check and exact MCP parameters. |
| Helper or legacy strategy metadata unavailable during an already-authorized, identity-verified emergency reduction | Do not delay protection for a plan/journal prerequisite or database repair; use safely targeted documented MCP reduction and reconcile the record when possible. |
