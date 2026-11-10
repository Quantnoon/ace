import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  isDecimal, decimalSign, formatDecimal, formatMoney, formatPercent, formatCount,
  formatTimestamp, sourceFreshness, scopeKey, approvedAmounts, canonicalStatus, ratioFill, progressGeometry,
  intentStatus, contextForIntent, journalForScope, mergeActivity, isDashboardResponse, mergeDashboardPage,
  pollDelay, ACTIVITY_PREVIEW_SIZE, DashboardController,
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
    session: null,
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
    strategies: { items: [], next_cursor: null },
    activity: { items: [{ id: 12, command: "check", at: GENERATED, snapshot_at: OBSERVED, decision: "within_budget", reason_codes: [], closure_verified: false, journal: null, intent: null }], next_cursor: 12 },
    progress: { points: [{ event_id: 12, snapshot_id: "sample-1", as_of: OBSERVED, gain: "80.00", pct: "16.000", target: "500.000", x: 0.5, y: 0.84, gap_before: false, legacy: false }], target_y: 0, zero_y: 1, min_pct: "0", max_pct: "100", incomplete: false, from: OBSERVED, to: OBSERVED, next_cursor: null },
    warnings: [],
  };
}

function strategyFixture(id = "idea-1") {
  const intent = { id, kind: "entry", status: "completed", symbol: "SYNTH", tickets: [], risk: "10.0001",
    created_at: OBSERVED, snapshot_at: OBSERVED, outcome: { outcome: "completed", at: GENERATED, snapshot_at: GENERATED, broker_tickets: ["pending-1"] },
    context: { version: 1, operation: "entry", rationale: "Range breakout with a fixed allocation.", source_refs: ["synthetic:closed-bars"], origin_intent_id: null,
      strategy: { name: `Range breakout ${id}`, thesis: "A closed candle held above the range.", side: "buy", timeframe: "M15", invalidation: "Close back inside the range.",
        expiry_rule: "Cancel before the session ends.", breakeven_rule: "Protect costs after one risk unit.", trailing_rule: "Tighten behind closed candles.", addition_rule: false } } };
  const latest_action = { id: `trail-${id}`, kind: "reduce", status: "unknown", symbol: "SYNTH", tickets: ["pending-1"], risk: "0",
    created_at: GENERATED, snapshot_at: GENERATED, outcome: { outcome: "unknown", at: GENERATED, snapshot_at: GENERATED, broker_tickets: [] },
    context: { version: 1, operation: "trail", rationale: "Tighten the stop; broker readback is pending.", source_refs: ["synthetic:stop-read"], origin_intent_id: id, strategy: null } };
  return { intent, latest_action, latest_journal: { ...fixture().latest_journal, intent_id: latest_action.id,
    activity: "management", summary: "Stop update remains unverified", reason: "Do not infer protection from submission." } };
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

test("signed gain starts at fixed zero and moves on a proportional budget-to-target scale", () => {
  for (const [gain, budgetFill, targetFill, position] of [
    ["-3", 100, 0, 0], ["-2", 100, 0, 0], ["-1", 50, 0, 25],
    ["-0.000", 0, 0, 50], ["0", 0, 0, 50], ["1", 0, 50, 75], ["2", 0, 100, 100], ["3", 0, 100, 100],
  ]) assert.deepEqual(progressGeometry("2", "2", gain), { split: 50, budgetFill, targetFill, position });
  const profit = progressGeometry("5", "10", "2.06");
  const loss = progressGeometry("5", "10", "-2.06");
  assert.equal(profit.split, 33.333333333);
  assert.equal(profit.budgetFill, 0);
  assert.equal(profit.targetFill, 20.6);
  assert.ok(Math.abs(profit.position - 47.0666666667) < 1e-8);
  assert.equal(loss.split, profit.split);
  assert.equal(loss.budgetFill, 41.2);
  assert.equal(loss.targetFill, 0);
  assert.ok(Math.abs(loss.position - 19.6) < 1e-8);
});

test("gain geometry handles large and tiny exact decimals without financial rounding", () => {
  assert.equal(ratioFill("19.95", "250.00"), 7.98);
  assert.equal(ratioFill("250.01", "250.00"), 100);
  assert.ok(ratioFill("99.99999999999999999999", "100") < 100);
  assert.equal(ratioFill("900719925474099300000000", "1801439850948198600000000"), 50);
  const zeros = "0".repeat(600);
  const large = progressGeometry(`1${zeros}`, `2${zeros}`, `1${zeros}`);
  assert.equal(large.split, 33.333333333);
  assert.equal(large.targetFill, 50);
  assert.ok(Math.abs(large.position - 66.6666666667) < 1e-8);
  const tiny = progressGeometry(`0.${zeros}2`, `0.${zeros}2`, `-0.${zeros}1`);
  assert.deepEqual(tiny, { split: 50, budgetFill: 50, targetFill: 0, position: 25 });
  assert.equal(progressGeometry("1", "1", "-0.000000000001").targetFill, 0);
});

test("unavailable or invalid scale inputs never become an invented zero or draft", () => {
  for (const bad of [null, undefined, "", "NaN", "1e20", 5, "<b>5</b>"]) {
    assert.equal(progressGeometry("5", "10", bad).position, null);
    assert.equal(progressGeometry(bad, "10", "2").split, null);
    assert.equal(ratioFill("1", bad), null);
  }
  for (const invalidLimit of ["0", "-0.0", "-5"]) {
    assert.equal(progressGeometry(invalidLimit, "10", "2").position, null);
    assert.equal(progressGeometry("5", invalidLimit, "-2").position, null);
  }
  assert.equal(ratioFill("-1", "250"), null);
  assert.deepEqual(progressGeometry("5", "10", null), { split: 33.333333333, budgetFill: null, targetFill: null, position: null });
  assert.equal(ACTIVITY_PREVIEW_SIZE, 5);
});

test("activity deduplicates by safe event ID without coercing unknown lists to empty", () => {
  assert.equal(mergeActivity([{ id: 1 }], null), null);
  assert.deepEqual(mergeActivity(null, []), []);
  assert.deepEqual(mergeActivity([{ id: 4, decision: "old" }, { id: 3 }], [{ id: 4, decision: "new" }, { id: 5 }, null, { id: "2" }, { id: -1 }]), [{ id: 5 }, { id: 4, decision: "new" }, { id: 3 }]);
});

test("older pages append once and update the current summary", () => {
  const first = fixture();
  let state = mergeDashboardPage(null, first);
  const older = fixture();
  older.revision = 13;
  older.metrics.estimated_goal_gain = "85.00";
  older.activity = { items: [{ ...first.activity.items[0], id: 11 }], next_cursor: 11 };
  state = mergeDashboardPage(state, older, { before: 12 });
  assert.deepEqual(state.activity.map((item) => item.id), [12, 11]);
  assert.equal(state.data.metrics.estimated_goal_gain, "85.00");
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
    this.attributeWrites = new Map();
    this.styleValues = new Map();
    this.styleWrites = new Map();
    this.style = {
      setProperty: (key, value) => {
        this.styleValues.set(key, value);
        this.styleWrites.set(key, (this.styleWrites.get(key) ?? 0) + 1);
      },
      getPropertyValue: (key) => this.styleValues.get(key) ?? "",
    };
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
    this.attributeWrites.set(key, (this.attributeWrites.get(key) ?? 0) + 1);
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
  assert.doesNotMatch(html, /session-strip|session-metrics|id="session-(?:status|phase|reason|next-wake|wake-reason)"/);
  assert.doesNotMatch(css, /\.session-strip|\.session-metrics/);
  assert.doesNotMatch(source, /innerHTML|outerHTML|insertAdjacentHTML|\beval\s*\(|new Function|localStorage|sessionStorage|indexedDB|document\.cookie|serviceWorker|WebSocket|EventSource/);
  assert.doesNotMatch(html, /https?:\/\/|\son[a-z]+\s*=/i);
  assert.doesNotMatch(css, /@import|https?:\/\//i);
  assert.match(html, /src="\/assets\/logo\.png"/);
  assert.match(html, /href="\/dashboard\.css"/);
  assert.match(html, /type="module" src="\/dashboard\.mjs"/);
  assert.match(html, /id="target-progress"[^>]+role="group"/);
  assert.match(html, /id="budget-progress"[^>]+role="progressbar"/);
  assert.match(html, /id="goal-progress"[^>]+role="progressbar"/);
  assert.equal([...html.matchAll(/class="gain-fill"/g)].length, 1);
  assert.match(html, /class="gain-marker"/);
  assert.match(html, /class="gain-axis-zero numeric">0</);
  assert.match(html, /id="gain-scale"[\s\S]*?class="progress-current"[\s\S]*?id="net-gain"/);
  assert.match(html, /id="progress-exact"/);
  assert.match(html, /<details class="disclosure target-details">[\s\S]*?<\/details>\s*<p id="active-draft-note"[^>]*>[^<]*<\/p>\s*<section class="decision-section"/);
  assert.ok(html.indexOf('id="decision-heading"') < html.indexOf('id="risk-heading"'));
  assert.match(html, /id="activity-toggle"[^>]+aria-controls="activity-list"[^>]+aria-expanded="false"/);
  assert.match(html, /id="strategies"[^>]+aria-labelledby="strategies-heading"/);
  assert.match(html, /id="strategies-more"[^>]+aria-controls="strategies-list"/);
  assert.match(html, /<h2 id="intents-heading">Unresolved requests<\/h2>/);
  assert.ok(html.indexOf('id="intents-heading"') > html.indexOf('id="activity-heading"'));
  assert.doesNotMatch(html, /id="orders"|id="order-filter"|id="orders-list"|>Orders<|observation-table|progress-chart|target-progress-ring|progress-pct|<circle|stroke-dash|pathLength|style=/);
  assert.match(css, /\.gain-fill\s*\{[^}]*left: var\(--fill-start\); width: var\(--fill-width\)/);
  assert.match(css, /data-tone="danger"[^}]+background: var\(--red\)/);
  assert.match(css, /data-tone="positive"[^}]+background: var\(--green\)/);
  assert.match(css, /\.progress-current\s*\{[^}]*left: clamp\(/);
  assert.match(css, /data-animate="true"[^}]+transition: left 600ms/);
  assert.doesNotMatch(css, /stroke-dash|repeating-linear-gradient/);
  assert.match(css, /@media \(max-width: 920px\)[\s\S]*?\.overview-grid \{ grid-template-columns: minmax\(0, 1fr\)/);
  assert.match(css, /\.strategy-context \{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.strategy-context \{ grid-template-columns: minmax\(0, 1fr\)/);
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
  payload.metrics.estimated_goal_gain = "-0.000000000001";
  payload.metrics.progress_pct = "-0.0000000000002";
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(controller.error, null);
  assert.equal(doc.getElementById("journal-summary").textContent, malicious);
  assert.equal(doc.getElementById("journal-summary").children.length, 0);
  assert.match(doc.getElementById("journal-details").textContent, /javascript:alert\(1\)/);
  assert.equal(doc.getElementById("account-login").textContent, "000042");
  assert.equal(doc.getElementById("approved-target").textContent, "500.000 USD cents");
  assert.equal(doc.getElementById("approved-budget").textContent, "-250.00 USD cents");
  assert.equal(doc.getElementById("net-gain").textContent, "-0.000000000001 USD cents");
  assert.equal(doc.getElementById("net-gain").dataset.tone, "danger");
  assert.equal(doc.getElementById("progress-exact").textContent, "-0.0000000000002%");
  assert.equal(doc.getElementById("budget-progress").getAttribute("aria-valuenow"), "0");
  assert.match(doc.getElementById("budget-progress").getAttribute("aria-valuetext"), /-0\.000000000001 USD cents toward budget 250\.00 USD cents/);
  assert.equal(doc.getElementById("goal-progress").getAttribute("aria-valuenow"), "0");
  assert.match(doc.getElementById("goal-progress").getAttribute("aria-valuetext"), /no positive gain/);
  assert.equal(doc.getElementById("gain-scale").style.getPropertyValue("--fill-width"), "0%");
  assert.equal(doc.getElementById("target-progress").dataset.tone, "danger");
  assert.equal(doc.getElementById("pending-count").textContent, "1");
  assert.equal(doc.getElementById("canonical-state").textContent, "Within budget at last check");
  assert.match(doc.getElementById("loop-status").textContent, /recorded only/);
  assert.match(doc.getElementById("intents-list").textContent, /request-001/);
});

test("gain label moves from zero with one fill and never substitutes trailing drawdown", async (context) => {
  const payload = fixture();
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  const progress = doc.getElementById("target-progress");
  const scale = doc.getElementById("gain-scale");
  const geometry = (key) => Number.parseFloat(scale.style.getPropertyValue(key));
  const budget = doc.getElementById("budget-progress");
  const goal = doc.getElementById("goal-progress");
  assert.equal(doc.getElementById("net-gain").textContent, "+80.00 USD cents");
  assert.doesNotMatch(doc.getElementById("net-gain").textContent, /%/);
  assert.equal(doc.getElementById("progress-exact").textContent, "+16.000%");
  assert.equal(budget.getAttribute("aria-valuenow"), "0");
  assert.equal(goal.getAttribute("aria-valuenow"), "16");
  assert.match(goal.getAttribute("aria-valuetext"), /\+80\.00 USD cents toward approved target 500\.000 USD cents/);
  assert.equal(progress.dataset.tone, "positive");
  assert.equal(geometry("--zero-position"), 33.333333333);
  assert.equal(geometry("--fill-start"), geometry("--zero-position"));
  assert.ok(Math.abs(geometry("--gain-position") - 44) < 1e-8);
  assert.ok(Math.abs(geometry("--fill-width") - 10.6666666667) < 1e-8);
  const writes = scale.styleWrites.get("--gain-position");
  payload.revision += 1;
  payload.metrics.drawdown = "200";
  await controller.request();
  assert.equal(scale.styleWrites.get("--gain-position"), writes);
  assert.equal(budget.getAttribute("aria-valuenow"), "0");
  assert.equal(doc.getElementById("drawdown").textContent, "200 USD cents");
  payload.revision += 1;
  payload.metrics.estimated_goal_gain = "100";
  payload.metrics.progress_pct = "20";
  await controller.request();
  assert.equal(progress.dataset.animate, "true");
  assert.ok(geometry("--gain-position") > 44);

  for (const [gain, percentage, leftFill, rightFill, tone] of [
    ["620.000000000005", "124.000000000001", "0", "100", "positive"],
    ["-125", "-25", "50", "0", "danger"],
    ["-250", "-50", "100", "0", "danger"],
    ["-300.000000000001", "-60.0000000000002", "100", "0", "danger"],
    ["0", "0", "0", "0", "neutral"],
    ["-0.000", "-0.000", "0", "0", "neutral"],
  ]) {
    payload.revision += 1;
    const previousTone = progress.dataset.tone;
    payload.metrics.estimated_goal_gain = gain;
    payload.metrics.progress_pct = percentage;
    await controller.request();
    assert.equal(progress.dataset.tone, tone);
    assert.equal(budget.getAttribute("aria-valuenow"), leftFill);
    assert.equal(goal.getAttribute("aria-valuenow"), rightFill);
    assert.equal(doc.getElementById("net-gain").textContent, formatMoney(gain, "USD cents", { signed: true }));
    assert.equal(doc.getElementById("progress-exact").textContent, formatPercent(percentage));
    assert.equal(doc.getElementById("canonical-state").textContent, "Within budget at last check");
    assert.ok(geometry("--gain-position") >= 0 && geometry("--gain-position") <= 100);
    if (tone !== previousTone) assert.equal(progress.dataset.animate, "false");
    if (leftFill !== "0") {
      assert.equal(geometry("--fill-start"), geometry("--gain-position"));
      assert.ok(Math.abs(geometry("--fill-start") + geometry("--fill-width") - geometry("--zero-position")) < 1e-8);
    } else assert.equal(geometry("--fill-start"), geometry("--zero-position"));
  }
});

test("unknown gain or scale clears fill and recovers without replacing approved amounts with drafts", async (context) => {
  const payload = fixture();
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  const scale = doc.getElementById("gain-scale");
  const progress = doc.getElementById("target-progress");
  payload.revision += 1;
  payload.metrics.estimated_goal_gain = null;
  payload.metrics.progress_pct = null;
  await controller.request();
  assert.equal(doc.getElementById("net-gain").textContent, "Unavailable");
  assert.equal(doc.getElementById("progress-exact").textContent, "Unavailable");
  assert.equal(doc.getElementById("goal-progress").getAttribute("aria-valuenow"), null);
  assert.equal(doc.getElementById("budget-progress").getAttribute("aria-valuenow"), null);
  assert.equal(doc.getElementById("goal-progress").getAttribute("aria-valuetext"), "Target progress unavailable");
  assert.equal(progress.dataset.state, "unavailable");
  assert.equal(progress.dataset.tone, "muted");
  assert.equal(scale.style.getPropertyValue("--fill-width"), "0%");
  assert.equal(doc.getElementById("gain-scale-unavailable").hidden, false);

  payload.revision += 1;
  payload.metrics.estimated_goal_gain = "80";
  payload.metrics.progress_pct = "16";
  payload.policy.budget = null;
  await controller.request();
  assert.equal(progress.dataset.state, "ready");
  assert.equal(doc.getElementById("approved-budget").textContent, "-250.00 USD cents");
  payload.revision += 1;
  payload.metrics.budget = null;
  await controller.request();
  assert.equal(progress.dataset.state, "unavailable");
  assert.equal(doc.getElementById("approved-budget").textContent, "Unavailable");
  assert.equal(scale.style.getPropertyValue("--fill-width"), "0%");
  payload.revision += 1;
  payload.policy.budget = "100";
  payload.scope.policy_id = "new-policy";
  payload.goal.target = "100";
  payload.scope.goal_id = "new-goal";
  await controller.request();
  assert.equal(progress.dataset.state, "ready");
  assert.equal(progress.dataset.animate, "false");
  assert.equal(scale.style.getPropertyValue("--zero-position"), "50%");
  assert.equal(scale.style.getPropertyValue("--gain-position"), "90%");
  assert.equal(doc.getElementById("goal-progress").getAttribute("aria-valuenow"), "80");
});

test("activity shows five rows then fetches every older page sequentially", async (context) => {
  const calls = [];
  let active = 0;
  let maxActive = 0;
  const page = (ids, nextCursor, revision) => {
    const data = fixture();
    data.revision = revision;
    data.activity = {
      items: ids.map((id) => ({ ...data.activity.items[0], id })),
      next_cursor: nextCursor,
    };
    return data;
  };
  const pages = new Map([
    ["/api/dashboard", page([100, 99, 98, 97, 96, 95, 94], 94, 12)],
    ["/api/dashboard?before=94", page([93, 92, 91], 91, 13)],
    ["/api/dashboard?before=91", page([90, 89], null, 14)],
  ]);
  const { doc, controller } = setup(context, async (url) => {
    calls.push(url);
    active += 1;
    maxActive = Math.max(maxActive, active);
    await Promise.resolve();
    active -= 1;
    return response(structuredClone(pages.get(url)));
  });
  await controller.request();
  assert.equal(doc.getElementById("activity-list").children.length, 5);
  assert.equal(doc.getElementById("activity-toggle").hidden, false);
  assert.equal(doc.getElementById("activity-toggle").textContent, "View all activity");
  assert.equal(doc.getElementById("activity-toggle").getAttribute("aria-expanded"), "false");
  controller.onActivityToggle();
  for (let count = 0; count < 5; count += 1) await flush();
  assert.deepEqual(calls, ["/api/dashboard", "/api/dashboard?before=94", "/api/dashboard?before=91"]);
  assert.equal(maxActive, 1);
  assert.equal(controller.state.cursor, null);
  assert.equal(controller.state.activity.length, 12);
  assert.equal(doc.getElementById("activity-list").children.length, 12);
  assert.equal(doc.getElementById("activity-toggle").textContent, "Show latest 5");
  assert.equal(doc.getElementById("activity-toggle").getAttribute("aria-expanded"), "true");
  assert.equal(doc.getElementById("activity-list").getAttribute("aria-busy"), "false");
  assert.match(doc.getElementById("activity-state").textContent, /complete available history/);
  controller.state.historyGap = true;
  controller.view.renderActivity(controller.state);
  controller.view.controls(controller);
  assert.match(doc.getElementById("activity-note").textContent, /reported gap/);
  assert.match(doc.getElementById("activity-state").textContent, /may have a gap/);
  controller.onActivityToggle();
  assert.equal(doc.getElementById("activity-list").children.length, 5);
  assert.equal(doc.getElementById("activity-toggle").textContent, "View all activity");
  assert.equal(doc.getElementById("activity-toggle").getAttribute("aria-expanded"), "false");
});

test("view all stops safely when an older cursor does not advance", async (context) => {
  const calls = [];
  const first = fixture();
  first.activity = { items: Array.from({ length: 6 }, (_, index) => ({ ...first.activity.items[0], id: 60 - index })), next_cursor: 55 };
  const stuck = fixture();
  stuck.revision = 13;
  stuck.activity = { items: [{ ...stuck.activity.items[0], id: 54 }], next_cursor: 55 };
  const { doc, controller } = setup(context, async (url) => {
    calls.push(url);
    return response(structuredClone(url.includes("before") ? stuck : first));
  });
  await controller.request();
  controller.onActivityToggle();
  for (let count = 0; count < 3; count += 1) await flush();
  assert.deepEqual(calls, ["/api/dashboard", "/api/dashboard?before=55"]);
  assert.equal(controller.activityPaginationStalled, true);
  assert.match(doc.getElementById("activity-state").textContent, /cursor did not advance/);
});

test("view all retains loaded rows across failure and resumes after refresh", async (context) => {
  const first = fixture();
  first.activity = { items: Array.from({ length: 6 }, (_, index) => ({ ...first.activity.items[0], id: 70 - index })), next_cursor: 65 };
  const refreshed = structuredClone(first);
  refreshed.revision = 13;
  const older = fixture();
  older.revision = 14;
  older.activity = { items: [{ ...older.activity.items[0], id: 64 }], next_cursor: null };
  let baseReads = 0;
  let olderReads = 0;
  const { doc, controller } = setup(context, async (url) => {
    if (!url.includes("before")) return response(structuredClone(baseReads++ === 0 ? first : refreshed));
    olderReads += 1;
    return olderReads === 1
      ? response({ ok: false, error: "reader_busy" }, false)
      : response(structuredClone(older));
  });
  await controller.request();
  controller.onActivityToggle();
  for (let count = 0; count < 2; count += 1) await flush();
  assert.equal(controller.error, "reader_busy");
  assert.equal(controller.state.activity.length, 6);
  assert.match(doc.getElementById("activity-state").textContent, /paused after 6 events/);
  await controller.request();
  for (let count = 0; count < 3; count += 1) await flush();
  assert.equal(controller.error, null);
  assert.equal(olderReads, 2);
  assert.equal(controller.state.cursor, null);
  assert.equal(controller.state.activity.length, 7);
  assert.equal(doc.getElementById("activity-list").children.length, 7);
});

test("view all stops retrying an older page after bounded failures", async (context) => {
  const first = fixture();
  first.activity = { items: Array.from({ length: 6 }, (_, index) => ({ ...first.activity.items[0], id: 70 - index })), next_cursor: 65 };
  let baseReads = 0;
  let olderReads = 0;
  const { doc, controller } = setup(context, async (url) => {
    if (url.includes("before")) {
      olderReads += 1;
      return response({ ok: false, error: "reader_busy" }, false);
    }
    const data = structuredClone(first);
    data.revision = 12 + baseReads++;
    return response(data);
  });
  await controller.request();
  controller.onActivityToggle();
  for (let count = 0; count < 2; count += 1) await flush();
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await controller.request();
    for (let count = 0; count < 2; count += 1) await flush();
  }
  assert.equal(olderReads, 3);
  assert.equal(controller.activityPaginationStalled, true);
  assert.equal(controller.activityPaginationReason, "failures");
  await controller.request();
  for (let count = 0; count < 2; count += 1) await flush();
  assert.equal(olderReads, 3);
  assert.match(doc.getElementById("activity-state").textContent, /stopped after 3 failed reads/);
});

test("view all pauses older-page reads while the document is hidden", async (context) => {
  const first = fixture();
  first.activity = { items: Array.from({ length: 6 }, (_, index) => ({ ...first.activity.items[0], id: 70 - index })), next_cursor: 65 };
  const older = fixture();
  older.revision = 13;
  older.activity = { items: [{ ...older.activity.items[0], id: 64 }], next_cursor: null };
  const calls = [];
  const { doc, controller } = setup(context, async (url) => {
    calls.push(url);
    return response(structuredClone(url.includes("before") ? older : first));
  });
  await controller.request();
  doc.hidden = true;
  controller.onActivityToggle();
  await flush();
  assert.deepEqual(calls, ["/api/dashboard"]);
  doc.hidden = false;
  controller.onVisibility();
  for (let count = 0; count < 4; count += 1) await flush();
  assert.deepEqual(calls, ["/api/dashboard", "/api/dashboard", "/api/dashboard?before=65"]);
  assert.equal(controller.state.cursor, null);
});

test("pagehide clears cursor bookkeeping so page restore can resume view all", async (context) => {
  const pending = deferred();
  const first = fixture();
  first.activity = { items: Array.from({ length: 6 }, (_, index) => ({ ...first.activity.items[0], id: 70 - index })), next_cursor: 65 };
  const refreshed = structuredClone(first);
  refreshed.revision = 13;
  const older = fixture();
  older.revision = 14;
  older.activity = { items: [{ ...older.activity.items[0], id: 64 }], next_cursor: null };
  let baseReads = 0;
  let olderReads = 0;
  const { controller } = setup(context, async (url) => {
    if (!url.includes("before")) return response(structuredClone(baseReads++ === 0 ? first : refreshed));
    olderReads += 1;
    return olderReads === 1 ? pending.promise : response(structuredClone(older));
  });
  await controller.request();
  controller.onActivityToggle();
  assert.equal(controller.inFlight.before, 65);
  assert.equal(controller.activityCursors.has(65), true);
  controller.stop();
  assert.equal(controller.activityCursors.size, 0);
  pending.resolve(response(structuredClone(older)));
  await flush();
  controller.start();
  for (let count = 0; count < 5; count += 1) await flush();
  assert.equal(olderReads, 2);
  assert.equal(controller.activityPaginationStalled, false);
  assert.equal(controller.state.cursor, null);
});

test("account or goal changes collapse activity back to the newest five", async (context) => {
  let payload = fixture();
  payload.activity = { items: Array.from({ length: 6 }, (_, index) => ({ ...payload.activity.items[0], id: 80 - index })), next_cursor: null };
  const { doc, controller } = setup(context, async () => response(structuredClone(payload)));
  await controller.request();
  controller.onActivityToggle();
  assert.equal(controller.view.activityExpanded, true);
  assert.equal(doc.getElementById("activity-list").children.length, 6);
  payload = fixture();
  payload.scope.goal_id = "goal-b";
  payload.goal.id = "goal-b";
  payload.activity = { items: [{ ...payload.activity.items[0], id: 200 }], next_cursor: null };
  await controller.request();
  assert.equal(controller.view.activityExpanded, false);
  assert.equal(doc.getElementById("activity-list").children.length, 1);
  assert.equal(doc.getElementById("activity-toggle").hidden, true);
});

test("a disjoint refresh starts a new cursor generation without a false loop stall", async (context) => {
  const initial = fixture();
  initial.activity = { items: [{ ...initial.activity.items[0], id: 100 }], next_cursor: null };
  const refreshed = fixture();
  refreshed.revision = 13;
  refreshed.activity = { items: [{ ...refreshed.activity.items[0], id: 600 }], next_cursor: 500 };
  const older = fixture();
  older.revision = 14;
  older.activity = { items: [{ ...older.activity.items[0], id: 499 }], next_cursor: null };
  let baseReads = 0;
  const calls = [];
  const { controller } = setup(context, async (url) => {
    calls.push(url);
    if (url.includes("before")) return response(structuredClone(older));
    return response(structuredClone(baseReads++ === 0 ? initial : refreshed));
  });
  await controller.request();
  controller.view.activityExpanded = true;
  controller.activityCursors.add(500);
  await controller.request();
  for (let count = 0; count < 3; count += 1) await flush();
  assert.deepEqual(calls, ["/api/dashboard", "/api/dashboard", "/api/dashboard?before=500"]);
  assert.equal(controller.activityPaginationStalled, false);
  assert.equal(controller.state.cursor, null);
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

test("removing the session panel leaves configured account, risk and loop sections rendering", async (context) => {
  const payload = fixture();
  payload.session = { id: "session-1", status: "active", started_at: OBSERVED, updated_at: GENERATED,
    reason: "User requested trading until stopped.", execution: "running" };
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(controller.error, null);
  assert.equal(doc.nodes.has("session-status"), false);
  assert.equal(doc.nodes.has("session-phase"), false);
  assert.equal(doc.getElementById("session-id").textContent, payload.session.id);
  assert.equal(doc.getElementById("session-started").dateTime, OBSERVED);
  assert.equal(doc.getElementById("session-updated").dateTime, GENERATED);
  assert.equal(doc.getElementById("account-login").textContent, payload.account.login);
  assert.equal(doc.getElementById("approved-budget").textContent, "-250.00 USD cents");
  assert.equal(doc.getElementById("approved-target").textContent, "500.000 USD cents");
  assert.equal(doc.getElementById("remaining-risk").textContent, "+230.05 USD cents");
  assert.equal(doc.getElementById("loop-status").textContent, "active (recorded only)");
  assert.equal(doc.getElementById("loop-execution").textContent, "Unverified");
  assert.equal(doc.getElementById("loop-wake").dateTime, payload.loop.next_wake_at);
  assert.match(doc.getElementById("intents-list").textContent, /request-001/);
  payload.stops.target_latched_at = OBSERVED;
  payload.loop.status = "closing";
  payload.loop.wake_reason = "closure";
  await controller.request();
  assert.equal(doc.getElementById("loop-wake-reason").textContent, "Closure / reconciliation");
  payload.stops.closure_verified = true;
  payload.loop.status = "closed";
  payload.loop.wake_reason = "monitor";
  await controller.request();
  assert.equal(doc.getElementById("loop-wake-reason").textContent, "Stopped-account observation");
  assert.equal(doc.getElementById("canonical-state").textContent, "Target stop latched");
  assert.match(doc.getElementById("status-announcement").textContent, /execution unverified/);
});

test("action context recognizes explicit operations and disabled rules, not legacy guesses", () => {
  const { intent, latest_action } = strategyFixture();
  assert.equal(contextForIntent(intent), intent.context);
  assert.equal(contextForIntent(intent).strategy.addition_rule, false);
  for (const operation of ["add", "breakeven", "trail", "close", "cancel"]) {
    const action = { ...latest_action, kind: operation === "add" ? "entry" : "reduce", context: { ...latest_action.context, operation } };
    assert.equal(contextForIntent(action).operation, operation);
  }
  for (const context of [undefined, null, false, {}, { ...intent.context, version: 2 }, { ...intent.context, operation: "__proto__" },
    { ...intent.context, rationale: " " }, { ...intent.context, source_refs: [] }, { ...intent.context, origin_intent_id: false },
    { ...intent.context, strategy: { ...intent.context.strategy, trailing_rule: null } },
    { ...intent.context, strategy: { ...intent.context.strategy, timeframe: "unknown" } }]) assert.equal(contextForIntent({ ...intent, context }), null);
  assert.equal(contextForIntent({ ...latest_action, kind: "entry" }), null);
  assert.equal(contextForIntent({ ...latest_action, context: { ...latest_action.context, origin_intent_id: null } }), null);
  assert.equal(contextForIntent({ ...latest_action, context: { ...latest_action.context, operation: "close", origin_intent_id: null } }).operation, "close");
});

test("strategy pages append without duplicates only within a single saved revision", () => {
  const first = fixture();
  first.strategies = { items: [strategyFixture("idea-3"), strategyFixture("idea-2")], next_cursor: 2 };
  let state = mergeDashboardPage(null, first);
  const older = fixture();
  older.strategies = { items: [strategyFixture("idea-2"), strategyFixture("idea-1")], next_cursor: null };
  state = mergeDashboardPage(state, older, { strategyBefore: 2 });
  assert.deepEqual(state.strategies.map((item) => item.intent.id), ["idea-3", "idea-2", "idea-1"]);
  assert.equal(state.strategyCursor, null);
  state = mergeDashboardPage(state, first);
  assert.equal(state.strategies.length, 3);
  assert.equal(state.strategyCursor, null);
  const updated = structuredClone(first);
  updated.revision += 1;
  updated.strategies.items[1].latest_journal.reason = "New saved assessment";
  state = mergeDashboardPage(state, updated);
  assert.deepEqual(state.strategies.map((item) => item.intent.id), ["idea-3", "idea-2"]);
  assert.equal(state.strategies[1].latest_journal.reason, "New saved assessment");
  assert.equal(state.strategyCursor, 2);
  assert.equal(state.strategiesNeedRefresh, false);
});

test("strategy pages reject stale cursors and discard scope or revision races", () => {
  const first = fixture();
  first.strategies = { items: [strategyFixture()], next_cursor: 20 };
  const previous = mergeDashboardPage(null, first);
  const older = structuredClone(first);
  older.strategies = { items: [strategyFixture("older")], next_cursor: null };
  assert.equal(mergeDashboardPage(previous, older, { strategyBefore: 19 }), previous);
  assert.equal(mergeDashboardPage(previous, older, { strategyBefore: 20, requestId: 1, latestRequestId: 2 }), previous);
  for (const change of [
    (data) => { data.revision += 1; },
    (data) => { data.account.login = "another-account"; },
    (data) => { data.scope.goal_id = "another-goal"; },
    (data) => { data.scope.policy_id = "another-policy"; },
  ]) {
    const changed = structuredClone(older);
    change(changed);
    const state = mergeDashboardPage(previous, changed, { strategyBefore: 20 });
    assert.equal(state.strategies, null);
    assert.equal(state.strategyCursor, null);
    assert.equal(state.strategiesNeedRefresh, true);
    assert.equal(state.data.metrics.estimated_goal_gain, first.metrics.estimated_goal_gain);
  }
  older.revision -= 1;
  assert.equal(mergeDashboardPage(previous, older, { strategyBefore: 20 }), previous);
  const gone = mergeDashboardPage(previous, { ...fixture(), status: "unconfigured", account: null, scope: null, revision: 0 });
  assert.equal(gone.strategies, null);
  assert.equal(gone.strategyCursor, null);
});

test("session changes do not freshen financial evidence or break remaining sections", async (context) => {
  let now = NOW;
  const payload = fixture();
  payload.session = { id: "session-1", status: "stopped", started_at: OBSERVED, updated_at: GENERATED,
    reason: "<img src=x onerror=alert(1)> user stop", execution: "unverified" };
  payload.loop.next_wake_at = null;
  payload.loop.wake_reason = null;
  const { doc, controller } = setup(context, async () => response(payload), () => now);
  await controller.request();
  assert.equal(controller.error, null);
  assert.equal(doc.nodes.has("session-status"), false);
  assert.equal(doc.getElementById("session-id").textContent, payload.session.id);
  assert.equal(doc.getElementById("canonical-state").textContent, "Within budget at last check");
  assert.equal(doc.getElementById("account-login").textContent, payload.account.login);
  assert.equal(doc.getElementById("approved-target").textContent, "500.000 USD cents");
  assert.match(doc.getElementById("closure-state").textContent, /No verified account closure/);
  now += 600000;
  payload.session.status = "interrupted";
  payload.session.updated_at = new Date(now).toISOString();
  await controller.request();
  assert.equal(controller.error, null);
  assert.equal(doc.getElementById("source-badge").textContent, "Stale observation");
  assert.equal(doc.getElementById("source-time").dateTime, OBSERVED);
  payload.session.status = "active";
  payload.loop.next_wake_at = GENERATED;
  payload.loop.wake_reason = "session_check";
  await controller.request();
  assert.equal(doc.getElementById("loop-wake-reason").textContent, "Fresh session observation");
  assert.equal(doc.getElementById("loop-execution").textContent, "Unverified");
});

test("session activity is explanation-only and missing session data remains unavailable", async (context) => {
  const payload = fixture();
  payload.activity.items = [{ id: 12, command: "session", at: GENERATED, snapshot_at: null, decision: "session_saved",
    reason_codes: [], closure_verified: false, journal: null, intent: null,
    session: { id: "session-1", status: "stopped", reason: "User ended this task; broker exposure is unchanged." } }];
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.match(doc.getElementById("activity-list").textContent, /User stop recorded/);
  assert.match(doc.getElementById("activity-list").textContent, /broker exposure is unchanged/);
  assert.match(doc.getElementById("activity-list").textContent, /No broker observation, closure or current client execution/);
  assert.equal(doc.nodes.has("session-status"), false);
  assert.equal(doc.getElementById("session-id").textContent, "Unavailable");
  for (const session of [null, false, {}, { status: "running" }]) {
    payload.session = session;
    await controller.request();
    assert.equal(controller.error, null);
    assert.match(doc.getElementById("activity-list").textContent, /User stop recorded/);
    assert.equal(doc.getElementById("session-id").textContent, "Unavailable");
  }
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

test("unchanged polls preserve expanded and focused activity rows", async (context) => {
  let payload = fixture();
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  const row = controller.view.rowCaches.get("activity-list").values().next().value;
  const intent = controller.view.rowCaches.get("intents-list").values().next().value;
  row.details.open = true;
  row.summary.focus();
  const replacements = row.summary.replacements;
  const intentReplacements = intent.summary.replacements;
  const gainWrites = doc.getElementById("gain-scale").styleWrites.get("--gain-position");
  payload = { ...structuredClone(payload), revision: 13, generated_at: "2026-11-04T12:00:25Z" };
  await controller.request();
  assert.equal(row.details.open, true);
  assert.equal(doc.activeElement, row.summary);
  assert.equal(row.summary.replacements, replacements);
  assert.equal(intent.summary.replacements, intentReplacements);
  assert.equal(doc.getElementById("gain-scale").styleWrites.get("--gain-position"), gainWrites);
  payload.activity.items[0].decision = "blocked";
  await controller.request();
  assert.equal(row.details.open, true);
  assert.equal(doc.activeElement, row.summary);
  assert.match(row.summary.textContent, /Latest check blocked/);
});

test("reader failure retains conspicuously last-known values and original timestamps", async (context) => {
  let now = NOW;
  let payload = fixture();
  let ok = true;
  const { doc, controller } = setup(context, async () => response(payload, ok), () => now);
  await controller.request();
  const oldRead = controller.successfulAt;
  const gainPosition = doc.getElementById("gain-scale").style.getPropertyValue("--gain-position");
  const gainWrites = doc.getElementById("gain-scale").styleWrites.get("--gain-position");
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
  assert.equal(doc.getElementById("gain-scale").style.getPropertyValue("--gain-position"), gainPosition);
  assert.equal(doc.getElementById("gain-scale").styleWrites.get("--gain-position"), gainWrites);
  payload = { ...fixture(), status: "unconfigured", revision: 0, account: null, scope: null, snapshot: null, metrics: null };
    ok = true;
    await controller.request();
    assert.equal(controller.error, null);
    assert.equal(doc.getElementById("configured-workspace").hidden, true);
    assert.equal(doc.getElementById("activity-list").children.length, 0);
    assert.equal(doc.getElementById("intents-list").children.length, 0);
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

test("unsupported schema explains viewer-only recovery while retaining evidence and retry behavior", async (context) => {
  for (const retained of [false, true]) {
    await context.test(retained ? "last-known data" : "first read", async (context) => {
      let now = NOW;
      let failed = false;
      const calls = [];
      const { doc, controller } = setup(context, async (url, options) => {
        calls.push({ url, method: options.method });
        return response(failed ? { ok: false, status: "unavailable", error: "unsupported_schema", generated_at: GENERATED } : fixture(), !failed);
      }, () => now);
      if (retained) await controller.request();
      const previous = controller.state;
      const successfulAt = controller.successfulAt;
      failed = true;
      now += 60000;
      await controller.request();
      assert.equal(controller.state, previous);
      assert.equal(controller.error, "unsupported_schema");
      assert.equal(controller.successfulAt, successfulAt);
      assert.equal(controller.failures, 1);
      assert.notEqual(controller.timer, null);
      const message = doc.getElementById("reader-error").textContent;
      assert.match(message, /format is not supported by this viewer/);
      assert.match(message, /older Python viewer may still be running/);
      assert.match(message, /Browser refresh does not reload it/);
      assert.match(message, /if outdated, restart only the matching viewer/);
      assert.match(message, /Leave the checkpoint and trading agent unchanged/);
      if (retained) {
        assert.match(message, /last-known saved data/);
        assert.equal(doc.getElementById("source-time").dateTime, OBSERVED);
        assert.equal(doc.getElementById("net-gain").textContent, "+80.00 USD cents");
        assert.match(doc.getElementById("source-badge").textContent, /Last-known \/ Stale observation/);
      } else {
        assert.match(message, /unknown values are not zero/);
        assert.equal(doc.getElementById("account-login").textContent, "Unavailable");
        assert.equal(doc.getElementById("source-time").textContent, "Unavailable");
        assert.equal(doc.getElementById("configured-workspace").hidden, true);
      }
      await controller.request();
      assert.equal(controller.failures, 2);
      assert.equal(pollDelay(false, controller.failures), 20000);
      failed = false;
      now += 1000;
      await controller.request();
      assert.equal(controller.error, null);
      assert.equal(controller.failures, 0);
      assert.equal(doc.getElementById("reader-error").hidden, true);
      assert.equal(doc.getElementById("source-time").dateTime, OBSERVED);
      assert.equal(doc.getElementById("source-badge").textContent, "Stale observation");
      assert.equal(doc.getElementById("configured-workspace").hidden, false);
      assert.ok(calls.every(({ url, method }) => url === "/api/dashboard" && method === "GET"));
    });
  }
});

test("unknown order counts, progress and intents remain unavailable", async (context) => {
  const payload = fixture();
  payload.pending_orders = null;
  payload.exposure = { positions_count: null, orders_count: null, entry_orders_count: null, protective_orders_count: null };
  payload.unresolved_intents = null;
  payload.metrics.progress_pct = null;
  payload.metrics.target = null;
  payload.goal.target = null;
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  assert.equal(doc.getElementById("pending-count").textContent, "Unavailable");
  assert.equal(doc.getElementById("approved-target").textContent, "Unavailable");
  assert.equal(doc.getElementById("progress-exact").textContent, "Unavailable");
  assert.equal(doc.getElementById("goal-progress").getAttribute("aria-valuenow"), null);
  assert.equal(doc.getElementById("gain-scale").style.getPropertyValue("--fill-width"), "0%");
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

test("recorded strategies show fixed allocation, explicit actions and inert source-bound evidence", async (context) => {
  const payload = fixture();
  const item = strategyFixture();
  const malicious = '<img src="x" onerror="alert(1)">';
  item.intent.context.strategy.name = malicious;
  item.intent.context.strategy.thesis = "<script>not executable</script>";
  item.intent.context.source_refs = ["javascript:alert(1)"];
  item.latest_action.context.rationale = malicious;
  item.intent.parameters = { secret: "private-parameters" };
  item.latest_action.evidence_ref = "private-receipt";
  payload.strategies = { items: [item], next_cursor: null };
  payload.unresolved_intents.items = [item.latest_action];
  payload.activity.items[0] = { ...payload.activity.items[0], command: "prepare", decision: "prepared",
    intent: { ...item.latest_action, status: "completed" } };
  payload.stops.loss_latched_at = OBSERVED;
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  const rows = doc.getElementById("strategies-list");
  assert.equal(rows.children.length, 1);
  assert.match(rows.textContent, /Fixed original risk allocation10\.0001 USD cents/);
  assert.match(rows.textContent, /Stressed risk0 USD cents/);
  assert.match(rows.textContent, /Addition ruleDisabled in original plan/);
  assert.match(rows.textContent, /Plan source observed2026-11-04 12:00:00 UTC/);
  assert.match(rows.textContent, /Assessment recorded at2026-11-04 12:00:20 UTC/);
  assert.match(rows.textContent, /Outcome source time2026-11-04 12:00:20 UTC/);
  assert.match(rows.textContent, /Trailing stop/);
  assert.match(rows.textContent, /javascript:alert\(1\)/);
  assert.ok(rows.textContent.includes(malicious));
  assert.doesNotMatch(rows.textContent, /private-parameters|private-receipt/);
  const tags = (node) => [node.tagName, ...node.children.flatMap(tags)];
  assert.ok(!tags(rows).some((tag) => ["img", "script", "a", "iframe"].includes(tag)));
  assert.match(doc.getElementById("activity-list").textContent, /Current request status at page read: Settled request/);
  assert.match(doc.getElementById("activity-list").textContent, /not the outcome at this historical event/);
  assert.match(doc.getElementById("intents-list").textContent, /Recorded operationTrailing stop/);
  assert.match(doc.getElementById("intents-list").textContent, /Original entry IDidea-1/);
  assert.ok(doc.getElementById("intents-list").textContent.includes(malicious));
  assert.equal(doc.getElementById("canonical-state").textContent, "Loss stop latched");
  assert.equal(doc.getElementById("net-gain").textContent, "+80.00 USD cents");
  assert.equal(doc.getElementById("pending-count").textContent, "1");
  assert.match(html, /not live exposure or current ownership/);
  assert.match(html, /unfilled pending order/);
});

test("legacy and malformed strategy context never infer rules or unrelated assessments", async (context) => {
  const payload = fixture();
  const item = strategyFixture();
  item.intent.context = null;
  item.latest_action = null;
  delete item.latest_journal;
  payload.latest_journal.summary = "Unrelated same-symbol report";
  payload.strategies = { items: [item], next_cursor: null };
  payload.stops.loss_latched_at = OBSERVED;
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  const rows = doc.getElementById("strategies-list");
  assert.match(rows.textContent, /Original strategy unavailable/);
  assert.match(rows.textContent, /Trailing ruleUnavailable/);
  assert.doesNotMatch(rows.textContent, /Disabled in original plan|Unrelated same-symbol report/);
  const unsupported = strategyFixture();
  unsupported.intent.context.version = 999;
  unsupported.latest_action.context.origin_intent_id = "another-idea";
  unsupported.latest_journal.goal_id = "old-goal";
  payload.strategies.items = [unsupported];
  await controller.request();
  assert.match(rows.textContent, /Original strategy unavailable/);
  assert.match(rows.textContent, /Linked action unavailable/);
  assert.match(rows.textContent, /No supported linked assessment/);
  assert.match(doc.getElementById("warnings").textContent, /action context is unavailable/);
  assert.equal(doc.getElementById("canonical-state").textContent, "Loss stop latched");
});

test("malformed or unsafe strategy pages cannot break canonical financial rendering", async (context) => {
  const payload = fixture();
  payload.stops.loss_latched_at = OBSERVED;
  const { doc, controller } = setup(context, async () => response(payload));
  for (const page of [undefined, null, [], { items: "bad", next_cursor: null }, { items: [null], next_cursor: null },
    { items: [], next_cursor: "2" }, { items: [], next_cursor: -1 }, { items: [], next_cursor: Number.MAX_SAFE_INTEGER + 1 },
    { items: Array.from({ length: 21 }, (_, index) => strategyFixture(`idea-${index}`)), next_cursor: null }]) {
    payload.strategies = page;
    await controller.request();
    assert.equal(controller.error, null);
    assert.equal(controller.state.strategies, null);
    assert.equal(doc.getElementById("strategies-list").children.length, 0);
    assert.equal(doc.getElementById("strategies-more").hidden, true);
    assert.match(doc.getElementById("strategies-empty").textContent, /unavailable/);
    assert.equal(doc.getElementById("canonical-state").textContent, "Loss stop latched");
    assert.equal(doc.getElementById("net-gain").textContent, "+80.00 USD cents");
  }
});

test("unchanged strategy polls preserve native expanded rows and focus", async (context) => {
  let payload = fixture();
  payload.strategies = { items: [strategyFixture()], next_cursor: null };
  const { doc, controller } = setup(context, async () => response(payload));
  await controller.request();
  const row = controller.view.rowCaches.get("strategies-list").get("idea-1");
  row.details.open = true;
  row.summary.focus();
  const replacements = row.summary.replacements;
  payload = structuredClone(payload);
  payload.revision += 1;
  payload.generated_at = "2026-11-04T12:00:25Z";
  await controller.request();
  assert.equal(row.summary.replacements, replacements);
  assert.equal(row.details.open, true);
  assert.equal(doc.activeElement, row.summary);
  payload.strategies.items[0].latest_journal.summary = "Later linked assessment";
  await controller.request();
  assert.equal(row.details.open, true);
  assert.equal(doc.activeElement, row.summary);
  assert.match(row.summary.textContent, /Later linked assessment/);
});

test("strategy pagination loads exactly one bounded page per user action", async (context) => {
  const first = fixture();
  first.strategies = { items: [strategyFixture("idea-20"), strategyFixture("idea-10")], next_cursor: 10 };
  const older = { ...fixture(), strategies: { items: [strategyFixture("idea-5")], next_cursor: 5 } };
  const last = { ...fixture(), strategies: { items: [strategyFixture("idea-1")], next_cursor: null } };
  const pages = new Map([["/api/dashboard", first], ["/api/dashboard?strategy_before=10", older], ["/api/dashboard?strategy_before=5", last]]);
  const calls = [];
  const { doc, controller } = setup(context, async (url, options) => {
    calls.push(url);
    assert.equal(options.method, "GET");
    return response(structuredClone(pages.get(url)));
  });
  await controller.request();
  assert.equal(calls.length, 1);
  assert.equal(doc.getElementById("strategies-more").hidden, false);
  controller.onStrategiesMore();
  await flush();
  assert.deepEqual(calls, ["/api/dashboard", "/api/dashboard?strategy_before=10"]);
  assert.equal(controller.state.strategies.length, 3);
  assert.equal(controller.state.strategyCursor, 5);
  await controller.request(null, 10);
  await controller.request(12, 5);
  await controller.request(null, "5");
  assert.equal(calls.length, 2);
  doc.hidden = true;
  controller.onStrategiesMore();
  assert.equal(calls.length, 2);
  doc.hidden = false;
  controller.onStrategiesMore();
  await flush();
  assert.equal(calls.length, 3);
  assert.equal(controller.state.strategies.length, 4);
  assert.equal(doc.getElementById("strategies-more").hidden, true);
  assert.equal(doc.getElementById("activity-list").children.length, 1);
});

test("strategy reads serialize with refresh and existing activity-history requests", async (context) => {
  const pending = deferred();
  const first = fixture();
  first.strategies = { items: [strategyFixture("idea-10")], next_cursor: 10 };
  const older = { ...fixture(), strategies: { items: [strategyFixture("idea-5")], next_cursor: 5 } };
  const history = structuredClone(first);
  history.activity = { items: [{ ...first.activity.items[0], id: 11 }], next_cursor: null };
  const calls = [];
  let active = 0;
  let maxActive = 0;
  const { doc, controller } = setup(context, async (url) => {
    calls.push(url);
    active += 1;
    maxActive = Math.max(maxActive, active);
    try {
      if (url.includes("strategy_before")) return await pending.promise;
      return response(structuredClone(url.includes("?before") ? history : first));
    } finally { active -= 1; }
  });
  await controller.request();
  const loading = controller.request(null, 10);
  controller.onStrategiesMore();
  controller.onActivityToggle();
  await controller.request();
  await controller.request(12);
  assert.equal(calls.length, 2);
  assert.equal(doc.getElementById("strategies-more").disabled, true);
  assert.equal(doc.getElementById("strategies-list").getAttribute("aria-busy"), "true");
  assert.equal(doc.getElementById("activity-list").getAttribute("aria-busy"), "false");
  pending.resolve(response(older));
  await loading;
  for (let count = 0; count < 3; count += 1) await flush();
  assert.deepEqual(calls, ["/api/dashboard", "/api/dashboard?strategy_before=10", "/api/dashboard", "/api/dashboard?before=12"]);
  assert.equal(maxActive, 1);
  assert.equal(controller.state.strategies.length, 2);
  assert.equal(controller.state.activity.length, 2);
  assert.equal(controller.state.strategyCursor, 5);
  assert.equal(doc.getElementById("strategies-list").getAttribute("aria-busy"), "false");
});

test("failed strategy pages retain loaded evidence but retry only on another user action", async (context) => {
  const first = fixture();
  first.strategies = { items: [strategyFixture("idea-10")], next_cursor: 10 };
  const older = { ...fixture(), strategies: { items: [strategyFixture("idea-5")], next_cursor: null } };
  let reads = 0;
  const calls = [];
  const { doc, controller } = setup(context, async (url) => {
    calls.push(url);
    if (!url.includes("strategy_before")) return response(structuredClone(first));
    return ++reads === 1 ? response({ ok: false, error: "reader_busy" }, false) : response(structuredClone(older));
  });
  await controller.request();
  controller.onStrategiesMore();
  await flush();
  assert.equal(controller.error, "reader_busy");
  assert.equal(controller.state.strategies.length, 1);
  assert.match(doc.getElementById("strategies-state").textContent, /Last-known strategies/);
  await controller.request();
  await flush();
  assert.equal(controller.error, null);
  assert.equal(reads, 1);
  assert.equal(calls.length, 3);
  controller.onStrategiesMore();
  await flush();
  assert.equal(reads, 2);
  assert.equal(controller.state.strategies.length, 2);
});

test("strategy revision and campaign races refresh first pages without mixing evidence", async (context) => {
  for (const changeScope of [false, true]) {
    const pending = deferred();
    const first = fixture();
    first.strategies = { items: [strategyFixture("old-first")], next_cursor: 10 };
    const current = structuredClone(first);
    current.revision += 1;
    if (changeScope) current.scope.goal_id = "new-goal";
    current.strategies = { items: [strategyFixture("new-first")], next_cursor: 3 };
    const mismatched = structuredClone(current);
    mismatched.strategies = { items: [strategyFixture("stale-page")], next_cursor: null };
    let baseReads = 0;
    const calls = [];
    const { doc, controller } = setup(context, async (url) => {
      calls.push(url);
      if (url.includes("strategy_before")) return pending.promise;
      return response(structuredClone(baseReads++ === 0 ? first : current));
    });
    await controller.request();
    controller.onStrategiesMore();
    pending.resolve(response(mismatched));
    for (let count = 0; count < 3; count += 1) await flush();
    assert.deepEqual(calls, ["/api/dashboard", "/api/dashboard?strategy_before=10", "/api/dashboard"]);
    assert.equal(controller.state.strategiesNeedRefresh, false);
    assert.equal(controller.state.data.revision, current.revision);
    assert.deepEqual(controller.state.strategies.map((item) => item.intent.id), ["new-first"]);
    assert.doesNotMatch(doc.getElementById("strategies-list").textContent, /old-first|stale-page/);
    controller.stop();
  }
});

test("a non-advancing strategy cursor stops paging until the recorded revision changes", async (context) => {
  let first = fixture();
  first.strategies = { items: [strategyFixture("idea-10")], next_cursor: 10 };
  const stuck = { ...fixture(), strategies: { items: [strategyFixture("idea-5")], next_cursor: 10 } };
  const calls = [];
  const { doc, controller } = setup(context, async (url) => {
    calls.push(url);
    return response(structuredClone(url.includes("strategy_before") ? stuck : first));
  });
  await controller.request();
  controller.onStrategiesMore();
  await flush();
  assert.equal(controller.strategyPaginationStalled, true);
  assert.equal(doc.getElementById("strategies-more").disabled, true);
  assert.match(doc.getElementById("strategies-state").textContent, /cursor did not advance/);
  controller.onStrategiesMore();
  assert.equal(calls.length, 2);
  first = { ...first, revision: 13 };
  await controller.request();
  assert.equal(controller.strategyPaginationStalled, false);
  assert.equal(controller.state.strategies.length, 1);
});

test("stopping during strategy pagination aborts and ignores the late page", async (context) => {
  const pending = deferred();
  const first = fixture();
  first.strategies = { items: [strategyFixture("idea-10")], next_cursor: 10 };
  let signal;
  const { controller } = setup(context, async (url, options) => {
    if (!url.includes("strategy_before")) return response(first);
    signal = options.signal;
    return pending.promise;
  });
  await controller.request();
  const previous = controller.state;
  const reading = controller.request(null, 10);
  controller.stop();
  assert.equal(signal.aborted, true);
  pending.resolve(response({ ...fixture(), strategies: { items: [strategyFixture("late")], next_cursor: null } }));
  await reading;
  assert.equal(controller.state, previous);
  assert.equal(controller.inFlight, null);
});
