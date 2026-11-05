import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  isDecimal, decimalSign, formatDecimal, formatMoney, formatPercent, formatCount,
  formatTimestamp, sourceFreshness, scopeKey, approvedAmounts, canonicalStatus,
  intentStatus, journalForScope, orderDetail, ordersForFilter, mergeActivity,
  isDashboardResponse, mergeDashboardPage, chartGeometry, pollDelay, DashboardController,
} from "../ui/dashboard.mjs";

const NOW = Date.parse("2026-11-04T12:00:20Z");
const OBSERVED = "2026-11-04T12:00:00Z";
const GENERATED = "2026-11-04T12:00:20Z";

function fixture() {
  return {
    ok: true, api_version: 1, status: "configured", generated_at: GENERATED, revision: 12,
    account: { login: "000042", server: "Synthetic-Demo", type: "demo", currency: "USD cents" },
    scope: { policy_id: "policy-a", goal_id: "goal-a" },
    snapshot: { id: "sample-1", as_of: OBSERVED, max_age_seconds: 30, freshness: "fresh", age_seconds: 20 },
    policy: { id: "policy-a", budget: "250.00", started_at: OBSERVED },
    goal: { id: "goal-a", target: "500.000", start_equity: "100000.00", started_at: OBSERVED, approved_at: OBSERVED },
    draft: { budget: "999", target: "9999" },
    metrics: { budget: "250.00", target: "500.000", balance: "100000.00", equity: "100080.05", peak: "100100.00", drawdown: "19.95", remaining_risk: "230.05", account_stop_floor: "99850.00", estimated_goal_gain: "80.00", progress_pct: "16.000", remaining_target: "420.000", remaining_close_costs: "0.05", existing_risk: "20.00", free_margin: "80000.00", final_net: null, final_shortfall: null },
    result: { decision: "within_budget", reason_codes: [], closure_verified: false, required_action: "none", last_verified_at: OBSERVED },
    stops: { loss_latched_at: null, target_latched_at: null, target_trigger_gain: null, closure_verified: false },
    loop: { id: "loop-1", status: "active", cycles: 2, timeframe: "M15", last_cycle_at: OBSERVED,
      next_cycle_at: "2026-11-04T12:15:05Z", next_latch_check_at: "2026-11-04T12:05:02Z",
      next_wake_at: "2026-11-04T12:05:02Z", wake_reason: "latch_check", max_gap_seconds: 901, end_reason: null,
      policy_id: "policy-a", goal_id: "goal-a", binding_verified_at: OBSERVED,
      last_observation_at: OBSERVED, last_observation_received_at: "2026-11-04T12:00:02Z", observation_age_seconds: 20,
      observation_gap_seconds: 300, max_observation_gap_seconds: 600, max_observation_gap_at: OBSERVED,
      wake_overdue_seconds: 0, execution: "unverified" },
    exposure: { positions_count: 1, orders_count: 1, entry_orders_count: 1, protective_orders_count: 0 },
    pending_orders: [{ ticket: "00009007199254740993", symbol: "SYNTH", kind: "entry", protected: true, risk: "20.00", position_ticket: null,
      details: { order_type: "buy_limit", side: "buy", volume_initial: "0.20", volume_remaining: "0.10", volume_unit: "lots", entry_price: "1.01001", stop_limit_price: null, stop_loss: "0.99001", take_profit: null, placed_at: OBSERVED, expires_at: null, ownership: "manual", unset_fields: ["stop_limit_price", "take_profit", "expires_at"] } }],
    unresolved_intents: { count: 1, items: [{ id: "request-001", kind: "entry", status: "unknown", symbol: "SYNTH", tickets: [], risk: "10.0001", created_at: OBSERVED, snapshot_at: OBSERVED, outcome: { outcome: "unknown", at: GENERATED, snapshot_at: OBSERVED, broker_tickets: [] } }] },
    latest_journal: { version: 1, activity: "wait", summary: "Wait for a closed candle", reason: "No independent entry is supported.", next_step: "Reassess after the next recorded candle.", market_summary: "Range-bound synthetic fixture.", risk_summary: "Existing exposure included.", invalidation: "A close below the range.", symbols: ["SYNTH"], source_refs: ["synthetic-bars-1"], intent_id: null, snapshot_id: "sample-1", as_of: OBSERVED, recorded_at: GENERATED, policy_id: "policy-a", goal_id: "goal-a" },
    activity: { items: [{ id: 12, command: "check", at: GENERATED, snapshot_at: OBSERVED, decision: "within_budget", reason_codes: [], closure_verified: false, journal: null, intent: null }], next_cursor: 12 },
    progress: { points: [{ event_id: 12, snapshot_id: "sample-1", as_of: OBSERVED, gain: "80.00", pct: "16.000", target: "500.000", x: 0.5, y: 0.84, gap_before: false, legacy: false }], target_y: 0, zero_y: 1, min_pct: "0", max_pct: "100", incomplete: false, from: OBSERVED, to: OBSERVED, next_cursor: null },
    warnings: [],
  };
}

test("exact decimal formatting does not pass money through floating point", () => {
  assert.equal(formatDecimal("1234567890123456789012345678.123456789012"), "1,234,567,890,123,456,789,012,345,678.123456789012");
  assert.equal(formatMoney("10000000000000000001.000000000001", "USD"), "10,000,000,000,000,000,001.000000000001 USD");
  assert.equal(formatDecimal("0000100.0100"), "100.0100");
  assert.equal(formatDecimal("+10.00"), "+10.00");
  assert.equal(formatDecimal("0.00", { signed: true }), "0.00");
  assert.equal(formatMoney("1.234567", "broker credits"), "1.234567 broker credits");
  assert.equal(formatMoney("2.50", null), "2.50 (currency unavailable)");
});

test("negative tiny values and supplied negative-zero signs are never rounded away", () => {
  assert.equal(formatMoney("-0.000000000001", "JPY"), "-0.000000000001 JPY");
  assert.equal(formatPercent("-0.0000000000000000001"), "-0.0000000000000000001%");
  assert.equal(formatDecimal("-0.000"), "-0.000");
  assert.equal(decimalSign("-0.000000000001"), -1);
  assert.equal(decimalSign("-0.000"), 0);
  assert.equal(decimalSign("+1000000000000000000000001"), 1);
});

test("percentage text retains negatives and progress beyond one hundred", () => {
  assert.equal(formatPercent("124.000000000001"), "+124.000000000001%");
  assert.equal(formatPercent("99.99999999999999999"), "+99.99999999999999999%");
  assert.equal(formatPercent("-110.50"), "-110.50%");
  assert.equal(formatPercent("0"), "0%");
});

test("compact percentages never round to a trigger or hide a tiny loss", () => {
  const compact = { compact: true };
  assert.equal(formatPercent("55.16666666666666666667", compact), "~+55.1666%");
  assert.equal(formatPercent("99.99999999999999999999", compact), "~+99.9999%");
  assert.equal(formatPercent("100.00000000001", compact), "~+100.0000%");
  assert.equal(formatPercent("-0.000000001", compact), "<0.0001% loss");
  assert.equal(formatPercent("0.000000001", compact), "<0.0001% gain");
  assert.equal(formatPercent("120.2300000", compact), "+120.2300%");
  assert.equal(formatPercent(null, compact), "Unavailable");
});

test("the browser accepts fixed decimals only, matching the normalized API", () => {
  for (const value of [null, undefined, 5, NaN, Infinity, "", "1e19", "-1E-12", "NaN", "Infinity", " 1.2 ", "1,000", "1.", ".5", "<b>5</b>"]) {
    assert.equal(isDecimal(value), false);
    assert.equal(formatDecimal(value), "Unavailable");
    assert.equal(formatMoney(value, "USD"), "Unavailable");
    assert.equal(decimalSign(value), null);
  }
});

test("only safe count numbers are formatted as counts", () => {
  assert.equal(formatCount(0), "0");
  assert.equal(formatCount(100), "100");
  for (const value of [null, undefined, "0", -1, 0.5, Infinity, Number.MAX_SAFE_INTEGER + 1]) assert.equal(formatCount(value), "Unavailable");
});

test("timestamps preserve source subsecond precision and require an explicit UTC zone", () => {
  assert.equal(formatTimestamp("2026-11-04T12:00:00.123456Z"), "2026-11-04 12:00:00.123456 UTC");
  assert.equal(formatTimestamp("2026-11-04T12:00:00+00:00"), "2026-11-04 12:00:00 UTC");
  assert.equal(formatTimestamp("2026-11-04T12:00:00"), "Unavailable");
  assert.equal(formatTimestamp(null), "Unavailable");
});

test("freshness ages from source time, not API generation, revision or journal time", () => {
  const data = fixture();
  assert.equal(sourceFreshness(data.snapshot, NOW).state, "fresh");
  assert.equal(sourceFreshness(data.snapshot, NOW + 10000).state, "fresh");
  assert.equal(sourceFreshness(data.snapshot, NOW + 10001).state, "stale");
  data.generated_at = "2026-11-04T13:00:00Z";
  data.revision = 999;
  data.latest_journal.recorded_at = data.generated_at;
  data.snapshot.age_seconds = 0;
  assert.equal(sourceFreshness(data.snapshot, NOW + 3600000).state, "stale");
});

test("future, explicitly stale and unknown freshness never become fresh by inference", () => {
  const snapshot = fixture().snapshot;
  assert.equal(sourceFreshness(snapshot, Date.parse(OBSERVED) - 1).state, "future");
  assert.equal(sourceFreshness({ ...snapshot, freshness: "future" }, NOW).state, "future");
  assert.equal(sourceFreshness({ ...snapshot, freshness: "stale" }, NOW).state, "stale");
  for (const changes of [{ as_of: null }, { max_age_seconds: null }, { max_age_seconds: "30" }, { max_age_seconds: 0 }, { freshness: "unavailable" }]) assert.equal(sourceFreshness({ ...snapshot, ...changes }, NOW).state, "unavailable");
  assert.equal(sourceFreshness(null, NOW).state, "unavailable");
});

test("approved goal and policy amounts never fall back to an unapproved draft", () => {
  const data = fixture();
  assert.deepEqual(approvedAmounts(data), { target: "500.000", budget: "250.00" });
  data.goal.target = null;
  assert.equal(approvedAmounts(data).target, "500.000");
  data.metrics.target = null;
  assert.equal(approvedAmounts(data).target, null);
  assert.deepEqual(approvedAmounts({ ...data, status: "draft" }), { target: null, budget: null });
});

test("scope includes exact account identity, policy and goal", () => {
  const data = fixture();
  const original = scopeKey(data);
  for (const field of ["login", "server", "type", "currency"]) {
    const changed = structuredClone(data);
    changed.account[field] += "changed";
    assert.notEqual(scopeKey(changed), original);
  }
  for (const field of ["policy_id", "goal_id"]) {
    const changed = structuredClone(data);
    changed.scope[field] += "changed";
    assert.notEqual(scopeKey(changed), original);
  }
  assert.notEqual(scopeKey({ ...data, account: { ...data.account, login: "42" } }), original);
  assert.equal(scopeKey({ ...data, revision: 999, generated_at: "2026-11-05T00:00:00Z" }), original);
});

test("both canonical latches persist with loss precedence and closure separate", () => {
  const data = fixture();
  data.stops.loss_latched_at = OBSERVED;
  data.stops.target_latched_at = OBSERVED;
  data.result.decision = "prepared";
  let status = canonicalStatus(data);
  assert.equal(status.label, "Loss stop latched");
  assert.equal(status.loss, true);
  assert.equal(status.target, true);
  assert.equal(status.closureVerified, false);
  assert.match(status.description, /loss-stop handling takes priority/);
  data.stops.closure_verified = true;
  data.result.closure_verified = true;
  data.metrics.estimated_goal_gain = "10";
  status = canonicalStatus(data);
  assert.equal(status.label, "Loss stop latched");
  assert.equal(status.closureVerified, true);
  assert.match(status.description, /stop remains latched/);
});

test("metrics, prose, loop state and settled intents cannot create a stop or closure badge", () => {
  const data = fixture();
  data.metrics.progress_pct = "101.00001";
  data.metrics.final_net = "505.00";
  data.latest_journal.summary = "Target achieved; everything is closed";
  data.latest_journal.closure_verified = true;
  data.loop.status = "closed";
  data.unresolved_intents.items[0].status = "completed";
  assert.deepEqual(canonicalStatus(data), canonicalStatus(fixture()));
  assert.equal(intentStatus("completed"), "Settled request");
  assert.equal(intentStatus("not_executed"), "Not executed");
  assert.equal(intentStatus("unknown"), "Outcome unknown");
  assert.equal(intentStatus("__proto__"), "Request status unavailable");
  assert.equal(canonicalStatus({ result: { decision: "__proto__" } }).label, "Helper outcome unavailable");
});

test("account-level stop closure is canonical, including settlement preserved after a draft", () => {
  const data = fixture();
  data.stops.target_latched_at = OBSERVED;
  data.stops.closure_verified = true;
  data.result.decision = "draft_saved";
  assert.equal(canonicalStatus(data).closureVerified, true);
  data.stops.closure_verified = false;
  data.result.closure_verified = true;
  assert.equal(canonicalStatus(data).closureVerified, false);
  data.stops.closure_verified = null;
  assert.equal(canonicalStatus(data).closureVerified, true);
  data.result = null;
  assert.equal(canonicalStatus(data).closureVerified, false);
  data.stops.target_latched_at = null;
  data.result = { decision: "loss_stop" };
  assert.equal(canonicalStatus(data).label, "Loss stop latched");
});

test("journal metadata must bind to the current goal and remain explanation only", () => {
  const data = fixture();
  assert.equal(journalForScope(data), data.latest_journal);
  for (const changes of [{ goal_id: "old-goal" }, { policy_id: "old-policy" }, { version: 2 }, { activity: "filled" }, { summary: null }, { source_refs: [{ url: "https://invalid.test" }] }, { market_summary: { html: "bad" } }, { recorded_at: "yesterday" }]) assert.equal(journalForScope(data, { ...data.latest_journal, ...changes }), null);
  const malicious = "<img src=x onerror=alert(1)> & <script>fake()</script>";
  assert.equal(journalForScope(data, { ...data.latest_journal, summary: malicious }).summary, malicious);
});

test("pending orders distinguish unknown, empty, manual, entry and protective", () => {
  assert.equal(ordersForFilter(null), null);
  assert.deepEqual(ordersForFilter([]), []);
  const orders = fixture().pending_orders;
  orders.push({ ...orders[0], ticket: "00002", kind: "protective" });
  orders.push({ ...orders[0], ticket: "00003", kind: null });
  assert.equal(ordersForFilter(orders).length, 3);
  assert.equal(ordersForFilter(orders, "entry")[0].details.ownership, "manual");
  assert.deepEqual(ordersForFilter(orders, "protective").map((order) => order.ticket), ["00002"]);
});

test("order enrichment null is unavailable and explicit unset is not set", () => {
  const order = fixture().pending_orders[0];
  assert.equal(orderDetail({ ...order, details: null }, "stop_loss"), "Unavailable");
  assert.equal(orderDetail(order, "expires_at"), "Not set");
  assert.equal(orderDetail(order, "stop_limit_price"), "Not set");
  assert.equal(orderDetail(order, "volume_remaining"), "0.10 lots");
  assert.equal(orderDetail(order, "stop_loss"), "0.99001");
  order.details.unset_fields = [];
  assert.equal(orderDetail(order, "expires_at"), "Unavailable");
  order.details.unset_fields = ["stop_loss"];
  assert.equal(orderDetail(order, "stop_loss"), "Unavailable");
  order.details.volume_unit = "money";
  assert.equal(orderDetail(order, "volume_remaining"), "Unavailable");
});

test("activity deduplicates by safe event ID without coercing unknown lists to empty", () => {
  assert.equal(mergeActivity([{ id: 1 }], null), null);
  assert.deepEqual(mergeActivity(null, []), []);
  assert.deepEqual(mergeActivity([{ id: 4, decision: "old" }, { id: 3 }], [{ id: 4, decision: "new" }, { id: 5 }, null, { id: "2" }, { id: -1 }]), [{ id: 5 }, { id: 4, decision: "new" }, { id: 3 }]);
});

test("older pages append once and update the summary without replacing recent chart data", () => {
  const first = fixture();
  let state = mergeDashboardPage(null, first);
  const older = fixture();
  older.revision = 13;
  older.metrics.estimated_goal_gain = "85.00";
  older.activity = { items: [{ ...first.activity.items[0], id: 11 }], next_cursor: 11 };
  older.progress.points = [{ ...older.progress.points[0], gain: "1.00" }];
  state = mergeDashboardPage(state, older, { before: 12 });
  assert.deepEqual(state.activity.map((item) => item.id), [12, 11]);
  assert.equal(state.data.metrics.estimated_goal_gain, "85.00");
  assert.equal(state.progress, first.progress);
  assert.equal(state.cursor, 11);
  const newer = fixture();
  newer.revision = 14;
  state = mergeDashboardPage(state, newer);
  assert.deepEqual(state.activity.map((item) => item.id), [12, 11]);
  assert.equal(state.cursor, 11);
});

test("account or goal changes during pagination discard old pages and request current history", () => {
  const previous = mergeDashboardPage(null, fixture());
  const next = fixture();
  next.scope.goal_id = "goal-b";
  next.goal.id = "goal-b";
  next.activity.items[0].id = 30;
  const state = mergeDashboardPage(previous, next, { before: 12, requestScope: previous.scope });
  assert.equal(state.data.scope.goal_id, "goal-b");
  assert.equal(state.activity, null);
  assert.equal(state.progress, null);
  assert.equal(state.needsRefresh, true);
  const refreshed = mergeDashboardPage(state, next);
  assert.deepEqual(refreshed.activity.map((item) => item.id), [30]);
  assert.equal(refreshed.needsRefresh, false);
});

test("late async responses and decreasing same-scope revisions are ignored", () => {
  const previous = mergeDashboardPage(null, fixture());
  const late = fixture();
  late.scope.goal_id = "late-goal";
  assert.equal(mergeDashboardPage(previous, late, { requestId: 1, latestRequestId: 2 }), previous);
  late.scope.goal_id = previous.data.scope.goal_id;
  late.revision = 1;
  assert.equal(mergeDashboardPage(previous, late), previous);
  late.account.login = "different-account";
  assert.notEqual(mergeDashboardPage(previous, late), previous);
});

test("an unconfigured response after load clears current account/history state", () => {
  const state = mergeDashboardPage(mergeDashboardPage(null, fixture()), { ...fixture(), status: "unconfigured", revision: 0, account: null, scope: null, snapshot: null, metrics: null });
  assert.equal(state.data.status, "unconfigured");
  assert.equal(state.unconfiguredAfterLoad, true);
  assert.equal(state.activity, null);
  assert.equal(state.progress, null);
  assert.equal(state.cursor, null);
});

test("new activity after an empty page or a disjoint refresh retains a usable cursor", () => {
  const empty = fixture();
  empty.activity = { items: [], next_cursor: null };
  let state = mergeDashboardPage(null, empty);
  state = mergeDashboardPage(state, fixture());
  assert.equal(state.cursor, 12);
  const fresh = fixture();
  fresh.revision += 1;
  fresh.activity = { items: [{ ...fresh.activity.items[0], id: 300 }], next_cursor: 300 };
  state = mergeDashboardPage(state, fresh);
  assert.equal(state.historyGap, true);
  assert.equal(state.cursor, 300);
});

test("response validation rejects error payloads, unknown API versions and unsafe revisions", () => {
  assert.equal(isDashboardResponse(fixture()), true);
  for (const changes of [{ ok: false }, { api_version: 2 }, { status: "running" }, { revision: "12" }, { revision: Number.MAX_SAFE_INTEGER + 1 }, { generated_at: null }]) assert.equal(isDashboardResponse({ ...fixture(), ...changes }), false);
  assert.equal(isDashboardResponse({ ok: false, status: "unavailable", error: "reader_busy", generated_at: GENERATED }), false);
});

test("chart uses only supplied normalized coordinates and retains exact source values", () => {
  const progress = fixture().progress;
  progress.points[0] = { ...progress.points[0], gain: "-0.000000000001", pct: "-0.0000000000002", x: 0.25, y: 0.9 };
  const geometry = chartGeometry(progress);
  assert.equal(geometry.samples[0].x, 230);
  assert.equal(geometry.samples[0].y, 182);
  assert.equal(geometry.samples[0].point.gain, "-0.000000000001");
  assert.equal(geometry.targetY, 20);
  assert.equal(geometry.zeroY, 200);
  progress.points[0].pct = "150.000000000001";
  assert.equal(chartGeometry(progress).samples[0].y, 182);
});

test("chart line segments break at gaps and unknown monetary values", () => {
  const progress = fixture().progress;
  const point = progress.points[0];
  progress.points = [
    { ...point, x: 0 }, { ...point, x: 0.1 },
    { ...point, x: 0.2, gap_before: true }, { ...point, x: 0.3, gain: null },
    { ...point, x: 0.4 }, { ...point, x: 0.5, y: null }, { ...point, x: 1, legacy: true },
  ];
  const geometry = chartGeometry(progress);
  assert.deepEqual(geometry.segments.map((segment) => segment.length), [2, 1, 1, 1]);
  assert.deepEqual(geometry.gaps, [194]);
  assert.equal(geometry.samples.length, 5);
  assert.equal(geometry.samples.at(-1).point.legacy, true);
});

test("malformed chart coordinates are never coerced into numbers or zero", () => {
  const progress = fixture().progress;
  const point = progress.points[0];
  progress.points = [null, { ...point, x: "0.2" }, { ...point, x: NaN }, { ...point, y: -0.1 }, { ...point, y: 1.01 }];
  progress.target_y = "0";
  assert.equal(chartGeometry(progress).samples.length, 0);
  assert.equal(chartGeometry(progress).targetY, null);
  assert.equal(chartGeometry(null).points, null);
  assert.deepEqual(chartGeometry({ points: [] }).points, []);
});

test("poll timing is sequential-friendly, slows hidden tabs and bounds backoff", () => {
  assert.deepEqual([0, 1, 2, 3, 99].map((failures) => pollDelay(false, failures)), [5000, 10000, 20000, 30000, 30000]);
  assert.equal(pollDelay(true, 0), 30000);
  assert.equal(pollDelay(true, 999), 30000);
});

// A deliberately small DOM double exercises text-only rendering and keyed rows.
// It is not a layout/browser accessibility test.
class FakeNode {
  constructor(tag, doc) {
    this.tagName = tag;
    this.ownerDocument = doc;
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.dataset = {};
    this.listeners = new Map();
    this._text = "";
    this.hidden = false;
    this.open = false;
    this.value = "all";
    this.replacements = 0;
    this.textWrites = 0;
  }
  get textContent() { return this._text + this.children.map((child) => child.textContent).join(""); }
  set textContent(value) { this._text = value; this.replaceChildren(); this.textWrites += 1; }
  set innerHTML(_value) { throw new Error("HTML parsing must not be used"); }
  get firstElementChild() { return this.children[0] ?? null; }
  get nextElementSibling() { return this.parentNode?.children[this.parentNode.children.indexOf(this) + 1] ?? null; }
  append(...nodes) { for (const node of nodes) { node.remove(); node.parentNode = this; this.children.push(node); } }
  replaceChildren(...nodes) { for (const child of this.children) child.parentNode = null; this.children = []; this.replacements += 1; this.append(...nodes); }
  insertBefore(node, next) {
    if (node === next) return;
    node.remove();
    const index = next ? this.children.indexOf(next) : this.children.length;
    this.children.splice(index, 0, node);
    node.parentNode = this;
  }
  remove() { if (this.parentNode) { this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; } }
  setAttribute(key, value) {
    this.attributes.set(key, value);
    if (key === "hidden") this.hidden = true;
    if (key.startsWith("data-")) this.dataset[key.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value;
  }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); if (key === "datetime") delete this.dateTime; if (key === "hidden") this.hidden = false; }
  toggleAttribute(key, force = !this.attributes.has(key)) { if (force) this.setAttribute(key, ""); else this.removeAttribute(key); return force; }
  addEventListener(type, listener) { const listeners = this.listeners.get(type) ?? new Set(); listeners.add(listener); this.listeners.set(type, listeners); }
  removeEventListener(type, listener) { this.listeners.get(type)?.delete(listener); }
  focus() { this.ownerDocument.activeElement = this; for (const listener of this.listeners.get("focus") ?? []) listener({ target: this }); }
}

const html = await readFile(new URL("../ui/index.html", import.meta.url), "utf8");
const source = await readFile(new URL("../ui/dashboard.mjs", import.meta.url), "utf8");
const css = await readFile(new URL("../ui/dashboard.css", import.meta.url), "utf8");

class FakeDocument {
  constructor() {
    this.nodes = new Map();
    this.events = new FakeNode("document", this);
    this.defaultView = new FakeNode("window", this);
    this.hidden = false;
    this.activeElement = null;
    for (const match of html.matchAll(/<([a-z][a-z0-9]*)\b[^>]*\bid="([^"]+)"[^>]*>/gi)) {
      const node = new FakeNode(match[1], this);
      node.hidden = /\bhidden\b/.test(match[0]);
      if (node.hidden) node.setAttribute("hidden", "");
      this.nodes.set(match[2], node);
    }
  }
  getElementById(id) { const node = this.nodes.get(id); assert.ok(node, `HTML must contain #${id}`); return node; }
  createElement(tag) { return new FakeNode(tag, this); }
  createElementNS(_namespace, tag) { return this.createElement(tag); }
  addEventListener(...args) { this.events.addEventListener(...args); }
  removeEventListener(...args) { this.events.removeEventListener(...args); }
}

function response(data, ok = true) { return { ok, json: async () => data }; }
function deferred() { let resolve; const promise = new Promise((done) => { resolve = done; }); return { promise, resolve }; }
const flush = () => new Promise((resolve) => setImmediate(resolve));

function setup(context, fetcher, clock = () => NOW) {
  const doc = new FakeDocument();
  const controller = new DashboardController(doc, { fetcher, clock });
  controller.stopped = false;
  controller.view.render(null, { now: clock() });
  context.after(() => controller.stop());
  return { doc, controller };
}

test("markup and code use local assets, safe text APIs and accessible alternatives", () => {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  for (const match of source.matchAll(/\b(?:text|node|show|time|money)\("([^"]+)"/g)) assert.ok(ids.includes(match[1]), `Missing static element ${match[1]}`);
  assert.doesNotMatch(source, /innerHTML|outerHTML|insertAdjacentHTML|\beval\s*\(|new Function|localStorage|sessionStorage|indexedDB|document\.cookie|serviceWorker|WebSocket|EventSource/);
  assert.doesNotMatch(html, /https?:\/\/|\son[a-z]+\s*=/i);
  assert.doesNotMatch(css, /@import|https?:\/\//i);
  assert.match(html, /src="\/assets\/logo\.png"/);
  assert.match(html, /href="\/dashboard\.css"/);
  assert.match(html, /type="module" src="\/dashboard\.mjs"/);
  assert.match(html, /<svg[^>]+aria-labelledby=/);
  assert.match(html, /<table class="observation-table">/);
  assert.match(html, /<caption>/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /:focus-visible/);
});

test("loading, draft and missing state do not invent progress or zeros", async (context) => {
  let payload = { ...fixture(), status: "draft", scope: null, snapshot: null, metrics: null, goal: null, policy: null };
  const { doc, controller } = setup(context, async () => response(payload));
  assert.match(doc.getElementById("empty-title").textContent, /Reading/);
  await controller.request();
  assert.equal(doc.getElementById("configured-workspace").hidden, true);
  assert.equal(doc.getElementById("draft-amounts").hidden, false);
  assert.match(doc.getElementById("draft-target").textContent, /9,999 USD cents/);
  assert.match(doc.getElementById("empty-title").textContent, /Approval not recorded/);
  payload = { ...payload, status: "unconfigured", account: null, draft: null, revision: 0 };
  await controller.request();
  assert.equal(doc.getElementById("draft-amounts").hidden, true);
  assert.equal(doc.getElementById("account-login").textContent, "Unavailable");
  assert.equal(doc.getElementById("source-time").textContent, "Unavailable");
});

test("configured rendering keeps malicious strings as inert text and canonical values separate", async (context) => {
  const payload = fixture();
  const malicious = '<img src="x" onerror="alert(1)">';
  payload.latest_journal.summary = malicious;
  payload.latest_journal.source_refs = ["javascript:alert(1)", "../../private"];
  payload.pending_orders[0].symbol = "<script>symbol</script>";
  payload.metrics.estimated_goal_gain = "-0.000000000001";
  payload.metrics.progress_pct = "-0.0000000000002";
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(controller.error, null);
  assert.equal(doc.getElementById("journal-summary").textContent, malicious);
  assert.equal(doc.getElementById("journal-summary").children.length, 0);
  assert.match(doc.getElementById("journal-details").textContent, /javascript:alert\(1\)/);
  assert.match(doc.getElementById("orders-list").textContent, /<script>symbol<\/script>/);
  assert.match(doc.getElementById("orders-list").textContent, /00009007199254740993/);
  assert.equal(doc.getElementById("account-login").textContent, "000042");
  assert.equal(doc.getElementById("approved-target").textContent, "500.000 USD cents");
  assert.equal(doc.getElementById("net-gain").textContent, "-0.000000000001 USD cents");
  assert.equal(doc.getElementById("net-gain").dataset.tone, "danger");
  assert.equal(doc.getElementById("canonical-state").textContent, "Within budget at last check");
  assert.match(doc.getElementById("loop-status").textContent, /recorded only/);
  assert.doesNotMatch(doc.getElementById("orders-list").textContent, /request-001/);
  assert.match(doc.getElementById("intents-list").textContent, /request-001/);
});

test("loop labels separate candle timing, earlier account wakes and observation gaps", async (context) => {
  const payload = fixture();
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(doc.getElementById("loop-next").dateTime, "2026-11-04T12:15:05Z");
  assert.equal(doc.getElementById("loop-latch-next").dateTime, "2026-11-04T12:05:02Z");
  assert.equal(doc.getElementById("loop-wake").dateTime, "2026-11-04T12:05:02Z");
  assert.equal(doc.getElementById("loop-wake-reason").textContent, "Account-only limit check");
  assert.equal(doc.getElementById("loop-overdue").textContent, "Not overdue");
  assert.equal(doc.getElementById("loop-gap").textContent, "15m 1s");
  assert.equal(doc.getElementById("loop-observation-gap").textContent, "5m 0s");
  assert.equal(doc.getElementById("loop-max-observation-gap").textContent, "10m 0s");
  assert.equal(doc.getElementById("loop-observation").dateTime, OBSERVED);
  assert.equal(doc.getElementById("loop-observation-received").dateTime, "2026-11-04T12:00:02Z");
  assert.equal(doc.getElementById("loop-observation-age").textContent, "20s");
  assert.equal(doc.getElementById("loop-policy").textContent, "policy-a");
  assert.equal(doc.getElementById("loop-goal").textContent, "goal-a");
  assert.equal(doc.getElementById("loop-binding").dateTime, OBSERVED);
  assert.match(html, /Largest recorded cycle spacing/);
  assert.match(html, /Largest source-observation gap/);
  assert.doesNotMatch(html, /Largest recorded gap|unwatched account gap/i);
  assert.match(html, /Wake overdue at API read/);
  assert.match(html, /Source age at API read/);
  assert.match(html, /not scheduled or executed waits/);
  assert.match(html, /browser refresh or healthy local viewer does not verify agent execution/);
  payload.loop.next_cycle_at = null;
  for (const [reason, label] of Object.entries({ candle: "Candle check", bar_retry: "Candle data retry",
    clock_refresh: "Broker timing refresh", market_closed: "Closed-market poll", closure: "Closure / reconciliation" })) {
    payload.loop.wake_reason = reason;
    await controller.request();
    assert.equal(doc.getElementById("loop-wake-reason").textContent, label);
  }
  assert.equal(doc.getElementById("loop-next").textContent, "Unavailable");
  assert.equal(doc.getElementById("loop-next").getAttribute("datetime"), null);
  assert.equal(doc.getElementById("loop-wake").dateTime, payload.loop.next_wake_at);
});

test("active, closing and closed financial loops never verify current execution", async (context) => {
  const payload = fixture();
  const { doc, controller } = setup(context, async () => response(payload));
  for (const status of ["active", "closing", "closed"]) {
    payload.loop.status = status;
    payload.loop.execution = "running";
    if (status !== "active") {
      payload.loop.end_reason = "target_latch";
      payload.loop.next_cycle_at = null;
      payload.loop.next_latch_check_at = null;
      payload.loop.wake_reason = status === "closing" ? "closure" : null;
      if (status === "closed") {
        payload.loop.next_wake_at = null;
        payload.loop.wake_overdue_seconds = null;
      }
    }
    await controller.request();
    assert.equal(doc.getElementById("loop-status").textContent, `${status} (recorded only)`);
    assert.equal(doc.getElementById("loop-execution").textContent, "Unverified");
    assert.equal(doc.getElementById("canonical-state").textContent, "Within budget at last check");
    assert.match(doc.getElementById("closure-state").textContent, /No verified account closure/);
  }
  assert.equal(doc.getElementById("loop-wake").textContent, "Unavailable");
  assert.equal(doc.getElementById("loop-wake-reason").textContent, "Unavailable");
  assert.equal(doc.getElementById("loop-overdue").textContent, "Unavailable");
  assert.equal(doc.getElementById("loop-end").textContent, "target latch");
});

test("legacy and malformed loop telemetry stays unavailable, not zero or cycle-derived", async (context) => {
  const payload = fixture();
  payload.loop = { id: "legacy-loop", status: "active", cycles: 3, timeframe: "M15",
    last_cycle_at: OBSERVED, next_cycle_at: "2026-11-04T12:15:05Z", max_gap_seconds: 901, end_reason: null };
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(doc.getElementById("loop-cycles").textContent, "3");
  assert.equal(doc.getElementById("loop-gap").textContent, "15m 1s");
  for (const id of ["loop-policy", "loop-goal", "loop-binding", "loop-latch-next", "loop-wake", "loop-wake-reason",
    "loop-observation", "loop-observation-received", "loop-observation-age", "loop-observation-gap",
    "loop-max-observation-gap", "loop-max-observation-gap-at", "loop-overdue"]) {
    assert.equal(doc.getElementById(id).textContent, "Unavailable", id);
  }
  Object.assign(payload.loop, { observation_age_seconds: "0", observation_gap_seconds: -1,
    max_observation_gap_seconds: Infinity, wake_overdue_seconds: false, wake_reason: {} });
  await controller.request();
  for (const id of ["loop-observation-age", "loop-observation-gap", "loop-max-observation-gap", "loop-overdue", "loop-wake-reason"]) {
    assert.equal(doc.getElementById(id).textContent, "Unavailable", id);
  }
  payload.loop = null;
  await controller.request();
  assert.equal(doc.getElementById("loop-status").textContent, "No loop record available");
  assert.equal(doc.getElementById("loop-execution").textContent, "Unverified");
});

test("a journal revision and browser read leave loop evidence unchanged while source ages", async (context) => {
  let now = NOW;
  const payload = fixture();
  const original = structuredClone(payload.loop);
  const { doc, controller } = setup(context, async () => response(payload), () => now);
  await controller.request();
  now += 600000;
  payload.revision += 1;
  payload.generated_at = new Date(now).toISOString();
  payload.latest_journal.recorded_at = payload.generated_at;
  payload.latest_journal.summary = "A later explanation, not a new observation";
  payload.loop.observation_age_seconds = 620;
  payload.loop.wake_overdue_seconds = 318;
  await controller.request();
  assert.equal(doc.getElementById("source-time").dateTime, OBSERVED);
  assert.equal(doc.getElementById("loop-observation").dateTime, original.last_observation_at);
  assert.equal(doc.getElementById("loop-observation-received").dateTime, original.last_observation_received_at);
  assert.equal(doc.getElementById("loop-last").dateTime, original.last_cycle_at);
  assert.equal(doc.getElementById("loop-cycles").textContent, String(original.cycles));
  assert.equal(doc.getElementById("loop-wake").dateTime, original.next_wake_at);
  assert.equal(doc.getElementById("loop-gap").textContent, "15m 1s");
  assert.equal(doc.getElementById("loop-observation-gap").textContent, "5m 0s");
  assert.equal(doc.getElementById("loop-observation-age").textContent, "10m 20s");
  assert.equal(doc.getElementById("loop-overdue").textContent, "5m 18s");
  assert.equal(doc.getElementById("loop-execution").textContent, "Unverified");
  assert.equal(doc.getElementById("source-badge").textContent, "Stale observation");
});

test("SVG visibility updates the hidden attribute, not an unsupported property", async (context) => {
  const payload = fixture();
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(doc.getElementById("progress-chart").getAttribute("hidden"), null);
  payload.progress.points = [];
  await controller.request();
  assert.equal(doc.getElementById("progress-chart").getAttribute("hidden"), "");
});

test("unchanged polls preserve expanded/focused rows, exact table and active filter", async (context) => {
  let payload = fixture();
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  const row = controller.view.rowCaches.get("orders-list").values().next().value;
  row.details.open = true;
  row.summary.focus();
  const replacements = row.summary.replacements;
  const chartReplacements = doc.getElementById("chart-drawing").replacements;
  doc.getElementById("chart-table-details").open = true;
  controller.view.filter = "entry";
  payload = { ...structuredClone(payload), revision: 13, generated_at: "2026-11-04T12:00:25Z" };
  await controller.request();
  assert.equal(row.details.open, true);
  assert.equal(doc.activeElement, row.summary);
  assert.equal(row.summary.replacements, replacements);
  assert.equal(doc.getElementById("chart-drawing").replacements, chartReplacements);
  assert.equal(doc.getElementById("chart-table-details").open, true);
  assert.equal(controller.view.filter, "entry");
  payload.pending_orders[0].details.volume_remaining = "0.05";
  await controller.request();
  assert.equal(row.details.open, true);
  assert.equal(doc.activeElement, row.summary);
  assert.match(row.summary.textContent, /0\.05 lots/);
});

test("reader failure retains conspicuously last-known values and original timestamps", async (context) => {
  let now = NOW;
  let payload = fixture();
  let ok = true;
  const { doc, controller } = setup(context, async () => response(payload, ok), () => now);
  await controller.request();
  const oldRead = controller.successfulAt;
  payload = { ok: false, status: "unavailable", error: "reader_busy", generated_at: GENERATED };
  ok = false;
  now += 60000;
  await controller.request();
  assert.equal(controller.error, "reader_busy");
  assert.equal(controller.successfulAt, oldRead);
  assert.equal(doc.getElementById("source-time").dateTime, OBSERVED);
  assert.equal(doc.getElementById("reader-error").hidden, false);
  assert.match(doc.getElementById("reader-error").textContent, /last-known saved data/);
  assert.match(doc.getElementById("source-badge").textContent, /Last-known \/ Stale observation/);
  assert.equal(doc.getElementById("net-gain").textContent, "+80.00 USD cents");
  payload = { ...fixture(), status: "unconfigured", revision: 0, account: null, scope: null, snapshot: null, metrics: null };
  ok = true;
  await controller.request();
  assert.equal(controller.error, null);
  assert.equal(doc.getElementById("configured-workspace").hidden, true);
  assert.equal(doc.getElementById("orders-list").children.length, 0);
  assert.match(doc.getElementById("empty-description").textContent, /values have been cleared/);
  assert.equal(doc.getElementById("source-time").textContent, "Unavailable");
});

test("reader error before first data remains unavailable without zero-filled fallback", async (context) => {
  const { doc, controller } = setup(context, async () => { throw new TypeError("network failure with private detail"); });
  await controller.request();
  assert.equal(controller.state, null);
  assert.equal(controller.error, "reader_unavailable");
  assert.equal(doc.getElementById("configured-workspace").hidden, true);
  assert.match(doc.getElementById("empty-title").textContent, /unavailable/);
  assert.doesNotMatch(doc.getElementById("reader-error").textContent, /private detail/);
});

test("unknown orders render unavailable rather than an empty broker account", async (context) => {
  const payload = fixture();
  payload.pending_orders = null;
  payload.exposure = { positions_count: null, orders_count: null, entry_orders_count: null, protective_orders_count: null };
  payload.unresolved_intents = null;
  payload.progress = null;
  payload.metrics.target = null;
  payload.goal.target = null;
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(doc.getElementById("pending-count").textContent, "Unavailable");
  assert.match(doc.getElementById("orders-empty").textContent, /does not mean there are no/);
  assert.equal(doc.getElementById("approved-target").textContent, "Unavailable");
  assert.equal(doc.getElementById("chart-empty").textContent, "Progress history unavailable.");
  assert.match(doc.getElementById("intents-empty").textContent, /not an empty list/);
});

test("loss and target render together while unverified final metrics stay unavailable", async (context) => {
  const payload = fixture();
  payload.stops.loss_latched_at = OBSERVED;
  payload.stops.target_latched_at = OBSERVED;
  payload.stops.target_trigger_gain = "505.01";
  payload.metrics.final_net = "498.00";
  payload.metrics.final_shortfall = "2.00";
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(doc.getElementById("canonical-state").textContent, "Loss stop latched");
  assert.match(doc.getElementById("loss-stop").textContent, /Latched/);
  assert.match(doc.getElementById("target-stop").textContent, /Latched/);
  assert.match(doc.getElementById("closure-state").textContent, /not verified/);
  assert.equal(doc.getElementById("final-net").textContent, "Unavailable");
  payload.result.closure_verified = true;
  payload.stops.closure_verified = true;
  await controller.request();
  assert.equal(doc.getElementById("final-net").textContent, "+498.00 USD cents");
  assert.equal(doc.getElementById("final-shortfall").textContent, "2.00 USD cents");
  assert.equal(doc.getElementById("canonical-state").textContent, "Loss stop latched");
});

test("a later draft does not replace an approved target or hide verified final settlement", async (context) => {
  const payload = fixture();
  payload.stops.target_latched_at = OBSERVED;
  payload.stops.target_trigger_gain = "505.00";
  payload.stops.closure_verified = true;
  payload.metrics.final_net = "498.00";
  payload.metrics.final_shortfall = "2.00";
  payload.result = { decision: "draft_saved", reason_codes: [], closure_verified: false, required_action: null, last_verified_at: null };
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(doc.getElementById("approved-target").textContent, "500.000 USD cents");
  assert.equal(doc.getElementById("canonical-state").textContent, "Target stop latched");
  assert.match(doc.getElementById("closure-state").textContent, /closure verified/);
  assert.equal(doc.getElementById("final-net").textContent, "+498.00 USD cents");
  assert.equal(doc.getElementById("final-shortfall").textContent, "2.00 USD cents");
});

test("requests are GET-only, sequential, abortable and do not overlap on refresh", async (context) => {
  const pending = deferred();
  const calls = [];
  const { controller } = setup(context, (url, options) => {
    calls.push({ url, options });
    return calls.length === 1 ? pending.promise : Promise.resolve(response(fixture()));
  });
  const first = controller.request();
  await controller.request();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/dashboard");
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[0].options.credentials, "omit");
  assert.equal(calls[0].options.cache, "no-store");
  assert.ok(calls[0].options.signal instanceof AbortSignal);
  pending.resolve(response(fixture()));
  await first;
  await flush();
  assert.equal(calls.length, 2);
  await controller.request(12);
  assert.equal(calls.at(-1).url, "/api/dashboard?before=12");
});

test("native fetch retains its global receiver instead of the controller", async (context) => {
  const { controller } = setup(context, function () {
    assert.equal(this, globalThis);
    return Promise.resolve(response(fixture()));
  });
  await controller.request();
  assert.equal(controller.error, null);
  assert.equal(controller.state.data.status, "configured");
});

test("stopping aborts the read and prevents a late async result from changing the view", async (context) => {
  const pending = deferred();
  let signal;
  const { controller } = setup(context, (_url, options) => { signal = options.signal; return pending.promise; });
  const request = controller.request();
  controller.stop();
  assert.equal(signal.aborted, true);
  pending.resolve(response(fixture()));
  await request;
  assert.equal(controller.state, null);
  assert.equal(controller.inFlight, null);
});
