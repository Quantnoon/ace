const UNAVAILABLE = "Unavailable";
const DECIMAL = /^[+-]?\d+(?:\.\d+)?$/;
const UTC_STAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$/;
export const ACTIVITY_PREVIEW_SIZE = 5;
const ACTIVITY_PAGE_RETRIES = 3;
const STRATEGY_PAGE_SIZE = 20;
const OPERATIONS = { entry: "Initial entry", add: "Winner addition", breakeven: "Breakeven stop", trail: "Trailing stop", close: "Close", cancel: "Cancel" };
const STRATEGY_RULES = { expiry_rule: "Expiry / session rule", breakeven_rule: "Cost-aware breakeven rule", trailing_rule: "Trailing rule", addition_rule: "Addition rule" };
const TIMEFRAMES = new Set(["M1", "M2", "M3", "M4", "M5", "M6", "M10", "M12", "M15", "M20", "M30", "H1", "H2", "H3", "H4", "H6", "H8", "H12", "D1", "W1", "MN1"]);
const ACTIVITIES = new Set(["analysis", "wait", "entry", "management", "exit", "blocked"]);
const SESSION_LABELS = { active: "Continue requested", stopped: "User stop recorded", interrupted: "Interruption recorded" };
const OUTCOMES = {
  within_budget: ["Within budget at last check", "neutral", "The recorded check was within the monetary budget. It is not a current permission to trade."],
  blocked: ["Latest check blocked", "caution", "The helper recorded a blocker. Values below still belong to the displayed source observation; they do not imply the latest action succeeded."],
  reconciliation_required: ["Reconciliation required", "caution", "The helper could not establish a reconciled result. Saved metrics must not be treated as a successful new check."],
  prepared: ["Request prepared", "neutral", "A local request was prepared. Preparation is not evidence of broker execution."],
  cached: ["Saved helper result", "muted", "This is a saved result, not a fresh account verification."],
  draft: ["Unapproved draft", "caution", "Draft amounts do not authorize execution."],
  draft_saved: ["Unapproved draft", "caution", "Draft amounts do not authorize execution."],
  session_saved: ["Session control recorded", "muted", "A task-control request was saved. It is not an account observation or proof of current execution."],
};

function record(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function text(value, fallback = UNAVAILABLE) {
  return typeof value === "string" && value.length ? value : fallback;
}

function strings(value, empty = "None recorded") {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) return UNAVAILABLE;
  return value.length ? value.join(", ") : empty;
}

function codeLabel(value) {
  const label = text(value);
  return label === UNAVAILABLE ? label : label.replaceAll("_", " ");
}

export function isDecimal(value) {
  return typeof value === "string" && value.length <= 2048 && DECIMAL.test(value);
}

export function decimalSign(value) {
  if (!isDecimal(value)) return null;
  if (!/[1-9]/.test(value)) return 0;
  return value.startsWith("-") ? -1 : 1;
}

export function formatDecimal(value, { signed = false } = {}) {
  if (!isDecimal(value)) return UNAVAILABLE;
  const hasSign = value[0] === "+" || value[0] === "-";
  const sign = hasSign ? value[0] : signed && decimalSign(value) === 1 ? "+" : "";
  const [integer, fraction] = (hasSign ? value.slice(1) : value).split(".");
  const grouped = integer.replace(/^0+(?=\d)/, "").replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return sign + grouped + (fraction === undefined ? "" : `.${fraction}`);
}

export function formatMoney(value, currency, options) {
  const amount = formatDecimal(value, options);
  return amount === UNAVAILABLE ? amount : `${amount} ${text(currency, "(currency unavailable)")}`;
}

export function formatPercent(value, { compact = false } = {}) {
  if (compact && isDecimal(value) && value.includes(".")) {
    const end = value.indexOf(".") + 5;
    if (value.length > end) {
      const shortened = value.slice(0, end);
      if (/[1-9]/.test(value.slice(end))) {
        if (decimalSign(shortened) === 0) return `<0.0001% ${decimalSign(value) === -1 ? "loss" : "gain"}`;
        return `~${formatDecimal(shortened, { signed: true })}%`;
      }
      value = shortened;
    }
  }
  const amount = formatDecimal(value, { signed: true });
  return amount === UNAVAILABLE ? amount : `${amount}%`;
}

export function progressFill(value) {
  if (!isDecimal(value)) return null;
  if (decimalSign(value) !== 1) return 0;
  const unsigned = value[0] === "+" ? value.slice(1) : value;
  const integer = unsigned.split(".")[0].replace(/^0+(?=\d)/, "");
  if (integer.length > 3 || integer.length === 3 && integer >= "100") return 100;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return 100;
  return amount >= 100 ? 100 - Number.EPSILON * 100 : amount;
}

export function formatCount(value) {
  return Number.isSafeInteger(value) && value >= 0 ? String(value) : UNAVAILABLE;
}

function timestamp(value) {
  if (typeof value !== "string" || !UTC_STAMP.test(value)) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatTimestamp(value) {
  return timestamp(value) === null ? UNAVAILABLE : value.replace("T", " ").replace(/(?:Z|\+00:00)$/, " UTC");
}

function duration(seconds) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return UNAVAILABLE;
  if (seconds < 1) return "<1s";
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

export function sourceFreshness(snapshot, now = Date.now()) {
  const source = timestamp(snapshot?.as_of);
  const limit = snapshot?.max_age_seconds;
  const age = source === null || !Number.isFinite(now) ? null : (now - source) / 1000;
  if (!record(snapshot) || source === null || typeof limit !== "number" || !Number.isFinite(limit) || limit <= 0 ||
      !["fresh", "stale", "future"].includes(snapshot.freshness) || age === null) {
    return { state: "unavailable", age, limit: null };
  }
  if (age < 0 || snapshot.freshness === "future") return { state: "future", age, limit };
  return { state: age > limit || snapshot.freshness === "stale" ? "stale" : "fresh", age, limit };
}

export function scopeKey(data) {
  return JSON.stringify([
    data?.status ?? null,
    data?.account?.login ?? null, data?.account?.server ?? null,
    data?.account?.type ?? null, data?.account?.currency ?? null,
    data?.scope?.policy_id ?? null, data?.scope?.goal_id ?? null,
  ]);
}

export function approvedAmounts(data) {
  if (data?.status !== "configured") return { target: null, budget: null };
  return {
    target: isDecimal(data.goal?.target) ? data.goal.target : isDecimal(data.metrics?.target) ? data.metrics.target : null,
    budget: isDecimal(data.policy?.budget) ? data.policy.budget : isDecimal(data.metrics?.budget) ? data.metrics.budget : null,
  };
}

export function canonicalStatus(data) {
  const stops = data?.stops;
  const result = data?.result;
  const decision = text(result?.decision, "");
  const loss = Boolean(stops?.loss_latched_at) || decision === "loss_stop";
  const target = Boolean(stops?.target_latched_at) || decision === "target_stop";
  // The account-level stop projection retains a verified settlement even when
  // a later draft is the latest helper result; draft saving is not a new check.
  const closureVerified = typeof stops?.closure_verified === "boolean" ? stops.closure_verified : result?.closure_verified === true;
  let [label, tone, description] = Object.hasOwn(OUTCOMES, decision)
    ? OUTCOMES[decision]
    : ["Helper outcome unavailable", "muted", "No recognized helper outcome is available. No execution or closure is inferred."];
  if (loss || target) {
    label = loss ? "Loss stop latched" : "Target stop latched";
    tone = loss ? "danger" : "accent";
    description = closureVerified
      ? "Account closure was verified in the saved result. The stop remains latched."
      : "Closure is not verified. The recorded mandate requires cancellation of pending entries and closure of all account positions, including manual exposure.";
    if (loss && target) description = `Both stops are latched; loss-stop handling takes priority. ${description}`;
  }
  return { label, tone, description, loss, target, closureVerified };
}

export function intentStatus(value) {
  const labels = { prepared: "Prepared request", completed: "Settled request", not_executed: "Not executed", unknown: "Outcome unknown", planned: "Planned request" };
  return Object.hasOwn(labels, value) ? labels[value] : "Request status unavailable";
}

export function contextForIntent(intent) {
  const value = intent?.context;
  const bounded = (item, limit) => typeof item === "string" && item.trim().length > 0 && item.length <= limit;
  if (!record(value) || value.version !== 1 || !Object.hasOwn(OPERATIONS, value.operation) ||
      !["entry", "reduce"].includes(intent.kind) || ["entry", "add"].includes(value.operation) !== (intent.kind === "entry") ||
      !bounded(value.rationale, 2000) || !Array.isArray(value.source_refs) || !value.source_refs.length || value.source_refs.length > 64 ||
      value.source_refs.some((item) => !bounded(item, 200)) ||
      value.origin_intent_id !== null && !bounded(value.origin_intent_id, 200)) return null;
  if (value.operation !== "entry") {
    return value.strategy === null && (!["add", "breakeven", "trail"].includes(value.operation) || value.origin_intent_id !== null) ? value : null;
  }
  const plan = value.strategy;
  if (value.origin_intent_id !== null || !record(plan) || !bounded(plan.name, 120) || !bounded(plan.thesis, 2000) ||
      !bounded(plan.invalidation, 1000) || !["buy", "sell"].includes(plan.side) || !TIMEFRAMES.has(plan.timeframe) ||
      Object.keys(STRATEGY_RULES).some((field) => plan[field] !== false && !bounded(plan[field], 1000))) return null;
  return value;
}

function strategyItems(page) {
  if (!record(page) || !Array.isArray(page.items) || page.items.length > STRATEGY_PAGE_SIZE ||
      page.next_cursor !== null && cursor(page.next_cursor) === null ||
      page.items.some((item) => !record(item) || !record(item.intent) || item.intent.kind !== "entry" ||
        typeof item.intent.id !== "string" || !item.intent.id.length ||
        contextForIntent(item.intent) && contextForIntent(item.intent).operation !== "entry")) return null;
  return page.items;
}

export function journalForScope(data, journal = data?.latest_journal) {
  if (!record(journal) || journal.version !== 1 || !ACTIVITIES.has(journal.activity) ||
      ![journal.summary, journal.reason, journal.next_step].every((value) => typeof value === "string" && value.length > 0) ||
      !data?.scope || typeof data.scope.policy_id !== "string" || typeof data.scope.goal_id !== "string" ||
      journal.policy_id !== data.scope.policy_id || journal.goal_id !== data.scope.goal_id ||
      timestamp(journal.as_of) === null || timestamp(journal.recorded_at) === null ||
      ["market_summary", "risk_summary", "invalidation"].some((key) => journal[key] != null && typeof journal[key] !== "string") ||
      ["symbols", "source_refs"].some((key) => journal[key] != null && (!Array.isArray(journal[key]) || journal[key].some((value) => typeof value !== "string")))) return null;
  return journal;
}

export function mergeActivity(current, incoming) {
  if (!Array.isArray(incoming)) return null;
  const rows = new Map();
  for (const item of [...(Array.isArray(current) ? current : []), ...incoming]) {
    if (record(item) && Number.isSafeInteger(item.id) && item.id > 0) rows.set(item.id, item);
  }
  return [...rows.values()].sort((left, right) => right.id - left.id);
}

export function isDashboardResponse(data) {
  return record(data) && data.ok === true && data.api_version === 1 &&
    ["configured", "draft", "unconfigured"].includes(data.status) &&
    Number.isSafeInteger(data.revision) && data.revision >= 0 && timestamp(data.generated_at) !== null;
}

function cursor(value) {
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

// An older page carries a current summary, but its events cannot be attached
// to a different account/policy/goal while a request is in flight.
export function mergeDashboardPage(previous, data, {
  before = null, strategyBefore = null, requestScope = scopeKey(previous?.data),
  requestRevision = previous?.data.revision, requestId = 0, latestRequestId = requestId,
} = {}) {
  if (requestId !== latestRequestId) return previous;
  if (strategyBefore !== null && (cursor(strategyBefore) === null || strategyBefore !== previous?.strategyCursor)) return previous;
  if (!isDashboardResponse(data)) throw new TypeError("invalid_response");
  const scope = scopeKey(data);
  const changed = !previous || previous.scope !== scope;
  if (!changed && data.revision < previous.data.revision) return previous;
  const hadConfigured = previous?.hadConfigured === true || data.status === "configured";
  if (data.status !== "configured") {
    return { data, scope, activity: null, cursor: null, needsRefresh: false,
      strategies: null, strategyCursor: null, strategiesNeedRefresh: false,
      historyGap: false, hadConfigured, unconfiguredAfterLoad: data.status === "unconfigured" && hadConfigured };
  }
  const mismatchedPage = before !== null && requestScope !== scope;
  const incoming = data.activity?.items;
  const oldRows = changed ? null : previous.activity;
  const activity = mismatchedPage ? null : mergeActivity(oldRows, incoming);
  const disjoint = before === null && Array.isArray(oldRows) && oldRows.length > 0 && Array.isArray(incoming) && incoming.length > 0 &&
    !incoming.some((item) => record(item) && oldRows.some((old) => item.id === old.id));
  let nextCursor = cursor(data.activity?.next_cursor);
  if (!changed && before === null && oldRows?.length && !disjoint) nextCursor = previous.cursor;
  // "Latest" assessments must share one scope and revision. Older strategy
  // pages are discarded, not silently retained as current across a write.
  const strategiesNeedRefresh = strategyBefore !== null && (requestScope !== scope || requestRevision !== data.revision);
  const newStrategies = strategiesNeedRefresh ? null : strategyItems(data.strategies);
  const previousStrategies = !changed && data.revision === previous.data.revision ? previous.strategies : null;
  let strategies = newStrategies;
  let strategyCursor = newStrategies === null ? null : cursor(data.strategies.next_cursor);
  if (newStrategies && previousStrategies?.length) {
    const merged = new Map(previousStrategies.map((item) => [item.intent.id, item]));
    for (const item of newStrategies) merged.set(item.intent.id, item);
    strategies = [...merged.values()];
    if (strategyBefore === null) strategyCursor = previous.strategyCursor;
  }
  return {
    data, scope, activity,
    strategies, strategyCursor, strategiesNeedRefresh,
    cursor: mismatchedPage ? null : nextCursor,
    needsRefresh: mismatchedPage,
    historyGap: !changed && (previous.historyGap || disjoint),
    hadConfigured, unconfiguredAfterLoad: false,
  };
}

export function pollDelay(hidden, failures = 0) {
  if (hidden) return 30000;
  const count = Number.isSafeInteger(failures) && failures > 0 ? Math.min(failures, 3) : 0;
  return Math.min(30000, 5000 * (2 ** count));
}

function setText(node, value) {
  const content = typeof value === "string" ? value : UNAVAILABLE;
  if (node.textContent !== content) node.textContent = content;
}

function element(doc, tag, content, className) {
  const node = doc.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) setText(node, content);
  return node;
}

function definition(doc, list, label, value, numeric = false, exact = null) {
  const wrapper = element(doc, "div");
  const term = element(doc, "dt", label);
  const description = element(doc, "dd", value, numeric ? "numeric" : undefined);
  if (typeof exact === "string") description.title = exact;
  wrapper.append(term, description);
  list.append(wrapper);
}

function journalFields(doc, list, journal) {
  definition(doc, list, "Source observed", formatTimestamp(journal.as_of), false, journal.as_of);
  definition(doc, list, "Snapshot ID", text(journal.snapshot_id), true);
  definition(doc, list, "Market context", text(journal.market_summary));
  definition(doc, list, "Risk context", text(journal.risk_summary));
  definition(doc, list, "Invalidation", text(journal.invalidation));
  definition(doc, list, "Symbols", strings(journal.symbols));
  definition(doc, list, "Source references (inert text)", strings(journal.source_refs));
  definition(doc, list, "Linked request ID", text(journal.intent_id), true);
}

function intentFields(doc, list, intent, currency) {
  const context = contextForIntent(intent);
  definition(doc, list, "Request ID", text(intent.id), true);
  definition(doc, list, "Request kind", codeLabel(intent.kind));
  definition(doc, list, "Recorded operation", context ? OPERATIONS[context.operation] : UNAVAILABLE);
  definition(doc, list, "Action rationale", text(context?.rationale));
  definition(doc, list, "Original entry ID", context ? text(context.operation === "entry" ? intent.id : context.origin_intent_id) : UNAVAILABLE, true);
  definition(doc, list, "Current request status at page read", intentStatus(intent.status));
  definition(doc, list, "Instrument", text(intent.symbol));
  definition(doc, list, "Stressed risk", formatMoney(intent.risk, currency), true, intent.risk);
  definition(doc, list, "Recorded tickets", strings(intent.tickets), true);
  definition(doc, list, "Prepared at", formatTimestamp(intent.created_at), false, intent.created_at);
  definition(doc, list, "Source observed", formatTimestamp(intent.snapshot_at), false, intent.snapshot_at);
  definition(doc, list, "Latest recorded request outcome", intentStatus(intent.outcome?.outcome));
  definition(doc, list, "Outcome recorded at", formatTimestamp(intent.outcome?.at), false, intent.outcome?.at);
  definition(doc, list, "Outcome source time", formatTimestamp(intent.outcome?.snapshot_at), false, intent.outcome?.snapshot_at);
  definition(doc, list, "Outcome broker tickets", strings(intent.outcome?.broker_tickets), true);
  definition(doc, list, "Action source references (inert text)", context ? strings(context.source_refs) : UNAVAILABLE);
}

class DashboardView {
  constructor(doc) {
    this.doc = doc;
    this.rowCaches = new Map();
    this.progressSignature = null;
    this.journalSignature = null;
    this.warningSignature = null;
    this.scope = null;
    this.currency = null;
    this.lastAnnouncement = "";
    this.activityExpanded = false;
  }

  node(id) { return this.doc.getElementById(id); }
  text(id, value) { setText(this.node(id), value); }
  show(id, visible) { this.node(id).toggleAttribute("hidden", !visible); }

  time(id, value) {
    const node = this.node(id);
    setText(node, formatTimestamp(value));
    if (timestamp(value) !== null) {
      node.dateTime = value;
      node.title = value;
    } else {
      node.removeAttribute("datetime");
      node.removeAttribute("title");
    }
  }

  money(id, value, { signed = false, tonal = false } = {}) {
    const node = this.node(id);
    setText(node, formatMoney(value, this.currency, { signed }));
    node.title = isDecimal(value) ? `${value} ${text(this.currency, "(currency unavailable)")} (exact)` : UNAVAILABLE;
    if (tonal) node.dataset.tone = decimalSign(value) === -1 ? "danger" : decimalSign(value) === 1 ? "positive" : "neutral";
  }

  reset(scope) {
    this.scope = scope;
    for (const id of this.rowCaches.keys()) this.node(id).replaceChildren();
    this.rowCaches.clear();
    this.progressSignature = null;
    this.journalSignature = null;
    this.activityExpanded = false;
  }

  // Preserve the native details/summary nodes, focus, and expanded state.
  // Unchanged polls never replace row contents or move existing rows.
  rows(id, items, keyFor, update) {
    const container = this.node(id);
    const cache = this.rowCaches.get(id) ?? new Map();
    this.rowCaches.set(id, cache);
    const kept = new Set();
    let next = container.firstElementChild;
    for (const item of items) {
      const key = keyFor(item);
      if (key === null || kept.has(key)) continue;
      kept.add(key);
      let row = cache.get(key);
      if (!row) {
        const li = element(this.doc, "li");
        const details = element(this.doc, "details");
        const summary = element(this.doc, "summary");
        const body = element(this.doc, "div");
        details.append(summary, body);
        li.append(details);
        row = { li, details, summary, body, signature: null };
        cache.set(key, row);
      }
      const signature = JSON.stringify([item, this.currency]);
      if (signature !== row.signature) {
        update(row, item);
        row.signature = signature;
      }
      if (row.li !== next) container.insertBefore(row.li, next);
      next = row.li.nextElementSibling;
    }
    for (const [key, row] of cache) {
      if (!kept.has(key)) { row.li.remove(); cache.delete(key); }
    }
  }

  render(state, { error = null, successfulAt = null, now = Date.now() } = {}) {
    const data = state?.data;
    if (state && state.scope !== this.scope) this.reset(state.scope);
    this.currency = data?.account?.currency ?? null;
    this.node("ace-dashboard").setAttribute("aria-busy", data || error ? "false" : "true");
    this.show("reader-error", Boolean(error));
    if (error) {
      const retained = data ? ` Displaying last-known saved data only, with its original source timestamps. No current account state is established.` : " No account data is available; unknown values are not zero.";
      const recovery = error === "unsupported_schema"
        ? " The saved checkpoint format is not supported by this viewer. An older Python viewer may still be running after an update. Browser refresh does not reload it. Verify reader compatibility; if outdated, restart only the matching viewer through its owning client's process controls. Leave the checkpoint and trading agent unchanged."
        : "";
      this.text("reader-error", `Local reader unavailable (${error}).${retained}${recovery} The page will retry; it does not repair state or contact the broker.`);
    }
    this.time("ui-time", successfulAt);
    this.text("account-login", text(data?.account?.login));
    this.text("account-server", text(data?.account?.server, data ? "Server unavailable" : "Account details not yet read"));
    this.text("account-type", data?.account?.type === "live" ? "LIVE ACCOUNT" : data?.account?.type === "demo" ? "DEMO ACCOUNT" : "Type unavailable");
    this.node("account-type").dataset.tone = data?.account?.type === "live" ? "caution" : "muted";
    this.text("account-currency", text(this.currency, "Currency unavailable"));
    this.time("api-time", data?.generated_at);
    this.text("saved-revision", formatCount(data?.revision));
    this.text("policy-id", text(data?.scope?.policy_id));
    this.text("goal-id", text(data?.scope?.goal_id));
    this.text("snapshot-id", text(data?.snapshot?.id));
    this.show("configured-workspace", data?.status === "configured");
    this.show("empty-state", data?.status !== "configured");
    this.show("draft-amounts", data?.status === "draft");
    if (!data) {
      this.text("empty-kicker", "LOCAL CHECKPOINT");
      this.text("empty-title", error ? "Saved account data is unavailable." : "Reading saved account observations.");
      this.text("empty-description", error ? "The local API could not be read. No balance, goal, exposure or connection state can be inferred." : "The desk reads the local checkpoint. It does not connect to the broker or run the trading agent.");
    } else if (data.status === "draft") {
      this.text("empty-kicker", "UNAPPROVED DRAFT");
      this.text("empty-title", "Amounts recorded. Approval not recorded.");
      this.text("empty-description", "These are monetary drafts, not an active mandate. There is no authorized target progress to display. The agent verifies and activates a real trading-start request; this page cannot authorize trading.");
      this.money("draft-target", data.draft?.target);
      this.money("draft-budget", data.draft?.budget);
    } else if (data.status === "unconfigured") {
      this.text("empty-kicker", "NO CONFIGURED CHECKPOINT");
      this.text("empty-title", state.unconfiguredAfterLoad ? "The saved checkpoint is no longer available." : "No saved account is configured.");
      this.text("empty-description", state.unconfiguredAfterLoad
        ? "Previously displayed account values have been cleared. A missing checkpoint is not a reset policy, a flat account or approval to trade."
        : "No configured account was returned by the local reader. This page does not create state, connect to MT5 or start account setup.");
    } else {
      this.renderConfigured(state);
    }
    this.renderWarnings(data);
    this.freshness(data, now, Boolean(error));
  }

  freshness(data, now, retained = false) {
    const current = sourceFreshness(data?.snapshot, now);
    const labels = { fresh: "Within source age limit", stale: "Stale observation", future: "Future source timestamp", unavailable: "Observation unavailable" };
    this.text("source-badge", `${retained ? "Last-known / " : ""}${labels[current.state]}`);
    this.node("source-badge").dataset.tone = current.state === "future" ? "danger" : current.state === "stale" || retained ? "caution" : "muted";
    this.time("source-time", data?.snapshot?.as_of);
    this.text("source-age", current.age === null ? "Age unavailable" : current.age < 0 ? `${duration(-current.age)} ahead of this clock` : `${duration(current.age)} old`);
    this.text("source-limit", current.limit === null ? "Approved age limit unavailable" : `Approved max age ${duration(current.limit)}`);
    const notice = current.state === "stale" ? "Stale source observation. Saved money, orders and outcomes are not current account verification. UI refreshes do not refresh the broker observation."
      : current.state === "future" ? "The source timestamp is in the future or was rejected as future by the reader. It is not fresh data; clock/source reconciliation is required."
        : current.state === "unavailable" && data?.status === "configured" ? "Source freshness is unavailable. No current account verification can be inferred from the saved values." : "";
    this.show("source-notice", Boolean(notice));
    if (notice) this.text("source-notice", notice);
    const announcement = `${data?.status ?? "loading"}|${current.state}|${canonicalStatus(data).label}|${data?.session?.status}|${retained}`;
    if (announcement !== this.lastAnnouncement) {
      const sessionLabel = Object.hasOwn(SESSION_LABELS, data?.session?.status) ? ` ${SESSION_LABELS[data.session.status]}; execution unverified.` : "";
      this.text("status-announcement", `${retained ? "Reader failed. Last-known data only. " : ""}${labels[current.state]}. ${data?.status === "configured" ? canonicalStatus(data).label : codeLabel(data?.status ?? "loading")}.${sessionLabel}`);
      this.lastAnnouncement = announcement;
    }
  }

  renderWarnings(data) {
    const warnings = Array.isArray(data?.warnings) ? data.warnings.filter((item) => typeof item === "string") : [];
    if (data?.latest_journal != null && !journalForScope(data)) warnings.push("The latest explanation is unavailable: its display metadata or goal binding is unsupported.");
    if (data?.status === "configured" && data.activity?.items != null && !Array.isArray(data.activity.items)) warnings.push("Activity metadata is unavailable; canonical account values are shown separately.");
    if (data?.strategies != null && strategyItems(data.strategies) === null) warnings.push("Recorded strategy pages are unavailable; canonical account values are shown separately.");
    const intents = [
      ...(Array.isArray(data?.unresolved_intents?.items) ? data.unresolved_intents.items : []),
      ...(Array.isArray(data?.activity?.items) ? data.activity.items.map((item) => item?.intent) : []),
      ...(strategyItems(data?.strategies) ?? []).flatMap((item) => [item.intent, item.latest_action]),
    ];
    if (intents.some((item) => item?.context != null && !contextForIntent(item))) warnings.push("Some recorded action context is unavailable or uses an unsupported format.");
    const signature = JSON.stringify(warnings);
    if (this.warningSignature !== signature) {
      this.node("warnings").replaceChildren(...warnings.map((warning) => element(this.doc, "li", warning)));
      this.warningSignature = signature;
    }
    this.show("warning-panel", warnings.length > 0);
  }

  renderConfigured(state) {
    const data = state.data;
    const metrics = record(data.metrics) ? data.metrics : {};
    const approved = approvedAmounts(data);
    this.money("approved-target", approved.target);
    this.money("net-gain", metrics.estimated_goal_gain, { signed: true, tonal: true });
    this.renderTargetProgress(metrics.progress_pct);
    this.money("remaining-target", metrics.remaining_target);
    this.money("baseline-equity", data.goal?.start_equity);
    this.money("close-costs", metrics.remaining_close_costs);
    this.time("goal-start", data.goal?.started_at);
    this.time("goal-approved", data.goal?.approved_at);
    this.show("active-draft-note", record(data.draft) && (data.draft.budget != null || data.draft.target != null));
    this.money("risk-budget", approved.budget);
    for (const [id, key] of Object.entries({ drawdown: "drawdown", "existing-risk": "existing_risk", "stop-floor": "account_stop_floor", equity: "equity", balance: "balance", "observed-peak": "peak", "free-margin": "free_margin" })) this.money(id, metrics[key]);
    this.money("remaining-risk", metrics.remaining_risk, { signed: true, tonal: true });
    for (const [id, key] of Object.entries({ "positions-count": "positions_count", "pending-count": "orders_count", "entries-count": "entry_orders_count", "protective-count": "protective_orders_count" })) this.text(id, formatCount(data.exposure?.[key]));
    const status = canonicalStatus(data);
    this.text("canonical-state", status.label);
    this.node("canonical-state").dataset.tone = status.tone;
    this.text("canonical-description", status.description);
    this.time("result-time", data.result?.last_verified_at);
    const actions = { remain_stopped: "Remain stopped", cancel_entries_and_close_all: "Cancel pending entries and close all account positions", none: "No stop action recorded" };
    this.text("required-action", Object.hasOwn(actions, data.result?.required_action) ? actions[data.result.required_action] : codeLabel(data.result?.required_action));
    const reasons = data.result?.reason_codes;
    const reasonText = strings(reasons, "No reason codes recorded");
    if (this.node("reason-codes").dataset.signature !== reasonText) {
      this.node("reason-codes").replaceChildren(...(Array.isArray(reasons) && reasons.length ? reasons.filter((reason) => typeof reason === "string") : [reasonText]).map((reason) => element(this.doc, "li", reason)));
      this.node("reason-codes").dataset.signature = reasonText;
    }
    for (const [id, latched, at] of [["loss-stop", status.loss, data.stops?.loss_latched_at], ["target-stop", status.target, data.stops?.target_latched_at]]) {
      this.text(id, latched ? `Latched / ${formatTimestamp(at)}` : record(data.stops) ? "Not latched in saved state" : UNAVAILABLE);
      this.node(id).dataset.tone = latched ? id === "loss-stop" ? "danger" : "accent" : "muted";
    }
    this.text("closure-state", status.closureVerified ? "Account closure verified in saved result" : status.loss || status.target ? "Closure pending / not verified" : "No verified account closure recorded");
    this.node("closure-state").dataset.tone = status.loss && !status.closureVerified ? "danger" : status.target && !status.closureVerified ? "caution" : "muted";
    this.show("closure-results", status.loss || status.target);
    this.money("trigger-gain", data.stops?.target_trigger_gain, { signed: true });
    this.money("final-net", status.closureVerified ? metrics.final_net : null, { signed: true, tonal: true });
    this.money("final-shortfall", status.closureVerified ? metrics.final_shortfall : null);
    this.time("policy-start", data.policy?.started_at);
    this.text("loop-status", data.loop ? `${codeLabel(data.loop.status)} (recorded only)` : "No loop record available");
    this.text("loop-execution", "Unverified");
    const session = record(data.session) && Object.hasOwn(SESSION_LABELS, data.session.status) ? data.session : null;
    this.text("session-status", session ? SESSION_LABELS[session.status] : "Not recorded");
    this.node("session-status").dataset.tone = session?.status === "interrupted" ? "caution" : "muted";
    this.text("session-phase", !session ? "Legacy / bounded workflow" : session.status !== "active" ? "Routine trading disabled"
      : status.loss || status.target ? status.closureVerified ? "Stopped monitoring / no new risk" : "Closure / reconciliation"
        : data.loop?.status === "active" ? "Trading / management" : "Fresh observation required");
    this.text("session-reason", text(session?.reason, "No session-control note recorded."));
    this.text("session-id", text(session?.id));
    this.time("session-started", session?.started_at);
    this.time("session-updated", session?.updated_at);
    this.time("session-next-wake", data.loop?.next_wake_at);
    this.text("loop-policy", text(data.loop?.policy_id));
    this.text("loop-goal", text(data.loop?.goal_id));
    this.time("loop-binding", data.loop?.binding_verified_at);
    this.text("loop-cycles", formatCount(data.loop?.cycles));
    this.text("loop-timeframe", text(data.loop?.timeframe));
    this.time("loop-last", data.loop?.last_cycle_at);
    this.time("loop-next", data.loop?.next_cycle_at);
    this.time("loop-latch-next", data.loop?.next_latch_check_at);
    this.time("loop-wake", data.loop?.next_wake_at);
    const wakeReasons = { candle: "Candle check", bar_retry: "Candle data retry", clock_refresh: "Broker timing refresh",
      market_closed: "Closed-market poll", latch_check: "Account-only limit check", closure: "Closure / reconciliation",
      monitor: "Stopped-account observation", session_check: "Fresh session observation" };
    this.text("loop-wake-reason", Object.hasOwn(wakeReasons, data.loop?.wake_reason) ? wakeReasons[data.loop.wake_reason] : UNAVAILABLE);
    this.text("session-wake-reason", Object.hasOwn(wakeReasons, data.loop?.wake_reason) ? wakeReasons[data.loop.wake_reason] : UNAVAILABLE);
    this.text("loop-overdue", data.loop?.wake_overdue_seconds === 0 ? "Not overdue" : duration(data.loop?.wake_overdue_seconds));
    this.text("loop-gap", duration(data.loop?.max_gap_seconds));
    this.time("loop-observation", data.loop?.last_observation_at);
    this.time("loop-observation-received", data.loop?.last_observation_received_at);
    this.text("loop-observation-age", duration(data.loop?.observation_age_seconds));
    this.text("loop-observation-gap", duration(data.loop?.observation_gap_seconds));
    this.text("loop-max-observation-gap", duration(data.loop?.max_observation_gap_seconds));
    this.time("loop-max-observation-gap-at", data.loop?.max_observation_gap_at);
    this.text("loop-end", codeLabel(data.loop?.end_reason));
    this.renderJournal(data);
    this.renderStrategies(state);
    this.renderActivity(state);
    this.renderIntents(data.unresolved_intents);
  }

  renderTargetProgress(value) {
    const fill = progressFill(value);
    const compact = formatPercent(value, { compact: true });
    const exact = formatPercent(value);
    const tone = decimalSign(value) === -1 ? "danger" : decimalSign(value) === 1 ? "positive" : "neutral";
    this.text("progress-pct", compact);
    this.text("progress-exact", exact);
    this.node("progress-pct").title = isDecimal(value) ? `${value}% (exact)` : UNAVAILABLE;
    this.node("progress-pct").dataset.tone = tone;
    this.node("progress-exact").dataset.tone = tone;
    const progress = this.node("target-progress");
    progress.dataset.tone = fill === null ? "muted" : tone;
    progress.setAttribute("aria-valuetext", fill === null ? "Target progress unavailable" : `${exact} toward the approved target`);
    if (fill === null) progress.removeAttribute("aria-valuenow");
    else progress.setAttribute("aria-valuenow", String(fill));
    const signature = JSON.stringify([value, fill]);
    if (signature !== this.progressSignature) {
      this.node("target-progress-ring").setAttribute("stroke-dashoffset", String(100 - (fill ?? 0)));
      this.progressSignature = signature;
    }
  }

  renderJournal(data) {
    const journal = journalForScope(data);
    const signature = JSON.stringify(journal);
    this.show("journal-content", Boolean(journal));
    this.show("journal-unavailable", !journal);
    this.text("journal-unavailable", data.latest_journal == null ? "No explanation recorded for this goal. Factual helper events remain available below." : "This explanation's metadata or goal binding is unavailable. It is not used to determine account state.");
    if (!journal || signature === this.journalSignature) return;
    this.journalSignature = signature;
    this.text("journal-activity", `Agent explanation / ${journal.activity}`);
    this.time("journal-time", journal.recorded_at);
    this.text("journal-summary", journal.summary);
    this.text("journal-reason", journal.reason);
    this.text("journal-next", journal.next_step);
    const list = this.node("journal-details");
    list.replaceChildren();
    journalFields(this.doc, list, journal);
  }

  renderActivity(state) {
    const { activity } = state;
    const visible = this.activityExpanded ? activity : activity?.slice(0, ACTIVITY_PREVIEW_SIZE);
    this.show("activity-empty", !activity?.length);
    this.text("activity-empty", state.needsRefresh ? "Account or goal changed. Reading its recent activity window." : activity === null ? "Activity unavailable. Missing history is not evidence that no actions occurred." : "No activity recorded in the available window for this goal.");
    const count = Array.isArray(activity) ? activity.length : null;
    let coverage = "";
    if (this.activityExpanded) coverage = `${count ?? 0} recorded events loaded${state.cursor === null ? state.historyGap ? "; the loaded history may still have a reported gap" : " for the complete available history" : " so far"}. `;
    else if (count === 0 && state.cursor !== null) coverage = "No matching events are in the newest loaded page; older recorded activity is available. ";
    else if (count !== null && (count > ACTIVITY_PREVIEW_SIZE || state.cursor !== null)) coverage = `Showing the newest ${Math.min(count, ACTIVITY_PREVIEW_SIZE)} of ${state.cursor !== null ? "at least " : ""}${count} recorded events. `;
    else if (count !== null) coverage = `Showing ${count} recorded ${count === 1 ? "event" : "events"}. `;
    this.text("activity-note", `${coverage}${state.historyGap ? "Loaded pages may have a gap between refreshes; omitted events are not reconstructed." : "This is recorded history, not a continuous execution feed."}`);
    this.rows("activity-list", visible ?? [], (item) => String(item.id), (row, item) => {
      row.details.className = "event-row";
      row.body.className = "event-body";
      const journal = journalForScope(state.data, item.journal ?? null);
      const context = contextForIntent(item.intent);
      const session = record(item.session) && Object.hasOwn(SESSION_LABELS, item.session.status) ? item.session : null;
      const main = element(this.doc, "span", undefined, "event-main");
      const meta = element(this.doc, "span", undefined, "event-meta");
      meta.append(element(this.doc, "span", `${journal ? `Explanation / ${journal.activity}` : `Helper / ${codeLabel(item.command)}`}${context ? ` / ${OPERATIONS[context.operation]}` : ""}`, "event-kind"), element(this.doc, "span", formatTimestamp(item.at)));
      const commandNames = { activate: "Mandate activation recorded", check: "Account snapshot checked", cycle: "Decision cycle recorded", prepare: "Action preparation recorded", resolve: "Action resolution recorded", journal: "Agent explanation recorded", draft: "Monetary draft recorded", session: "Session control recorded" };
      main.append(meta, element(this.doc, "span", journal?.summary ?? (session ? SESSION_LABELS[session.status] : Object.hasOwn(commandNames, item.command) ? commandNames[item.command] : "Account event recorded"), "event-title"));
      const outcome = canonicalStatus({ result: { decision: item.decision, closure_verified: item.closure_verified } });
      const helperLabel = item.decision == null ? "No helper outcome attached to this event" : `Helper outcome: ${outcome.label}`;
      const fact = element(this.doc, "span", `${helperLabel}${item.intent ? ` / Current request status at page read: ${intentStatus(item.intent.status)}` : ""}`, "event-outcome");
      fact.dataset.tone = outcome.tone;
      main.append(fact);
      const toggle = element(this.doc, "span", undefined, "row-toggle");
      toggle.setAttribute("aria-hidden", "true");
      row.summary.replaceChildren(main, toggle);
      row.body.replaceChildren();
      const details = element(this.doc, "dl", undefined, "context-fields");
      if (journal) {
        row.body.append(element(this.doc, "p", "Agent explanation only. The helper outcome and request status above are separate records."));
        definition(this.doc, details, "Reason", journal.reason);
        definition(this.doc, details, "Next recorded step", journal.next_step);
        journalFields(this.doc, details, journal);
      } else if (session) {
        row.body.append(element(this.doc, "p", "Task-control record only. No broker observation, closure or current client execution is established by this event."));
        definition(this.doc, details, "Session ID", text(session.id), true);
        definition(this.doc, details, "Session control", SESSION_LABELS[session.status]);
        definition(this.doc, details, "Recorded reason", text(session.reason));
      } else row.body.append(element(this.doc, "p", "No supported agent explanation is available for this event."));
      definition(this.doc, details, "Event ID", String(item.id), true);
      definition(this.doc, details, "Event recorded at", formatTimestamp(item.at), false, item.at);
      definition(this.doc, details, "Event source observed", formatTimestamp(item.snapshot_at), false, item.snapshot_at);
      definition(this.doc, details, "Helper decision code", text(item.decision), true);
      definition(this.doc, details, "Helper reason codes", strings(item.reason_codes));
      definition(this.doc, details, "Closure at this event", item.closure_verified === true ? "Verified in this event" : item.closure_verified === false ? "Not verified in this event" : UNAVAILABLE);
      if (record(item.intent)) {
        row.body.append(element(this.doc, "p", "Linked request status and its latest outcome are current at page read, not the outcome at this historical event."));
        intentFields(this.doc, details, item.intent, this.currency);
      }
      row.body.append(details);
    });
  }

  renderIntents(intents) {
    const items = Array.isArray(intents?.items) ? intents.items.filter(record) : null;
    this.text("intents-count", formatCount(intents?.count));
    this.show("intents-empty", !items?.length);
    this.text("intents-empty", items === null ? "Unresolved request list unavailable. Unknown requests are not an empty list." : items.length === 0 && intents?.count === 0 ? "No unresolved requests in the saved checkpoint." : "Request details are unavailable for the reported count.");
    this.rows("intents-list", items ?? [], (item) => typeof item.id === "string" ? item.id : null, (row, item) => {
      const context = contextForIntent(item);
      row.details.className = "intent-row";
      const main = element(this.doc, "span", undefined, "intent-main");
      main.append(element(this.doc, "span", `${intentStatus(item.status)} / ${text(item.symbol, "Instrument unavailable")}`, "intent-title"), element(this.doc, "span", `${context ? OPERATIONS[context.operation] : `${codeLabel(item.kind)} (operation unavailable)`} / ${formatTimestamp(item.created_at)}`, "intent-meta"));
      const toggle = element(this.doc, "span", undefined, "row-toggle");
      toggle.setAttribute("aria-hidden", "true");
      row.summary.replaceChildren(main, toggle);
      const list = element(this.doc, "dl", undefined, "context-fields");
      intentFields(this.doc, list, item, this.currency);
      row.body.replaceChildren(list);
    });
  }

  renderStrategies(state) {
    const items = state.strategies;
    this.show("strategies-empty", !items?.length);
    this.text("strategies-empty", state.strategiesNeedRefresh ? "Campaign or saved revision changed. Reading its first strategy page."
      : items === null ? "Recorded strategies unavailable. Missing context is not evidence of no exposure."
        : "No original entry requests in this recorded window. This is not an exposure list.");
    this.text("strategies-note", `${items === null ? "" : `${items.length} original requests loaded at revision ${formatCount(state.data.revision)}. `}Older strategy pages load only on request and reset when the saved revision changes.`);
    this.rows("strategies-list", items ?? [], (item) => item.intent.id, (row, item) => {
      const intent = item.intent;
      const context = contextForIntent(intent);
      const plan = context?.operation === "entry" ? context.strategy : null;
      const last = item.latest_action;
      const lastContext = contextForIntent(last);
      const latest = record(last) && (last.id === intent.id || lastContext?.origin_intent_id === intent.id) ? last : null;
      const note = journalForScope(state.data, item.latest_journal ?? null);
      row.details.className = "intent-row";
      const main = element(this.doc, "span", undefined, "intent-main");
      main.append(element(this.doc, "span", text(plan?.name, "Original strategy unavailable"), "intent-title"),
        element(this.doc, "span", `${text(intent.symbol, "Instrument unavailable")} / Fixed original allocation ${formatMoney(intent.risk, this.currency)}`, "intent-meta"),
        element(this.doc, "span", `Last recorded action: ${latest && lastContext ? OPERATIONS[lastContext.operation] : UNAVAILABLE} / ${formatTimestamp(latest?.created_at)}`, "intent-meta"),
        element(this.doc, "span", `Latest linked assessment: ${text(note?.summary, "Unavailable")} / ${formatTimestamp(note?.recorded_at)}`, "intent-meta"));
      const toggle = element(this.doc, "span", undefined, "row-toggle");
      toggle.setAttribute("aria-hidden", "true");
      row.summary.replaceChildren(main, toggle);
      const body = element(this.doc, "div", undefined, "strategy-context");
      const original = element(this.doc, "div");
      const fields = element(this.doc, "dl", undefined, "context-fields");
      original.append(element(this.doc, "h3", "Original plan, unchanged"), fields);
      definition(this.doc, fields, "Original entry ID", text(intent.id), true);
      definition(this.doc, fields, "Fixed original risk allocation", formatMoney(intent.risk, this.currency), true, intent.risk);
      definition(this.doc, fields, "Original thesis", text(plan?.thesis));
      definition(this.doc, fields, "Side / timeframe", plan ? `${plan.side} / ${plan.timeframe}` : UNAVAILABLE);
      definition(this.doc, fields, "Invalidation", text(plan?.invalidation));
      for (const [field, label] of Object.entries(STRATEGY_RULES)) definition(this.doc, fields, label, plan?.[field] === false ? "Disabled in original plan" : text(plan?.[field]));
      definition(this.doc, fields, "Preparation rationale", text(context?.rationale));
      definition(this.doc, fields, "Plan recorded at", formatTimestamp(intent.created_at), false, intent.created_at);
      definition(this.doc, fields, "Plan source observed", formatTimestamp(intent.snapshot_at), false, intent.snapshot_at);
      definition(this.doc, fields, "Plan source references (inert text)", context ? strings(context.source_refs) : UNAVAILABLE);
      const followup = element(this.doc, "div");
      followup.append(element(this.doc, "h3", "Last recorded action"));
      if (latest) {
        const action = element(this.doc, "dl", undefined, "context-fields");
        intentFields(this.doc, action, latest, this.currency);
        followup.append(action);
      } else followup.append(element(this.doc, "p", "Linked action unavailable; no outcome is inferred.", "section-note"));
      followup.append(element(this.doc, "h3", "Latest linked assessment"));
      if (note) {
        const assessment = element(this.doc, "dl", undefined, "context-fields");
        definition(this.doc, assessment, "Assessment", note.summary);
        definition(this.doc, assessment, "Reason", note.reason);
        definition(this.doc, assessment, "Next recorded step", note.next_step);
        definition(this.doc, assessment, "Assessment recorded at", formatTimestamp(note.recorded_at), false, note.recorded_at);
        journalFields(this.doc, assessment, note);
        followup.append(assessment);
      } else followup.append(element(this.doc, "p", "No supported linked assessment is available. Unlinked reports are not assigned by symbol.", "section-note"));
      body.append(original, followup);
      row.body.replaceChildren(body);
    });
  }

  controls(controller) {
    const busy = controller.inFlight !== null;
    const older = busy && controller.inFlight.before !== null;
    this.text("refresh-button", busy ? "Reading..." : "Refresh now");
    this.node("refresh-button").setAttribute("aria-disabled", busy ? "true" : "false");
    this.text("reader-state", busy ? "Reading local API" : controller.error ? `Read failed / retry within ${pollDelay(this.doc.hidden, controller.failures) / 1000}s` : `UI refresh / ${pollDelay(this.doc.hidden, controller.failures) / 1000}s`);
    const activity = controller.state?.activity;
    const loaded = Array.isArray(activity) ? activity.length : 0;
    const hasMore = cursor(controller.state?.cursor) !== null;
    const canToggle = Array.isArray(activity) && (this.activityExpanded || loaded > ACTIVITY_PREVIEW_SIZE || hasMore);
    this.show("activity-toggle", canToggle);
    this.text("activity-toggle", this.activityExpanded ? "Show latest 5" : "View all activity");
    this.node("activity-toggle").disabled = !canToggle;
    this.node("activity-toggle").setAttribute("aria-expanded", this.activityExpanded ? "true" : "false");
    this.node("activity-list").setAttribute("aria-busy", older ? "true" : "false");
    let activityState = "";
    if (controller.state?.needsRefresh) activityState = "Refreshing the changed account or goal";
    else if (activity === null) activityState = "Activity unavailable";
    else if (this.activityExpanded && older) activityState = `Loading older activity / ${loaded} events loaded`;
    else if (this.activityExpanded && controller.activityPaginationStalled) activityState = controller.activityPaginationReason === "failures"
      ? `View all stopped after ${ACTIVITY_PAGE_RETRIES} failed reads of the same older page / ${loaded} events loaded`
      : `View all stopped because the activity cursor did not advance / ${loaded} events loaded`;
    else if (this.activityExpanded && controller.error && hasMore) activityState = `View all paused after ${loaded} events / retrying the reader`;
    else if (this.activityExpanded && controller.error) activityState = `${loaded} last-known events shown / latest read failed`;
    else if (this.activityExpanded && hasMore) activityState = `Preparing older activity / ${loaded} events loaded`;
    else if (this.activityExpanded) activityState = controller.state?.historyGap ? `${loaded} events shown / loaded history may have a gap` : `${loaded} events shown / complete available history`;
    else if (canToggle) activityState = `Latest ${Math.min(loaded, ACTIVITY_PREVIEW_SIZE)} shown`;
    this.text("activity-state", activityState);
    const strategyMore = cursor(controller.state?.strategyCursor) !== null;
    const readingStrategies = busy && controller.inFlight.strategyBefore !== null;
    this.show("strategies-more", strategyMore);
    this.node("strategies-more").disabled = busy || !strategyMore || controller.strategyPaginationStalled;
    this.node("strategies-list").setAttribute("aria-busy", readingStrategies ? "true" : "false");
    this.text("strategies-state", readingStrategies ? "Loading one older strategy page"
      : controller.state?.strategiesNeedRefresh ? "Refreshing the changed campaign or saved revision"
        : controller.strategyPaginationStalled ? "Older strategies unavailable: the cursor did not advance"
          : controller.state?.strategies === null ? "Strategy data unavailable"
            : controller.error ? "Last-known strategies only / reader retry pending"
              : strategyMore ? "More original requests are available" : "End of the available strategy window");
  }
}

export class DashboardController {
  constructor(doc, { fetcher = globalThis.fetch, clock = () => Date.now() } = {}) {
    this.doc = doc;
    this.fetcher = fetcher.bind(globalThis);
    this.clock = clock;
    this.view = new DashboardView(doc);
    this.state = null;
    this.error = null;
    this.successfulAt = null;
    this.failures = 0;
    this.sequence = 0;
    this.inFlight = null;
    this.refreshQueued = false;
    this.activityCursors = new Set();
    this.activityCursorFailures = new Map();
    this.activityPaginationStalled = false;
    this.activityPaginationReason = null;
    this.strategyPaginationStalled = false;
    this.timer = null;
    this.ageTimer = null;
    this.stopped = true;
    this.onVisibility = () => {
      clearTimeout(this.timer);
      if (!this.doc.hidden) this.request();
      else if (!this.inFlight) this.schedule();
      this.view.controls(this);
    };
    this.onRefresh = () => { if (!this.inFlight) this.request(); };
    this.onActivityToggle = () => {
      if (!Array.isArray(this.state?.activity)) return;
      this.view.activityExpanded = !this.view.activityExpanded;
      this.activityCursors.clear();
      this.activityCursorFailures.clear();
      this.activityPaginationStalled = false;
      this.activityPaginationReason = null;
      this.view.renderActivity(this.state);
      this.view.controls(this);
      if (this.view.activityExpanded && !this.inFlight) this.loadNextActivityPage();
    };
    this.onPageHide = () => this.stop();
    this.onPageShow = () => { if (this.stopped) this.start(); };
    this.onStrategiesMore = () => {
      const next = cursor(this.state?.strategyCursor);
      if (!this.stopped && !this.doc.hidden && !this.inFlight && !this.strategyPaginationStalled && next !== null) this.request(null, next);
    };
  }

  start() {
    if (!this.stopped) return;
    this.stopped = false;
    this.doc.addEventListener("visibilitychange", this.onVisibility);
    this.view.node("refresh-button").addEventListener("click", this.onRefresh);
    this.view.node("activity-toggle").addEventListener("click", this.onActivityToggle);
    this.view.node("strategies-more").addEventListener("click", this.onStrategiesMore);
    this.doc.defaultView?.addEventListener("pagehide", this.onPageHide);
    this.doc.defaultView?.addEventListener("pageshow", this.onPageShow);
    this.ageTimer = setInterval(() => {
      if (!this.doc.hidden) this.view.freshness(this.state?.data, this.clock(), Boolean(this.error));
    }, 1000);
    this.view.render(this.state, { error: this.error, successfulAt: this.successfulAt, now: this.clock() });
    this.request();
  }

  stop() {
    this.stopped = true;
    this.sequence += 1;
    clearTimeout(this.timer);
    clearInterval(this.ageTimer);
    this.inFlight?.abort.abort();
    this.inFlight = null;
    this.refreshQueued = false;
    this.activityCursors.clear();
    this.activityCursorFailures.clear();
    this.activityPaginationStalled = false;
    this.activityPaginationReason = null;
    this.strategyPaginationStalled = false;
    this.doc.removeEventListener("visibilitychange", this.onVisibility);
    this.view.node("refresh-button").removeEventListener("click", this.onRefresh);
    this.view.node("activity-toggle").removeEventListener("click", this.onActivityToggle);
    this.view.node("strategies-more").removeEventListener("click", this.onStrategiesMore);
    this.doc.defaultView?.removeEventListener("pagehide", this.onPageHide);
  }

  schedule() {
    clearTimeout(this.timer);
    if (!this.stopped) this.timer = setTimeout(() => this.request(), pollDelay(this.doc.hidden, this.failures));
  }

  loadNextActivityPage() {
    const next = cursor(this.state?.cursor);
    if (this.stopped || this.doc.hidden || this.inFlight || !this.view.activityExpanded || this.activityPaginationStalled || next === null) return false;
    if ((this.activityCursorFailures.get(next) ?? 0) >= ACTIVITY_PAGE_RETRIES) {
      this.activityPaginationStalled = true;
      this.activityPaginationReason = "failures";
      this.view.controls(this);
      return false;
    }
    if (this.activityCursors.has(next)) {
      this.activityPaginationStalled = true;
      this.activityPaginationReason = "cursor";
      this.view.controls(this);
      return false;
    }
    this.activityCursors.add(next);
    this.request(next);
    return true;
  }

  async request(before = null, strategyBefore = null) {
    if (this.stopped) return;
    if (this.inFlight) { if (before === null && strategyBefore === null) this.refreshQueued = true; return; }
    if (before !== null && (cursor(before) === null || strategyBefore !== null) || strategyBefore !== null && cursor(strategyBefore) === null) return;
    if (strategyBefore !== null && strategyBefore !== this.state?.strategyCursor) return;
    clearTimeout(this.timer);
    const requestId = ++this.sequence;
    const requestScope = scopeKey(this.state?.data);
    const requestRevision = this.state?.data.revision;
    const abort = new AbortController();
    this.inFlight = { before, strategyBefore, abort };
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; abort.abort(); }, 8000);
    this.view.controls(this);
    try {
      const url = strategyBefore !== null ? `/api/dashboard?strategy_before=${strategyBefore}` : before === null ? "/api/dashboard" : `/api/dashboard?before=${before}`;
      const response = await this.fetcher(url, {
        method: "GET", headers: { Accept: "application/json" }, cache: "no-store", credentials: "omit", redirect: "error", signal: abort.signal,
      });
      const data = await response.json();
      if (requestId !== this.sequence || this.stopped) return;
      if (!response.ok || !isDashboardResponse(data)) {
        const safeCode = data?.ok === false && typeof data.error === "string" && /^[a-z0-9_]{1,100}$/.test(data.error) ? data.error : "invalid_response";
        throw new Error(safeCode);
      }
      const next = mergeDashboardPage(this.state, data, { before, strategyBefore, requestScope, requestRevision, requestId, latestRequestId: this.sequence });
      if (next === this.state) throw new Error("revision_regressed");
      const previousScope = this.state?.scope;
      const previousCursor = this.state?.cursor;
      if (previousScope !== next.scope || this.state?.data.revision !== next.data.revision) this.strategyPaginationStalled = false;
      else if (strategyBefore !== null) this.strategyPaginationStalled = next.strategyCursor !== null && next.strategyCursor >= strategyBefore;
      this.state = next;
      if (previousScope !== next.scope) {
        this.activityCursors.clear();
        this.activityCursorFailures.clear();
        this.activityPaginationStalled = false;
        this.activityPaginationReason = null;
      } else if (before === null && previousCursor !== next.cursor) {
        this.activityCursors.clear();
        this.activityCursorFailures.clear();
        this.activityPaginationStalled = false;
        this.activityPaginationReason = null;
      } else if (before !== null) {
        this.activityCursorFailures.delete(before);
        this.activityPaginationStalled = next.cursor !== null && next.cursor >= before;
        this.activityPaginationReason = this.activityPaginationStalled ? "cursor" : null;
      }
      this.error = null;
      this.failures = 0;
      this.successfulAt = new Date(this.clock()).toISOString();
      this.view.render(this.state, { successfulAt: this.successfulAt, now: this.clock() });
      if (next.needsRefresh || next.strategiesNeedRefresh) this.refreshQueued = true;
    } catch (error) {
      if (requestId !== this.sequence || this.stopped) return;
      if (before !== null) {
        this.activityCursors.delete(before);
        const failures = (this.activityCursorFailures.get(before) ?? 0) + 1;
        this.activityCursorFailures.set(before, failures);
        if (failures >= ACTIVITY_PAGE_RETRIES) {
          this.activityPaginationStalled = true;
          this.activityPaginationReason = "failures";
        }
      }
      this.failures = Math.min(this.failures + 1, 3);
      this.error = timedOut ? "request_timeout" : typeof error?.message === "string" && /^[a-z0-9_]{1,100}$/.test(error.message) ? error.message : "reader_unavailable";
      this.view.render(this.state, { error: this.error, successfulAt: this.successfulAt, now: this.clock() });
    } finally {
      clearTimeout(timeout);
      if (requestId === this.sequence) {
        this.inFlight = null;
        this.view.controls(this);
        if (this.refreshQueued && !this.stopped) {
          this.refreshQueued = false;
          this.request();
        } else if (!this.error && this.loadNextActivityPage()) {
          // The bounded cursor chain remains sequential through request().
        } else this.schedule();
      }
    }
  }
}

if (typeof document !== "undefined" && document.getElementById("ace-dashboard")) {
  new DashboardController(document).start();
}
