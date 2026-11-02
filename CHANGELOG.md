# Changelog

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
