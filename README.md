<p align="center">
  <img src="assets/logo.png" alt="Ace hat logo" width="100">
</p>

# Ace

Client-neutral instructions for an AI agent that analyses markets and trades a MetaTrader 5 (MT5) account through an MT5 Model Context Protocol (MCP) server, with a small Python/SQLite account checker and a separate read-only local dashboard. You supply a monetary trailing-loss budget and a profit target; the agent reads the market itself and decides which orders to place. The mandate covers the whole named account, including manual exposure.

Version: **[1.6.2](VERSION)** | [Changelog](CHANGELOG.md)

## v1.6.2 Highlights

- **Animated target:** the responsive, read-only [local dashboard](#local-dashboard) now presents exact saved target progress in an animated donut, with essential amounts visible and accounting details available on demand.
- **Focused activity:** Account activity shows the newest five events first and can fetch the complete recorded history through bounded pages. Unresolved local requests remain visible directly below it.
- **Cleaner account desk:** the detailed broker pending-order list is no longer rendered. Canonical order data and counts remain available to risk checks and the read-only API.

Checkpoint compatibility is unchanged: SQLite schema 3 reads versions 1/2/3, the dashboard API stays at version 1, and journal/display envelopes stay at version 1. Existing checkpoints keep approved limits, baselines, latches and history; read-only access never upgrades them. See the [changelog](CHANGELOG.md) for release details.

## Getting Started

1. Load [AGENTS.md](AGENTS.md) in your AI client if it is not discovered automatically.
2. Have the client read all four instruction files below before every trading session.
3. Make Python 3.10+ and its standard-library SQLite support available for local helper execution. For autonomous trading, the client must also have a documented way to wait and continue the same executing task; Ace verifies this before promising a loop or opening its first new exposure. No database server, installed service or network-enabled Python trading bridge is needed.
4. Connect an existing MT5 MCP server through your client's secure setup. Keep credentials outside this repository and out of chat; execution still follows the client's tool permissions.
5. Ask the client to connect to the MT5 MCP to begin onboarding. Ace also starts or reuses its local dashboard automatically. A request to "only check the connection" remains read-only and does not start setup or the viewer.

The whole flow: connect and verify the account -> give one budget and one target -> Ace discovers instruments and analyses current conditions through MCP -> one named-account approval -> activate and immediately start a fresh loop cycle -> manage and place qualifying orders -> reconcile, journal, consume revision, report progress, actually wait and read fresh data again -> at either trigger cancel pending entries and close every position. There is no post-batch keep-going choice or routine per-action approval.

## Instructions

- [MT5 Connection](instructions/mt5-connection.md)
- [Monetary Risk And SQLite/Helper Contract](instructions/risk-management.md)
- [Goals And Progress](instructions/goals.md)
- [Loop Sessions](instructions/loop.md)

## How Ace Trades

There is no strategy catalogue and no backtesting. Ace works from live MT5 data each session:

- **Universe.** It lists the broker's actual symbols and keeps the majors, major minors (such as EURJPY, GBPJPY and AUDJPY), spot metals, oil and other commodities, index CFDs, and the broker's synthetics, excluding anything whose contract size, tick value, conversion, stop distance, spread, commission, swap, margin or availability cannot be verified.
- **Analysis.** It reads current quotes and bars across several timeframes and states what the market is doing: direction or range, momentum, volatility, spread quality versus the planned stop, session, and the levels that would invalidate the view.
- **Execution.** It opens positions and pending orders across independent trade ideas instead of committing the budget to one trade, each with a broker-side protective stop, sized to the broker's lot step.
- **Management.** [Active Order Management](instructions/risk-management.md#active-order-management) defines adaptive cost-aware breakeven and trailing stops, early invalidation exits and cancellation of invalid pending entries for verified Ace-owned trades. Valid pending setups stay in place. New entries still need fresh signals; protect-first winner additions require earlier legs to be profitable and protected at verified breakeven or better, sharing the original idea's fixed risk allocation rather than counting as diversification. Floating-profit give-back remains risk even at breakeven.
- **Budget.** The budget is one account-wide trailing allowance. It follows the highest cash-flow-adjusted equity actually observed, so several orders share the same remaining headroom; no order may use the whole budget, and no martingale, averaging into losses or stop widening is allowed.
- **Target.** The target is account-wide gain from the approved baseline, adjusted for external cash flows and estimated incremental closing costs.
- **Stops.** At observed drawdown greater than or equal to the budget, or estimated net gain greater than or equal to the target, Ace latches, cancels all pending entries and closes all positions including manual trades. Loss handling takes precedence when both triggers apply, and a latch survives reconnects, new days and recovery.

Trading begins only after one approval naming the exact login/server/demo-live type/currency, both amounts, the approved symbol universe, the current market read, the Ace-only management rules and both whole-account closure mandates. It also covers immediate autonomous looping, the agent-selected entry timeframe, any latch-only tripwire and bounded recovery, with host/observed-only limitations disclosed. After that, qualifying actions need no separate per-trade confirmation, subject to client permissions. Routine management does not adopt manual trades or expand old approvals, including explicitly one-shot mandates. Stops adjust only while the AI is active, not through a continuous trailing service; these judgments remain the agent's responsibility, not independent Python enforcement.

## Local Checker

The agent obtains actual MT5 account/exposure/history data and passes verified snapshots to `scripts/account_check.py`. The helper uses Python's standard library and defaults to repository-root `ace_state.sqlite3`, independent of the caller's directory. It performs no networking or trading, does not authenticate supplied facts or approval, and runs only when invoked. Follow the [exact command, JSON, and SQLite contract](instructions/risk-management.md), rather than inventing inputs or editing SQL.

| Command | Role |
| --- | --- |
| `draft` | Save account-bound monetary drafts without approving trading or resetting an active policy. |
| `activate` | Record a genuinely approved, reconciled mandate; preserve same-policy risk anchors for a new goal, and require explicit approval for a replacement policy. |
| `check` | Record a verified snapshot and report limits/latches/actions, including latch-only loop wakes or explicit one-shot checks; does not start a loop. |
| `prepare` | Recheck fresh inputs and durably record the exact intended MCP action before dispatch, reserving risk locally when applicable. |
| `resolve` | Reconcile verified broker outcomes, retaining uncertainty instead of assuming a timeout means failure. |
| `cycle` | Record a fresh unique loop observation, per-symbol closed-bar progress and verified wake plan; a fresh no-bar observation can count without permitting entry. |
| `journal` | Save a concise explanation against the latest accepted snapshot, without another risk check, cycle or dispatch permission. |
| `status` | Read saved state and derived observation/wake health without writing or proving current MT5 access or agent execution. |

After successful activation, the agent obtains a separate fresh snapshot and calls `cycle` in the same executing task, even without an entry signal. Subsequent loop decisions use `cycle`; latch-only wakes and explicit one-shot checks use `check`. Monetary latches and required management of existing positions/pending entries take priority over additions. An eligible action uses fresh `prepare` -> the actual MCP call -> verified fill/stop/volume or cancellation/closure readback -> `resolve`. Only a successful fresh `prepare` grants dispatch for that action. Local transactions and one local writer protect local reservations, not against manual trading, copied repositories, account switches or the check-to-dispatch race. SQLite is not atomic broker gating or an independent continuous guard.

After that actual work, the agent records concise decision/outcome/no-trade explanations using the [journal contract](instructions/risk-management.md#journal-reports) and [reporting workflow](instructions/goals.md#dashboard-reporting). These are source-grounded summaries, not private chain-of-thought or new execution evidence. Consume the journal revision but retain the operational loop result and wake plan: journal omits continuation fields and cannot start/end a loop or refresh observation health. Reporting never goes between preparation and dispatch, repeats a check just to log, or delays protection. Failure is neither completion nor a new approval gate; the unfinished loop continues with an actual wait/read after progress.

Deploy the helper and read-only consumer together before a schema-3 write. Upgrades occur atomically on the next authorized write, not on `status` or dashboard reads. Legacy unbound loops require verified existing-authority `activate resume` for prospective binding, preserving their ID/history without another routine approval. An old viewer may need reload through existing client-managed process controls; its failure is dashboard-only, not a reason to reset state or delay protection. See [SQLite And Recovery](instructions/risk-management.md#sqlite-and-recovery).

The SQLite file is the sole local account checkpoint and must stay private. A missing database is unconfigured, never an approved reset. Root `risk_management.csv` and `risk_management.csv.*` account backups are retired and discarded without import; do not recreate, detect, read, migrate, depend on, or ask about them during onboarding, or copy old approvals/peaks into fresh state.

## Local Dashboard

Ace automatically starts or reuses the dashboard when an ordinary connection, setup,
trading or progress-reporting session begins or resumes, and reports its URL. You do not
need to launch a separate terminal. This uses the AI client's supported background-process
facility and respects its permissions; an explicit opt-out or connection-only check skips
startup. If that facility is unavailable, Ace reports the viewer limitation without
delaying required trading checks or authorized protection. See
[Automatic Dashboard](AGENTS.md#automatic-dashboard).

The same command remains available for manual use from the repository root:

```text
python scripts/dashboard.py
```

Open `http://127.0.0.1:8765`. Python 3.10+ and its standard library are sufficient; there are no external Python packages, frontend dependencies or build steps. Optional CLI flags are `--port <port>` and `--db <path>`; the default database is repository-root `ace_state.sqlite3`. The browser cannot choose a database path. An alternate path is for a fixture or an explicitly managed checkpoint, not a second trading ledger.

Repeated launches reuse an existing server only when `/api/health` matches the workspace
and checkpoint. This endpoint returns a nonsecret viewer identity, not account data, and
does not open SQLite. A different service or checkpoint on the port is left untouched and
reported as a startup failure. The viewer follows the client's process lifetime; this is
not an OS startup task, a trading daemon or proof that the AI is executing between turns.

The separate loopback HTTP server serves static UI files and read-only GET routes, opening SQLite with `mode=ro`. It cannot trade, change settings, approve or activate state, start the agent, or refresh MCP. Starting or viewing it does not begin onboarding or grant trading authority; it needs no client-specific configuration.

The view shows the current approved target and exact estimated net progress in an animated donut, essential target amounts, account-wide risk/stop state, recorded decisions, and the newest five activity events with an on-demand complete-history view. Unresolved local requests remain visible below activity. The detailed broker pending-order list is not rendered, but canonical order counts and read-only API data remain available; local prepared/unknown intentions are not broker orders, and a settled request does not necessarily mean a fill or a flat account.

Page refresh rereads saved records, not a continuous broker feed. Freshness follows source `as_of` and the approved maximum age, never the page refresh, journal time or recorded active loop. The viewer distinguishes financial lifecycle, planned/overdue wakes, account-observation gaps and cycle spacing; health remains execution-unverified, and an overdue wake does not prove a crash. Missing state is unconfigured without file creation; draft-only amounts cannot replace an approved target. Stale or failed reads retain at most labeled last-known data with original timestamps, not zeros or silent repair. The donut's arc is bounded to 0-100 for geometry while its text retains exact negative or above-target progress; it is not a trigger, promised return or continuous guard.

## Loop Sessions

An approved autonomous trading mandate automatically starts a [loop session](instructions/loop.md), even when the first cycle has no entry. Ace uses verified broker candle timing, a 3-5-second settle buffer and any earlier approved latch-only check, not guessed UTC candle alignment. Missing bars/timing trigger bounded data retries; transient MCP reads use 5/10/20/30-second backoff. Failed reads make no helper call, while processed blocked helper requests may consume a revision. No-trade, closed-market and retry reports are nonterminal and must lead to actual wait/read continuation, not another user prompt.

Financial `active` and `closing` both mean unfinished work (`may_continue: true`), not proof of a running client. Normal completion needs a monetary latch and fresh verified flat/reconciled exposure, settled intents and final costs. Explicit user stops, revoked authority, actual permission failures or host hard limits can interrupt the task without completing/resetting its financial session. Do not resume against a stop or close solely because the task stopped. Interruption evidence is reported honestly; no continuous observation is claimed. Capital protection and original authority always override target pursuit. Explicit bounded/read-only requests and mere dashboard/status/journal activity do not start loops.

## Safety Model

- The fixed-money budget trails the highest cash-flow-adjusted equity actually observed since policy approval. It is not a starting-equity floor, cumulative losing-trade total, or daily allowance. The target is additional account equity gain since its approved baseline, adjusted for external cash flows and estimated incremental closing costs not already reflected in equity.
- All account equity, costs, manual exposure and pending orders count, even when equity greatly exceeds the budget. The budget is not segregated capital. Broker stops and verified economics/sizing/margin are mandatory; existing stressed exposure plus proposed risk, costs exactly once and a safety margin must be strictly below remaining monetary headroom. Equality or an unaffordable minimum lot means no entry, not greater leverage or wider stops.
- At observed drawdown greater than or equal to the budget, or estimated net liquidation gain greater than or equal to the target, stop new risk, cancel all account pending entries and close ALL account positions under the approved mandate. Preserve protective orders until their positions are safely closed, reconcile late fills/orphans, and verify outcomes. Loss-stop handling takes precedence if both triggers apply.
- Both stops persist across reconnects, new days, equity recovery and corrections. Final profit below target does not resume trading: report the trigger, pending closure, verified final result and shortfall separately. A same-policy new goal preserves the observed risk peak and cannot release a loss latch; a risk reset needs explicit replacement-policy approval.
- There is NO independent continuous guard/service. Only snapshots supplied while the AI is active check the monetary limits. Missed peaks/breaches, price gaps, slippage, inactivity and closure delays can produce overshoots; neither cap, target return nor completion time is guaranteed.
- Unknown/stale data, invalid state, missing helper, uncertain execution or absent authority blocks new exposure. Do not blindly retry an ambiguous order. Previously authorized identity-verified emergency reductions must not wait for a database repair or an entry signal; actual tool permissions and safe broker targeting still apply.

## Tests

From the repository root:

```text
python -m unittest discover -s tests -v
node --test tests/test_dashboard.mjs
```

The tests use synthetic temporary checkpoints, not the real account database or MT5. Python covers the helper, read-only API and safe startup/reuse; Node.js covers frontend formatting, rendering and state handling. Node.js is only needed for frontend tests, not to run the dashboard. Helper tests do not prove AI continuation: the [synthetic continuation checks](instructions/loop.md#synthetic-continuation-checks) require an actual supported client/tool trace, otherwise that behavior remains unverified.
