<p align="center">
  <img src="assets/logo.png" alt="Ace hat logo" width="100">
</p>

# Ace

Client-neutral instructions for an AI agent that analyses markets and trades a MetaTrader 5 (MT5) account through an MT5 Model Context Protocol (MCP) server, with a small Python/SQLite account checker and a separate read-only local dashboard. You supply a monetary trailing-loss budget and a profit target; the agent reads the market itself and decides which orders to place. The mandate covers the whole named account, including manual exposure.

Version: **[1.7.0](VERSION)** | [Changelog](CHANGELOG.md)

## v1.7.0 Highlights

- **Start from your request:** open Ace in an AI client with execution-enabled MT5 MCP already connected and provide the budget and target. Ace verifies and activates that trading-start instruction without a final-account, per-order or keep-going confirmation.
- **User-controlled session:** the agent keeps acting, waiting and reading until you end the session. A budget/target trigger still latches and closes exposure; after settlement the session continues stopped-account monitoring without automatically trading again.
- **Recoverable decisions:** original strategy/rules and action reasons are saved before dispatch; routine assessments and verified outcomes go to the read-only [local dashboard](#local-dashboard). Recorded session control, financial state and planned wakes remain separate, not proof that the client is currently running.

SQLite schema 5 reads versions 1/2/3/4/5; the dashboard API and journal/display envelopes remain version 1, and action context has its own version 1. The next authorized write upgrades using the same three tables, preserving limits, baselines, latches, user stops, intents and history. Reads never upgrade state, backfill missing plans or expand an old bounded mandate into indefinite authority. Historical reviewed-baseline receipts remain supported.

## Getting Started

1. Open this project in your AI client. Load [AGENTS.md](AGENTS.md) if it is not discovered automatically.
2. Have the client read all four instruction files below before every trading session.
3. Make Python 3.10+ and standard-library SQLite available. The AI client is the runtime and must support actual waits/continuation, preferably its documented native persistent-task and scheduled-wake facilities. Ace verifies this before new exposure; no additional trading runner, database server or client-specific repository configuration is needed.
4. Ensure your client's MT5 MCP is connected and execution-enabled. Ace reuses it rather than asking you to connect again. Keep credentials in the client's secure setup, outside this repository and chat. Real client/tool restrictions still apply.
5. Provide the monetary budget and target for trading. That is the start instruction for the documented account-wide workflow; no extra final or per-action approval is requested. Ace starts/reuses the local dashboard and reports its verified URL. Only genuinely missing/ambiguous inputs or account targeting need a question. Explicit connection-only, analysis-only, dashboard-only and other bounded requests retain their narrower scope.

The whole flow: existing MT5 MCP -> your budget/target start request -> automatic account/capability verification and mandate preparation -> fresh activation and session control -> separate fresh first cycle -> analyse/manage/place eligible orders -> reconcile -> journal to the dashboard -> consume revision -> actually wait/read again. At either monetary trigger, cancel pending entries and close every position under the mandate, verify settlement, then keep observing with the latches intact until you end the agent session.

## Instructions

- [MT5 Connection](instructions/mt5-connection.md)
- [Monetary Risk And SQLite/Helper Contract](instructions/risk-management.md)
- [Goals And Progress](instructions/goals.md)
- [Loop Sessions](instructions/loop.md)

## How Ace Trades

There is no strategy catalogue and no backtesting. Ace works from live MT5 data each session:

- **Universe.** It lists the broker's actual symbols and keeps the majors, major minors (such as EURJPY, GBPJPY and AUDJPY), spot metals, oil and other commodities, index CFDs, and the broker's synthetics, excluding anything whose contract size, tick value, conversion, stop distance, spread, commission, swap, margin or availability cannot be verified.
- **Analysis.** It reads current quotes and bars across several timeframes: direction or range, momentum, volatility, spread quality, session and invalidation. Before dispatch, `prepare` saves the original strategy/rules and factual rationale in `action.context`, separate from exact MCP parameters. The root entry intent ID identifies the idea and its fixed original risk allocation.
- **Execution.** It opens positions and pending orders across independent trade ideas instead of committing the budget to one trade, each with a broker-side protective stop, sized to the broker's lot step.
- **Management.** [Active Order Management](instructions/risk-management.md#active-order-management) defines adaptive cost-aware breakeven and trailing stops, early invalidation exits and cancellation of invalid pending entries for verified Ace-owned trades. Valid pending setups stay in place. New entries still need fresh signals; protect-first winner additions require earlier legs to be profitable and protected at verified breakeven or better, sharing the original idea's fixed risk allocation rather than counting as diversification. Floating-profit give-back remains risk even at breakeven.
- **Budget.** The budget is one account-wide trailing allowance. It follows the highest cash-flow-adjusted equity actually observed, so several orders share the same remaining headroom; no order may use the whole budget, and no martingale, averaging into losses or stop widening is allowed.
- **Target.** The target is account-wide gain from the approved baseline, adjusted for external cash flows and estimated incremental closing costs.
- **Stops.** At observed drawdown greater than or equal to the budget, or estimated net gain greater than or equal to the target, Ace latches, cancels all pending entries and closes all positions including manual trades. Loss handling takes precedence when both triggers apply, and a latch survives reconnects, new days and recovery.

In a normal trading/setup request, supplying both amounts authorizes the [documented start contract](AGENTS.md#execution-contract), including agent-selected eligible instruments/settings, Ace-owned management, whole-account monetary-stop closures including manual exposure, and ongoing stopped monitoring after settlement. This delegates task-scoped MT5 operations, not unrelated/admin access, changed host permissions or a bypass of denied tools. Ace reports the verified binding and observed-only/host limits without another confirmation, records the real request, activates promptly from fresh data and analyses each idea before entry. A saved draft, arithmetic example or read-only request is not a trading instruction. Existing bounded mandates, account bindings and financial stops are not silently replaced. Stops adjust only while the AI is active; market-management judgments remain the agent's responsibility, not independent Python enforcement.

## Local Checker

The agent obtains actual MT5 account/exposure/history data and passes verified snapshots to `scripts/account_check.py`. The helper uses Python's standard library and defaults to repository-root `ace_state.sqlite3`, independent of the caller's directory. It performs no networking or trading, does not authenticate supplied facts or approval, and runs only when invoked. Follow the [exact command, JSON, and SQLite contract](instructions/risk-management.md), rather than inventing inputs or editing SQL.

| Command | Role |
| --- | --- |
| `draft` | Save account-bound monetary drafts without approving trading or resetting an active policy. |
| `activate` | Record a genuinely approved, reconciled mandate; preserve same-policy risk anchors for a new goal, and require explicit approval for a replacement policy. |
| `session` | Record authorized start/recovery, explicit user end or an actual runtime interruption separately from financial state; never grants trading permission or refreshes account data. |
| `check` | Record a verified snapshot and report limits/latches/actions, including latch-only loop wakes or explicit one-shot checks; does not start a loop. |
| `prepare` | Recheck fresh inputs and durably record exact MCP parameters plus separate strategy/rationale before dispatch, reserving risk locally when applicable. |
| `resolve` | Reconcile verified broker outcomes, retaining uncertainty instead of assuming a timeout means failure. |
| `cycle` | Record a fresh unique loop observation, per-symbol closed-bar progress and verified wake plan; a fresh no-bar observation can count without permitting entry. |
| `journal` | Save a concise explanation against the latest accepted snapshot; return cached canonical continuation without another observation, changed deadline or dispatch permission. |
| `status` | Read saved state, unresolved intents and canonical continuation/health without writing or proving current MT5 access or agent execution. |
| `context` | Read bounded current-campaign original/related intent records, including completed entries, and linked assessments; private recovery data, not live market evidence. |

After successful activation and handling any immediate latch, the agent registers/reuses session control, obtains a separate fresh snapshot and calls `cycle`, even without an entry signal. Subsequent trading decisions use `cycle`; latch-only wakes, stopped monitoring and explicit one-shot checks use `check`. Monetary latches and required management take priority over additions. An eligible action uses fresh `prepare` -> the actual MCP call -> verified readback -> `resolve`. Only successful fresh preparation permits that exact action; a user stop invalidates unused routine dispatch permission. Local transactions and one writer protect local reservations, not against manual trading, copied repositories, account switches or the check-to-dispatch race. SQLite is not atomic broker gating or an independent continuous guard.

New risk increases and newly prepared routine management require the bounded [decision-context contract](instructions/risk-management.md#decision-context), retaining the root entry's original plan/allocation. Read-only `python scripts/account_check.py context` returns up to 20 originating entries by default; `--before`, `--limit` (1-100) and `--origin-intent-id` provide scoped recovery, including completed origins and related actions. It takes no JSON stdin/`--input`, requires no owner/revision, and never creates or upgrades state. Its raw records, like `status`, are private, not the dashboard API. Legacy missing plans stay unavailable while existing intents remain resolvable. Emergency reductions may omit context; unusable optional context is dropped with a warning, never a new protection prerequisite.

After actual work, the agent records concise linked decision/outcome/no-trade explanations using the [journal contract](instructions/risk-management.md#journal-reports), not private chain-of-thought or new execution evidence. `journal`, `status` and `context` return cached canonical `session`, `loop`, `may_continue` and derived `loop_health`; `state.last_result` can predate a stop/resume and cannot override them. Consume the journal revision and current control while retaining actual financial/action evidence. Journal never observes or moves deadlines; errors or absent fields do not imply completion. Reports never go between preparation and dispatch or delay protection. Continue with the next actual wait/read, not a keep-going question. Chat is for startup, missing input, requested progress, actual interruption or user end; dashboard failure does not abandon other permitted work.

Deploy the helper and read-only consumer together before a schema-5 write; older writers must reject it rather than drop required context. Upgrades occur atomically on the next authorized write, not on `status`, `context` or dashboard reads. Legacy unbound loops require verified existing-authority `activate resume` for prospective binding, preserving their ID/history without another routine approval. Migration never manufactures session control or plans; user stops survive activation, new goals and owner handoff. An old viewer may need a [verified viewer-only restart](#local-dashboard), not a browser refresh; its failure is dashboard-only, not a reason to reset state or delay protection. See [SQLite And Recovery](instructions/risk-management.md#sqlite-and-recovery). Repository maintenance never migrates a real checkpoint; only an explicit viewer-repair request permits the managed viewer recovery below, without checkpoint or trading changes.

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

`/api/health` retains flat `service`, `api_version: 1`, `read_only: true` and `instance_id` fields, adding integer `reader_build`, integer `viewer_build` and an array of integers `readable_schemas`. These values are frozen at server construction; health never opens SQLite. `instance_id` remains the workspace/checkpoint-path hash, exposing neither raw paths nor account data. The checker keeps `SCHEMA_VERSION = 5`, shares `READABLE_SCHEMA_VERSIONS = (1, 2, 3, 4, 5)` with health and embeds integer `READER_BUILD = 1`; the viewer embeds integer `VIEWER_BUILD = 3`. Increment the corresponding build for reader/viewer behavior changes, including same-schema changes. On-disk `VERSION` or updated static assets are not evidence of loaded Python code. Health confirms identity/capability, not checkpoint readability/freshness or broker/AI execution.

Repeated launches reuse a matching viewer only with exact loaded build/capability compatibility and strict field types; build/schema numbers cannot be booleans or strings. Matching incompatible, legacy or unverifiable metadata produces a nonzero, actionable viewer-only restart-required error. An unrelated/unavailable service on an occupied port gets a generic refusal. Neither refusal stops the service; do not bypass it with auto-kill, hot reload, another port/checkpoint or an HTTP shutdown endpoint. The viewer follows the client's process lifetime; this is not an OS startup task, a trading daemon or proof that the AI is executing between turns.

The separate loopback HTTP server serves static UI files and read-only GET routes, opening SQLite with `mode=ro`. It cannot trade, change settings, approve or activate state, start the agent, or refresh MCP. Starting or viewing it does not begin onboarding or grant trading authority; it needs no client-specific configuration.

The view shows the current authorized target and exact estimated net progress in an animated donut, essential target amounts, account-wide risk/stop state, recorded decisions, and the newest five activity events with an on-demand complete-history view. A session strip separates requested continuation, stopped/interrupt control, the financial work phase and next planned wake. Session-control notes also appear in activity without refreshing financial evidence. Unresolved local requests remain visible below activity. The detailed broker pending-order list is not rendered, but canonical order counts and read-only API data remain available; local prepared/unknown intentions are not broker orders, and a settled request does not necessarily mean a fill or a flat account.

**Recorded Strategies** shows current-campaign original ideas, fixed allocations, management rules, latest linked actions/reasons and assessments with saved timestamps. It starts with up to 20 records; Load older strategies requests one bounded page through `/api/dashboard?strategy_before=<cursor>`, mutually exclusive with the activity `before` cursor. Pages are combined only within the same account/policy/goal and saved revision; a revision change refreshes the first page rather than retaining stale assessments. These are sanitized saved records, not a strategy engine or proof of current ownership/exposure. Completed entry requests can still be unfilled pending orders; missing legacy plans stay unavailable rather than inferred from symbol/ticket matches. Raw MCP parameters, approval/request references and private receipt paths remain outside the API. There are no trading controls.

Page refresh rereads saved records, not a continuous broker feed. Freshness follows source `as_of` and the approved maximum age, never the page refresh, journal time or recorded active loop. The viewer distinguishes financial lifecycle, planned/overdue wakes, account-observation gaps and cycle spacing; health remains execution-unverified, and an overdue wake does not prove a crash. Missing state is unconfigured without file creation; draft-only amounts cannot replace an approved target. Stale or failed reads retain at most labeled last-known data with original timestamps, not zeros or silent repair. The donut's arc is bounded to 0-100 for geometry while its text retains exact negative or above-target progress; it is not a trigger, promised return or continuous guard.

`unsupported_schema` (HTTP 503) means this viewer cannot read the saved format; an old Python viewer after an update is one possible cause, not a guarantee that restart fixes it. Browser refresh does not reload Python. For explicit viewer repair, verify workspace/checkpoint identity and that the current reader reads the same checkpoint with `mode=ro`, then stop/relaunch only that viewer through the original owning client's verified, permitted tracked process controls on the same workspace, checkpoint and port. Matching health or port ownership alone is insufficient. Recovery is complete only after compatible health and a successful `/api/dashboard` read; preserve stale source labels. Without the owning handle/controls, report dashboard-only recovery as blocked and continue otherwise permitted trading. Never interrupt trading/continuations, change or migrate the checkpoint, or add trading approval for viewer repair.

## Loop Sessions

Your monetary trading-start instruction starts an ongoing [agent session](instructions/loop.md), even when the first cycle has no entry. The financial task remains unfinished until an observed budget/target latch and verified liquidation/reconciliation; no fills, unchanged orders, no affordable setup or a saved report is completion. Ace uses verified broker candle timing, a 3-5-second settle buffer and any earlier latch-only check, not guessed UTC alignment. Missing bars/timing trigger bounded retries; transient MCP reads use actual 5/10/20/30-second waits. Failed reads create no snapshot-based helper/journal event, while processed blocked helper requests may consume a revision. No-trade, closed-market and retry outcomes lead to the next real wait/read, not another user prompt.

Financial `active`, `closing` and `closed` are separate from agent-session control. A monetary latch and fresh verified flat exposure, settled intents and final costs close the financial campaign, not the user-controlled session: `may_continue` remains true while session control is active. Continue account-only monitoring every five minutes or at a smaller positive latch interval, without new entries or automatic resets. A late fill reopens closing/reconciliation under the retained latch.

An explicit user end records `session stop` and cancels actual client continuations; it does not by itself close positions or reset risk. A real unavoidable host/runtime restriction may be recorded as `session interrupt`, never as a voluntary quiet-market exit. Resume interrupted work only after verified recovery; a user stop needs a genuinely new start instruction. Where native continuation requires a turn boundary, register it before yielding and do not mark the host goal complete after settlement. Client shutdown, cancellation and enforced limits remain real restrictions. A todo, persisted session, SQLite flag or viewer cannot make OpenCode or another client continue after a final response or shutdown; actual supported continuation must be verified separately. No new runner, plugin or client configuration is supplied. Explicit bounded/read-only requests and dashboard/status/context/journal activity never start a session.

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
