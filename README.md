<p align="center">
  <img src="assets/logo.png" alt="Ace hat logo" width="180">
</p>

# Ace

Client-neutral instructions for forex trading through a MetaTrader 5 (MT5) Model Context Protocol (MCP) server.

Version: **[1.0.0](VERSION)** | [Changelog](CHANGELOG.md)

## Getting Started

1. Load [AGENTS.md](AGENTS.md) in your AI client if it is not discovered automatically.
2. Have the client read all three instruction files below before every trading session.
3. Configure an existing MT5 MCP server through your client's secure setup. Keep credentials outside this repository and out of chat.
4. Ask the client to connect to the MT5 MCP to begin onboarding.

Onboarding order: verify connection and account -> risk limits -> profit target -> exact strategy -> explicit account approval -> protection verification.

## Instructions

- [MT5 Connection](instructions/mt5-connection.md)
- [Risk Management And CSV Contract](instructions/risk-management.md)
- [Goals, Progress, And Strategy](instructions/goals-and-strategy.md)

## Safety

- This is an instruction set, not a trading application, MCP server, built-in strategy, or always-running bot.
- Autonomous entries require explicit account approval, protective stops, and a verified independent MT5/MCP-side continuous risk guard. This repository does not implement that guard.
- Risk limits override profit targets. Returns and hard loss caps are not guaranteed.
- `risk_management.csv` is local-only and Git-ignored. Never store credentials in it; follow the CSV contract linked above.
