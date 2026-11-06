# Changelog

## [1.7.1] - 2026-11-06

### Changed

- Replace the target donut with a signed monetary scale from the negative approved budget through fixed zero to the positive approved target. Section widths remain proportional to the approved amounts. One solid fill starts at zero and extends right in green for positive `estimated_goal_gain` or left in red for negative gain, never both; zero has no fill and the gain label/marker moves with gain.
- Bound only fill/marker geometry to the signed endpoints, preserving exact money, signed percentages and overshoot text. Missing values remain unavailable, not zero.
- Keep actual trailing drawdown, headroom and latches separately in **Risk & state**. The negative-budget endpoint is only a signed-gain visual reference, not real trailing-budget usage or a trigger; financial calculations, authority and session behavior are unchanged.
- Advance `VIEWER_BUILD` from 3 to 4 so a matching build-3 viewer follows the existing nonzero, viewer-only restart-required path without stopping the service or changing the checkpoint. SQLite schema 5, reader build 1 and version-1 API/display/journal/action-context contracts are unchanged.

## [1.7.0] - 2026-11-05

### Added

- Durable `session` controls (`start`, `resume`, `stop`, `interrupt`) for requested work, interrupted recovery, explicit user end and actual runtime interruption, independent of financial campaign state. Stops survive activation, new goals and owner handoff; stopped/interrupted control blocks routine preparation and cycle advancement while retaining unresolved-intent recovery and separately still-authorized emergency reductions. Controls preserve observations, money, latches, intents and the latest financial result; restart after a user stop requires a genuinely new request, not replayed control evidence.
- Account-only stopped monitoring after verified budget/target settlement, with source/receipt-based five-minute or earlier positive latch-check wakes. It preserves the financial loop ID, closure history, counters and latches without advancing candles or opening risk. Late exposure returns the same campaign to closing/reconciliation, not a new campaign or monetary reset.
- Version-1 `action.context` saved at `prepare`, before dispatch and separately from exact MCP parameters. Original entries retain their strategy, thesis, invalidation and management rules, including explicitly disabled rules; additions and management retain root linkage, operation, factual rationale and source references without replacing the original plan or risk allocation.
- Read-only `context` recovery of current-account/policy/goal original entries, including completed origins, related actions and their latest linked assessments after restarts or unrelated journal updates. Root lookup and bounded pagination use `--origin-intent-id`, `--before` and `--limit`; private recovery output never creates/upgrades state or substitutes for current broker evidence.
- A Recorded Strategies section and navigation link showing saved original ideas, fixed allocations, rules, linked actions/reasons and assessments. Missing legacy plans remain unavailable, not automatically adopted or reconstructed; optional malformed strategy metadata cannot hide canonical financial state. These records are not a strategy catalogue, backtesting engine or proof of current ownership/exposure.
- Sanitized decision context in dashboard activity/unresolved requests and bounded strategy pages through `/api/dashboard?strategy_before=<cursor>`, separate from the activity `before` cursor. Strategies start with up to 20 records and load one older page per user action; reads serialize with refresh/activity, discard scope or revision races and stop non-advancing cursors. Raw MCP parameters and private authority/receipt references remain outside the API.
- A dashboard session strip and session-control activity showing requested state, financial work phase, reasons and planned wakes. Control records do not refresh financial source timestamps, create progress points or prove that the agent/MCP is executing.
- Database-free `/api/health` compatibility fields: `reader_build`, `viewer_build` and `readable_schemas`, frozen for the loaded server instance. Workspace/checkpoint identity remains path-hashed; health exposes neither raw paths nor account data and does not establish checkpoint readability or freshness. Corresponding build identifiers must advance for behavior changes, including same-schema fixes.
- Expanded synthetic regressions for request activation, stop replay protection and clock-rollback handling, interruption and closed monitoring, pre-dispatch context durability, root validation, emergency metadata fallback, read-only recovery/pagination and older-writer rejection. Dashboard coverage includes strategy privacy/races, canonical control, stale-reader reuse, unavailable/last-known recovery, panel placement and signed donut colors; actual native continuation remains a separate verification requirement.

### Changed

- Normal onboarding reuses the client's verified, execution-enabled MT5 MCP. Complete budget/target inputs in an explicit trading/setup request are the start instruction; `activate` records actual request evidence with `approval_mode: "start_request"` and a fresh post-request baseline. Historical `reviewed` receipts retain their frozen-baseline behavior. Drafts/examples do not grant authority; explicit read-only or bounded requests retain their narrower scope.
- New entries/additions and newly prepared routine management require validated decision context and applicable original-entry linkage; an opaque `analysis_ref` alone is insufficient. Legacy intents remain readable/resolvable, but missing original plans cannot justify new routine actions or backfill/adoption. Emergency context remains optional, with unusable metadata dropped with a warning rather than blocking otherwise-authorized protection.
- Routine reports are source-bound and dashboard-first. Chat is reserved for startup, genuinely missing input, requested progress, actual interruption/dashboard unavailability or user end. The AI client remains the runtime: use actual native continuation or supported interruptible waits, registering continuation before a required yield. A completed batch/report, stored flag or viewer neither ends otherwise permitted work nor proves continued execution; genuine user ends and unavoidable host restrictions remain effective.
- SQLite writes schema 5 and reads schemas 1/2/3/4/5, upgrading only on the next authorized write using the same three tables. Limits, baselines, latches, user stops, intents and history are preserved without manufacturing legacy plans or session authority; older writers reject unsupported schema 5. Display, journal and dashboard API versions remain 1, with action context independently versioned at 1.
- Moved **03 Latest recorded decision** below Target accounting details and the separate unapproved-draft notice in the left target column. It remains visible outside the collapsed accounting details; Recorded Strategies now leads the lower records area before activity and unresolved requests.
- Target donut colors now follow exact signed progress: success green for positive values, danger red for negative values and neutral gray for zero/unavailable values. Negative progress colors the track so losses remain visible even with an empty arc; monetary calculations, exact percentage text and 0-100 arc bounds are unchanged.

### Fixed

- Prevent silent reuse of an outdated viewer after a checkpoint/code update. Startup requires exact loaded build/schema compatibility with strict field types; matching incompatible, legacy or unverifiable health returns a nonzero restart-required diagnostic, while unrelated/unavailable services receive a generic refusal. Neither path kills a process, switches port/checkpoint or repairs state.
- Actionable `unsupported_schema` guidance explains that browser refresh does not reload Python. Documented viewer-only recovery requires an explicit repair request, identity/current-reader readability verification, the original owning client's tracked process controls, and successful health plus `/api/dashboard` checks after restart. Initial-unavailable/last-known displays, source timestamps and retries are preserved; trading, continuations and the checkpoint remain untouched.
- `journal`, `status` and `context` now return canonical `session`, `loop`, `may_continue` and `loop_health` instead of requiring callers to trust potentially older `state.last_result` control. These projections do not observe the account, move deadlines or grant dispatch; journal still consumes its reporting revision.
- Historical activity without its own journal no longer borrows the latest unrelated explanation, and strategy assessments stay bound to the relevant root/actions. Activity request status and outcomes are explicitly labeled as current at page read, rather than implied to be historical execution receipts.

### Removed

- The separate final named-account confirmation step for complete ordinary trading-start requests. Actual user authority, verified account/scope and client tool permissions remain mandatory; per-order and keep-going confirmations were already absent in earlier releases.
- The requirement to repeat a full compact report in every trading chat response, replaced by source-bound dashboard reporting and focused exception/requested chat updates.
- Financial settlement as an implicit end of an authorized ongoing user session. Legacy session-less and explicitly bounded mandates retain their original completion boundaries and are not silently expanded by an upgrade.

## [1.6.2] - 2026-11-05

### Changed

- Replace the sampled target history chart and table with an animated current-progress donut. Essential target values stay visible, accounting details move into a disclosure, exact signed percentages remain visible below zero and above 100, and reduced-motion preferences disable the transition.
- Account activity now starts with the newest five events. The on-demand View all control reads every older page sequentially through the existing bounded cursor API, remains scoped to the current account and goal, and can collapse back to five rows.
- Move unresolved local action requests below account activity while retaining their distinction from broker orders.

### Removed

- Remove the visible Broker pending orders section, filter, and navigation link. Canonical order data, risk counts, closure checks, checkpoint state, and read-only API compatibility are unchanged.

## [1.6.1] - 2026-11-05

### Changed

- The first named-account approval now covers immediate autonomous looping: activate, fresh first `cycle`, management/entries and reconciliation, source-bound journal, consume revision, compact progress and actual wait/read continuation. No separate keep-going menu, routine per-action approval or discretionary final reply after an unfinished batch/quiet cycle.
- Clarify financial `active`/`closing`/`closed` separately from task execution. Capital-first original authority, explicit bounded/read-only contexts, user stops, actual permissions and host limits remain binding; no continuous guard or automatic future goal is introduced.
- SQLite schema 3 explicitly reads versions 1/2/3 and upgrades on the next authorized write. Preserve approvals, monetary history, latches, intents, reports and version-1 display/journal envelopes; read-only loads and journal-first upgrades do not initialize/rebind loop metadata. Legacy loop binding requires verified existing-authority resume, not another routine approval.

### Added

- Verified per-symbol closed-bar and broker-clock evidence, approved-timeframe cadence, separate candle/risk/earliest wake deadlines and bounded missing-data/closed-market retry plans. Cycle counts represent unique accepted observations, not candles or trades.
- Cached read-only observation health with source/receipt timestamps, age, actual observation gaps and overdue wakes, separate from cycle spacing and explicitly unverified execution. The existing dashboard exposes this evidence without backfill or new authority.

### Fixed

- Unfinished liquidation remains continuable; relevant observations and intent resolution synchronize loop lifecycle. Closed observations preserve session identity, late exposure reopens closure work, and approved goal/policy replacement archives the prior loop.
- Snapshot replays and invalid/missing/regressing bars cannot fabricate activity or candle progress. Timing failures preserve accepted financial observations/latches; failed MCP reads differ from processed helper requests that may consume revisions.
- Journal results preserve the operational result, loop/deadlines and source age while advancing only reporting revision/state; missing continuation fields or viewer health never mean execution or completion.

## [1.6.0] - 2026-11-05

### Added

- Responsive, read-only [Ace Account Desk](README.md#local-dashboard) with the approved target, net gain, remaining target, signed percentage, sampled progress chart, account-wide risk and persistent stop/closure state.
- Recorded decision timeline and pending-order details, including reasons for waiting, entry/stop prices, quantities and reported ownership where available. Manual and protective pending orders remain visible; unresolved local intentions and settled requests are not presented as verified fills.
- Isolated `journal` helper command for concise explanations and normalized pending-order details bound to the latest accepted snapshot. Reporting advances the revision without granting dispatch permission or changing financial metrics, source timestamps, approvals, latches, intents or cycle state.
- Versioned display-event metadata containing finalized observation results, including liquidation outcome and shortfall, for current-goal history. Exact decimal values, source age, observation gaps and unavailable legacy information are preserved without backfill.
- Standard-library Python local server with read-only SQLite access, bounded history pagination, fixed static routes, Host/Origin checks and restricted browser responses. The `/api/health` endpoint identifies the workspace/checkpoint without reading account state; Windows listeners use exclusive port binding.
- Synthetic Python and frontend regression tests for reporting isolation, monetary precision, order/intent distinctions, read-only access, startup/reuse, freshness, rendering and persistent stop behavior.

### Changed

- Normal Ace connection, setup, trading and progress sessions automatically start or reuse the matching dashboard through the client's managed background-process facility. Explicit opt-outs and connection-only checks skip startup; unrelated services/checkpoints are not reused or stopped.
- Agent workflows record explanations after actual checks, management and readback/resolution, consuming the journal's returned revision before the next mutation. Dashboard startup and reporting never interrupt preparation/dispatch, delay emergency protection, add trading approvals or serve as a continuous trading guard.
- Checkpoint schema remains version 2: display metadata uses existing state/event JSON, and version-1 checkpoints retain the existing read-only compatibility and next-write normalization. Upgrading does not reset approved limits, goal baselines, observed peaks, stop latches or unresolved actions.

## [1.5.0] - 2026-11-04

### Added

- [Active Order Management](instructions/risk-management.md#active-order-management): Ace-only adaptive cost-aware breakeven/trailing stops, early invalidation exits, invalid pending-entry cancellation and protect-first additions to winners within the original idea's fixed risk allocation.
- Synthetic management scenarios covering broker restrictions, cancellation/fill uncertainty, profit give-back, add-on eligibility and account-wide stop precedence.

### Changed

- Decision-cycle instructions prioritize existing-position and pending-entry management before new exposure, including pending setups far from entry triggers; clarify `check` versus loop-session `cycle` usage.
- Named-account approval and compact reporting explicitly cover management scope, original trade conditions and verified action outcomes without changing the helper, database schema or existing monetary limits.

## [1.4.0] - 2026-11-04

### Added

- Loop sessions: [instructions/loop.md](instructions/loop.md) defines cadence, outage handling, interruption and end conditions for a "keep working until the budget or target" request.
- `cycle` helper command recording one session cycle, the confirmed entry-timeframe bar, the observed gap and the next candle boundary. It replaces `check` during a loop but performs the same observation and latch arithmetic.
- Optional mandate fields `entry_timeframe` (default M15 when absent) and `latch_check_seconds` (default 0, candle-only cadence).

### Changed

- Loop cadence follows the closed candle of the entry timeframe instead of a fixed polling interval; the helper returns `next_cycle_at` including the settle buffer.
- MCP outages are retried indefinitely with backoff and recorded as gaps; they never end a session, advance a cycle, or reuse a previous observation as a fresh snapshot.
- Only an observed loss or target latch ends a session, and only after verified flat exposure. Quiet markets, closed instruments, missing candles and interruptions never end it.
- SQLite checkpoint schema is now version 2. Version 1 files stay readable and migrate in place on the next write without touching anchors, peak, latches, drafts or unresolved intents.

## [1.3.0] - 2026-11-03

### Removed

- The strategy catalogue, `instructions/strategy.md`, and the entire `strategies/` tree including archived backtest runs, methods, reports and temporary working directories.
- All backtesting, evidence-binding, suitability-review, member/composite-playbook and bounded-research-bundle requirements.

### Changed

- Ace now analyses live MT5 MCP market data, discovers the broker's own symbol universe (majors, major minors, metals, oil and commodities, indices, synthetics), and places orders directly to work toward the account-wide target.
- Budget and target remain account-wide and shared by every order; Ace plans multiple independent orders with protective stops instead of committing the allowance to one trade, while still requiring stressed open-plus-pending risk strictly below remaining headroom.
- The mandate is now the approved broker symbol universe plus freshness, safety-margin and permission fields; entry actions require a market `analysis_ref`, broker checks and a protective stop rather than playbook/member attestations.
- The observed-only trailing budget, target latch, whole-account cancellation/closure, persistent latches and the single named-account approval are unchanged.
- README and instruction files no longer describe research-only, strategy or backtest workflows.

## [1.2.0] - 2026-11-03

### Added

- Agent-invoked standard-library Python/SQLite checker at `scripts/account_check.py`, with `draft`, `activate`, `check`, `prepare`, `resolve`, and `status` commands and repository-root `ace_state.sqlite3` as the sole local account checkpoint. The helper performs no networking or trading and is not a continuous guard/service.

### Changed

- Replace required user-supplied strategy selection with Ace-generated adaptive playbooks based on verified market conditions, regimes, sessions, and instrument types; autonomous switching stays inside frozen approved rules.
- Extend eligibility to broker-supported forex, metals, indices, commodities, and crypto with verified economics, costs, calendars, margin and minimum-lot feasibility against actual account equity and remaining monetary headroom.
- Make a positive account-currency monetary trailing-loss budget and profit target the only user-supplied trading settings. Apply them to the full named account, including manual exposure, without percentage-risk or separate capital-allocation questions.
- Trail the highest cash-flow-adjusted equity actually observed while the AI is active by a fixed monetary allowance. Use equity gain since the approved goal baseline, adjusted for external cash flows and incremental closing costs, for target progress; disclose missed peaks/breaches, inactivity and overshoots without promising a cap or return.
- At an observed budget breach including equality, or target trigger, latch off new risk, cancel all account pending entries and close all account positions, including manual exposure. Preserve protective orders until safely closed, verify outcomes, and keep stops latched across reconnects/recovery or final profit below target; same-policy goals preserve risk history.
- Require genuine member and selector/shared-capital composite evidence, all six after-cost metrics, regime/session validation, and exact result/playbook/named-account authorization. Reuse unchanged runs; mark the catalogue historical and discover actual sources rather than infer current absence from old records.
- Delegate one frozen first onboarding research bundle under the actual request, at most three members and one composite across at most three preselected symbols, retaining at least two symbols per test and existing history windows. Record `delegated-onboarding-request` authority instead of inventing setup approval; preserve standalone setup/review boundaries and prohibit hidden retries or optimization.
- Model the selected observation cadence, broker stops, finite inactivity/stress scenarios and whole-account monetary exits in research; neither a profitable result nor delegated research authority approves trading.
- After one final named-account approval covering exact results/playbook, baselines, monetary definitions, both closure mandates and observed-only limitations, permit real documented MCP market/pending orders and approved management after fresh helper preparation, without separate per-trade confirmation. Preserve client permissions, intended-account verification, broker stops/sizing/margin/costs, one local writer and durable pre-dispatch intent/outcome reconciliation; local SQLite is not atomic broker gating.
- Retire and discard root `risk_management.csv` and `risk_management.csv.*` account backups without import, copied approvals/peaks, or future CSV detection/migration/setup gates. Fresh SQLite state is unconfigured; preserve research CSV evidence and existing SQLite anchors, latches, receipts and unresolved intents on resumption. Retiring local records neither closes broker exposure nor authorizes trading.

## [1.1.0] - 2026-11-02

### Added

- Strategy catalogue and AI-executed Python backtesting workflow using read-only MT5 MCP prices, AI-selected symbols, independent symbol tests, and a shared-capital portfolio.
- Standardized profit factor, return percentage, Sharpe ratio, Sortino ratio, maximum drawdown, and monetary total-return reporting.

### Changed

- Store sources at `strategies/<name>.md`, working Python under `strategies/backtests/<name>/temp/<run-id>/`, and archived evidence under `strategies/backtests/<name>/<run-id>/`.
- Allow AI-proposed missing strategy rules and complete test settings, with user approval before execution. Reuse unchanged completed runs; repeated or failed/changed attempts require fresh authorization.
- Require 3-6 evaluation months below H4 and at least 12 months for H4 and higher, plus separate indicator warm-up.
- Separate goal/progress and strategy/backtesting instructions. Onboarding now lists strategies for selection, returns per-strategy results, and awaits explicit account authorization before protection checks and compliant autonomous orders.

## [1.0.0] - 2026-11-02

### Added

- Client-neutral MT5 MCP connection, risk-management, goal, and strategy instructions.
- Simple README with setup guidance and a transparent Ace logo.
- `VERSION` file tracking the instruction-set version.
