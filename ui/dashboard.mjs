const UNAVAILABLE = "Unavailable";
const DECIMAL = /^[+-]?\d+(?:\.\d+)?$/;
const UTC_STAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$/;
const SVG_NS = "http://www.w3.org/2000/svg";
const ACTIVITIES = new Set(["analysis", "wait", "entry", "management", "exit", "blocked"]);
const OUTCOMES = {
  within_budget: ["Within budget at last check", "neutral", "The recorded check was within the monetary budget. It is not a current permission to trade."],
  blocked: ["Latest check blocked", "caution", "The helper recorded a blocker. Values below still belong to the displayed source observation; they do not imply the latest action succeeded."],
  reconciliation_required: ["Reconciliation required", "caution", "The helper could not establish a reconciled result. Saved metrics must not be treated as a successful new check."],
  prepared: ["Request prepared", "neutral", "A local request was prepared. Preparation is not evidence of broker execution."],
  cached: ["Saved helper result", "muted", "This is a saved result, not a fresh account verification."],
  draft: ["Unapproved draft", "caution", "Draft amounts do not authorize execution."],
  draft_saved: ["Unapproved draft", "caution", "Draft amounts do not authorize execution."],
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

export function orderDetail(order, field, currency) {
  const details = order?.details;
  if (!record(details)) return UNAVAILABLE;
  if (Array.isArray(details.unset_fields) && details.unset_fields.includes(field)) {
    return details[field] == null ? "Not set" : UNAVAILABLE;
  }
  if (field === "placed_at" || field === "expires_at") return formatTimestamp(details[field]);
  if (field === "volume_initial" || field === "volume_remaining") {
    return details.volume_unit === "lots" && isDecimal(details[field]) ? `${formatDecimal(details[field])} lots` : UNAVAILABLE;
  }
  if (["entry_price", "stop_limit_price", "stop_loss", "take_profit"].includes(field)) return formatDecimal(details[field]);
  if (field === "risk") return formatMoney(order.risk, currency);
  if (field === "side") return ["buy", "sell"].includes(details.side) ? codeLabel(details.side) : UNAVAILABLE;
  if (field === "ownership") return ["ace", "manual", "mixed", "unknown"].includes(details.ownership) ? details.ownership === "ace" ? "Ace" : codeLabel(details.ownership) : UNAVAILABLE;
  return text(details[field]);
}

export function ordersForFilter(orders, filter = "all") {
  if (!Array.isArray(orders)) return null;
  return orders.filter((order) => record(order) && (filter === "all" || order.kind === filter));
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

// An older page carries a current summary, but its chart and events cannot be
// attached to a different account/policy/goal while a request is in flight.
export function mergeDashboardPage(previous, data, {
  before = null, requestScope = scopeKey(previous?.data), requestId = 0, latestRequestId = requestId,
} = {}) {
  if (requestId !== latestRequestId) return previous;
  if (!isDashboardResponse(data)) throw new TypeError("invalid_response");
  const scope = scopeKey(data);
  const changed = !previous || previous.scope !== scope;
  if (!changed && data.revision < previous.data.revision) return previous;
  const hadConfigured = previous?.hadConfigured === true || data.status === "configured";
  if (data.status !== "configured") {
    return { data, scope, activity: null, progress: null, cursor: null, needsRefresh: false,
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
  return {
    data, scope, activity,
    progress: mismatchedPage ? null : before === null ? data.progress ?? null : changed ? null : previous.progress,
    cursor: mismatchedPage ? null : nextCursor,
    needsRefresh: mismatchedPage,
    historyGap: !changed && (previous.historyGap || disjoint),
    hadConfigured, unconfiguredAfterLoad: false,
  };
}

function coordinate(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

export function chartGeometry(progress) {
  const points = Array.isArray(progress?.points) ? progress.points.filter(record) : null;
  const samples = [];
  const segments = [];
  const gaps = [];
  let segment = [];
  for (const [index, point] of (points ?? []).entries()) {
    const plottable = coordinate(point.x) && coordinate(point.y) && isDecimal(point.gain) && isDecimal(point.pct);
    if (point.gap_before || !plottable) {
      if (segment.length) segments.push(segment);
      segment = [];
    }
    if (point.gap_before && coordinate(point.x)) gaps.push(50 + point.x * 720);
    if (!plottable) continue;
    const sample = { point, key: JSON.stringify([point.event_id, point.snapshot_id, point.as_of, index]), x: 50 + point.x * 720, y: 20 + point.y * 180 };
    samples.push(sample);
    segment.push(sample);
  }
  if (segment.length) segments.push(segment);
  return {
    points, samples, segments, gaps,
    targetY: coordinate(progress?.target_y) ? 20 + progress.target_y * 180 : null,
    zeroY: coordinate(progress?.zero_y) ? 20 + progress.zero_y * 180 : null,
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

function svgElement(doc, tag, attributes = {}, content) {
  const node = doc.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
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
  definition(doc, list, "Request ID", text(intent.id), true);
  definition(doc, list, "Request kind", codeLabel(intent.kind));
  definition(doc, list, "Recorded status", intentStatus(intent.status));
  definition(doc, list, "Instrument", text(intent.symbol));
  definition(doc, list, "Stressed risk", formatMoney(intent.risk, currency), true, intent.risk);
  definition(doc, list, "Recorded tickets", strings(intent.tickets), true);
  definition(doc, list, "Prepared at", formatTimestamp(intent.created_at), false, intent.created_at);
  definition(doc, list, "Source observed", formatTimestamp(intent.snapshot_at), false, intent.snapshot_at);
  definition(doc, list, "Recorded outcome", intentStatus(intent.outcome?.outcome));
  definition(doc, list, "Outcome recorded at", formatTimestamp(intent.outcome?.at), false, intent.outcome?.at);
  definition(doc, list, "Outcome source time", formatTimestamp(intent.outcome?.snapshot_at), false, intent.outcome?.snapshot_at);
  definition(doc, list, "Outcome broker tickets", strings(intent.outcome?.broker_tickets), true);
}

class DashboardView {
  constructor(doc) {
    this.doc = doc;
    this.rowCaches = new Map();
    this.chartSignature = null;
    this.journalSignature = null;
    this.warningSignature = null;
    this.scope = null;
    this.currency = null;
    this.lastAnnouncement = "";
    this.filter = "all";
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
    this.chartSignature = null;
    this.journalSignature = null;
    this.text("chart-readout", "Focus or point to a sample for exact values.");
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
      this.text("reader-error", `Local reader unavailable (${error}).${retained} The page will retry; it does not repair state or contact the broker.`);
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
      this.text("empty-description", "These are monetary drafts, not an active mandate. There is no approved target progress to display. Onboarding and approval happen with the agent, not on this page.");
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
    const announcement = `${data?.status ?? "loading"}|${current.state}|${canonicalStatus(data).label}|${retained}`;
    if (announcement !== this.lastAnnouncement) {
      this.text("status-announcement", `${retained ? "Reader failed. Last-known data only. " : ""}${labels[current.state]}. ${data?.status === "configured" ? canonicalStatus(data).label : codeLabel(data?.status ?? "loading")}.`);
      this.lastAnnouncement = announcement;
    }
  }

  renderWarnings(data) {
    const warnings = Array.isArray(data?.warnings) ? data.warnings.filter((item) => typeof item === "string") : [];
    if (data?.latest_journal != null && !journalForScope(data)) warnings.push("The latest explanation is unavailable: its display metadata or goal binding is unsupported.");
    if (data?.status === "configured" && data.activity?.items != null && !Array.isArray(data.activity.items)) warnings.push("Activity metadata is unavailable; canonical account values are shown separately.");
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
    this.text("progress-pct", formatPercent(metrics.progress_pct, { compact: true }));
    this.node("progress-pct").title = isDecimal(metrics.progress_pct) ? `${metrics.progress_pct}% (exact)` : UNAVAILABLE;
    this.node("progress-pct").dataset.tone = decimalSign(metrics.progress_pct) === -1 ? "danger" : decimalSign(metrics.progress_pct) === 1 ? "positive" : "neutral";
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
      market_closed: "Closed-market poll", latch_check: "Account-only limit check", closure: "Closure / reconciliation" };
    this.text("loop-wake-reason", Object.hasOwn(wakeReasons, data.loop?.wake_reason) ? wakeReasons[data.loop.wake_reason] : UNAVAILABLE);
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
    this.renderChart(state.progress);
    this.renderActivity(state);
    this.renderOrders(data.pending_orders);
    this.renderIntents(data.unresolved_intents);
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

  renderChart(progress) {
    const signature = JSON.stringify([progress, this.currency]);
    if (signature === this.chartSignature) return;
    this.chartSignature = signature;
    const geometry = chartGeometry(progress);
    const { points, samples, segments, gaps, targetY, zeroY } = geometry;
    const drawing = this.node("chart-drawing");
    const focusedKey = this.doc.activeElement?.getAttribute("data-point-key");
    drawing.replaceChildren();
    const shape = (tag, attributes, content) => {
      const node = svgElement(this.doc, tag, attributes, content);
      drawing.append(node);
      return node;
    };
    for (const y of [20, 65, 110, 155, 200]) shape("line", { x1: 50, x2: 770, y1: y, y2: y, class: "chart-grid", "aria-hidden": "true" });
    if (zeroY !== null) shape("line", { x1: 50, x2: 770, y1: zeroY, y2: zeroY, class: "chart-zero", "aria-hidden": "true" });
    if (targetY !== null) {
      shape("line", { x1: 50, x2: 770, y1: targetY, y2: targetY, class: "chart-target", "aria-hidden": "true" });
      shape("text", { x: 770, y: Math.max(12, targetY - 7), "text-anchor": "end", class: "chart-target-label", "aria-hidden": "true" }, "TARGET");
    }
    for (const x of gaps) shape("line", { x1: x, x2: x, y1: 20, y2: 200, class: "chart-gap", "aria-hidden": "true" });
    for (const segment of segments) {
      if (segment.length < 2) continue;
      const path = segment.map((sample, index) => `${index ? "L" : "M"}${sample.x.toFixed(3)},${sample.y.toFixed(3)}`).join(" ");
      shape("path", { d: path, class: "chart-line", "aria-hidden": "true" });
    }
    let restoreFocus = null;
    for (const sample of samples) {
      const { point } = sample;
      const note = `${formatTimestamp(point.as_of)} | Net gain ${formatMoney(point.gain, this.currency, { signed: true })} | ${formatPercent(point.pct)} | Target ${formatMoney(point.target, this.currency)}${point.gap_before ? " | Gap before this sample" : ""}${point.legacy ? " | Legacy checkpoint" : ""}`;
      const dot = shape("circle", { cx: sample.x, cy: sample.y, r: 5, tabindex: 0, role: "img", class: "chart-point", "data-point-key": sample.key, "aria-label": note });
      dot.append(svgElement(this.doc, "title", {}, note));
      dot.addEventListener("focus", () => this.text("chart-readout", note));
      dot.addEventListener("pointerenter", () => this.text("chart-readout", note));
      dot.addEventListener("click", () => this.text("chart-readout", note));
      if (focusedKey === sample.key) restoreFocus = dot;
    }
    this.show("progress-chart", samples.length > 0);
    this.show("chart-empty", samples.length === 0);
    this.text("chart-empty", points === null ? "Progress history unavailable." : points.length === 0 ? "No progress observations recorded for this goal." : "No plottable gain values in this window. Available source details are in the table.");
    this.time("chart-from", progress?.from);
    this.time("chart-to", progress?.to);
    this.text("chart-scale", isDecimal(progress?.min_pct) && isDecimal(progress?.max_pct) ? `Window scale ${formatPercent(progress.min_pct, { compact: true })} to ${formatPercent(progress.max_pct, { compact: true })}` : "Scale unavailable");
    const coverage = ["Recent current-goal window only. Straight lines join recorded samples, not continuous observations."];
    if (progress?.incomplete === true || cursor(progress?.next_cursor) !== null) coverage.push("Coverage is incomplete; earlier or missing observations are not reconstructed.");
    if (gaps.length) coverage.push("Vertical dashed marks and line breaks show reported gaps.");
    if (points?.some((point) => point.legacy)) coverage.push("Legacy checkpoint values are timestamped samples; detailed history was not recorded.");
    if (targetY === null && points?.length) coverage.push("The target reference coordinate is unavailable.");
    this.text("chart-coverage", coverage.join(" "));
    this.text("chart-table-summary", points === null ? "Exact observations unavailable" : `View exact observations (${points.length})`);
    this.text("chart-readout", samples.length ? "Focus or point to a sample for exact values. All values are also in the table." : "Exact available source values are shown in the observations table.");
    const tbody = this.node("chart-table-body");
    tbody.replaceChildren();
    for (const point of points ?? []) {
      const row = element(this.doc, "tr");
      for (const [value, numeric, exact] of [
        [formatTimestamp(point.as_of), false, point.as_of],
        [formatMoney(point.gain, this.currency, { signed: true }), true, point.gain],
        [formatPercent(point.pct), true, point.pct],
        [formatMoney(point.target, this.currency), true, point.target],
        [`${text(point.snapshot_id)}${point.gap_before ? " / gap before" : ""}${point.legacy ? " / legacy checkpoint" : ""}`, false, null],
      ]) {
        const cell = element(this.doc, "td", value, numeric ? "numeric" : undefined);
        if (typeof exact === "string") cell.title = exact;
        row.append(cell);
      }
      tbody.append(row);
    }
    if (!points?.length) {
      const row = element(this.doc, "tr");
      const cell = element(this.doc, "td", points === null ? "Observation values unavailable." : "No recorded samples in this window.");
      cell.colSpan = 5;
      row.append(cell);
      tbody.append(row);
    }
    restoreFocus?.focus({ preventScroll: true });
  }

  renderActivity(state) {
    const { activity } = state;
    this.show("activity-empty", !activity?.length);
    this.text("activity-empty", state.needsRefresh ? "Account or goal changed. Reading its recent activity window." : activity === null ? "Activity unavailable. Missing history is not evidence that no actions occurred." : "No activity recorded in the available window for this goal.");
    this.text("activity-note", `${Array.isArray(activity) ? `${activity.length} loaded events for this account and goal. ` : ""}Older pages load only on request.${state.historyGap ? " Loaded pages may have a gap between refreshes; omitted events are not reconstructed." : " This is recorded history, not a continuous execution feed."}`);
    this.rows("activity-list", activity ?? [], (item) => String(item.id), (row, item) => {
      row.details.className = "event-row";
      row.body.className = "event-body";
      const journal = journalForScope(state.data, item.journal);
      const main = element(this.doc, "span", undefined, "event-main");
      const meta = element(this.doc, "span", undefined, "event-meta");
      meta.append(element(this.doc, "span", journal ? `Explanation / ${journal.activity}` : `Helper / ${codeLabel(item.command)}`, "event-kind"), element(this.doc, "span", formatTimestamp(item.at)));
      const commandNames = { activate: "Mandate activation recorded", check: "Account snapshot checked", cycle: "Decision cycle recorded", prepare: "Action preparation recorded", resolve: "Action resolution recorded", journal: "Agent explanation recorded", draft: "Monetary draft recorded" };
      main.append(meta, element(this.doc, "span", journal?.summary ?? (Object.hasOwn(commandNames, item.command) ? commandNames[item.command] : "Account event recorded"), "event-title"));
      const outcome = canonicalStatus({ result: { decision: item.decision, closure_verified: item.closure_verified } });
      const helperLabel = item.decision == null ? "No helper outcome attached to this event" : `Helper outcome: ${outcome.label}`;
      const fact = element(this.doc, "span", `${helperLabel}${item.intent ? ` / ${intentStatus(item.intent.status)}` : ""}`, "event-outcome");
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
      } else row.body.append(element(this.doc, "p", "No supported agent explanation is available for this event."));
      definition(this.doc, details, "Event ID", String(item.id), true);
      definition(this.doc, details, "Event recorded at", formatTimestamp(item.at), false, item.at);
      definition(this.doc, details, "Event source observed", formatTimestamp(item.snapshot_at), false, item.snapshot_at);
      definition(this.doc, details, "Helper decision code", text(item.decision), true);
      definition(this.doc, details, "Helper reason codes", strings(item.reason_codes));
      definition(this.doc, details, "Closure at this event", item.closure_verified === true ? "Verified in this event" : item.closure_verified === false ? "Not verified in this event" : UNAVAILABLE);
      if (record(item.intent)) intentFields(this.doc, details, item.intent, this.currency);
      row.body.append(details);
    });
  }

  renderOrders(orders) {
    const all = ordersForFilter(orders);
    const visible = ordersForFilter(orders, this.filter);
    this.text("orders-total", all === null ? UNAVAILABLE : `${all.length} recorded`);
    this.node("order-filter").disabled = all === null;
    this.show("orders-empty", !visible?.length);
    this.text("orders-empty", all === null ? "Pending order list unavailable. This does not mean there are no broker orders." : all.length === 0 ? "No broker pending orders in this source observation." : "No recorded orders match this filter. Other account orders remain in the all-orders view.");
    this.rows("orders-list", all ?? [], (order) => typeof order.ticket === "string" ? order.ticket : null, (row, order) => {
      row.details.className = "order-row";
      const identity = element(this.doc, "span", undefined, "order-identity");
      identity.append(element(this.doc, "span", text(order.symbol), "order-symbol"), element(this.doc, "span", `Ticket ${text(order.ticket)}`, "order-ticket numeric"));
      const classification = element(this.doc, "span", undefined, "order-classification");
      const kind = order.kind === "entry" ? "Entry" : order.kind === "protective" ? "Protective" : "Kind unavailable";
      classification.append(element(this.doc, "span", kind, "order-type"), element(this.doc, "span", `${orderDetail(order, "side")} / ${orderDetail(order, "ownership")}`, "order-sub"));
      const remaining = element(this.doc, "span", undefined, "order-value numeric");
      remaining.append(element(this.doc, "span", "Lots left", "mobile-label"), element(this.doc, "span", orderDetail(order, "volume_remaining")));
      const risk = element(this.doc, "span", undefined, "order-value numeric");
      risk.title = isDecimal(order.risk) ? `${order.risk} ${text(this.currency)} (exact)` : UNAVAILABLE;
      risk.append(element(this.doc, "span", "Stressed risk", "mobile-label"), element(this.doc, "span", formatMoney(order.risk, this.currency)));
      const toggle = element(this.doc, "span", undefined, "row-toggle");
      toggle.setAttribute("aria-hidden", "true");
      row.summary.replaceChildren(identity, classification, remaining, risk, toggle);
      row.body.replaceChildren();
      const list = element(this.doc, "dl", undefined, "order-fields");
      definition(this.doc, list, "Order type", orderDetail(order, "order_type"));
      definition(this.doc, list, "Side", orderDetail(order, "side"));
      definition(this.doc, list, "Ownership", orderDetail(order, "ownership"));
      definition(this.doc, list, "Protective stop verified", order.protected === true ? "Protected" : order.protected === false ? "Not protected" : UNAVAILABLE);
      for (const [field, label] of Object.entries({ volume_initial: "Original volume", volume_remaining: "Remaining volume", entry_price: "Entry price", stop_limit_price: "Stop-limit price", stop_loss: "Stop loss", take_profit: "Take profit", placed_at: "Placed at", expires_at: "Expires at" })) {
        definition(this.doc, list, label, orderDetail(order, field), !field.endsWith("_at"), order.details?.[field]);
      }
      definition(this.doc, list, "Related position ticket", text(order.position_ticket), true);
      definition(this.doc, list, "Stressed risk", formatMoney(order.risk, this.currency), true, order.risk);
      row.body.append(list, element(this.doc, "p", order.details == null ? "Display enrichment is unavailable. This order exists in the saved broker snapshot; no side, price or ownership is inferred." : "Details are agent-supplied for the source snapshot. Ownership is not inferred from a ticket or local intent.", "order-detail-note"));
    });
    const visibleTickets = new Set((visible ?? []).map((order) => order.ticket));
    for (const [ticket, row] of this.rowCaches.get("orders-list") ?? []) row.li.hidden = !visibleTickets.has(ticket);
  }

  renderIntents(intents) {
    const items = Array.isArray(intents?.items) ? intents.items.filter(record) : null;
    this.text("intents-count", formatCount(intents?.count));
    this.show("intents-empty", !items?.length);
    this.text("intents-empty", items === null ? "Unresolved request list unavailable. Unknown requests are not an empty list." : items.length === 0 && intents?.count === 0 ? "No unresolved requests in the saved checkpoint." : "Request details are unavailable for the reported count.");
    this.rows("intents-list", items ?? [], (item) => typeof item.id === "string" ? item.id : null, (row, item) => {
      row.details.className = "intent-row";
      const main = element(this.doc, "span", undefined, "intent-main");
      main.append(element(this.doc, "span", `${intentStatus(item.status)} / ${text(item.symbol, "Instrument unavailable")}`, "intent-title"), element(this.doc, "span", `${codeLabel(item.kind)} / ${formatTimestamp(item.created_at)}`, "intent-meta"));
      const toggle = element(this.doc, "span", undefined, "row-toggle");
      toggle.setAttribute("aria-hidden", "true");
      row.summary.replaceChildren(main, toggle);
      const list = element(this.doc, "dl", undefined, "context-fields");
      intentFields(this.doc, list, item, this.currency);
      row.body.replaceChildren(list);
    });
  }

  controls(controller) {
    const busy = controller.inFlight !== null;
    const older = busy && controller.inFlight.before !== null;
    this.text("refresh-button", busy ? "Reading..." : "Refresh now");
    this.node("refresh-button").setAttribute("aria-disabled", busy ? "true" : "false");
    this.text("reader-state", busy ? "Reading local API" : controller.error ? `Read failed / retry within ${pollDelay(this.doc.hidden, controller.failures) / 1000}s` : `UI refresh / ${pollDelay(this.doc.hidden, controller.failures) / 1000}s`);
    this.text("older-button", older ? "Loading older activity..." : "Load older activity");
    this.node("older-button").disabled = busy || !controller.state?.cursor;
    this.text("older-state", older ? "Reading one older page" : controller.state?.needsRefresh ? "Refreshing the changed account/goal" : controller.state?.activity === null || !controller.state ? "" : controller.state.cursor === null ? "No older page available" : "Current view is retained");
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
    this.onOlder = () => { if (!this.inFlight && this.state?.cursor) this.request(this.state.cursor); };
    this.onFilter = () => {
      this.view.filter = this.view.node("order-filter").value;
      this.view.renderOrders(this.state?.data?.pending_orders);
    };
    this.onPageHide = () => this.stop();
    this.onPageShow = () => { if (this.stopped) this.start(); };
  }

  start() {
    if (!this.stopped) return;
    this.stopped = false;
    this.doc.addEventListener("visibilitychange", this.onVisibility);
    this.view.node("refresh-button").addEventListener("click", this.onRefresh);
    this.view.node("older-button").addEventListener("click", this.onOlder);
    this.view.node("order-filter").addEventListener("change", this.onFilter);
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
    this.doc.removeEventListener("visibilitychange", this.onVisibility);
    this.view.node("refresh-button").removeEventListener("click", this.onRefresh);
    this.view.node("older-button").removeEventListener("click", this.onOlder);
    this.view.node("order-filter").removeEventListener("change", this.onFilter);
    this.doc.defaultView?.removeEventListener("pagehide", this.onPageHide);
  }

  schedule() {
    clearTimeout(this.timer);
    if (!this.stopped) this.timer = setTimeout(() => this.request(), pollDelay(this.doc.hidden, this.failures));
  }

  async request(before = null) {
    if (this.stopped) return;
    if (this.inFlight) { if (before === null) this.refreshQueued = true; return; }
    if (before !== null && cursor(before) === null) return;
    clearTimeout(this.timer);
    const requestId = ++this.sequence;
    const requestScope = scopeKey(this.state?.data);
    const abort = new AbortController();
    this.inFlight = { before, abort };
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; abort.abort(); }, 8000);
    this.view.controls(this);
    try {
      const response = await this.fetcher(before === null ? "/api/dashboard" : `/api/dashboard?before=${before}`, {
        method: "GET", headers: { Accept: "application/json" }, cache: "no-store", credentials: "omit", redirect: "error", signal: abort.signal,
      });
      const data = await response.json();
      if (requestId !== this.sequence || this.stopped) return;
      if (!response.ok || !isDashboardResponse(data)) {
        const safeCode = data?.ok === false && typeof data.error === "string" && /^[a-z0-9_]{1,100}$/.test(data.error) ? data.error : "invalid_response";
        throw new Error(safeCode);
      }
      const next = mergeDashboardPage(this.state, data, { before, requestScope, requestId, latestRequestId: this.sequence });
      if (next === this.state) throw new Error("revision_regressed");
      this.state = next;
      this.error = null;
      this.failures = 0;
      this.successfulAt = new Date(this.clock()).toISOString();
      this.view.render(this.state, { successfulAt: this.successfulAt, now: this.clock() });
      if (next.needsRefresh) this.refreshQueued = true;
    } catch (error) {
      if (requestId !== this.sequence || this.stopped) return;
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
        } else this.schedule();
      }
    }
  }
}

if (typeof document !== "undefined" && document.getElementById("ace-dashboard")) {
  new DashboardController(document).start();
}
