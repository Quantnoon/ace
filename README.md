<p align="center">
  <img src="assets/logo.png" alt="Ace hat logo" width="100">
</p>

# Ace

Client-neutral instructions for an AI agent that analyses markets and trades a MetaTrader 5 (MT5) account through an MT5 Model Context Protocol (MCP) server, with a small Python/SQLite account checker. You supply a monetary trailing-loss budget and a profit target; the agent reads the market itself and decides which orders to place. The mandate covers the whole named account, including manual exposure.

Version: **[1.4.0](VERSION)** | [Changelog](CHANGELOG.md)

## Getting Started

1. Load [AGENTS.md](AGENTS.md) in your AI client if it is not discovered automatically.
2. Have the client read all four instruction files below before every trading session.
3. Make Python 3.10+ and its standard-library SQLite support available to the client for local helper execution. No database server, installed service, or network-enabled Python trading bridge is needed.
4. Connect an existing MT5 MCP server through your client's secure setup. Keep credentials outside this repository and out of chat; execution still follows the client's tool permissions.
5. Ask the client to connect to the MT5 MCP to begin onboarding. A request to "only check the connection" remains read-only and does not start setup.

The whole flow: connect and verify the account -> give one budget and one target -> Ace discovers the broker's instruments and analyses current conditions through MCP -> one approval of the named account and limits -> Ace places and manages as many qualifying orders as fit the remaining budget -> at either trigger it cancels pending entries and closes every position.

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

Trading begins only after one approval naming the exact login/server/demo-live type/currency, both amounts, the approved symbol universe, the current market read, the Ace-only management rules, and both whole-account closure mandates. After that, qualifying actions need no separate per-trade confirmation, subject to client tool permissions. Routine management does not adopt manual trades or silently expand old approvals. Stops are adjusted only while the AI is active, not by a continuous trailing service; these management judgments remain the agent's responsibility, not independent Python enforcement.

## Local Checker

The agent obtains actual MT5 account/exposure/history data and passes verified snapshots to `scripts/account_check.py`. The helper uses Python's standard library and defaults to repository-root `ace_state.sqlite3`, independent of the caller's directory. It performs no networking or trading, does not authenticate supplied facts or approval, and runs only when invoked. Follow the [exact command, JSON, and SQLite contract](instructions/risk-management.md), rather than inventing inputs or editing SQL.

| Command | Role |
| --- | --- |
| `draft` | Save account-bound monetary drafts without approving trading or resetting an active policy. |
| `activate` | Record a genuinely approved, reconciled mandate; preserve same-policy risk anchors for a new goal, and require explicit approval for a replacement policy. |
| `check` | Record a verified snapshot, update the observed peak and persistent stop latches, and report arithmetic/blockers/required actions. |
| `prepare` | Recheck fresh inputs and durably record the exact intended MCP action before dispatch, reserving risk locally when applicable. |
| `resolve` | Reconcile verified broker outcomes, retaining uncertainty instead of assuming a timeout means failure. |
| `cycle` | Record one loop-session cycle and the next entry-timeframe candle boundary; ends a session only on a monetary latch. |
| `status` | Read saved state with its original timestamps, not current MT5 verification. |

Each active decision cycle includes a current snapshot and `check` (`cycle` instead during a loop), even without an entry signal. Monetary latches and required management of existing positions/pending entries take priority over additions. An eligible action uses fresh `prepare` -> the actual MCP call -> verified fill/stop/volume or cancellation/closure readback -> `resolve`. Local transactions and one local writer prevent conflicting reservations in this database, not manual trading, copied-repository conflicts, account switches, or the check-to-dispatch race. SQLite is not atomic broker gating or an independent continuous guard.

The SQLite file is the sole local account checkpoint and must stay private. A missing database is unconfigured, never an approved reset. Root `risk_management.csv` and `risk_management.csv.*` account backups are retired and discarded without import; do not recreate, detect, read, migrate, depend on, or ask about them during onboarding, or copy old approvals/peaks into fresh state.

## Loop Sessions

"Keep working until the budget or the target is hit" is a [loop session](instructions/loop.md), not a background service. Ace records each cycle with `cycle`, wakes at the next closed candle of the approved entry timeframe instead of a fixed polling interval, and retries MCP outages with a 5/10/20/30-second backoff instead of stopping. A session never ends because the market is quiet, the instrument is closed, or an outage occurred: only an observed loss or target latch ends it, and only after the account is verified flat. When the client stops executing turns the session is recorded as interrupted with an explicit gap, and the next run resumes it — nothing claims to be watching the account in between.



- The fixed-money budget trails the highest cash-flow-adjusted equity actually observed since policy approval. It is not a starting-equity floor, cumulative losing-trade total, or daily allowance. The target is additional account equity gain since its approved baseline, adjusted for external cash flows and estimated incremental closing costs not already reflected in equity.
- All account equity, costs, manual exposure and pending orders count, even when equity greatly exceeds the budget. The budget is not segregated capital. Broker stops and verified economics/sizing/margin are mandatory; existing stressed exposure plus proposed risk, costs exactly once and a safety margin must be strictly below remaining monetary headroom. Equality or an unaffordable minimum lot means no entry, not greater leverage or wider stops.
- At observed drawdown greater than or equal to the budget, or estimated net liquidation gain greater than or equal to the target, stop new risk, cancel all account pending entries and close ALL account positions under the approved mandate. Preserve protective orders until their positions are safely closed, reconcile late fills/orphans, and verify outcomes. Loss-stop handling takes precedence if both triggers apply.
- Both stops persist across reconnects, new days, equity recovery and corrections. Final profit below target does not resume trading: report the trigger, pending closure, verified final result and shortfall separately. A same-policy new goal preserves the observed risk peak and cannot release a loss latch; a risk reset needs explicit replacement-policy approval.
- There is NO independent continuous guard/service. Only snapshots supplied while the AI is active check the monetary limits. Missed peaks/breaches, price gaps, slippage, inactivity and closure delays can produce overshoots; neither cap, target return nor completion time is guaranteed.
- Unknown/stale data, invalid state, missing helper, uncertain execution or absent authority blocks new exposure. Do not blindly retry an ambiguous order. Previously authorized identity-verified emergency reductions must not wait for a database repair or an entry signal; actual tool permissions and safe broker targeting still apply.
