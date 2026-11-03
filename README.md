<p align="center">
  <img src="assets/logo.png" alt="Ace hat logo" width="100">
</p>

# Ace

Client-neutral instructions for adaptive trading through a MetaTrader 5 (MT5) Model Context Protocol (MCP) server, with a small Python/SQLite account checker. You supply a monetary trailing-loss budget and profit target; Ace chooses strategies and sizing from verified market conditions and instrument economics. The mandate covers the whole named account, including manual exposure.

Version: **[1.2.0](VERSION)** | [Changelog](CHANGELOG.md)

## Getting Started

1. Load [AGENTS.md](AGENTS.md) in your AI client if it is not discovered automatically.
2. Have the client read all four instruction files below before every trading session.
3. Make Python 3.10+ and its standard-library SQLite support available to the client for local helper execution. No database server, installed service, or network-enabled Python trading bridge is needed.
4. Configure an existing MT5 MCP server through your client's secure setup. Keep credentials outside this repository and out of chat; execution still follows the client's tool permissions.
5. Ask the client to connect to the MT5 MCP to begin onboarding. A request to "only check the connection" remains read-only and does not start setup.

Onboarding order: verify connection/account -> supply budget and target together -> Ace's assessment and reused evidence or one bounded research bundle -> exact results and playbook proposal -> one final named-account approval -> fresh helper checks and real MCP orders/management. There is no separate setup-approval question for the first delegated onboarding bundle and no separate user confirmation for each eligible trade after final approval.

Budget and target are the only user-supplied trading settings. For example, `5 USD` and `15 USD` are monetary amounts, not defaults or percentages; the currency must match the verified account. Ace fetches account facts through MCP and asks only for missing or ambiguous amounts/currency, not a capital allocation or routine strategy/symbol choice. Supplying money amounts does not approve an account or place an order.

## Instructions

- [MT5 Connection](instructions/mt5-connection.md)
- [Monetary Risk And SQLite/Helper Contract](instructions/risk-management.md)
- [Goals And Progress](instructions/goals.md)
- [Adaptive Strategies And Backtesting](instructions/strategy.md)

## Strategies And Backtests

Ace assesses broker-supported forex, metals, indices, commodities, and crypto, excludes unsuitable or unaffordable instruments, and proposes a finite set of generated or reusable hypotheses. Optional supplied sources may contain ideas, code, or incomplete rules; they remain inert research data. Member and composite-playbook sources live in `strategies/<name>.md`, using the same filename stem for `strategies/backtests/<name>/`. The [historical catalogue](instructions/strategy.md#strategy-catalogue) is not a current inventory: discover actual sources and verify evidence before reuse. Missing historical records do not prove that all current sources are absent or require you to supply a strategy.

The playbook contains full member entry/exit/protection/sizing rules plus a frozen regime/session selector and shared-capital allocator, transitions, order ownership, no-trade states, and suitability criteria. Onboarding first reuses verified results. If new evidence is needed, the actual onboarding request delegates one bundle of at most three candidate members and one composite across at most three preselected symbols, retaining at least two suitable symbols per test. Before results, Ace freezes the full setup, rules, dates, modeled capital/currency, monetary checks and observation cadence, costs, allocator, acceptance criteria, and finite validation/inactivity/stress cases. Its authority is recorded as `delegated-onboarding-request`, not a fabricated user setup approval.

Historical prices come through documented read-only MT5 MCP tools; Ace generates and actually executes deterministic Python under `strategies/backtests/<name>/temp/<run-id>/`. The simulations exercise observed monetary checks, broker stops, inactivity gaps, and whole-account stop/target exits, not a nonexistent continuous guard. Missing essential tools/data or unresolved modeling assumptions block the affected test, not produce an AI-estimated result.

| Member Entry / Signal Timeframe | Backtest Evaluation History |
| --- | --- |
| Below H4, including H1 | 3-6 calendar months |
| H4, daily, or higher | At least 12 calendar months |

Indicator warm-up is additional. An entirely sub-H4 composite uses 3-6 months; one containing H4+ members uses at least 12 common months, explicitly allowing longer lower-timeframe coverage inside that composite. Each member and the actual selector/composite tests symbols independently and simulates its own shared-capital portfolio. Member results or their average cannot validate adaptive allocation. Reports show **profit factor, return %, Sharpe ratio, Sortino ratio, maximum drawdown, and total return** per symbol/portfolio, plus regime/session samples, costs, exposure, suitability outcomes and limitations. Return % is cumulative marked-equity growth; total return is the corresponding modeled-currency gain/loss, never account goal progress.

Unchanged verified member/composite runs are reused, not repeated or refreshed on reconnect, elapsed time, new regime observations, or changed goals/budgets. Failed/incomplete attempts or genuinely changed rules/settings require a new explicit research request and applicable setup authorization; running/unknown attempts must be reconciled, not duplicated. Old receipts and onboarding delegation never permit hidden optimization or retry loops. Saved periods remain visible, and execution completion or suitability alone is not result review/account authorization.

Evidence is archived at `strategies/backtests/<name>/<run-id>/`: full source/rules and member/controller bindings, configuration, exact executed Python, report, metrics and auditable trade/equity/selection traces. `temp/` is separate and cleaned only after verified archival. The entire backtests tree is Git-ignored; sanitized artifacts may be explicitly shared when permitted, but restricted data and review provenance remain private. Credentials stay outside the repository entirely. Sharing does not automatically commit or push anything.

After results, Ace recommends one exact eligible playbook. The single final confirmation presents the exact login/server/demo-live type/currency, budget and target definitions, starting equities/cash-flow anchors/observed peak with timestamps, full stored English member/controller rules, all pinned results/evidence, broker symbols, and normal management permissions. It explicitly requests review of those exact results and autonomous execution, including account-wide cancellation and closure at either monetary trigger, even for manual exposure. It also discloses observed-only checks, inactivity and overshoot risks, and no guaranteed cap or return. New results remain unreviewed until that confirmation; failed suitability means no trading.

After approval and fresh successful preparation, Ace may place real market/pending orders and perform approved modifications, cancellations, and closes through documented MCP tools without another per-trade user confirmation. Ace may select/switch only among frozen approved members; new members, material rules/thresholds, symbols, versions, or substituted runs need fresh applicable evidence/review/account approval. Client tool permissions still apply. No eligible signal or affordable minimum lot means no trade.

Standalone strategy generation, market assessment, backtesting or result review is research: read-only MCP data access, explicit setup approval before a new test and exact result review afterward, no account database initialization/update, and no orders. Research authority and result review never substitute for named-account trading authority.

## Local Checker

The agent obtains actual MT5 account/exposure/history data and passes verified snapshots to `scripts/account_check.py`. The helper uses Python's standard library and defaults to repository-root `ace_state.sqlite3`, independent of the caller's directory. It performs no networking or trading, does not authenticate supplied facts or approval, and runs only when invoked. Follow the [exact command, JSON, and SQLite contract](instructions/risk-management.md), rather than inventing inputs or editing SQL.

| Command | Role |
| --- | --- |
| `draft` | Save account-bound monetary drafts without approving trading or resetting an active policy. |
| `activate` | Record a genuinely approved, reconciled mandate; preserve same-policy risk anchors for a new goal, and require explicit approval for a replacement policy. |
| `check` | Record a verified snapshot, update the observed peak and persistent stop latches, and report arithmetic/blockers/required actions. |
| `prepare` | Recheck fresh inputs and durably record the exact intended MCP action before dispatch, reserving risk locally when applicable. |
| `resolve` | Reconcile verified broker outcomes, retaining uncertainty instead of assuming a timeout means failure. |
| `status` | Read saved state with its original timestamps, not current MT5 verification. |

Each active decision cycle includes a current snapshot and `check`, even without an entry signal. An eligible action uses fresh `prepare` -> the actual MCP call -> verified fill/stop/volume or cancellation/closure readback -> `resolve`. Local transactions and one local writer prevent conflicting reservations in this database, not manual trading, copied-repository conflicts, account switches, or the check-to-dispatch race. SQLite is not atomic broker gating or an independent continuous guard.

The SQLite file is the sole local account checkpoint and must stay private. A missing database is unconfigured, never an approved reset; maintenance, tests, and standalone research must not create live account state. Root `risk_management.csv` and `risk_management.csv.*` account backups are retired and discarded without import. Do not recreate, detect, read, migrate, depend on, or ask about them during onboarding, or copy old approvals/peaks into fresh state. Research CSV trade/equity/decision artifacts remain evidence. Discarding local records neither closes broker exposure nor authorizes trading.

## Safety

- The fixed-money budget trails the highest cash-flow-adjusted equity actually observed since policy approval. It is not a starting-equity floor, cumulative losing-trade total, or daily allowance. The target is additional account equity gain since its approved baseline, adjusted for external cash flows and estimated incremental closing costs not already reflected in equity.
- All account equity, costs, manual exposure and pending orders count, even when equity greatly exceeds the budget. The budget is not segregated capital. Broker stops and verified economics/sizing/margin are mandatory; existing stressed exposure plus proposed risk, costs exactly once and a safety margin must be strictly below remaining monetary headroom. Equality or an unaffordable minimum lot means no entry, not greater leverage or wider stops.
- At observed drawdown greater than or equal to the budget, or estimated net liquidation gain greater than or equal to the target, stop new risk, cancel all account pending entries and close ALL account positions under the approved mandate. Preserve protective orders until their positions are safely closed, reconcile late fills/orphans, and verify outcomes. Loss-stop handling takes precedence if both triggers apply.
- Both stops persist across reconnects, new days, equity recovery and corrections. Final profit below target does not resume trading: report the trigger, pending closure, verified final result and shortfall separately. A same-policy new goal preserves the observed risk peak and cannot release a loss latch; a risk reset needs explicit replacement-policy approval.
- There is NO independent continuous guard/service. Only snapshots supplied while the AI is active check the monetary limits. Missed peaks/breaches, price gaps, slippage, inactivity and closure delays can produce overshoots; neither cap, target return nor completion time is guaranteed.
- Unknown/stale data, invalid state, missing helper, uncertain execution or absent authority blocks new exposure. Do not blindly retry an ambiguous order. Previously authorized identity-verified emergency reductions must not wait for a database repair or an entry signal; actual tool permissions and safe broker targeting still apply.
