# MT5 Connection Instructions

## Connection First

This file applies to the trading workflow in [AGENTS.md](../AGENTS.md) and read-only historical-price research in [Strategy Catalogue And Backtesting](strategy.md), not repository maintenance. Use the selected AI client's MCP interface; tool names and setup formats differ between clients and servers.

1. Discover tools/resources already exposed to the client. Read the actual MT5 server's tool schemas and documentation. Do not invent tool names, parameters, transports, or a health API.
2. If a candidate MT5 connection exists, make a documented read-only account/terminal request for trading, or the authenticated historical-data request described below for research-only access. A server name, saved configuration, TCP response, or health message alone is not proof of either capability.
3. Reuse a working verified connection. If credentials/configuration are missing or unusable, ask for the base URL and confirm the complete MCP endpoint, including its documented path. Do not guess a `/mcp` or other suffix. Reuse valid nonsecret connection inputs after a transient outage rather than requesting new secrets unnecessarily.
4. Request the access token through the client's secure secret store, trusted user configuration outside the repository, or supported environment mechanism. Ask the user to confirm that it is configured, not to paste it into chat. If the client has no secure way to supply it, report the blocker.
5. Use the selected server's documented remote MCP transport and authentication. Use `Authorization: Bearer <access token>` only if the server specifies bearer authentication. Verify endpoint identity and certificate validation; require HTTPS except explicitly approved loopback HTTP. Never forward credentials to unapproved endpoints or redirects, or use a token embedded in a URL/query string.
6. If the client cannot add a connection dynamically, guide the user through its own MCP setup and required reload/restart. Do not create vendor-specific configuration in this repository. Obtain permission before changing external host settings, preserve unrelated settings, and do not grant blanket tool permissions.
7. Discover the newly exposed tools and repeat the appropriate authenticated read-only verification. Report an MT5 account connected only when actual account access succeeds, then follow the trading handoff below. Research-only history access verifies the data capability, not account trading access, and follows the research handoff instead.

Do not assume any particular environment-variable interpolation syntax, JSON configuration format, slash command, secret UI, or automatic `.env` loading. A config edit is not a connection. Do not install a trading bridge or call ad-hoc order HTTP endpoints as a fallback.

## Post-Connection Handoff

For a request to connect or reconnect to the MT5 MCP without a research-only or connection/status-only qualification, once authenticated read-only access verifies the account login plus broker server, demo/live type, and currency, report that identity and ask the first outstanding risk question from `instructions/risk-management.md` in the same response. This also applies when reusing an already-working connection. Do not end with only "connected", require a separate risk-management request, or ask whether to begin collecting inputs. Honor the explicit read-only exceptions in `AGENTS.md` without starting onboarding.

For trading onboarding, validate the root CSV before reusing or updating saved inputs. Reuse verified same-account inputs, including unapproved drafts as drafts; if all four risk inputs are valid, continue to the next incomplete onboarding step. A different account binding or corrupt saved state requires the risk file's recovery rules, not silent replacement. Transport connectivity, configuration, or a health response without authenticated account verification must not trigger account-bound risk collection; report failed verification or missing MCP/secure-secret capabilities as connection blockers.

Missing broker timezone, history, execution, or independent guard evidence does not by itself prevent collecting unapproved draft inputs for the verified account. Report those blockers and keep new exposure blocked; connection or input collection alone never establishes approval or `ready`. Include the compact progress report from `instructions/goals.md`, with actual source timestamps, unavailable metrics clearly marked, and `Next Permitted Step` identifying the requested input or blocker. Do not delay previously approved, identity-verified emergency safety actions for onboarding questions.

## Research Data Access

When selected strategy research needs MT5 data, or the user explicitly requests a research-only connection, follow the same documented MCP transport, authentication, secure-secret, and permission rules, but verify an actual authenticated historical-price response and source instead of starting account setup. Discover documented read-only symbol inventory, instrument/history, and currency-conversion capabilities needed for the independent-symbol and shared-portfolio tests. Check actual forex symbol mapping, interval/warm-up coverage, timestamps/timezone, resolution, pagination, ordering/deduplication, quality, and bid/ask/spread semantics under [strategy instructions](strategy.md). Configuration or a health response is not data verification; history access does not prove account trading access.

Ace selects multiple suitable verified symbols from the available universe; do not invent symbol names or require a routine user-supplied symbol list. Missing essential discovery/history/conversion capability blocks the affected test. Prices must come through documented MT5 MCP operations, not ad-hoc HTTP endpoints or a credential-bearing Python bridge. Use the approved history bounds and settings; present-day costs/contract conditions are not automatically verified historical facts.

For listing, reviewing, or reusing local saved results, check completed-run evidence before connecting for new data, changing symbols, or fetching replacement history. An unchanged verified completed bundle is returned with its actual historical period and limitations, not re-executed or refreshed. Merely reading saved results requires no new MCP connection and does not establish current connectivity; an explicit connection request still needs authenticated verification.

Research can proceed without account trading capabilities or a continuous guard. If account identifiers are returned incidentally, keep them private; do not initialize/update the CSV, ask onboarding risk/goal questions, arm a guard, escalate trading permissions, or place test orders. Missing essential history/interpretation or local Python execution blocks a new backtest, not permission to invent prices or returns. New or retry attempts require the strategy instructions' setup approval. Use their research report; mixed trading requests must complete onboarding and all account gates.

## Secret Handling

- Tokens must never enter the CSV, Markdown, Git, repository files, reports, URLs, or diagnostic logs. Do not print secret environment values or resolved host configuration just to check connectivity.
- Redact authentication headers and sensitive query values from errors before reporting. Request only the endpoint and authentication needed for this MT5 server, not unrelated credentials.
- If a user pastes a token into chat, do not repeat or persist it. Advise rotation if it has been exposed and request secure replacement. Do not claim that prior chat/log exposure has been erased.
- An ignored credential file is not a secure secret store. Keep actual credentials outside this repository and within the user's trusted client mechanism.

## Capability Verification

Before trading account approval or resumption, collect verified values and timestamps for these capabilities. Missing information permits setup/reporting, not new exposure. Research-only access requires the historical-price capabilities above, not the full trading capability set.

| Capability | Required Evidence |
| --- | --- |
| Account identity | Account login and broker server together, demo/live type, account currency, authenticated terminal/account status. Confirm the exact account with the user. |
| Account telemetry | Current balance, equity, floating P&L, margin and free margin, source timestamps, and health of quote/account feeds. |
| Broker day | Verified server timezone and DST rules/day boundaries; reliable broker-midnight equity and external cash-flow records. Do not infer broker timezone from the host clock. |
| Exposure | Complete open positions and pending orders, including manual/other-origin orders, tickets, symbols, volume, direction, stops, and execution status. |
| Accounting | Deal/order history, unique event IDs or reliable cursors, realized-profit/cost semantics, commissions, swaps, fees, partial closes, and external capital movement classification. |
| Instrument rules | Actual forex symbol names, prices, price precision, contract/tick values, account-currency conversion, volume minimum/maximum/step, stop/freeze restrictions, and market availability. |
| Execution | Trading enabled, actual order and close/cancel/modify schemas, protective-stop support, hedging/netting semantics, atomic expected-account binding, durable mutation journal/idempotency support, and client tool permission requirements. Do not place a test order to check access. |
| Continuous guard | Documented guard operations and independently verified status/policy. See risk instructions for the mandatory continuous health, account-wide coverage, peaks/latches, budgets, and ownership evidence. |

Read only the capabilities actually exposed. If a value cannot be verified, identify it explicitly and ask for authoritative documentation/data rather than inventing an implementation. Read-only credentials cannot execute trades; do not silently escalate access.

## Mutation Binding And Journal

Every mutation must be atomically bound server-side to the approved login plus broker server and current execution ownership/fencing generation, or use a documented immutable account-scoped connection that cannot switch accounts during execution. A read-only identity check immediately before submission is not sufficient for a default-current-account mutator: the terminal could switch between the check and dispatch. If the MCP/guard cannot enforce the binding, do not use that mutation tool or claim safe autonomous execution.

Before dispatching an entry or other risk increase, use a documented durable guard/MCP execution journal to record the expected account, policy, owner/fencing generation, unique correlation/idempotency ID, approved signal/action, and intended parameters. Verify that the journal acknowledges durable intent before broker submission. Reference that supported journal through `guard_reference`; keep any secret authentication material outside the CSV. A local `ready` snapshot or in-memory request ID is not a write-ahead execution record.

On every startup/resumption, recover all unresolved journal intents and in-flight broker requests before new exposure. Empty broker orders/deals immediately after reconnecting do not prove that a pre-crash request cannot still execute later. Require documented authoritative completion/nonexecution or safe server-side deduplication using the same intent ID; do not create a replacement ID and repeat the same action while its prior outcome is uncertain. If durable correlation/recovery semantics are unavailable, setup/reporting may continue, but autonomous entries remain blocked. Do not implement a new journal/server in this instructions-only repository.

Coordinate emergency cancellation/liquidation through the guard's documented ownership and mutation journal. A guard may preempt the agent on breach; stale agent fencing must then reject further dispatch. If the guard is already liquidating, read back its progress and broker state instead of issuing an uncoordinated duplicate close. Assist only through supported account-bound, coordinated safety operations and documented remaining-volume/idempotency semantics.

## Reconnection And Uncertain Results

On any authentication failure, permission rejection, stale feed, disconnect, account switch, or unknown connection state, stop submitting risk-increasing actions. Report the blocker with last verified timestamps. Existing approved safety reductions remain permitted only on a positively verified account, through documented tools; the independent guard must protect the account when the AI cannot.

After reconnecting for trading, reverify identity, currency, broker day, exposure, history, guard policy/health, ownership, CSV bindings, and every unresolved mutation journal entry. Recover continuous high-water marks and breach events from the guard; never treat reconnection as a new policy/day or reset missing state.

For research-only reconnection when MCP data is needed, reverify authenticated source/history consistency without account onboarding. Reuse unchanged verified completed results without replaying Python or shifting their period; report saved data as historical, not freshly acquired. Retain provenance. Failed/changed tests may receive another approved attempt; changed data/configuration is never a silent alteration of reviewed evidence or an automatic completed-run refresh. Reconcile running/unknown attempts before any new invocation.

For any mutation that times out, is interrupted, or returns an ambiguous acknowledgment:

1. Treat its execution status as unknown, not failed or successful. Freeze further risk-increasing actions.
2. Recover the durable intent and reconcile broker orders, positions, and deals using its submitted ticket/client identifier and documented result semantics, including still-in-flight requests. Request authoritative status if the result remains ambiguous.
3. Retry only when the actual state and the server's documented idempotency/remaining-volume rules make the operation safe. Never blindly duplicate an entry or a close.
4. Verify actual pending-order cancellation and position closure/remaining volume by readback. Never assume an opposite order closes a position; it may create hedged exposure or reverse a net position.
5. If liquidation is rejected, partially filled, or unavailable, report unresolved exposure and continue only verified, bounded safety actions. Do not claim that the account is flat or that a drawdown cap was preserved.

The client's permission system is a separate execution gate. User strategy approval does not bypass it. Explain blocked tool-specific access without enabling all tools or treating a denied safety action as completed.
