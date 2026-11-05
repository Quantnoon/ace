# Loop Sessions

The first genuine named-account approval covers immediately starting and sustaining this
loop toward the target within the original risk and management mandate. No separate
"keep going" request is needed. These instructions define agent-driven continuation, not
a service, scheduler or watchdog; the one-shot helper does not wait, network or trade.

**No voluntary yield:** while an authorized loop is unfinished and the task can execute,
follow each compact progress message with an actual supported wait or due fresh read,
not a discretionary final reply. Never replace continuation with "say continue", a
"keep going / check now / cancel all" menu or a promise to check later. A completed order
batch, no trade, unchanged orders, a future deadline, closed markets and transient read
failures are not completion. Do not invent a private cycle-count or elapsed-time cutoff.

## Authority And Execution

The single approval includes the agent-selected entry timeframe, any latch-only tripwire,
immediate looping, bounded recovery, eligible entries, original-authority management and
both whole-account closure mandates. Disclose actual host and observed-only limitations
at that approval, without adding a trading setting, approval field or second opt-in.
Reuse verifiable existing approval for an ongoing autonomous task without asking again;
never expand an explicitly single-batch/one-cycle mandate retroactively.

Explicit connection-only, analysis-only, dashboard-only, progress-only, maintenance and
bounded one-shot requests do not start trading loops. Neither viewing state nor calling
`status`, `journal` or an ordinary one-shot `check` activates a loop or grants authority.
Material mandate changes, a new goal and a risk reset retain their explicit-approval gates.
Defer optional out-of-scope actions and continue other permitted work.

Before promising a loop or opening its first new exposure, verify the client's documented
ability to wait and return control to the same executing task. Use only actual available
tools and bounded, interruptible waits within their limits; chunk long waits without
skipping a due risk check. Report a genuinely missing capability before orders, not after
the first batch as a new choice. Previously authorized emergency protection takes priority.
A wait is not monitoring. The between-turns limitation does not justify voluntarily ending
the task; a runtime blocker needs an actual error or documented capability limit.
Never invent a scheduler, assume a client-specific tool or bypass host permissions/limits.

Follow [Automatic Dashboard](../AGENTS.md#automatic-dashboard) before entering or resuming
the loop where possible. Reuse the session-managed viewer, not a server per candle.
Do not wait for its long-running process or let startup suspend trading. Viewer failure
is a dashboard-only limitation, not a completion signal or reason to delay protection.

## Financial Session And Task

The persisted financial lifecycle is separate from current AI execution:

- **`active`**: the approved loop has unfinished observation/decision work without a stop.
- **`closing`**: a monetary latch requires cancellation, closure or reconciliation work.
- **`closed`**: a monetary latch and fresh verified flat positions, no pending orders,
  settled intents and final costs establish completion.

A task can be executing, waiting or interrupted while its financial session remains
unfinished. Interruption does not close or reset it. Stored `loop.status`, cached `status`,
`loop_health` and dashboard refresh cannot prove client liveness or MCP connectivity;
health reports `execution: "unverified"`. Never claim the account is watched between reads.

When a loop exists, `may_continue` means unfinished work: true for `active` and `closing`,
including recoverable blockers, and false only on fresh verified completion. Inspect
`required_action` and `closure_verified` before waiting or finishing.
`required_action: "none"` and the normal `cycle.may_dispatch: false` do not end a task. Only a fresh successful
`prepare.may_dispatch` permits its exact mutation; continuation never authorizes new risk
after a latch. Invalid/stale data cannot establish completion from cached state.

## Bootstrap

After the first approval, use fresh verified data to `activate` and enforce any activation-time
latch immediately. After successful activation, obtain a separate fresh snapshot and call
`cycle` in the same executing task before normal management/entries. Establish the loop even if no entry
qualifies; do not wait for a fill, completed batch or another message. Do not repeat
approval or activation every candle. Explicit bounded requests retain their narrower scope.

## Duties On Every Cycle

1. Read current account, positions, pending orders and history through documented MCP tools;
   build one coherent snapshot; call `cycle` (it performs the same observation and latch
   arithmetic as `check`, plus session bookkeeping). A latch-only wake uses `check`, not a
   candle decision; coincident wakes may use one fresh `cycle`.
2. Enforce monetary latches and previously authorized emergency reductions first. A latch
   invokes the whole-account cancellation/closure mandate, including manual exposure, ahead
   of ordinary trailing, pending-order review or new entries.
3. Apply [Active Order Management](risk-management.md#active-order-management) to existing Ace
   positions and every Ace pending entry. Review breakeven/trailing eligibility, original
   position invalidation and pending-entry validity, including orders far from entry triggers.
   Use confirmed closed candles for structural decisions, but check recorded expiry and
   current protection/session/economics conditions on fresh reads even without a new bar.
   Leave valid setups alone; cancel invalid ones rather than chasing price. Routine changes
   require original Ace ownership and authority; manual exposure still counts in the account
   snapshot and risk but is not adopted for routine management.
4. Perform required management using fresh `prepare` -> the exact MCP call -> later readback
   -> `resolve` for every mutation. Recalculate risk from verified outcomes before considering
   additions. Unknown outcomes block new risk, not separately authorized, safely targeted
   safety reductions. Such reductions do not wait for a candle or entry signal.
5. Once a new entry-timeframe candle for the affected symbol is confirmed and required
   management is reconciled,
   re-test prospective entry levels within a proximity band of their triggers. Consider fresh
   independent setups and protect-first winner additions only under the canonical management
   rules and a new successful `prepare`. An order's cancellation, a breakeven stop or spare
   headroom is not itself a new signal; a missing bar or latch-only read does not permit entry.
6. After the actual cycle and any management/readback/`resolve` work, record a concise
   decision/outcome/no-trade explanation with [`journal`](risk-management.md#journal-reports),
   matching the final latest accepted snapshot. Consume its returned revision, but retain
   the latest operational result: journal output omits loop/continuation fields and its
   `may_dispatch: false` is not completion. It does not change source time, loop, deadlines
   or `last_result`. Do not repeat `cycle` just to log, insert reporting between preparation
   and dispatch, or delay
   emergency protection for a report. Summarize conclusions, not private chain-of-thought.
7. Keep per-cycle output small: cycle number, decision, equity, drawdown, remaining risk,
   latch state, actual management results/blockers under [Outcome / Next](goals.md#compact-trading-report),
   and the next wake/reason. This is a progress message, not a final answer. Full snapshots
   belong in SQLite, not in the conversation. Read the bars needed for existing position/order
   management and nearby prospective triggers, not
   the whole symbol universe every cycle; entry proximity must never exclude required management.
8. Actually wait until the earliest applicable wake from the final operational result, or
   read immediately when due. Then obtain fresh data and repeat. Later accepted observations
   from management/readback can update the latch-check deadline; journal cannot. Individual
   wait chunks do not require another verbose report.
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
- A failed MCP read makes no helper call, changes no revision or financial observation and
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
  management evidence and broker outcomes/intents. Obtain fresh account/history/exposure
  data, then `cycle` (with verified `activate resume` when required by the
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

## End Conditions

Normal financial completion requires one of these monetary latches and fresh verified closure:

- `loss_latch`: observed drawdown greater than or equal to the approved budget.
- `target_latch`: estimated net gain greater than or equal to the approved target.

A session never completes because the market is quiet, no order filled, no setup qualified,
an instrument is closed, a transient outage occurred or the agent ran out of work to describe.
When both latches apply, loss handling takes precedence.

At a latch the session moves to `closing`: cancel all account pending entries, close all
positions including manual exposure, verify flat and reconciled, report the trigger
separately from the final net result and any shortfall, then mark the session `closed`.
Keep working while closure or costs/intents remain unresolved. Repeated closed observations
retain the same ID/history and have no planned wake. Fresh late exposure returns that same
session to `closing`, preserving latches and prior closure history; verify closure again.

Explicit user cancellation/revocation, actual denied permissions that leave no permitted
continuation, or a documented/enforced host limit can interrupt the executing task. Report the blocker and last observation,
not completed target work. Do not resume against an explicit stop or close positions merely
because the user stopped the task; retain only applicable existing emergency authority.
"Do not stop for any reason" cannot override these boundaries, the loss stop or capital-first
rules. Never force turnover, widen stops, enlarge the budget or promise profit to continue.

An explicitly approved `new_goal` or `replace_policy` archives the previous loop, not a
fabricated target completion. The agent automatically issues the first fresh `cycle` after
that activation. Same-goal reauthorization preserves identity/history; a changed approved
timeframe invalidates only the affected cadence/bar tracking. Failed activation does not
discard the prior loop. No automatic new goal or risk reset is allowed.

## Guardrails

- Freshness: each cycle carries its own snapshot under the mandate's
  `max_snapshot_age_seconds`. A stale snapshot is retried, not relaxed.
- Safety reductions and verified protective management remain allowed during a session;
  risk increases still require every pre-trade check.
- One active account and one local writer. A second writer, a different account binding, or
  corrupt state stops new exposure rather than starting a parallel session.

## Reporting

Add one line to the compact report:

```text
Loop: <id; financial active/closing/closed; execution/wait/blocker evidence; cycles/timeframe; last source; planned wake/reason; observation gap/max; cycle spacing separately>
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
Reporting failure neither requires new approval nor ends the loop. Every nonterminal report
must lead to actual wait/read continuation, not "session running" paired with a final reply.

## Synthetic Continuation Checks

Exercise both reported failure shapes without a real account: one synthetic named-account
approval -> activation -> fresh first cycle (also when no entry qualifies) -> eligible
pending entries with prepare/readback/resolve -> journal -> consume revision -> actual
wait/read. Continue past three quiet candle cycles with approved intermediate risk-only
checks and no additional user message; select the earlier tripwire, not just the entry
boundary. End through a synthetic monetary latch and verified closure, not a test-imposed
cycle limit presented as completion. "Loop: none" after the ordinary first batch, a final
choice menu and a future-monitoring promise without executing continuation all fail.

Also cover missing-bar retry without entry, bounded outage recovery, original-intent
reconciliation, unfinished liquidation and honest interruption for explicit stop or an
unavailable wait capability. Helper tests alone cannot verify AI response behavior: inspect
an actual supported synthetic client/tool trace, or report client continuation as unverified.
Do not add a runtime platform or use live/demo broker operations to obtain that evidence.
