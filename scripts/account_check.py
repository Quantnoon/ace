"""Agent-invoked account checks and SQLite journal; never connects or trades."""

import argparse
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import uuid


DEFAULT_DB = Path(__file__).resolve().parents[1] / "ace_state.sqlite3"
SCHEMA_VERSION = 2
COMMANDS = ("draft", "activate", "check", "cycle", "prepare", "resolve", "status")
UNRESOLVED = ("prepared", "unknown")
PERIODS = {"M1": 1, "M2": 2, "M3": 3, "M4": 4, "M5": 5, "M6": 6, "M10": 10,
           "M12": 12, "M15": 15, "M20": 20, "M30": 30, "H1": 60, "H2": 120,
           "H3": 180, "H4": 240, "H6": 360, "H8": 480, "H12": 720,
           "D1": 1440, "W1": 10080, "MN1": 43200}
MARKET_STATES = ("open", "closed", "unknown")


class CheckError(ValueError):
    """A machine-readable, nonsecret contract or state error."""


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise CheckError("invalid_" + field)
    return value


def money(value, field, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise CheckError("invalid_" + field)
    if isinstance(value, str) and (not value or any(char not in "0123456789eE+-." for char in value)):
        raise CheckError("invalid_" + field)
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise CheckError("invalid_" + field) from None
    if (not result.is_finite() or len(result.as_tuple().digits) > 28
            or result.adjusted() > 18 or result.as_tuple().exponent < -12
            or (positive and result <= 0) or (nonnegative and result < 0)):
        raise CheckError("invalid_" + field)
    return result


def stamp(value, field):
    try:
        if not isinstance(value, str) or "T" not in value or not value.endswith("Z"):
            raise ValueError
        result = datetime.fromisoformat(value[:-1] + "+00:00")
        if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
            raise ValueError
        return result
    except ValueError:
        raise CheckError("invalid_" + field) from None


def utc(now):
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def period_minutes(value):
    name = text(value, "timeframe")
    if name not in PERIODS:
        raise CheckError("invalid_timeframe")
    return PERIODS[name]


def next_boundary(now, timeframe, buffer_seconds=5):
    """Next entry-timeframe candle boundary in UTC, plus a settle buffer."""
    if type(buffer_seconds) is not int or not 0 <= buffer_seconds <= 60:
        raise CheckError("invalid_buffer_seconds")
    base = datetime(1970, 1, 1, tzinfo=timezone.utc)
    if timeframe == "D1":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif timeframe == "W1":
        monday = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        start = monday + timedelta(days=7)
    elif timeframe == "MN1":
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = (first + timedelta(days=32)).replace(day=1)
    else:
        seconds = PERIODS[timeframe] * 60
        elapsed = (now - base).total_seconds()
        start = base + timedelta(seconds=(int(elapsed // seconds) + 1) * seconds)
    return start + timedelta(seconds=buffer_seconds)


def encode(value):
    def decimal_string(item):
        if isinstance(item, Decimal) and item.is_finite():
            return format(item, "f") if item else "0"
        raise TypeError("unsupported_json_value")
    return json.dumps(value, default=decimal_string, allow_nan=False,
                      sort_keys=True, separators=(",", ":"))


def decode(value, *, exact_numbers=True):
    def object_pairs(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise CheckError("duplicate_json_key")
            result[key] = item
        return result

    def nonfinite(_value):
        raise CheckError("nonfinite_json_number")

    try:
        return json.loads(value, parse_float=Decimal if exact_numbers else float,
                          parse_constant=nonfinite, object_pairs_hook=object_pairs)
    except (ValueError, RecursionError) as error:
        if isinstance(error, CheckError):
            raise
        raise CheckError("invalid_json") from None


def account(value):
    if not isinstance(value, dict):
        raise CheckError("invalid_account")
    result = {key: text(value.get(key), "account_" + key)
              for key in ("login", "server", "type", "currency")}
    if result["type"] not in ("demo", "live"):
        raise CheckError("invalid_account_type")
    return result


def strings(value, field):
    if not isinstance(value, list) or not value:
        raise CheckError("invalid_" + field)
    result = [text(item, field) for item in value]
    if len(set(result)) != len(result):
        raise CheckError("duplicate_" + field)
    return result


def mandate(value):
    if not isinstance(value, dict):
        raise CheckError("invalid_mandate")
    result = {"symbols": strings(value.get("symbols"), "symbols")}
    age = value.get("max_snapshot_age_seconds")
    if type(age) is not int or age <= 0:
        raise CheckError("invalid_max_snapshot_age_seconds")
    result["max_snapshot_age_seconds"] = age
    result["safety_margin"] = format(money(value.get("safety_margin"),
                                           "safety_margin", positive=True), "f")
    for permission in ("allow_entries", "allow_management", "close_all_on_loss",
                       "close_all_on_target", "accept_observed_only"):
        if value.get(permission) is not True:
            raise CheckError("missing_" + permission)
        result[permission] = True
    # Optional loop timing: absent fields keep an existing approved mandate byte-comparable.
    if "entry_timeframe" in value:
        result["entry_timeframe"] = text(value.get("entry_timeframe"), "entry_timeframe")
        if result["entry_timeframe"] not in PERIODS:
            raise CheckError("invalid_entry_timeframe")
    if "latch_check_seconds" in value:
        latch = value.get("latch_check_seconds")
        if type(latch) is not int or not 0 <= latch <= 3600:
            raise CheckError("invalid_latch_check_seconds")
        result["latch_check_seconds"] = latch
    return result


def snapshot(value, state, now, *, approved_baseline=False):
    """Validate the coherent accounting core before advancing an observed peak."""
    if not isinstance(value, dict):
        raise CheckError("missing_snapshot")
    if account(value.get("account")) != state["account"]:
        raise CheckError("account_mismatch")
    as_of = stamp(value.get("as_of"), "as_of")
    age = (now - as_of).total_seconds()
    if age < 0 or (not approved_baseline and age > state["mandate"]["max_snapshot_age_seconds"]):
        raise CheckError("stale_or_future_snapshot")
    through = stamp(value.get("history_through"), "history_through")
    if value.get("history_complete") is not True or not as_of <= through <= now:
        raise CheckError("incomplete_history")
    anchor = value.get("history_anchor")
    anchor_time = stamp(anchor, "history_anchor")
    if anchor != state["history_anchor"] or anchor_time > as_of:
        raise CheckError("history_anchor_mismatch")
    flows = value.get("cashflows")
    if not isinstance(flows, list):
        raise CheckError("missing_cashflows")
    seen = {}
    for flow in flows:
        if not isinstance(flow, dict):
            raise CheckError("invalid_cashflow")
        flow_id = text(flow.get("id"), "cashflow_id")
        when = stamp(flow.get("at"), "cashflow_at")
        if flow_id in seen or not anchor_time <= when <= as_of:
            raise CheckError("duplicate_or_out_of_window_cashflow")
        seen[flow_id] = {"id": flow_id, "at": flow["at"],
                         "amount": format(money(flow.get("amount"), "cashflow"), "f")}
    result = {
        "account": state["account"], "as_of": value["as_of"],
        "id": text(value.get("id"), "snapshot_id"),
        "source_ref": text(value.get("source_ref"), "source_ref"),
        "history_anchor": anchor, "history_through": value["history_through"],
        "history_cursor": text(value.get("history_cursor"), "history_cursor"),
        "history_complete": True, "cashflows": sorted(seen.values(), key=lambda f: f["id"]),
        "balance": format(money(value.get("balance"), "balance"), "f"),
        "equity": format(money(value.get("equity"), "equity"), "f"),
    }
    # Unknown execution inputs block additions, not a known account loss trigger.
    for key in ("positions", "pending_orders", "free_margin", "remaining_close_costs",
                "costs_final", "trading_enabled"):
        result[key] = value.get(key)
    result = decode(encode(result), exact_numbers=False)
    previous = state.get("last_snapshot")
    if previous:
        previous_time = stamp(previous["as_of"], "previous_as_of")
        if as_of < previous_time:
            raise CheckError("out_of_order_snapshot")
        if result["id"] == previous["id"] and result != previous:
            raise CheckError("conflicting_snapshot_id")
        if as_of == previous_time and result != previous:
            raise CheckError("conflicting_snapshot_time")
        for flow in previous["cashflows"]:
            if seen.get(flow["id"]) != flow:
                raise CheckError("cashflow_history_changed")
        previous_ids = {flow["id"] for flow in previous["cashflows"]}
        if any(flow_id not in previous_ids and stamp(flow["at"], "cashflow_at") <= previous_time
               for flow_id, flow in seen.items()):
            raise CheckError("backdated_cashflow_requires_reconciliation")
    return result


def exposure(value):
    positions, orders = value.get("positions"), value.get("pending_orders")
    if not isinstance(positions, list) or not isinstance(orders, list):
        raise CheckError("exposure_unavailable")
    total = Decimal(0)
    position_ids = set()
    for collection, items in (("position", positions), ("order", orders)):
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                raise CheckError("invalid_exposure")
            ticket = text(item.get("ticket"), "ticket")
            text(item.get("symbol"), "symbol")
            if ticket in seen:
                raise CheckError("duplicate_exposure")
            seen.add(ticket)
            if collection == "position":
                position_ids.add(ticket)
            elif item.get("kind") == "protective":
                if (item.get("reduce_only") is not True
                        or item.get("position_ticket") not in position_ids):
                    raise CheckError("unverified_protective_order")
                continue  # Its loss is already part of the protected position's risk.
            elif item.get("kind") != "entry":
                raise CheckError("invalid_pending_order_kind")
            if item.get("protected") is not True:
                raise CheckError("unprotected_exposure")
            total += money(item.get("risk"), "exposure_risk", nonnegative=True)
    return total


def observe(state, supplied, now, *, approved_baseline=False):
    current = snapshot(supplied, state, now, approved_baseline=approved_baseline)
    flow_total = sum((money(f["amount"], "cashflow") for f in current["cashflows"]), Decimal(0))
    equity = money(current["equity"], "equity")
    policy_flows = flow_total - money(state["policy"]["cashflow_anchor"], "policy_cashflow_anchor")
    goal_flows = flow_total - money(state["goal"]["cashflow_anchor"], "goal_cashflow_anchor")
    adjusted = equity - policy_flows
    peak = max(money(state["peak"], "peak"), adjusted)
    drawdown = peak - adjusted
    budget = money(state["policy"]["budget"], "budget", positive=True)
    target = money(state["goal"]["target"], "target", positive=True)
    state["peak"] = format(peak, "f")
    if drawdown >= budget and not state["loss_latched_at"]:
        state["loss_latched_at"] = current["as_of"]
    errors = []
    metrics = {"budget": budget, "target": target, "balance": current["balance"],
               "equity": equity, "peak": peak, "drawdown": drawdown,
               "remaining_risk": budget - drawdown, "adjusted_stop_floor": peak - budget,
               "account_stop_floor": peak - budget + policy_flows,
               "policy_cashflows": policy_flows, "goal_cashflows": goal_flows,
               "estimated_goal_gain": None, "progress_pct": None, "remaining_target": None,
               "remaining_close_costs": None, "existing_risk": None, "free_margin": None,
               "final_net": None, "final_shortfall": None}
    try:
        close_costs = money(current["remaining_close_costs"], "remaining_close_costs", nonnegative=True)
        gain = equity - goal_flows - money(state["goal"]["start_equity"], "goal_start_equity") - close_costs
        metrics.update(remaining_close_costs=close_costs, estimated_goal_gain=gain,
                       progress_pct=100 * gain / target, remaining_target=max(Decimal(0), target - gain))
        if gain >= target and not state["target_latched_at"]:
            state["target_latched_at"] = current["as_of"]
            state["target_trigger_gain"] = format(gain, "f")
    except CheckError as error:
        errors.append(str(error))
    try:
        metrics["existing_risk"] = exposure(current)
        metrics["free_margin"] = money(current["free_margin"], "free_margin")
        if metrics["existing_risk"] + money(state["mandate"]["safety_margin"], "safety_margin") >= budget - drawdown:
            errors.append("existing_risk_exhausts_headroom")
    except CheckError as error:
        errors.append(str(error))
    if equity <= 0:
        errors.append("nonpositive_equity")
    if current["trading_enabled"] is not True:
        errors.append("trading_disabled_or_unknown")
    state["last_snapshot"] = current
    state["last_metrics"] = decode(encode(metrics), exact_numbers=False)
    return metrics, errors


def report(state, metrics=None, errors=(), outstanding=0):
    reasons = list(errors)
    if outstanding:
        reasons.append("unresolved_intents")
    if not state.get("policy"):
        decision = "draft"
    elif state["loss_latched_at"]:
        decision = "loss_stop"
    elif state["target_latched_at"]:
        decision = "target_stop"
    elif outstanding or metrics is None:
        decision = "reconciliation_required"
    elif reasons:
        decision = "blocked"
    else:
        decision = "within_budget"
    stopped = bool(state.get("loss_latched_at") or state.get("target_latched_at"))
    current = state.get("last_snapshot")
    closed = bool(stopped and metrics is not None and not outstanding and current
                  and current["positions"] == [] and current["pending_orders"] == []
                  and current["costs_final"] is True
                  and metrics.get("remaining_close_costs") == 0)
    if closed:
        metrics["final_net"] = (money(current["equity"], "equity")
                                - metrics["goal_cashflows"]
                                - money(state["goal"]["start_equity"], "goal_start_equity"))
        metrics["final_shortfall"] = max(Decimal(0), metrics["target"] - metrics["final_net"])
    if metrics is not None:
        state["last_metrics"] = decode(encode(metrics), exact_numbers=False)
    return {"ok": True, "decision": decision, "may_dispatch": False,
            "reason_codes": sorted(set(reasons)), "metrics": metrics,
            "loss_latched_at": state.get("loss_latched_at"),
            "target_latched_at": state.get("target_latched_at"),
            "last_verified_at": current["as_of"] if current else None,
            "closure_verified": closed,
            "required_action": ("remain_stopped" if closed else "cancel_entries_and_close_all")
            if stopped else "none"}


def loop_cycle(state, request, now, result):
    """Record one active decision cycle; only a monetary latch closes the session."""
    timeframe = request["timeframe"] if "timeframe" in request else state["mandate"].get("entry_timeframe", "M15")
    period_minutes(timeframe)
    buffer_seconds = request.get("buffer_seconds", 5)
    next_cycle_at = utc(next_boundary(now, timeframe, buffer_seconds))
    market_state = request.get("market_state", "open")
    if market_state not in MARKET_STATES:
        raise CheckError("invalid_market_state")
    bar_time, confirmed = None, None
    bar = request.get("bar")
    if bar is not None:
        if not isinstance(bar, dict):
            raise CheckError("invalid_bar")
        bar_time = stamp(bar.get("open_time"), "bar_open_time")
        if bar_time > now:
            raise CheckError("future_bar")
        if not isinstance(bar.get("confirmed"), bool):
            raise CheckError("invalid_bar_confirmed")
        confirmed = bar["confirmed"]
    loop = state.get("loop")
    if not isinstance(loop, dict) or loop.get("status") == "closed":
        loop = {"id": "loop-" + str(uuid.uuid4()), "started_at": utc(now), "cycles": 0,
                "gap_seconds": None, "max_gap_seconds": None, "max_gap_at": None,
                "missing_bars": 0, "end_reason": None, "ended_at": None,
                "timeframe": timeframe, "bar_open_time": None, "bar_confirmed": None,
                "bar_advanced": None, "market_state": market_state}
    previous = stamp(loop["last_cycle_at"], "last_cycle_at") if loop.get("last_cycle_at") else None
    gap = None if previous is None else max(0.0, (now - previous).total_seconds())
    loop["gap_seconds"] = gap
    if gap is not None and (loop.get("max_gap_seconds") is None or gap > loop["max_gap_seconds"]):
        loop["max_gap_seconds"] = gap
        loop["max_gap_at"] = utc(now)
    loop["cycles"] = int(loop.get("cycles", 0)) + 1
    loop["last_cycle_at"] = utc(now)
    loop["timeframe"] = timeframe
    loop["market_state"] = market_state
    if bar_time is not None:
        previous_bar = stamp(loop["bar_open_time"], "bar_open_time") if loop.get("bar_open_time") else None
        advanced = previous_bar is None or bar_time > previous_bar
        loop["bar_open_time"] = utc(bar_time)
        loop["bar_confirmed"] = confirmed
        loop["bar_advanced"] = advanced
        loop["missing_bars"] = 0 if advanced else int(loop.get("missing_bars", 0)) + 1
    loop["next_cycle_at"] = next_cycle_at
    if result["loss_latched_at"] or result["target_latched_at"]:
        loop["end_reason"] = "loss_latch" if result["loss_latched_at"] else "target_latch"
        loop["status"] = "closed" if result["closure_verified"] else "closing"
        if loop["status"] == "closed" and not loop.get("ended_at"):
            loop["ended_at"] = utc(now)
    else:
        loop["status"] = "active"
        loop["end_reason"] = None
    state["loop"] = loop
    return loop


def tool_parameters(value):
    """Keep MCP JSON number types; monetary accounting itself stays Decimal."""
    if isinstance(value, dict):
        secrets = {"authorization", "password", "access_token", "api_key", "api_secret", "client_secret"}
        if any(key.lower().replace("-", "_") in secrets for key in value):
            raise CheckError("credentials_in_parameters")
        return {key: tool_parameters(item) for key, item in value.items()}
    if isinstance(value, list):
        return [tool_parameters(item) for item in value]
    if isinstance(value, Decimal):
        converted = float(value)
        if not math.isfinite(converted) or Decimal(str(converted)) != value:
            raise CheckError("unrepresentable_mcp_number")
        return converted
    if isinstance(value, float) and not math.isfinite(value):
        raise CheckError("unrepresentable_mcp_number")
    return value


def action(value, state, metrics, errors):
    if not isinstance(value, dict):
        raise CheckError("missing_action")
    result = {key: text(value.get(key), "action_" + key)
              for key in ("id", "kind", "tool", "authority_ref")}
    if value.get("tool_permission") is not True:
        raise CheckError("missing_tool_permission")
    if not isinstance(value.get("parameters"), dict) or not value["parameters"]:
        raise CheckError("missing_action_parameters")
    result["parameters"] = tool_parameters(value["parameters"])
    if value.get("policy_id") != state["policy"]["id"] or value.get("goal_id") != state["goal"]["id"]:
        raise CheckError("action_mandate_mismatch")
    if result["kind"] == "entry":
        if state["loss_latched_at"] or state["target_latched_at"] or errors or metrics is None:
            raise CheckError("entry_blocked")
        for key in ("broker_checks_passed", "protective_stop_in_request"):
            if value.get(key) is not True:
                raise CheckError("missing_" + key)
        result["analysis_ref"] = text(value.get("analysis_ref"), "analysis_ref")
        if value.get("symbol") not in state["mandate"]["symbols"]:
            raise CheckError("unapproved_symbol")
        result["symbol"] = value["symbol"]
        result["signal_id"] = text(value.get("signal_id"), "signal_id")
        risk = money(value.get("risk"), "proposed_risk", positive=True)
        margin = money(value.get("margin"), "proposed_margin", nonnegative=True)
        if metrics["existing_risk"] + risk + money(state["mandate"]["safety_margin"], "safety_margin") >= metrics["remaining_risk"]:
            raise CheckError("insufficient_headroom")
        if margin > metrics["free_margin"]:
            raise CheckError("insufficient_margin")
        result["risk"] = format(risk, "f")
        result["margin"] = format(margin, "f")
    elif result["kind"] == "reduce":
        if value.get("reduction_verified") is not True:
            raise CheckError("unverified_reduction")
        reason = value.get("reason")
        if (reason not in ("management", "protection_failure", "loss", "target")
                or (reason == "loss" and not state["loss_latched_at"])
                or (reason == "target" and not state["target_latched_at"])):
            raise CheckError("invalid_reduction_authority")
        result["reason"] = reason
        result["tickets"] = strings(value.get("tickets"), "tickets")
        current = state["last_snapshot"]
        if not isinstance(current.get("positions"), list) or not isinstance(current.get("pending_orders"), list):
            raise CheckError("exposure_unavailable")
        known = {item.get("ticket") for item in current["positions"] + current["pending_orders"]
                 if isinstance(item, dict)}
        if not set(result["tickets"]) <= known:
            raise CheckError("unknown_reduction_ticket")
        result["risk"] = "0"
    else:
        raise CheckError("invalid_action_kind")
    return result


def load_state(connection):
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version not in (1, SCHEMA_VERSION):
        raise CheckError("unsupported_schema")
    row = connection.execute("SELECT revision, payload FROM state WHERE id = 1").fetchone()
    if row is None:
        if connection.execute("SELECT count(*) FROM events").fetchone()[0]:
            raise CheckError("missing_account_state")
        return 0, None
    latest = connection.execute("SELECT state_sha256 FROM events ORDER BY id DESC LIMIT 1").fetchone()
    if not latest or latest[0] != hashlib.sha256(row[1].encode("utf-8")).hexdigest():
        raise CheckError("state_audit_mismatch")
    state = decode(row[1], exact_numbers=False)
    if not isinstance(state, dict) or account(state.get("account")) != state["account"]:
        raise CheckError("invalid_account_state")
    text(state.get("owner_id"), "owner_id")
    state.setdefault("loop", None)
    return row[0], state


def save_state(connection, revision, state, command, detail, now):
    serialized = encode(state)
    connection.execute("INSERT INTO state VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision, payload=excluded.payload",
                       (revision, serialized))
    connection.execute("INSERT INTO events(at, command, detail, state_sha256) VALUES (?, ?, ?, ?)",
                       (utc(now), command, encode(detail), hashlib.sha256(serialized.encode("utf-8")).hexdigest()))
    connection.execute("PRAGMA user_version = " + str(SCHEMA_VERSION))


def pending(connection):
    return connection.execute("SELECT id, payload, status, outcome FROM intents WHERE status IN ('prepared', 'unknown') ORDER BY id").fetchall()


def activate(state, request, now, outstanding):
    mode = request.get("mode")
    if mode not in ("start", "resume", "reauthorize", "new_goal", "replace_policy"):
        raise CheckError("invalid_activation_mode")
    if outstanding and mode != "resume":
        raise CheckError("unresolved_intents")
    if bool(state.get("policy")) == (mode == "start"):
        raise CheckError("invalid_activation_state")
    config = mandate(request.get("mandate"))
    approval_ref = text(request.get("approval_ref"), "approval_ref")
    approved_at = stamp(request.get("approved_at"), "approved_at")
    if approved_at > now:
        raise CheckError("future_approval")
    if not isinstance(request.get("snapshot"), dict):
        raise CheckError("missing_snapshot")
    draft = state["draft"]
    budget = money(state["policy"]["budget"] if mode == "resume" else draft.get("budget"), "budget", positive=True)
    target = money(state["goal"]["target"] if mode == "resume" else draft.get("target"), "target", positive=True)
    if mode != "resume" and config != draft.get("mandate"):
        raise CheckError("mandate_differs_from_saved_proposal")
    replacement = mode in ("start", "replace_policy")
    previous = copy.deepcopy(state)
    if mode == "resume":
        if config != state["mandate"] or budget != money(state["policy"]["budget"], "budget") or target != money(state["goal"]["target"], "target"):
            raise CheckError("resume_cannot_change_mandate")
    elif mode == "reauthorize":
        if budget != money(state["policy"]["budget"], "budget") or target != money(state["goal"]["target"], "target"):
            raise CheckError("reauthorization_cannot_change_money")
    elif mode == "new_goal":
        if budget != money(state["policy"]["budget"], "budget") or config != state["mandate"]:
            raise CheckError("new_goal_cannot_change_policy")
        if state["loss_latched_at"]:
            raise CheckError("loss_requires_replacement_policy")
    elif mode == "replace_policy":
        text(request.get("reset_reason"), "reset_reason")
    if request["owner_id"] != state["owner_id"]:
        text(request.get("takeover_ref"), "takeover_ref")
    state["mandate"] = config
    if mode not in ("resume", "reauthorize"):
        if not isinstance(request.get("baseline"), dict):
            raise CheckError("missing_approval_baseline")
        if stamp(request["baseline"].get("as_of"), "baseline_as_of") > approved_at:
            raise CheckError("baseline_not_in_approval")
        if replacement:
            state["last_snapshot"] = None
            state["history_anchor"] = request["baseline"].get("as_of")
        baseline = snapshot(request["baseline"], state, approved_at, approved_baseline=True)
        if money(baseline["equity"], "equity") <= 0:
            raise CheckError("nonpositive_baseline")
        total = sum((money(f["amount"], "cashflow") for f in baseline["cashflows"]), Decimal(0))
        if replacement:
            if baseline["cashflows"]:
                raise CheckError("new_policy_requires_new_cashflow_boundary")
            state["policy"] = {"id": str(uuid.uuid4()), "budget": format(budget, "f"),
                               "started_at": baseline["as_of"], "start_equity": baseline["equity"],
                               "cashflow_anchor": format(total, "f"), "approval_ref": approval_ref,
                               "approved_at": request["approved_at"]}
            state["peak"] = baseline["equity"]
            state["loss_latched_at"] = None
            state["history_start_cursor"] = baseline["history_cursor"]
        else:
            observe(state, baseline, approved_at, approved_baseline=True)
            if state["loss_latched_at"]:
                raise CheckError("loss_requires_replacement_policy")
        state["goal"] = {"id": str(uuid.uuid4()), "target": format(target, "f"),
                         "started_at": baseline["as_of"], "start_equity": baseline["equity"],
                         "cashflow_anchor": format(total, "f"), "approval_ref": approval_ref,
                         "approved_at": request["approved_at"]}
        state["target_latched_at"] = None
        state["target_trigger_gain"] = None
        state["last_snapshot"] = baseline
    current = snapshot(request["snapshot"], state, now)
    if mode != "resume" and stamp(current["as_of"], "as_of") < approved_at:
        raise CheckError("activation_snapshot_predates_approval")
    if mode in ("reauthorize", "new_goal", "replace_policy"):
        for boundary in ((current,) if mode == "reauthorize" else (baseline, current)):
            if boundary["positions"] != [] or boundary["pending_orders"] != []:
                raise CheckError("finish_existing_exposure_before_replacement")
            if boundary["costs_final"] is not True or money(boundary["remaining_close_costs"], "remaining_close_costs", nonnegative=True) != 0:
                raise CheckError("settle_existing_costs_before_replacement")
    state["approval_ref"] = approval_ref
    state["approved_at"] = request["approved_at"]
    state["owner_id"] = request["owner_id"]
    metrics, errors = observe(state, current, now)
    return report(state, metrics, errors, len(outstanding)), {"previous_state": previous, "mode": mode,
                                          "baseline": baseline if mode not in ("resume", "reauthorize") else None,
                                          "reset_reason": request.get("reset_reason"),
                                          "takeover_ref": request.get("takeover_ref")}


def transact(connection, command, request, now):
    revision, state = load_state(connection)
    if command == "status":
        return {"ok": True, "decision": "cached" if state else "unconfigured",
                "may_dispatch": False, "revision": revision, "state": state,
                "outstanding_intents": [{"id": row[0], "action": decode(row[1], exact_numbers=False),
                                         "status": row[2], "outcome": decode(row[3], exact_numbers=False) if row[3] else None}
                                        for row in pending(connection)]}
    if type(request.get("expected_revision")) is not int or request["expected_revision"] != revision:
        raise CheckError("revision_mismatch")
    owner = text(request.get("owner_id"), "owner_id")
    if state and owner != state["owner_id"] and command != "activate":
        raise CheckError("owner_mismatch")
    if command == "draft":
        identity = account(request.get("account"))
        source_ref = text(request.get("source_ref"), "source_ref")
        if state and identity != state["account"]:
            raise CheckError("account_mismatch")
        if state is None:
            state = {"account": identity, "owner_id": owner, "draft": {}, "policy": None,
                     "goal": None, "mandate": None, "peak": None, "history_anchor": None,
                     "last_snapshot": None, "last_metrics": None, "loss_latched_at": None,
                     "target_latched_at": None, "target_trigger_gain": None}
        for field in ("budget", "target"):
            if field in request:
                state["draft"][field] = format(money(request[field], field, positive=True), "f")
        if "mandate" in request:
            state["draft"]["mandate"] = mandate(request["mandate"])
        state["draft"]["source_ref"] = source_ref
        result, detail = {"ok": True, "decision": "draft_saved", "may_dispatch": False}, {"draft": state["draft"]}
    else:
        if state is None:
            raise CheckError("setup_incomplete")
        outstanding = pending(connection)
        if command == "activate":
            original = copy.deepcopy(state)
            try:
                result, detail = activate(state, request, now, outstanding)
            except CheckError as error:
                if not original.get("policy"):
                    raise
                state = original
                metrics, errors = None, [str(error)]
                if isinstance(request.get("baseline"), dict):
                    try:
                        observe(state, request["baseline"], min(stamp(request.get("approved_at"), "approved_at"), now),
                                approved_baseline=True)
                    except CheckError:
                        pass
                try:
                    metrics, observed_errors = observe(state, request.get("snapshot"), now)
                    errors.extend(observed_errors)
                except CheckError as observation_error:
                    errors.append(str(observation_error))
                result = report(state, metrics, errors, len(outstanding))
                detail = {"rejected_activation": errors, "snapshot": state["last_snapshot"] if metrics is not None else None}
        else:
            if not state.get("policy"):
                raise CheckError("setup_incomplete")
            metrics, errors = None, []
            try:
                metrics, errors = observe(state, request.get("snapshot"), now)
            except CheckError as error:
                errors.append(str(error))
            detail = {"snapshot": state["last_snapshot"] if metrics is not None else None,
                      "reason_codes": list(errors)}
            result = report(state, metrics, errors, len(outstanding))
            try:
                if command == "prepare":
                    if metrics is None:
                        raise CheckError("fresh_account_snapshot_required")
                    proposed = action(request.get("action"), state, metrics, errors)
                    if proposed["kind"] == "entry" and outstanding:
                        raise CheckError("unresolved_intents")
                    if proposed["kind"] == "reduce":
                        for _intent_id, raw, _status, _outcome in outstanding:
                            other = decode(raw, exact_numbers=False)
                            if other["kind"] == "reduce" and set(other["tickets"]) & set(proposed["tickets"]):
                                raise CheckError("overlapping_reduction")
                    signal_key = encode([state["goal"]["id"], proposed["symbol"], proposed["signal_id"]]) if proposed["kind"] == "entry" else None
                    if connection.execute("SELECT 1 FROM intents WHERE id = ? OR signal_key = ?", (proposed["id"], signal_key)).fetchone():
                        raise CheckError("duplicate_action_or_signal")
                    proposed.update(policy_id=state["policy"]["id"], goal_id=state["goal"]["id"],
                                    owner_id=owner, account=state["account"], snapshot_at=state["last_snapshot"]["as_of"],
                                    created_at=utc(now))
                    connection.execute("INSERT INTO intents(id, signal_key, status, payload) VALUES (?, ?, 'prepared', ?)",
                                       (proposed["id"], signal_key, encode(proposed)))
                    result.update(decision="prepared", may_dispatch=True, intent=proposed)
                    detail["intent_id"] = proposed["id"]
                elif command == "resolve":
                    intent_id = text(request.get("intent_id"), "intent_id")
                    row = connection.execute("SELECT status, payload FROM intents WHERE id = ?", (intent_id,)).fetchone()
                    if not row or row[0] not in UNRESOLVED:
                        raise CheckError("intent_not_unresolved")
                    intent = decode(row[1], exact_numbers=False)
                    outcome = request.get("outcome")
                    if outcome not in ("completed", "not_executed", "unknown"):
                        raise CheckError("invalid_outcome")
                    evidence = text(request.get("evidence_ref"), "outcome_evidence_ref")
                    tickets = request.get("broker_tickets", [])
                    if outcome != "unknown":
                        if metrics is None or stamp(state["last_snapshot"]["as_of"], "as_of") <= max(
                                stamp(intent["snapshot_at"], "intent_snapshot_at"), stamp(intent["created_at"], "intent_created_at")):
                            raise CheckError("post_action_snapshot_required")
                        if request.get("readback_verified") is not True:
                            raise CheckError("outcome_readback_required")
                        if outcome == "completed":
                            tickets = strings(tickets, "broker_tickets")
                        if intent["policy_id"] != state["policy"]["id"] or intent["goal_id"] != state["goal"]["id"]:
                            raise CheckError("intent_mandate_mismatch")
                    resolution = {"outcome": outcome, "evidence_ref": evidence, "broker_tickets": tickets,
                                  "at": utc(now), "snapshot_at": state["last_snapshot"]["as_of"] if metrics is not None else None}
                    connection.execute("UPDATE intents SET status = ?, outcome = ? WHERE id = ?", (outcome, encode(resolution), intent_id))
                    detail.update(intent_id=intent_id, resolution=resolution)
                    result = report(state, metrics, errors, len(pending(connection)))
                elif command == "cycle":
                    if metrics is None:
                        raise CheckError("fresh_account_snapshot_required")
                    loop = loop_cycle(state, request, now, result)
                    result.update(may_continue=loop["status"] == "active", loop=loop)
                    detail["loop"] = loop
                elif command != "check":
                    raise CheckError("unknown_command")
            except CheckError as error:
                # Commit a valid observed breach even when its proposed order is rejected.
                errors.append(str(error))
                result = report(state, metrics, errors, len(pending(connection)))
                if command == "cycle":
                    result.update(loop=state.get("loop"),
                                  may_continue=not (state.get("loss_latched_at")
                                                    or state.get("target_latched_at")))
                detail["reason_codes"] = errors
    state["last_result"] = {key: value for key, value in result.items() if key not in ("intent", "may_dispatch")}
    save_state(connection, revision + 1, state, command, detail, now)
    result.update(revision=revision + 1, policy_id=state["policy"]["id"] if state["policy"] else None,
                  goal_id=state["goal"]["id"] if state["goal"] else None)
    return decode(encode(result), exact_numbers=False)


def run(command, request=None, db_path=DEFAULT_DB, now=None):
    """Apply one local transaction. A returned permit is NOT a broker-side lock."""
    if command not in COMMANDS:
        raise CheckError("unknown_command")
    if request is None:
        request = {}
    if not isinstance(request, dict):
        raise CheckError("invalid_request")
    now = now or datetime.now(timezone.utc)
    path = Path(db_path).resolve()
    existed = path.exists()
    if not existed and command == "status":
        return {"ok": True, "decision": "unconfigured", "may_dispatch": False,
                "revision": 0, "state": None, "outstanding_intents": []}
    create = command == "draft"
    if not existed and not create:
        raise CheckError("setup_incomplete")
    if command == "draft":
        # Reject bad first inputs before SQLite can create an empty checkpoint file.
        account(request.get("account"))
        text(request.get("source_ref"), "source_ref")
        text(request.get("owner_id"), "owner_id")
        if type(request.get("expected_revision")) is not int or (not existed and request["expected_revision"] != 0):
            raise CheckError("revision_mismatch")
        for field in ("budget", "target"):
            if field in request:
                money(request[field], field, positive=True)
        if "mandate" in request:
            mandate(request["mandate"])
    mode = "ro" if command == "status" else "rwc" if create else "rw"
    connection = None
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=" + mode, uri=True, timeout=1)
        connection.execute("BEGIN" if command == "status" else "BEGIN IMMEDIATE")
        if not existed and create:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if not version and not tables:
                connection.execute("CREATE TABLE state(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL)")
                connection.execute("CREATE TABLE events(id INTEGER PRIMARY KEY, at TEXT NOT NULL, command TEXT NOT NULL, detail TEXT NOT NULL, state_sha256 TEXT NOT NULL)")
                connection.execute("CREATE TABLE intents(id TEXT PRIMARY KEY, signal_key TEXT UNIQUE, status TEXT NOT NULL CHECK(status IN ('prepared','unknown','completed','not_executed')), payload TEXT NOT NULL, outcome TEXT)")
                connection.execute("PRAGMA user_version = " + str(SCHEMA_VERSION))
        with localcontext() as context:
            context.prec = 64
            result = transact(connection, command, request, now)
        connection.commit()
        return result
    except sqlite3.Error:
        raise CheckError("database_unavailable_or_corrupt") from None
    finally:
        if connection is not None:
            connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite path; default is repository-root ace_state.sqlite3")
    parser.add_argument("--input", type=Path, help="Private JSON request file; otherwise read stdin (not needed for status)")
    args = parser.parse_args(argv)
    try:
        request = {} if args.command == "status" else decode(args.input.read_text(encoding="utf-8-sig") if args.input else sys.stdin.read())
        result = run(args.command, request, args.db)
        print(encode(result))
        return 0
    except (CheckError, OSError, UnicodeError, TypeError, KeyError, InvalidOperation):
        error = sys.exc_info()[1]
        code = str(error) if isinstance(error, CheckError) else "invalid_input_or_state"
        print(encode({"ok": False, "decision": "reconciliation_required", "may_dispatch": False,
                      "reason_codes": [code]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
