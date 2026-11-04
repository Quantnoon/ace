# Loop Sessions

These instructions govern a request to keep working toward the account target without
repeated prompts ("keep going", "loop until the budget or target is met"). They define the
cadence, the recovery behaviour, and the only conditions that end a session. They do not
create a service, scheduler, or background watchdog; the helper still performs no
networking and places no orders.

## What A Session Is

A loop session is a run of consecutive active decision cycles recorded by the helper's
`cycle` command. It is a bookkeeping record of observations, not a promise of observation.

- **Active** only while the AI client is actually executing turns and supplying snapshots.
- **Interrupted** whenever turns stop for any reason. The session keeps its id, cycle count
  and gap history; a later turn resumes the same session. An interruption is a gap, never an
  end.
- **Closed** only after a monetary latch has been enforced and verified flat.

Never describe a session as running, monitoring, or protected between turns. `status`
reports the last actually recorded cycle and its original timestamp.

## Cadence: Entry-Timeframe Candles

The wait between cycles follows the closed candle of the approved entry timeframe, not a
fixed polling interval.

1. `entry_timeframe` comes from the approved mandate. When an older approved mandate does not
   contain it, M15 applies; selecting a different value is a mandate change and requires
   re-authorization, not a silent switch mid-session.
2. Wake at the next boundary of that timeframe in trade-server time, plus a settle buffer of
   3-5 seconds so the new bar and quote are usable.
3. Confirm a new bar actually exists: the latest closed bar's `open_time` must be later than
   the stored `bar_open_time`. Clock arithmetic alone never proves a bar formed.
4. If no new bar is present, retry after about 15 seconds rather than treating it as a cycle.
5. If two consecutive boundaries pass with no new bar while the instrument is verifiably
   closed (weekend, daily break, holiday), switch to a long poll of about five minutes with
   `market_state: "closed"`. This is still not an end.
6. After a long gap, never replay missed bars one by one. Record the gap once and take a
   single fresh read.

`cycle` returns `next_cycle_at`, which already includes the buffer. The agent does not
invent its own cadence.

## Duties On Every Cycle

1. Read current account, positions, pending orders and history through documented MCP tools;
   build one coherent snapshot; call `cycle` (it performs the same observation and latch
   arithmetic as `check`, plus session bookkeeping).
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
5. Once a new entry-timeframe candle is confirmed and required management is reconciled,
   re-test prospective entry levels within a proximity band of their triggers. Consider fresh
   independent setups and protect-first winner additions only under the canonical management
   rules and a new successful `prepare`. An order's cancellation, a breakeven stop or spare
   headroom is not itself a new signal; a missing bar or latch-only read does not permit entry.
6. Keep per-cycle output small: cycle number, decision, equity, drawdown, remaining risk,
   latch state, actual management results/blockers under [Outcome / Next](goals.md#compact-trading-report),
   and the next boundary. Full snapshots belong in SQLite, not in the conversation. Read the
   bars needed for existing position/order management and nearby prospective triggers, not
   the whole symbol universe every cycle; entry proximity must never exclude required management.
7. Never raise risk to manufacture activity. A quiet cycle is a valid result.

## MCP Failure

- Retry with backoff: 5 s, 10 s, 20 s, then 30 s repeatedly. There is no attempt limit and an
  outage is never a reason to end the session.
- A failed read is not a cycle: it must not advance the revision, the cycle count, the peak
  or a latch.
- Never re-submit a previous observation as if it were new. Fabricating freshness would
  corrupt the trailing budget and the target baseline.
- Dispatch nothing while unverified, and queue nothing to fire on reconnect.
- Record the outage as a gap with its start time and duration.
- The first action after recovery is a fresh snapshot, then `cycle`: a trigger may have fired
  unseen. If a latch is found, cancellation and closure run immediately, ahead of any other
  work.

## End Conditions

Only two conditions end a session:

- `loss_latch`: observed drawdown greater than or equal to the approved budget.
- `target_latch`: estimated net gain greater than or equal to the approved target.

A session never ends because the market is quiet, no order filled, no setup qualified, the
instrument is closed, MCP is down, a cycle or time limit was reached, or the agent ran out of
work to describe. When both latches apply, loss handling takes precedence.

At a latch the session moves to `closing`: cancel all account pending entries, close all
positions including manual exposure, verify flat and reconciled, report the trigger
separately from the final net result and any shortfall, then mark the session `closed`.

## Guardrails

- Freshness: each cycle carries its own snapshot under the mandate's
  `max_snapshot_age_seconds`. A stale snapshot is retried, not relaxed.
- Safety reductions and verified protective management remain allowed during a session;
  risk increases still require every pre-trade check.
- `latch_check_seconds` is an optional tripwire. Zero, the default, means candle-only
  cadence. A positive value adds latch-only reads at that interval, which can trip a stop
  earlier but never authorizes an entry.
- One active account and one local writer. A second writer, a different account binding, or
  corrupt state stops new exposure rather than starting a parallel session.

## Reporting

Add one line to the compact report:

```text
Loop: <session id short / status active·interrupted·closing·closed / cycles / timeframe / last bar / max gap / end reason or next boundary>
```

State the observation gap explicitly. A long gap means the budget and target were unwatched,
and the broker stops were the only protection during it.
