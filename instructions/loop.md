# Loop Sessions

An ordinary Ace trading-start request with complete budget and target starts one ongoing
user-controlled agent session under the [Execution Contract](../AGENTS.md#execution-contract).
The AI client, already connected to execution-enabled MT5 MCP, is the runtime. No final
account confirmation, per-action permission or separate "keep going" request is needed.
The helper records state; it does not wait, network, trade or schedule the next invocation.

**No voluntary termination:** while the session is active and execution remains possible,
perform the next actual action, supported wait or fresh read. The financial task remains
unfinished through observation, management and eligible entries until an observed budget/target
latch, then through verified cancellation, liquidation and reconciliation. No fills, unchanged
orders, no affordable setup, completed batches and saved journals are nonterminal outcomes.
Publish routine reports to the dashboard, not as task boundaries. Quiet/closed markets and transient failures
do not end the session; after financial settlement it continues stopped monitoring. Never
substitute "say continue", a choice menu, a future-monitoring promise or a voluntary time/cycle
cutoff. Yield only after registering actual native continuation when the host requires that
boundary, not as final completion.

## Authority And Execution

The real start instruction authorizes agent-selected eligible instruments and technical
settings, immediate looping, bounded recovery, risk-limited entries, Ace-owned management,
whole-account cancellation/closure at either monetary trigger and stopped monitoring after
settlement. This delegates task-scoped documented MT5 operations, not unrelated/admin access,
changed host permissions or a bypass of denied tools. Briefly disclose the binding and actual
host/observed-only limitations without another approval question. Record the actual request,
not an assistant-generated receipt. Reuse verifiable existing authority; never expand a bounded,
single-batch or target-ending mandate into an indefinite session.

Explicit connection-only, analysis-only, dashboard-only, progress-only, maintenance and
bounded one-shot requests do not start trading loops. Neither viewing state nor calling
`status`, `context`, `journal` or an ordinary one-shot `check` activates a loop or grants authority.
Material mandate changes, a new goal and a risk reset require actual explicit user instructions.
Defer optional out-of-scope actions and continue other permitted work.

Before new exposure, verify the client's documented ability to wait and continue the logical
task. Prefer its native persistent-task/goal facility and scheduled continuations when
available. The objective is to operate this user-controlled session until the user ends it,
including stopped observation after a monetary trigger, not merely to submit a batch or
reach a financial result. Do not mark the host objective complete when the campaign settles.
Use the actual available tool schemas, not assumed client-specific names or configuration.

Register the next native wake before yielding when the host requires a turn boundary.
On resumption, reconcile the existing session and pending intents; a scheduler message is
not new user authority or permission to undo a stop. Where the host instead supports
bounded, interruptible waits within the same task, use those and chunk long waits without
skipping a due risk check. A todo, stored deadline, active flag or promise is not scheduling
and cannot make an idle/terminated host resume. Do not busy-spin a goal, introduce a runner,
plugin or client configuration, bypass limits or wait on the dashboard
server as though its lifetime were the trading task. Report a genuinely missing capability
before orders, not after the first batch as a keep-going choice. A wait is not monitoring.

Follow [Automatic Dashboard](../AGENTS.md#automatic-dashboard) before entering or resuming
the loop where possible. Reuse the session-managed viewer, not a server per candle.
Do not wait for its long-running process or let startup suspend trading. Viewer failure
is a dashboard-only limitation, not a completion signal or reason to delay protection.

## Financial Session And Task

The persisted financial lifecycle is separate from current AI execution:

- **`active`**: the approved loop has unfinished observation/decision work without a stop.
- **`closing`**: a monetary latch requires cancellation, closure or reconciliation work.
- **`closed`**: a monetary latch and fresh verified flat positions, no pending orders,
  settled intents and final costs establish financial settlement, not agent-session completion.

The separate [session control](risk-management.md#agent-session-control) records continuation
as `active`, explicit user end as `stopped`, and a real runtime interruption as `interrupted`.
`active` is a request, not proof of liveness. A task may be executing, waiting or interrupted
while the financial campaign remains active, closing or closed. Stored `loop.status`, session
control, cached `status`, `loop_health` and dashboard refresh cannot prove MCP connectivity
or current execution; health reports `execution: "unverified"`.

With active user-session control, `may_continue` stays true even after verified financial
closure. Continue stopped-account checks, never new entries. Stop/interruption sets it false
and clears planned wakes. Legacy absent session control retains its previously authorized
until-settlement behavior; do not infer indefinite authority from a schema upgrade.
Inspect the latest canonical session control, `required_action`, latches and `closure_verified`
to choose the next work. `status`, `context` and successful `journal` return cached `session`,
`loop`, `may_continue` and derived `loop_health`; they neither observe nor move deadlines.
Historical `state.last_result` can predate stop/resume. `required_action: "none"`,
`cycle.may_dispatch: false`, a journal acknowledgement or a closed campaign does not end an
active user session; reporting errors or absent fields do not imply completion either.
Only fresh successful `prepare.may_dispatch` permits its exact mutation, and never after
an intervening user stop invalidates unused routine dispatch permission.

## Bootstrap

1. Retain the actual budget/target trading-start request. Reuse/verify MCP account identity,
   local ownership/state and actual wait/continuation capability. Resolve genuinely missing
   inputs, not an extra final confirmation. An existing user stop takes priority over an
   automatic continuation, reconnect or stored active financial loop.
2. Save the full monetary/technical mandate. Capture and activate fresh baseline/current
   snapshots under `approval_mode: "start_request"` and its real request timestamp, following
   the [activation contract](risk-management.md#mandate-and-activation). Handle an activation
   latch immediately; do not delay protection for reporting or task bookkeeping.
3. Register `session` with `action: "start"` and the real ongoing request evidence, reuse
   an existing active record, or resume a genuinely interrupted session after verified
   recovery. Only a new explicit user instruction permits start after user end. None of
   these actions resets money or creates trading authority.
4. Obtain a separate fresh snapshot and call `cycle` before normal management/entries,
   even if no signal qualifies. Then perform the duties below and the actual next wait/read.
   Do not repeat activation/session start every candle. Explicit bounded requests retain
   their narrower scope rather than using this bootstrap.

## Duties On Every Cycle

1. Read current account, positions, pending orders and history through documented MCP tools;
   build one coherent snapshot; call `cycle` (it performs the same observation and latch
   arithmetic as `check`, plus financial-loop bookkeeping). A latch-only or stopped-monitoring
   wake uses `check`, not a candle decision; coincident trading-phase wakes may use one fresh `cycle`.
2. Enforce monetary latches and previously authorized emergency reductions first. A latch
   invokes the whole-account cancellation/closure mandate, including manual exposure, ahead
   of ordinary trailing, pending-order review or new entries.
3. Apply [Active Order Management](risk-management.md#active-order-management) to existing Ace
   positions and every Ace pending entry. Review breakeven/trailing eligibility, original
   position invalidation and pending-entry validity, including orders far from entry triggers.
   Use confirmed closed candles for structural decisions, but check recorded expiry and
   current protection/session/economics conditions on fresh reads even without a new bar.
   Leave valid setups alone; cancel invalid ones rather than chasing price. Routine changes
   require original Ace ownership and authority; recover the original strategy/allocation and
   linked assessments through read-only `context`, including completed origins. Missing legacy
   plans remain unavailable, not backfilled or inferred from a matching symbol. Manual exposure
   still counts in the snapshot and risk but is not adopted for routine management.
4. Perform required management using fresh `prepare` -> the exact MCP call -> later readback
   -> `resolve` for every mutation. Newly prepared routine management requires rationale and
   validated root-entry linkage in [`action.context`](risk-management.md#decision-context),
   outside exact MCP parameters.
   Recalculate risk from verified outcomes before additions. Unknown outcomes block new risk,
   not separately authorized, safely targeted safety reductions; missing strategy metadata
   must not delay those reductions or make them wait for a candle or entry signal. Unusable
   optional emergency context is dropped with a warning under the same helper contract.
5. Once a new entry-timeframe candle for the affected symbol is confirmed and required
   management is reconciled, re-test prospective entry levels within a proximity band of their
   triggers. Consider fresh independent setups and protect-first winner additions only under
   the canonical management
   rules and a new successful `prepare` with complete entry/add context. Persist the original
   plan before dispatch; an add links the root intent without replacing its rules/allocation.
   Cancellation, a breakeven stop or spare headroom is not a signal; a missing bar or latch-only
   read does not permit entry.
6. After the actual cycle and any management/readback/`resolve` work, record a concise
   decision/outcome/no-trade explanation with [`journal`](risk-management.md#journal-reports),
   matching the final latest accepted snapshot and relevant intent. Consume its returned
   revision and cached canonical continuation view while retaining actual financial/action
   evidence separately. Its `may_dispatch: false` is not completion; it does not change source
   or receipt time, loop, deadlines or `last_result`. Do not repeat `cycle` just to log, insert
   reporting between preparation and dispatch or delay emergency protection. Summarize
   conclusions and intended versus verified outcomes, not private chain-of-thought.
7. Keep the dashboard report concise: decision, risk, latches, actual management results/blockers
   under [Outcome / Next](goals.md#compact-trading-report), and the next wake/reason. Do not
   emit a routine final chat response or ask for another decision. Full snapshots belong in
   SQLite, not in the conversation. Read bars needed for position/order management and nearby triggers, not
   the whole symbol universe every cycle; entry proximity must never exclude required management.
8. Actually wait until the earliest applicable wake from the final operational result, or
   read immediately when due. Then obtain fresh data and repeat. Later accepted observations
   from management/readback can update latch/monitor deadlines; journal merely returns the
   saved plan. Register native continuation when required by the host before yielding. Wait chunks
   do not need another report. Recheck cancellation before any previously prepared dispatch.
9. Never raise risk to manufacture activity. A quiet cycle is a valid continuing result.

## Cadence And Candle Evidence

Use the [exact loop contract](risk-management.md#loop-input-and-results), not guessed UTC
candle alignment. `entry_timeframe` comes only from the approved mandate; absent legacy
values mean M15. A supplied `timeframe` must match. Changing it needs reauthorization,
not a silent mid-session switch. Preserve absent/zero `latch_check_seconds`; do not enable
an unapproved faster tripwire. The settle buffer is 3-5 seconds, default 5.

Supply verified broker `clock` evidence: approved symbol, actual source reference/time and
last/next boundaries expressed as UTC instants using documented broker timezone, DST and
calendar semantics. The helper checks assertions, not MCP provenance. Missing/invalid or
outdated timing requires a bounded data retry, not an extrapolated deadline. It must not
suppress valid account observations, known latches or authorized safety work.
The next boundary must still be ahead of the current receipt time; a clock captured just
before a boundary cannot advance the superseded candle after that boundary.

Confirm actual closed bars with approved symbol, source reference, `open_time`, `close_time`
and `confirmed`. Both open and close must be strictly newer to advance that symbol/timeframe's
high-water mark; unrelated symbols are not interchangeable. Missing, repeated, unconfirmed,
still-open, conflicting or regressing bars and legacy metadata without that evidence do not permit a
new candle-driven entry. Each `cycle` request resets its confirmation/advancement flags.
Other commands can return the saved last-cycle fields, but never create new candle progress
or entry permission.

`cycles` counts accepted unique `cycle` observations while work remains, not candles or
trades. A fresh no-bar observation still checks limits and can count, without granting an
entry. Failed reads, rejected accounting cores, snapshot replays, ordinary `check` calls
and observations merely reconfirming a closed session do not advance it or refresh its
cycle timestamp. Do not replay missed candles after a gap; take one fresh read.

| Condition | Next Work |
| --- | --- |
| Verified unprocessed boundary, including its current settling window | Wake at that boundary plus buffer; do not skip it just because the boundary itself passed. |
| Due candle absent/unconfirmed or clock needs refresh | Retry market-data verification after about 15 seconds; do not invent candle progress. |
| Two distinct boundaries missed while all approved and held/pending-exposure symbols are verifiably closed | About five-minute market-data polling, subject to any earlier risk check. Count each verified missed boundary once, not each retry. |
| Positive approved `latch_check_seconds` | Account-only `check` from the last genuinely accepted observation's receipt time; zero/absent means no additional periodic tripwire. |
| Latch or unfinished closure | Prioritize authorized reconciliation/reduction, not the next entry candle. |
| Financially closed, user session active | Account-only `check` after 300 seconds or the smaller positive latch interval, measured from the last accepted receipt; no candle analysis or new entry. |
| Authorized session start/resume with an existing loop | `session_check` requests an immediate fresh observation; the control write did not itself observe or grant dispatch. |

`market_state` defaults to `unknown`. `closed` asserts verified closure of **all** approved
and held/pending-exposure instruments, not just one reference symbol. A missing bar alone
does not prove a market closure. `next_cycle_at` is the candle deadline; `next_latch_check_at`
is the risk-check deadline; `next_wake_at` and `wake_reason` describe the earliest applicable
work. These are plans, not proof that a wait was scheduled or executed. Refresh stale clock
evidence rather than inventing future boundaries, and never sleep past an earlier risk check.

## Failure And Resumption

- Retry transient MCP reads with actual waits of 5 s, 10 s, 20 s, then 30 s repeatedly while
  execution is possible; reset backoff after verified recovery. Authentication, permission
  and required-user-input blockers are not blind retries or permission-bypass opportunities.
- A failed MCP read makes no snapshot-based helper/journal call or financial observation and
  is not a cycle. A processed blocked helper request is different: it may be audited and
  consume a revision, even for a stale snapshot. Always consume the returned revision;
  after an unknown local outcome or revision conflict, read `status` before proceeding.
- Accepted financial evidence still updates money/latches when cycle bar/clock metadata
  is rejected. Do not undo a known breach or delay authorized reductions for timing repair.
- Never re-submit a previous observation as if it were new. Fabricating freshness would
  corrupt the trailing budget and the target baseline. Do not write `journal` entries as
  outage heartbeats or to fabricate activity while turns are not executing.
- Do not dispatch while account targeting/data is unverified or queue actions to fire on
  reconnect. Previously authorized, safely targeted emergency reductions retain priority.
  A mutation timeout is an unknown original intent, not a retryable read; reconcile it,
  never blindly resubmit or replace its identity.
- On resumption verify account identity, actual approval, single-writer ownership, original
  management evidence, latest canonical user-session control and broker outcomes/intents.
  Use `status` for unresolved intents and bounded `context` for completed roots, related actions
  and linked reports. A pre-dispatch plan survives without a later journal, but proves no broker
  outcome. Never backfill a missing plan or replace an uncertain action ID. An explicit stop
  cannot be overridden by cached `last_result.may_continue`, activation or a scheduled wake.
  Obtain fresh account/history/exposure data, then `cycle` (`check` for stopped monitoring,
  with verified `activate resume` when required by the
  [recovery contract](risk-management.md#sqlite-and-recovery)). Observe limits before new
  exposure. A breach may have occurred unseen; do not reconstruct its time or an unseen peak.
- Keep the same loop ID on unchanged resume/owner handoff. An unbound legacy loop needs
  verified existing-authority `activate resume` to bind prospectively, not another routine
  human approval. Block new risk until reconciled, not authorized emergency reductions.
- An approved symbol-universe change invalidates obsolete clock and all-universe closed-market
  evidence while retaining only eligible per-symbol high-water marks. Do not use removed-symbol
  timing or an earlier smaller universe to plan new work.
- Retain actual source/receipt timestamps and measured observation gaps. Report an outage
  start/cause only if supported by evidence; an abrupt exit cannot record its own interruption
  and a cached overdue wake is not proof of a crash.
- Record `session interrupt` only when no permitted continuation can actually execute.
  It is a task-control event, not a new account observation or an outage heartbeat. Resume
  only after real recovery and authority verification; an explicit user stop requires a
  new user-start instruction instead. Optional tool denial does not end other permitted work.

## End Conditions

Financial settlement requires one of these monetary latches and fresh verified closure:

- `loss_latch`: observed drawdown greater than or equal to the approved budget.
- `target_latch`: estimated net gain greater than or equal to the approved target.

A session never completes because the market is quiet, no order filled, no setup qualified,
an instrument is closed, a transient outage occurred or the agent ran out of work to describe.
When both latches apply, loss handling takes precedence.

At a latch the financial loop moves to `closing`: cancel all account pending entries, close all
positions including manual exposure, verify flat and reconciled, report the trigger
separately from the final net result and any shortfall, then mark that campaign `closed`.
Keep working while closure or costs/intents remain unresolved. After settlement keep the
user-controlled session active and perform account-only monitoring at the `monitor` wake.
Repeated closed observations preserve the same financial ID/history/counters and advance
only genuine observation evidence and its monitor deadline. Fresh late exposure returns
the same loop to `closing`, preserving latches and prior closure history; verify closure again.
Never automatically clear a latch, reset money, trade to recover a shortfall or ask for a new goal.

Only explicit user end normally terminates this agent session. Record `session stop` when
possible, cancel queued native continuations, and stop routine dispatch. A stop received
between preparation and dispatch invalidates the unused normal permit: retain the intent
and reconcile the actual outcome, not a fabricated nonexecution. Do not close positions
merely because the user stopped; keep only applicable original emergency authority when
execution is not revoked. Never auto-resume after a stop, even through owner handoff or
financial reactivation. A genuine new user request may start a new session without resetting
the existing financial policy/goal or its latches.

A real host shutdown, cancellation or enforced limit leaving no permitted continuation
can interrupt execution. Record `session interrupt` and report the limitation if possible,
not completed target work or invented continuous protection. Scheduled waiting, a quiet
market and dashboard/reporting failure are not interruptions. If the host prevents even
the control write, say so. "Do not stop" does not authorize bypassing actual restrictions.

An explicitly approved `new_goal` or `replace_policy` archives the previous loop, not a
fabricated target completion. With permitted active session control, the agent automatically
issues the first fresh `cycle` after activation. Activation itself never clears a user stop.
Same-goal reauthorization preserves identity/history; a changed approved
timeframe invalidates only the affected cadence/bar tracking. Failed activation does not
discard the prior loop. No automatic new goal or risk reset is allowed.

## Guardrails

- Freshness: each cycle carries its own snapshot under the mandate's
  `max_snapshot_age_seconds`. A stale snapshot is retried, not relaxed.
- Safety reductions retain only their applicable authority; routine protective management
  requires active session control and original ownership. Risk increases still require every pre-trade check.
- One active account and one local writer. A second writer, a different account binding, or
  corrupt state stops new exposure rather than starting a parallel session.

## Reporting

Publish the [compact report](goals.md#compact-trading-report) through the dashboard's saved
observations and source-bound journal, not repeated chat messages. Include the distinction:

```text
Session / Loop: <session ID and requested active/stopped/interrupted control; financial active/closing/closed; execution unverified; last source; actual wait or planned wake; observation gaps; cycle spacing separately>
```

Use `loop_health` for cached source/receipt time, observation age/gaps and wake overdue
evidence; execution remains unverified. Account-observation gaps measure source-to-source
spacing. Loop `gap_seconds` and `max_gap_seconds` are **cycle spacing**, not account gaps:
intervening `check`/`prepare`/`resolve` observations
may check risk. Legacy missing observation evidence stays unavailable, not inferred from
cycle spacing. Between genuinely observed snapshots no continuous monetary check is proven;
broker stops cannot guarantee either threshold. Do not invent an exact outage cause/duration.

Follow the [dashboard reporting workflow](goals.md#dashboard-reporting) after real work.
Source age, deadlines and gaps are not refreshed by prose, journal or browser activity.
Reporting failure neither requires new approval nor ends the loop. Chat is reserved for a
brief startup/account/limits and dashboard link, genuinely missing input, requested progress,
an actual interruption or explicit user end. If the viewer is unavailable, report that
limitation and use brief nonterminal fallback progress while continuing permitted work.
Every routine report must lead to an actual next action/wait/read, not "session running"
paired with a final reply.

## Synthetic Continuation Checks

Exercise without a real account: one synthetic budget/target trading-start request ->
start_request activation -> session start -> fresh first cycle (also without entry) -> eligible
pending entries with context-backed prepare/readback/resolve -> journal -> consume revision and
canonical control -> actual wait/read. Continue beyond six quiet decision cycles with approved
intermediate risk-only checks and no additional user message; select the earlier tripwire, not
just the candle. Include a transient failed read with real backoff and no fabricated helper or
journal heartbeat. Trigger a synthetic monetary latch, keep working through partial/unknown
closure, verify settlement, then continue account-only observation without a new campaign or
prompt. End on the synthetic user's explicit stop, cancel actual queued continuations and
retain latches/history. A test-imposed cutoff or financial settlement is not session completion.
"Loop: none" after the ordinary first batch, a final choice menu and a future-monitoring
promise without executing continuation all fail.

Also cover missing-bar retry without entry, restart after preparation before a journal, recovery
of completed original plans after later wait notes, user stop between prepare and dispatch,
safe interrupted recovery, legacy bounded scope and genuinely unavailable wait capability.
Check journal/status/context response boundaries with active/closed/stopped/interrupted control
and older `last_result`; cached continuation must not observe, move deadlines or override a stop.

Helper tests cannot verify AI response behavior. Inspect an actual supported synthetic client/tool
trace with real waits/registered wakes and cancellation, or report continuation unverified.
For OpenCode, verify the installed version/agent, effective step limit, permission/repeated-call
blockers and last stop boundary separately, without changing settings or exposing secrets.
Passing helper tests, a todo, saved state or a running viewer does not prove continuation after
a final response or shutdown, nor diagnose a historical stop. Do not add a runtime platform or
use live/demo broker operations to obtain that evidence.
