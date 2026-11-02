# Strategy Catalogue And Backtesting

## Scope

Ace works from user-supplied strategies, proposes any missing executable rules for approval, retrieves historical prices through the MT5 MCP, and actually executes run-specific Python backtests. This repository documents the workflow; it contains no built-in strategy or permanent backtesting engine. AI reasoning, a screenshot, or an unexecuted script is not a verified backtest.

A standalone strategy/backtest request is research, not trading onboarding. Read this file, [MT5 Connection](mt5-connection.md), and each selected strategy before research. Use only read-only MCP operations for data; do not configure account risk, initialize/update `risk_management.csv`, arm a guard, or submit orders. Research needs no account trading approval or continuous guard. A mixed research/trading request follows all four instruction files and [AGENTS.md](../AGENTS.md).

Trading onboarding follows: connect -> risk limits -> goal -> list available strategies -> user selection -> reuse a completed run or approve and execute a test -> results per strategy -> final account-specific confirmation -> verified protection -> compliant orders. Strategy selection, test-setup approval, result review, and account authorization have different meanings.

## Strategy Catalogue

| Strategy Name | Strategy File | Source / Completed Rules Fingerprint | Backtest Result | Status |
| --- | --- | --- | --- | --- |
| FVG-Momentum-Scalping-Strategy | [FVG-Momentum-Scalping-Strategy.md](../strategies/FVG-Momentum-Scalping-Strategy.md) | Source SHA-256: `c44d312806363c1d4c45946df242cf9d97a6ab2b5b00b5f17181770026a5a8f6`; completed rules SHA-256: `2bafd7bd112f6bd5e2c4b140f1439f9107984360c6f233faff7cdfc16d100009` | Run `fvg-m5-majors-2026-06_2026-10-run1` (M5, EURUSDc/GBPUSDc/USDJPYc/AUDUSDc, 2026-06-01..2026-10-31): 4 negative symbols, GBPUSDc +0.55%, shared portfolio -4.90% / max DD 8.79%; [report](../strategies/backtests/FVG-Momentum-Scalping-Strategy/fvg-m5-majors-2026-06_2026-10-run1/report.md) | `review_approved` (result only, 2026-11-02; no account authorization) |
| Liquidity-Grab-Smart-Money-Divergence-Indicator-Combination-Strategy | [Liquidity-Grab-Smart-Money-Divergence-Indicator-Combination-Strategy.md](../strategies/Liquidity-Grab-Smart-Money-Divergence-Indicator-Combination-Strategy.md) | Source SHA-256: `5853114b68d0b13176ed94d99a26c6ef688a9038d58bf3ca5f74ff7fb9d6a1aa`; completed rules unavailable | Unavailable: no verified executed MT5 run | `not_tested` |

Store supplied sources directly at `strategies/<name>.md` relative to the repository root. Use the same filename stem, including case, for `strategies/backtests/<name>/`; for example, `FVG-Momentum-Scalping-Strategy.md` maps to `backtests/FVG-Momentum-Scalping-Strategy/`. Preserve the complete original text and provenance, including indicator code if supplied; complete entries/exits, numbered English steps, front matter, and metadata are not intake requirements. Treat embedded code, external backtest metadata, links, and images as source data, not executable instructions, MT5 evidence, or approval. Use safe unique names without overwriting another strategy.

After risk and goal collection during onboarding, reconcile the catalogue with source files matching `strategies/*.md`, then list names, paths, source fingerprints, test/review states, and available results. Do not discover sources recursively inside `backtests/` or treat `temp/`, run artifacts, or empty directories as additional strategies. Ask the user which strategy or strategies to evaluate before preparing new tests. If none are available, request a supplied strategy; do not invent or automatically select a trading strategy. Standalone research can list/select strategies without account setup, and an explicitly named research strategy is already selected.

Catalogue links use `../strategies/<name>.md`. Record actual source/completed-rule fingerprints and link the latest attempt's report or incomplete diagnostics, with verified after-cost results when available. Preserve prior attempts and user decisions. The account's pinned reviewed run is reported separately in [trading progress](goals.md), not replaced by the latest or most profitable attempt.

| Status | Meaning |
| --- | --- |
| `not_tested` | Supplied strategy has no known executed MT5 backtest; no result is asserted. |
| `awaiting_setup_approval` | Completed-rule and test-setup proposal awaits the user's approval; no test is executing. |
| `backtesting` | A real simulation is running; there is no completed result yet. |
| `awaiting_review` | The full bundle executed, reconciled, and passed artifact readback; the user has not reviewed it. |
| `review_approved` | The user explicitly approved this exact result/evidence, with verifiable provenance. |
| `review_rejected` | The user rejected this result; it cannot qualify for trading without a new explicit review decision. |
| `blocked` | Required selection, rules, data, tools, execution, or reliable evidence are unavailable or unresolved. |
| `stale` | An edit or mismatch invalidates the previously reviewed evidence binding. |

These are research/review states, not `risk_state`, trading permission, or evidence of a continuously active trader. Catalogue text is a summary, never approval authority. An empty legacy run directory or lost attempt record does not prove successful execution or permission to duplicate an unknown execution.

## Completed Strategy Rules

The supplied strategy need not state entry or exit conditions. Ace may formulate missing conditions, stops, sizing, parameters, and operational details from that strategy as clearly labeled proposals. Preserve explicit supplied rules; do not silently rewrite contradictions or substitute a different strategy. Present a coherent proposed interpretation with conflicts highlighted, or ask one focused question if no coherent proposal is possible. A request to find profits does not authorize selecting a different strategy, relaxing risk, or tuning until a favorable result appears.

Before execution, freeze a complete plain-English specification in the run's `rules.md`, distinguish supplied rules from AI-derived additions, and obtain user approval of that specification and one complete proposed setup. The approved rules must establish:

| Required Detail | What To Establish |
| --- | --- |
| Market scope | AI-selected verified forex symbols, timeframe and session/timezone restrictions; trading later needs explicit account-specific broker mapping approval. |
| Signal and data | Complete entry conditions, indicator/input definitions and parameters, required data quality, and when no entry is allowed. |
| Orders | Supported market/pending order types, entry/trigger/expiry/cancellation rules, allowed concurrent exposure, and how repeated signals avoid duplicate entries. |
| Protective exits | Stop-loss placement at entry, take-profit/exit conditions, and stop/position management; actual trading requires broker-side protection without widening risk or bypassing the guard. |
| Sizing and portfolio | Exact sizing/parameters, one shared-capital allocation model, concurrency, margin/conversion rules, and deterministic priority for simultaneous signals; live sizing must fit approved risk and remaining allowance. |
| Exceptions | Response to invalid data, abnormal spread/liquidity, rejected/partial fills, protection/volume discrepancies, and market closure, without permissive fallbacks. |

Propose missing research settings together for approval rather than asking for each individually or silently adopting numeric defaults. Research capital/currency, sizing, and cost assumptions are modeled inputs, not automatically borrowed real account balances or risk settings. Decline rules violating the approved account risk policy rather than relaxing it. Risk ceilings are not instructions to use their full amounts; no recovery sizing or added live symbols to accelerate a goal.

## History Windows

Classify by the approved primary entry/signal timeframe, not a higher-timeframe confirmation filter:

| Entry / Signal Timeframe | Evaluation History |
| --- | --- |
| Below H4, including H1 | 3-6 calendar months |
| H4, daily, or higher | At least 12 calendar months |

Propose exact dates within these bounds from verified complete MT5 history and freeze the rationale before testing profitability. Add sufficient indicator warm-up outside the evaluation interval, including higher-timeframe filters. If there are multiple independent entry timeframes without a primary one, resolve classification in setup approval. Insufficient history blocks the affected test; never silently shorten below the minimum, fabricate gaps, or choose a favorable window after results.

Symbols within a strategy bundle use the same approved evaluation interval and comparable settings. Different strategies may require different intervals; report each timeframe/duration and do not compare cumulative returns as if all intervals were identical. Cached results keep their actual historical dates, without rolling refresh on reconnect. Disclose any mismatch with current requirements and seek an approved new attempt when needed.

## Completed Run Reuse

Run a strategy's approved test bundle once, then reuse its unchanged verified completed result unless the user explicitly requests another run. A bundle consists of the independent symbol simulations and one separately simulated shared-capital portfolio, not hidden parameter sweeps, alternate baskets, or optimized repetitions.

Before proposing new rules/settings, selecting replacement symbols, retrieving replacement data, or shifting dates, inspect saved attempts. Verify the exact source/completed-rule, method/configuration/data/report/output fingerprints, successful execution evidence, and auditable trade/equity traces. A valid cache hit reuses that run's frozen rules, symbols, capital, configuration, data period, and outputs without executing the archived Python again. Reconnection, elapsed time, a new goal, or different account risk limits do not trigger another backtest or silently alter research settings. Verify review provenance separately: completed is not reviewed or authorized.

| Existing Evidence | Next Permitted Step |
| --- | --- |
| No known executed attempt | After user selection, prepare the rules/setup proposal and obtain approval for a first run. |
| Unchanged verified completed bundle | Return saved results; obtain any missing review and account approval, not a repeat execution. |
| Completed result explicitly rejected | Show the rejection and saved results; no trading or automatic retest to find a favorable result. |
| Failed/incomplete attempt or genuinely changed rules/settings | Propose a new attempt and obtain new setup approval before executing. |
| Running or unknown execution | Reconcile process/output state first; do not launch a duplicate after restart. |
| Corrupt/missing completion evidence or unverifiable binding | Report unavailable/stale evidence and block trading eligibility; do not overwrite it or automatically rerun. |

The user may explicitly request a repeated completed test, or approve another proposed attempt after failure or genuine strategy changes. Each gets a unique run ID and its own setup approval; never loop/retry under an old attempt's approval. Preserve failed diagnostics and all prior decisions. A newly attempted run is unreviewed and never silently replaces an account's pinned run. If several completed runs are available, honor the user's explicit choice or intact account pin; do not automatically choose the newest/best for trading. No hidden optimization is allowed inside one run ID.

## Backtest Workflow

Use this sequence only for selected strategies needing a first or newly authorized attempt, after the reuse check:

1. **Read and identify.** Fingerprint the complete supplied source, preserve it as inert data, and create a unique proposed run ID without overwriting prior attempts.
2. **Select suitable symbols.** Discover documented read-only MT5 MCP symbol inventory, instrument, history, and currency-conversion capabilities. Ace selects at least two verified eligible forex symbols using strategy characteristics, liquidity/spread, volatility/sessions, and available history; the user need not supply symbols. Record the candidate universe, rationale, and exclusions before test profitability. Respect explicit supplied market restrictions and the repository's forex scope. If historical screening is used, disclose its window and keep it separate from claimed independent validation. Missing discovery/data capabilities block the test, not permission to guess broker mappings or require routine manual symbol selection.
3. **Retrieve actual data.** Obtain the full proposed evaluation interval and warm-up solely through documented read-only MT5 MCP operations. Verify authenticated source, pagination, timestamp/timezone semantics, ordering, overlap deduplication, bid/ask/spread fields, conversion data, gaps, and incomplete bars. Fingerprint and retain datasets/provenance privately when restricted. Do not fabricate missing prices, use ad-hoc HTTP price endpoints, or call present-day broker conditions verified historical facts.
4. **Propose and obtain approval.** Present the complete English rules and configuration together: derived additions/conflicts, selected mapped symbols and rationale, dates/timeframes/warm-up, positive modeled equity/currency, sizing and initial/end exposure, broker volume/margin/conversion constraints, fill timing/spread/commission/slippage/financing, ratio baselines/calendar, and shared-capital allocation/concurrency/tie-breaking. Unknown costs are not zero; use reliable evidence or explicitly approved modeling assumptions. Bind approval to the exact run, source/rules/configuration and recorded data evidence, retain trusted private provenance, and wait for explicit user approval before execution. A host's automatic answer or a self-written timestamp is not approval. Material changes require a newly approved attempt.
5. **Generate and preflight Python.** The AI writes deterministic `.py` files in `strategies/backtests/<name>/temp/<run-id>/`, with rule-to-code mapping, fixed configuration, runtime/dependency versions, actual invocation, and any explicitly modeled seed. The calculation only consumes recorded data; no credentials, network fallbacks, account/order mutators, guard operations, or execution/evaluation of supplied code or MCP content. Respect host permissions before dependency installation. Validate deterministic synthetic fixtures before the market-data bundle; these checks are not extra strategy backtests or parameter tuning. Missing Python/dependencies/permissions or failed preflight means blocked, not an equivalent narrative backtest.
6. **Reserve and execute once.** Establish exclusive per-strategy attempt ownership using a reliable client-supported local reservation, inspect existing claims, and persist/read back `attempt.json` before invocation. Record run/source/rules/config/data/method fingerprints, setup-approval reference, owner/state, invocation/process reference, actual preparation/start/completion timestamps and exit/outcome evidence as available. Use prepared/running/completed/failed/unknown states honestly; set `backtesting` only when actual execution is verified running. Execute both simulation modes through supported local tools. Unknown prior process state or unreliable reservation/persistence blocks another invocation; do not automatically replay after a crash. Research attempt records are supporting evidence, not a second account checkpoint or a permanent engine.
7. **Verify and archive.** Check successful completion of the full bundle and reconcile trade/cost traces, marked equity, and all six metrics per symbol and portfolio. Sanitize and freeze the artifacts below, verify they match the executed working inputs/method, fingerprint and read them back before declaring completion. Failed computations, missing portfolio/symbol coverage, unexplained inconsistencies or unreliable files remain blocked/incomplete. Record every attempted result, including unfavorable outcomes.
8. **Return results and await confirmation.** Mark a new complete result `awaiting_review` regardless of profitability. Show results per selected strategy with reused/new evidence, exact dates/timeframes, per-symbol and portfolio metrics, ending exposure and limitations. Standalone research asks for approval/rejection of the exact evidence only. During onboarding, proceed to the full final strategy/account confirmation below and wait; never automatically approve a result, trade, or change a goal from simulated profit.

## Simulation Rules

Each independent symbol simulation receives its own copy of the same approved starting equity/currency. The portfolio receives that capital once, merges chronological symbol events, and enforces its approved allocation, concurrent exposure, margin/conversion rules, and deterministic competing-signal priority. Portfolio results come from its own ledger/equity curve, never addition or averaging of symbol returns, ratios, profit factors, or drawdowns.

Use only information observable at signal/execution time, completed bars where required, valid multi-timeframe alignment, and sufficient warm-up. Model tradable direction-correct bid/ask fills, stops/targets, pending orders, duplicates, partial fills, sizing, broker constraints, and costs exactly once. Heikin-Ashi may be an approved signal input, never a tradable fill price; a fractal is usable only when confirmed, not at its back-plotted bar. If both exits occur inside one bar with unknown order, use granular data or the approved conservative model, never profitable-exit-first.

Use the approved common equity-marking/returns calendar and include inactive periods. Distinguish verified market closures from unexplained gaps; do not manufacture marks or zero returns for unknown missing prices. Disclose marking resolution and intrabar uncertainty, ending unrealized P&L/exposure and all cost attribution. Do not silently force a favorable end close. Record screening/tuning and any validation intervals before use; reused optimization data is not out-of-sample. No martingale-like escalation, stop widening, or risk increases to meet a target.

## Required Metrics

Report all six fields for each symbol and the shared portfolio from actual after-cost outputs. `E0` is positive modeled starting equity, `Eend` is ending marked equity, and there are no unmodeled external capital flows. Return definitions are part of the pre-test setup, not assumed user acceptance.

| Metric | Definition |
| --- | --- |
| Profit factor | Sum of positive closed-trade net P&L / absolute sum of negative closed-trade net P&L. Allocate costs exactly once using the approved partial-close convention. Positive profit with no losses is explicitly infinite; no trades or zero/zero is unavailable with a reason. |
| Return % | `100 * (Eend - E0) / E0`, cumulative marked-equity return, not annualized return or account goal progress. |
| Sharpe ratio | `sqrt(A) * mean(r - rf) / sample_std(r - rf)`, annualized using the approved calendar and risk-free baseline. |
| Sortino ratio | `sqrt(A) * mean(r - MAR) / sqrt(mean(min(0, r - MAR)^2))`. Downside deviation uses all observations, not only negative returns. |
| Maximum drawdown | Maximum `100 * (H_t - E_t) / H_t`, where `H_t` is the running marked-equity peak including `E0`. Include floating P&L/costs; show the monetary loss at that percentage peak/trough and their timestamps. |
| Total return | `Eend - E0` in modeled currency, with realized net P&L and ending unrealized P&L/costs separately reconciled to that change. |

Use simple periodic net marked-equity returns `r_t = E_t / E_(t-1) - 1` on the same approved regular calendar, including inactive periods. Disclose calendar/timezone, observation count, positive periods/year `A`, and per-period `rf`/minimum acceptable return `MAR`; convert approved annual baselines as `(1 + annual_rate)^(1/A) - 1`. Sample standard deviation uses `ddof=1`. Proposed baselines are modeled assumptions, not verified historical rates.

Undefined ratios, insufficient observations, zero variance/downside deviation, missing reliable conversions, and returns following nonpositive equity are unavailable with exact reasons, not numeric zero. Preserve insolvency and genuine losses rather than clipping them. Use explicit labels/reasons for nonfinite values in serialized outputs. Simulated equity and drawdown are not actual account goal progress or verified continuous-guard history.

## Run Artifacts

Working Python, inputs, and diagnostics are under the Git-ignored `strategies/backtests/<name>/temp/<run-id>/`. Durable attempts and completed evidence are under `strategies/backtests/<name>/<run-id>/`, alongside `temp/`, not inside it. Use unique run IDs distinct from the reserved directory name `temp`.

```text
strategies/
  <name>.md
  backtests/
    <name>/
      temp/<run-id>/*.py
      <run-id>/
        attempt.json
        source.md
        rules.md
        config.json
        report.md
        method/*.py
        results/symbols/<symbol-name>/
        results/portfolio/
        private/
```

Create run directories and artifacts only as an approved research attempt requires them; empty scaffolding is not execution or completion evidence. Paths in the following table are relative to the durable run directory:

| Path | Content |
| --- | --- |
| `attempt.json` | Durable ownership/lifecycle and actual invocation/outcome record; retained even if incomplete. |
| `source.md`, `rules.md`, `config.json` | Frozen complete supplied source, approved completed English rules, and fixed configuration. |
| `method/*.py` | Exact executed Python archived from `temp/`, with runtime/dependency/invocation evidence. |
| `report.md` | Verified report with identity, source/rules/config/data/method/output references and limitations. |
| `results/symbols/<symbol-name>/` | Per-symbol `metrics.json`, `trades.csv`, and `equity.csv` or equally auditable outputs. |
| `results/portfolio/` | Separate shared-capital metrics, trade trace, and marked-equity curve. |
| `private/` | Restricted datasets/traces, sensitive diagnostics, and trusted setup/result review provenance. |

| Report Detail | Required Evidence |
| --- | --- |
| Identity | Source/completed-rule paths and fingerprints, run ID, actual execution evidence/timestamps, method fingerprint, runtime/dependencies, and invocation. |
| Data | Documented MT5 MCP source, mapped symbols/timeframes, verified source timestamps/timezone, evaluation interval and separate warm-up, dataset fingerprints, pagination/gaps/quality limitations. |
| Configuration | Modeled capital/currency, symbol and shared-portfolio sizing/exposure, constraints/conversions, costs/fills and sources, ratio/calendar conventions, configuration fingerprint and setup approval reference. |
| Method | Rule-to-code mapping, chronological signal/fill/mark treatment, intrabar model, competing-signal ordering, screening/validation boundaries and any tuning/seed. |
| Result | All six metrics per symbol and portfolio, trade count/wins/losses, realized net/unrealized P&L/cost attribution, ending exposure, and reconciled traces. |
| Reproduction | Exact archived source/rules/Python/config/data/output references and fingerprints, portable invocation and private-data access restrictions; rerunning still requires authorization. |
| Limitations | Unavailable/undefined metrics with reasons, costs/data sensitivity, interval comparability, and no guaranteed future return or hard loss cap. |

For text fingerprints, use SHA-256 over UTF-8 text with CRLF/CR normalized to LF, without trimming or otherwise changing content. For binary data, hash exact bytes. Record the fingerprint method for every artifact; never invent a digest. Fingerprint the complete source and completed rulebook separately; adding an evidence binding does not redefine either fingerprint.

Shareable sources/rules/reports/Python/configuration/outputs must contain no credentials, account identifiers, restricted dataset contents, or account-bound approval content. Sanitize before freezing/fingerprinting, retain necessary exact private inputs privately, and use portable repository-relative references. Market data may be shared only when privacy/redistribution rules permit; otherwise keep raw data and restricted traces in ignored `private/` with auditable references/fingerprints. Credentials remain outside the repository entirely, including ignored directories. Sharing artifacts never means automatically committing or pushing them.

Completed reports, methods, source/rules, inputs, outputs, and completion records are immutable evidence. Store the report's own digest externally in the review/evidence binding after freezing, not as a self-referential hash. Review receipts stay separate; do not append notes to a fingerprinted report. Corrections/configuration changes need a newly approved run. Clean `temp/` only after verifying exact methods, approved inputs, required private data, attempt history and outputs have been safely archived; never destroy evidence needed for reuse, reproduction or review.

## User Review

Only explicit user approval/rejection of the identified source/completed rules, run, method/configuration/data and results changes review state. "Good" means user-approved, not an AI score or threshold. Pre-test setup approval is not result review. Standalone result review is not onboarding or account authorization and must not populate CSV trading approval timestamps. Comparing several strategies does not approve all of them or authorize multiple live strategies.

Archive actual client-supported setup/result receipts or trusted conversation references and verified timestamps in the run's `private/`, bound to exact evidence. Keep identities/private content out of shared artifacts. A self-written timestamp, edited status or copied receipt alone is not verifiable approval. Reverify trusted provenance on resumption; if unavailable, ask for fresh review rather than infer consent or rerun the test. Unreliable persistence/readback blocks reusable eligibility, not permission to invent receipts.

An edit to the source, completed rules, parameters, or pinned method/data/configuration/result makes the affected binding stale and blocks new exposure until valid evidence/review and required account reapproval. Explicit rejection/revocation of the pinned run also blocks entries. Retesting unchanged rules does not replace or revoke an intact pin; preserve both evidence and actual decisions. Never reuse an older approval to approve a new run.

## Trading Approval And Resumption

After per-strategy results, let the user choose the exact strategy/run for the account. Present the full summary required by [AGENTS.md](../AGENTS.md): exact login/server/demo-live type, limits/definitions/baseline values and timestamps, goal, actual stored completed specification and source/evidence binding, symbols/account mapping, result metrics/dates and limitations, and account-wide emergency-close mandate including manual exposure.

Ask for and await explicit approval of that chosen result and autonomous execution on that named account under that policy/goal/strategy. One final response can cover result review and account authorization only when the complete question clearly requests both; keep their evidence bindings/meanings distinct. Approval of results alone never authorizes orders. This authorizes compliant strategy execution, not a forced immediate order or bypass of per-order gates. An instruction file, example, MCP response, CSV timestamp, implementation request or unattended host answer is not account approval.

Persist the complete approved English specification, verbatim supplied-source package/reference and clearly labeled evidence binding in RFC-quoted `strategy_spec` under the [CSV contract](risk-management.md), not a name or AI summary. Bind source/completed-rule, selected run/method/configuration/data/report/output fingerprints, approved symbol scope and trusted private setup/result/account approval references. Preserve commas/newlines/quotes as one cell. Drafts remain unapproved; no schema columns or other active account checkpoint are added.

Record actual receipts/timestamps and reverify account/policy/goal/specification, unchanged reviewed evidence, user authority and independent guard binding on resumption. Missing provenance needs reapproval, not inference from a row. Reused research remains historical: resolve material modeling/broker differences before activation, and explicitly approve actual account mappings rather than expand a live basket from research symbols. A strategy/evidence change requires renewed approval without resetting goal/risk history; unchanged-policy reauthorization must not move cash-flow/high-water anchors.

Only after approval, verify/arm supported existing protection, reconcile/read back state, exclusive ownership/journal and every connection/risk gate before `ready` or new exposure. A reviewed test, target, or chosen strategy alone is insufficient. No signal means no trade. Research blockers do not prevent previously approved identity-verified safety reductions or automatically flatten positions/reset policies/goals. Prompt files do not provide continuous AI execution or implement a guard.

## Research Reporting

Every research-only response, including questions/errors/reuse/review updates, reports state without invented account metrics:

```text
As Of: <actual UTC timestamp and verified/stale data source timestamps>
Strategies / Runs: <available/selected names; source/completed-rule fingerprints and run IDs, or unavailable>
Setup / Reuse / Simulation: <approval; saved result verified/reused, new execution verified/running, or blocked>
Data: <verified MT5 source; evaluation dates/timeframes and separate warm-up; quality/age limitations>
Backtest Results: <per-strategy table with six metrics per symbol and portfolio; realized/unrealized P&L and exposure, or unavailable>
Review / Status: <latest run review/status; provenance verified or missing>
Outcome: <verified research outcome, limitations, or blocker>
Next Permitted Step: <selection, proposal approval, compliant data/execution step, result review, or separately requested trading setup>
```

Result tables identify strategy/run, symbol or portfolio, dates/timeframe, profit factor, return %, Sharpe, Sortino, maximum drawdown % and total return in modeled currency. Include all fields with reasons when unavailable. During trading/onboarding, use the full [goals report](goals.md) and supplement it with per-strategy results at the results stage; identify the account pin and outstanding authorization/protection gates separately. Never count simulated returns as goal profit or promise future returns.

## Sanity Checks

These are synthetic validation cases, not research results, global defaults, or approval. Future generated Python must validate metric conventions and chronological portfolio reconciliation before executing its one real-data bundle.

| Case | Expected Outcome |
| --- | --- |
| Closed net trades `+120`, `-40` | Profit factor `3`, after costs. |
| `E0 = 1000`, `Eend = 1080` | Return `8%`, total return `80` in modeled currency. |
| Marked peak `1100`, later equity `990` | Maximum drawdown `10%`, loss `110` at that peak/trough. |
| Returns `0.02`, `-0.01`; `rf = MAR = 0`, `A = 1` | Sample deviation about `0.0212132`; Sharpe about `0.2357023`, Sortino about `0.7071068` using all observations. |
| No trades and flat positive equity | Return/total return/drawdown `0`; profit factor and zero-deviation ratios unavailable, not fake numeric scores. |
| Positive closed profit, no losses | Profit factor explicitly infinite; zero variance/downside ratios unavailable with reasons. |
| H1 versus H4 entry signals | H1 uses 3-6 evaluation months; H4 uses at least 12; warm-up is additional. |
| Unchanged completed bundle on reconnect | Read/verify saved results, no Python replay; completion is not review/account approval. |
| Failed or changed test; running/unknown prior process | New proposal/approval before another attempt; unknown/running execution must be reconciled, not duplicated. |
