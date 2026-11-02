<p align="center">
  <img src="assets/logo.png" alt="Ace hat logo" width="100">
</p>

# Ace

Client-neutral instructions for forex trading through a MetaTrader 5 (MT5) Model Context Protocol (MCP) server.

Version: **[1.1.0](VERSION)** | [Changelog](CHANGELOG.md)

## Getting Started

1. Load [AGENTS.md](AGENTS.md) in your AI client if it is not discovered automatically.
2. Have the client read all four instruction files below before every trading session.
3. Configure an existing MT5 MCP server through your client's secure setup. Keep credentials outside this repository and out of chat.
4. Ask the client to connect to the MT5 MCP to begin onboarding.

Onboarding order: verify connection/account -> risk limits -> profit goal -> list/select available strategies -> reuse a completed result or approve and execute a backtest -> results per strategy -> final autonomous-trading confirmation -> protection verification -> compliant orders.

## Instructions

- [MT5 Connection](instructions/mt5-connection.md)
- [Risk Management And CSV Contract](instructions/risk-management.md)
- [Goals And Progress](instructions/goals.md)
- [Strategy Catalogue And Backtesting](instructions/strategy.md)

## Strategies And Backtests

Supplied strategies live in `strategies/<name>.md`. Use the same filename stem, including case, for `strategies/backtests/<name>/`. Sources can contain English ideas, indicator code, or incomplete rules; entry and exit conditions are not required at submission. The [strategy catalogue](instructions/strategy.md) lists available sources, fingerprints, results, and review states. After risk and goal setup, Ace lists strategies and lets you select those to evaluate rather than choosing a trading strategy or testing every one automatically.

For a selected strategy without reusable results, Ace proposes missing entry/exit, stop, sizing, and operational rules consistent with the supplied source. It selects multiple suitable verified broker symbols; you do not need to supply a symbol list. You approve the completed rules and one full research setup before testing. Historical prices come from documented read-only MT5 MCP tools, and Ace generates and actually executes deterministic Python under `strategies/backtests/<name>/temp/<run-id>/`. Missing tools/data or unapproved assumptions block the test, not produce an AI-estimated result.

| Primary Entry / Signal Timeframe | Backtest Evaluation History |
| --- | --- |
| Below H4, including H1 | 3-6 calendar months |
| H4, daily, or higher | At least 12 calendar months |

Indicator warm-up is additional. Each strategy's fixed run tests symbols independently and simulates a separate shared-capital portfolio. Results per strategy show **profit factor, return %, Sharpe ratio, Sortino ratio, maximum drawdown, and total return** for each symbol and the portfolio, with costs, dates, exposure, and limitations. Return % is cumulative equity growth; total return is the corresponding monetary equity gain/loss in the approved modeled currency.

An unchanged verified completed run is reused, not automatically repeated or refreshed on reconnect, elapsed time, or changed goals/risk limits. Another completed-run execution requires your explicit request. Failed/incomplete attempts or changed rules/settings may receive another proposed and approved attempt; old approval never permits a retry loop. The saved interval stays visible, and completion is not result approval or account authorization.

Evidence is archived at `strategies/backtests/<name>/<run-id>/`: complete source/rules, configuration, exact executed Python, report, metrics, and auditable trade/equity outputs. The strategy's `temp/` directory is separate from these durable run directories and can be cleaned only after verified archival. Sanitized artifacts are shareable; restricted data and review provenance stay in the run's ignored `private/`. Credentials remain outside the repository entirely.

After results, choose the exact strategy/run and review the full account/risk/goal/result summary. One explicit final confirmation can approve that result and authorize autonomous compliant orders on the named account, but only if the question clearly requests both. All risk/protection gates still apply; confirmation does not force an immediate order. Standalone strategy research/review never starts account onboarding or authorizes orders.

## Safety

- This is an instruction set, not a trading application, permanent backtesting engine, MCP server, built-in strategy, or always-running bot.
- Autonomous entries require a verifiably reviewed strategy/backtest, explicit account approval, protective stops, and a verified independent MT5/MCP-side continuous risk guard. This repository does not implement that guard.
- Risk limits override profit targets. Returns and hard loss caps are not guaranteed.
- `risk_management.csv` is local-only and Git-ignored. Never store credentials in it; follow the CSV contract linked above.
