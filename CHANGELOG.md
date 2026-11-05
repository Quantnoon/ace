# Changelog

## [Unreleased]

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
