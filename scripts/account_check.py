"""Agent-invoked account checks and SQLite journal; never connects or trades."""

import argparse
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import uuid


DEFAULT_DB = Path(__file__).resolve().parents[1] / "ace_state.sqlite3"
SCHEMA_VERSION = 5
READABLE_SCHEMA_VERSIONS = (1, 2, 3, 4, 5)
# Advance for reader behavior changes, including fixes within the same schema.
READER_BUILD = 1
READ_ONLY_COMMANDS = ("status", "context")
COMMANDS = ("draft", "activate", "session", "check", "cycle", "prepare", "resolve", "journal", *READ_ONLY_COMMANDS)
UNRESOLVED = ("prepared", "unknown")
DISPLAY_VERSION = 1
CONTEXT_VERSION = 1
CONTEXT_OPERATIONS = ("entry", "add", "breakeven", "trail", "close", "cancel")
STRATEGY_RULES = ("expiry_rule", "breakeven_rule", "trailing_rule", "addition_rule")
METRIC_FIELDS = (
    "budget", "target", "balance", "equity", "peak", "drawdown", "remaining_risk",
    "adjusted_stop_floor", "account_stop_floor", "policy_cashflows", "goal_cashflows",
    "estimated_goal_gain", "progress_pct", "remaining_target", "remaining_close_costs",
    "existing_risk", "free_margin", "final_net", "final_shortfall",
)
JOURNAL_ACTIVITIES = ("analysis", "wait", "entry", "management", "exit", "blocked")
JOURNAL_TEXT = {"summary": 240, "reason": 2000, "next_step": 500,
                "market_summary": 2000, "risk_summary": 1000, "invalidation": 1000}
ORDER_NUMBERS = ("volume_initial", "volume_remaining", "entry_price", "stop_limit_price",
                 "stop_loss", "take_profit")
ORDER_UNSET = ("stop_limit_price", "stop_loss", "take_profit", "expires_at")
PERIODS = {"M1": 1, "M2": 2, "M3": 3, "M4": 4, "M5": 5, "M6": 6, "M10": 10,
           "M12": 12, "M15": 15, "M20": 20, "M30": 30, "H1": 60, "H2": 120,
           "H3": 180, "H4": 240, "H6": 360, "H8": 480, "H12": 720,
           "D1": 1440, "W1": 10080, "MN1": 43200}
MARKET_STATES = ("open", "closed", "unknown")
SESSION_STATUSES = ("active", "stopped", "interrupted")


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
    if approved_baseline and "observation" not in state:
        previous = state.get("last_snapshot")
        state["observation"] = ({"snapshot_id": previous["id"], "as_of": previous["as_of"],
                                 "received_at": None, "gap_seconds": None, "max_gap_seconds": None,
                                 "max_gap_at": None} if previous else None)
    if not approved_baseline:
        observation = state.get("observation")
        previous = observation if "observation" in state else state.get("last_snapshot")
        if previous is None or stamp(current["as_of"], "as_of") > stamp(previous["as_of"], "previous_as_of"):
            gap = ((stamp(current["as_of"], "as_of") - stamp(observation["as_of"], "previous_as_of")).total_seconds()
                   if observation and observation.get("received_at") is not None else None)
            maximum = observation.get("max_gap_seconds") if observation else None
            maximum_at = observation.get("max_gap_at") if observation else None
            if gap is not None and (maximum is None or gap > maximum):
                maximum, maximum_at = gap, current["as_of"]
            state["observation"] = {"snapshot_id": current["id"], "as_of": current["as_of"],
                                    "received_at": utc(now), "gap_seconds": gap,
                                    "max_gap_seconds": maximum, "max_gap_at": maximum_at}
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


def loop_health(state, now):
    """Derived evidence only: neither an observation nor a process-liveness probe."""
    state = state or {}
    observation = state.get("observation") or {}
    loop = state.get("loop") or {}
    session = state.get("session")
    wake = loop.get("next_wake_at")
    if (session and session["status"] != "active") or (not session and loop.get("status") == "closed"):
        wake = None
    source = (observation.get("as_of") if "observation" in state
              else (state.get("last_snapshot") or {}).get("as_of"))
    result = {"last_observation_at": source,
              "last_observation_received_at": observation.get("received_at"),
              "observation_gap_seconds": observation.get("gap_seconds"),
              "max_observation_gap_seconds": observation.get("max_gap_seconds"),
              "max_observation_gap_at": observation.get("max_gap_at"), "execution": "unverified"}
    for field, when in (("observation_age_seconds", source),
                         ("wake_overdue_seconds", wake)):
        result[field] = None
        if when is not None:
            try:
                age = (now - stamp(when, field)).total_seconds()
                result[field] = max(0.0, age) if field == "wake_overdue_seconds" or age >= 0 else None
            except CheckError:
                pass
    return result


def continuation_view(state, now):
    """Project cached task control without observing or moving a stored deadline."""
    state = state or {}
    session, loop = state.get("session"), state.get("loop")
    continuing = (session["status"] == "active" if session else
                  isinstance(loop, dict) and loop.get("status") in ("active", "closing"))
    return {"session": copy.deepcopy(session), "loop": copy.deepcopy(loop),
            "may_continue": continuing, "loop_health": loop_health(state, now)}


def loop_wake(state, now):
    """Plan deadlines from verified inputs; never wait, extrapolate bars or dispatch."""
    loop = state["loop"]
    loop.update(next_cycle_at=None, next_latch_check_at=None, next_wake_at=None, wake_reason=None)
    session = state.get("session")
    if session and session["status"] != "active":
        return
    if loop.get("status") == "closed":
        if session:
            interval = min(state["mandate"].get("latch_check_seconds") or 300, 300)
            received = (state.get("observation") or {}).get("received_at")
            due = stamp(received, "observation_received_at") + timedelta(seconds=interval) if received else now
            loop.update(next_wake_at=utc(due), wake_reason="monitor")
        return
    if loop.get("status") == "closing":
        loop.update(next_wake_at=utc(now), wake_reason="closure")
        return
    candidates = []
    interval = state["mandate"].get("latch_check_seconds", 0)
    received = (state.get("observation") or {}).get("received_at")
    if interval and received:
        due = stamp(received, "observation_received_at") + timedelta(seconds=interval)
        loop["next_latch_check_at"] = utc(due)
        candidates.append((due, "latch_check"))
    clock = loop.get("clock")
    retry = stamp(loop["market_retry_at"], "market_retry_at") if loop.get("market_retry_at") else now
    if not clock:
        candidates.append((retry, "clock_refresh"))
    elif (clock["symbol"] not in state["mandate"]["symbols"]
          or (now - stamp(clock["as_of"], "clock_as_of")).total_seconds() > state["mandate"]["max_snapshot_age_seconds"]
          or stamp(clock["next_boundary_at"], "next_boundary_at") <= now):
        candidates.append((now, "clock_refresh"))
    else:
        latest = (loop.get("bar_high_water") or {}).get(clock["symbol"], {})
        ready = (latest.get("timeframe") == loop["timeframe"]
                 and latest.get("close_time") == clock["last_boundary_at"])
        due = stamp(clock["next_boundary_at"] if ready else clock["last_boundary_at"], "candle_boundary")
        due += timedelta(seconds=loop.get("buffer_seconds", 5))
        loop["next_cycle_at"] = utc(due)
        if ready or due > now:
            candidates.append((due, "candle"))
        else:
            reason = "market_closed" if loop.get("closed_boundaries", 0) >= 2 else "bar_retry"
            candidates.append((retry, reason))
    due, reason = min(candidates, key=lambda item: item[0])
    loop.update(next_wake_at=utc(due), wake_reason=reason)


def sync_loop(state, result, detail, now):
    """Converge lifecycle after financial/intent work, without creating a loop."""
    session = state.get("session")
    if session:
        result.update(session=copy.deepcopy(session), may_continue=session["status"] == "active")
    loop = state.get("loop")
    if not isinstance(loop, dict):
        return
    previous = {key: loop.get(key) for key in ("status", "end_reason", "ended_at")}
    fresh = result.get("metrics") is not None
    stopped = state.get("loss_latched_at") or state.get("target_latched_at")
    if stopped and (fresh or loop.get("status") != "closed"):
        loop["status"] = "closed" if result["closure_verified"] else "closing"
        loop["end_reason"] = "loss_latch" if state.get("loss_latched_at") else "target_latch"
        loop["ended_at"] = (loop.get("ended_at") or utc(now)) if loop["status"] == "closed" else None
    elif fresh and not stopped:
        loop.update(status="active", end_reason=None, ended_at=None)
    if previous != {key: loop.get(key) for key in previous}:
        detail["previous_loop_lifecycle"] = previous
    if fresh or loop.get("status") == "closing":
        loop_wake(state, now)
    result.update(loop=copy.deepcopy(loop),
                  may_continue=session["status"] == "active" if session else not result.get("closure_verified", False),
                  loop_health=loop_health(state, now))
    detail["loop"] = copy.deepcopy(loop)


def loop_cycle(state, request, now, result):
    """Count unique account observations independently of confirmed candle advances."""
    if state.get("session") and state["session"]["status"] != "active":
        raise CheckError("session_not_active")
    timeframe = state["mandate"].get("entry_timeframe", "M15")
    loop = state.get("loop")
    if not isinstance(loop, dict):
        loop = {"id": "loop-" + str(uuid.uuid4()), "started_at": utc(now), "cycles": 0,
                "policy_id": state["policy"]["id"], "goal_id": state["goal"]["id"],
                "binding_verified_at": state["last_snapshot"]["as_of"], "status": "active",
                "gap_seconds": None, "max_gap_seconds": None, "max_gap_at": None,
                "missing_bars": 0, "end_reason": None, "ended_at": None,
                "timeframe": timeframe, "bar_high_water": {}, "market_state": "unknown"}
        state["loop"] = loop
    if loop.get("status") == "closed" and result["closure_verified"]:
        return
    loop.update(bar_confirmed=False, bar_advanced=False)
    if (loop.get("policy_id") != state["policy"]["id"] or loop.get("goal_id") != state["goal"]["id"]
            or not loop.get("binding_verified_at")):
        raise CheckError("loop_resume_required")
    current = state["last_snapshot"]
    if (loop.get("last_cycle_snapshot_id") == current["id"]
            or (loop.get("last_cycle_as_of") and stamp(current["as_of"], "as_of") <= stamp(loop["last_cycle_as_of"], "last_cycle_as_of"))):
        raise CheckError("duplicate_cycle_snapshot")
    previous = stamp(loop["last_cycle_at"], "last_cycle_at") if loop.get("last_cycle_at") else None
    gap = None if previous is None else max(0.0, (now - previous).total_seconds())
    loop["gap_seconds"] = gap
    if gap is not None and (loop.get("max_gap_seconds") is None or gap > loop["max_gap_seconds"]):
        loop.update(max_gap_seconds=gap, max_gap_at=utc(now))
    loop.update(cycles=int(loop.get("cycles", 0)) + 1, last_cycle_at=utc(now),
                last_cycle_snapshot_id=current["id"], last_cycle_as_of=current["as_of"],
                clock=None, market_state="unknown", market_retry_at=utc(now + timedelta(seconds=15)))
    if "timeframe" in request:
        period_minutes(request["timeframe"])
        if request["timeframe"] != timeframe:
            raise CheckError("timeframe_mismatch")
    buffer_seconds = request.get("buffer_seconds", 5)
    if type(buffer_seconds) is not int or not 3 <= buffer_seconds <= 5:
        raise CheckError("invalid_buffer_seconds")
    loop["buffer_seconds"] = buffer_seconds
    market_state = request.get("market_state", "unknown")
    if market_state not in MARKET_STATES:
        raise CheckError("invalid_market_state")
    loop["market_state"] = market_state
    if market_state != "closed":
        loop.update(closed_boundaries=0, closed_boundary_at=None, closed_next_boundary_at=None)
    clock = request.get("clock")
    if not isinstance(clock, dict):
        raise CheckError("broker_clock_unavailable")
    symbol = text(clock.get("symbol"), "clock_symbol")
    if symbol not in state["mandate"]["symbols"]:
        raise CheckError("unapproved_clock_symbol")
    clock = {key: text(clock.get(key), "clock_" + key)
             for key in ("symbol", "source_ref", "as_of", "last_boundary_at", "next_boundary_at")}
    clock_time = stamp(clock["as_of"], "clock_as_of")
    boundary = stamp(clock["last_boundary_at"], "last_boundary_at")
    following = stamp(clock["next_boundary_at"], "next_boundary_at")
    observed = stamp(current["as_of"], "as_of")
    if (not boundary <= clock_time < following or clock_time > observed or following <= now
            or (now - clock_time).total_seconds() > state["mandate"]["max_snapshot_age_seconds"]):
        raise CheckError("invalid_or_stale_broker_clock")
    clock.update(as_of=utc(clock_time), last_boundary_at=utc(boundary), next_boundary_at=utc(following))
    loop["clock"] = clock
    latest = loop.setdefault("bar_high_water", {}).get(symbol, {})
    if latest and stamp(latest["close_time"], "previous_bar_close") > boundary:
        loop["clock"] = None
        raise CheckError("regressing_broker_clock")
    bar = request.get("bar")
    if bar is not None:
        if not isinstance(bar, dict):
            raise CheckError("invalid_bar")
        opened = stamp(bar.get("open_time"), "bar_open_time")
        if opened > observed:
            raise CheckError("future_bar")
        if type(bar.get("confirmed")) is not bool:
            raise CheckError("invalid_bar_confirmed")
        if not all(bar.get(key) for key in ("symbol", "source_ref", "close_time")):
            raise CheckError("bar_evidence_unavailable")
        closed = stamp(bar["close_time"], "bar_close_time")
        text(bar["source_ref"], "bar_source_ref")
        if bar["symbol"] != symbol or closed <= opened or (bar["confirmed"] and closed > observed):
            raise CheckError("invalid_bar_clock")
        loop.update(bar_symbol=symbol, bar_open_time=utc(opened), bar_close_time=utc(closed))
        settled = observed >= boundary + timedelta(seconds=buffer_seconds)
        if bar["confirmed"] and closed == boundary and settled:
            if latest:
                previous_open = stamp(latest["open_time"], "previous_bar_open")
                previous_close = stamp(latest["close_time"], "previous_bar_close")
                if opened < previous_open or closed < previous_close:
                    raise CheckError("regressing_bar")
                if (opened == previous_open) != (closed == previous_close):
                    raise CheckError("conflicting_bar")
            loop["bar_confirmed"] = True
            if not latest or (opened > previous_open and closed > previous_close):
                loop["bar_high_water"][symbol] = {"timeframe": timeframe, "open_time": utc(opened), "close_time": utc(closed)}
                loop["bar_advanced"] = True
    latest = loop["bar_high_water"].get(symbol, {})
    ready = latest.get("close_time") == clock["last_boundary_at"] and latest.get("timeframe") == timeframe
    if ready:
        loop.update(missing_bars=0, closed_boundaries=0, closed_boundary_at=None,
                    closed_next_boundary_at=None, market_retry_at=None)
    elif observed >= boundary + timedelta(seconds=buffer_seconds):
        if not loop.get("missing_boundary_at") or boundary > stamp(loop["missing_boundary_at"], "missing_boundary_at"):
            loop["missing_bars"] = int(loop.get("missing_bars", 0)) + 1
            loop["missing_boundary_at"] = utc(boundary)
        if market_state == "closed" and loop.get("closed_boundary_at") != utc(boundary):
            consecutive = loop.get("closed_next_boundary_at") == utc(boundary)
            loop.update(closed_boundaries=loop.get("closed_boundaries", 0) + 1 if consecutive else 1,
                        closed_boundary_at=utc(boundary), closed_next_boundary_at=utc(following))
        if market_state == "closed" and loop.get("closed_boundaries", 0) >= 2:
            loop["market_retry_at"] = utc(now + timedelta(minutes=5))


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
    if (state.get("session") and state["session"]["status"] != "active"
            and (result["kind"] == "entry" or value.get("reason") == "management")):
        raise CheckError("session_not_active")
    if result["kind"] == "entry":
        if state["loss_latched_at"] or state["target_latched_at"] or errors or metrics is None:
            raise CheckError("entry_blocked")
        loop = state.get("loop")
        if loop is not None and (not isinstance(loop, dict) or not loop.get("binding_verified_at")
                                 or loop.get("policy_id") != state["policy"]["id"]
                                 or loop.get("goal_id") != state["goal"]["id"]):
            raise CheckError("loop_resume_required")
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
    emergency = result.get("reason") in ("protection_failure", "loss", "target")
    context = value.get("context")
    if context is None:
        if not emergency:
            raise CheckError("missing_action_context")
    else:
        try:
            context = action_context(context)
            display_text(result["id"], "action_id")
            if (result["kind"] == "entry") != (context["operation"] in ("entry", "add")):
                raise CheckError("context_action_kind_mismatch")
            if context["strategy"] and context["strategy"]["timeframe"] != state["mandate"].get("entry_timeframe", "M15"):
                raise CheckError("context_timeframe_mismatch")
            if result.get("reason") == "management" and context["origin_intent_id"] is None:
                raise CheckError("missing_context_origin")
            result["context"] = context
        except CheckError as error:
            if not emergency:
                raise
            # Optional explanation must not delay an otherwise valid emergency reduction.
            result["context_warning"] = str(error)
    return result


def display_text(value, field, limit=200):
    value = text(value, field)
    if len(value) > limit or any((ord(char) < 32 and char not in "\n\t") or ord(char) == 127 for char in value):
        raise CheckError("invalid_" + field)
    return value


def display_reference(value, field):
    value = display_text(value, field)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:#@-]*", value):
        raise CheckError("invalid_" + field)
    return value


def action_context(value):
    """Self-contained decision evidence, separate from exact broker parameters."""
    allowed = {"version", "operation", "rationale", "source_refs", "origin_intent_id", "strategy"}
    if not isinstance(value, dict) or set(value) - allowed or len(encode(value).encode("utf-8")) > 131072:
        raise CheckError("invalid_action_context")
    if type(value.get("version")) is not int or value["version"] != CONTEXT_VERSION:
        raise CheckError("unsupported_context_version")
    operation = value.get("operation")
    if operation not in CONTEXT_OPERATIONS:
        raise CheckError("invalid_context_operation")
    refs = strings(value.get("source_refs"), "context_source_refs")
    if len(refs) > 64:
        raise CheckError("invalid_context_source_refs")
    origin = value.get("origin_intent_id")
    result = {"version": CONTEXT_VERSION, "operation": operation,
              "rationale": display_text(value.get("rationale"), "context_rationale", 2000),
              "source_refs": [display_reference(ref, "context_source_ref") for ref in refs],
              "origin_intent_id": display_text(origin, "context_origin") if origin is not None else None,
              "strategy": None}
    if operation == "entry":
        plan = value.get("strategy")
        fields = {"name", "thesis", "side", "timeframe", "invalidation", *STRATEGY_RULES}
        if origin is not None or not isinstance(plan, dict) or set(plan) != fields:
            raise CheckError("invalid_strategy_fields")
        strategy = {field: display_text(plan.get(field), "strategy_" + field, limit)
                    for field, limit in (("name", 120), ("thesis", 2000), ("invalidation", 1000))}
        if plan.get("side") not in ("buy", "sell") or not isinstance(plan.get("timeframe"), str) or plan["timeframe"] not in PERIODS:
            raise CheckError("invalid_strategy_direction_or_timeframe")
        strategy.update(side=plan["side"], timeframe=plan["timeframe"])
        for field in STRATEGY_RULES:
            strategy[field] = False if plan[field] is False else display_text(plan[field], "strategy_" + field, 1000)
        result["strategy"] = strategy
    elif value.get("strategy") is not None:
        raise CheckError("strategy_only_on_original_entry")
    elif operation in ("add", "breakeven", "trail") and origin is None:
        raise CheckError("missing_context_origin")
    return result


def session_control(connection, state, request, now):
    """Record task control, never approval, an account observation or broker execution."""
    allowed = {"owner_id", "expected_revision", "action", "evidence_ref", "reason"}
    if set(request) - allowed:
        raise CheckError("invalid_session_fields")
    action = request.get("action")
    if action not in ("start", "resume", "stop", "interrupt"):
        raise CheckError("invalid_session_action")
    evidence = display_reference(request.get("evidence_ref"), "session_evidence_ref")
    reason = display_text(request.get("reason"), "session_reason", 500)
    previous = copy.deepcopy(state.get("session"))
    session = copy.deepcopy(previous)
    if action == "start":
        if previous and previous["status"] != "stopped":
            raise CheckError("session_already_started")
        session = {"id": "session-" + str(uuid.uuid4()), "started_at": utc(now), "request_ref": evidence}
    elif action == "resume":
        if not previous or previous["status"] != "interrupted":
            raise CheckError("session_not_interrupted")
    elif action == "interrupt":
        if not previous or previous["status"] != "active":
            raise CheckError("session_not_active")
    elif session is None:
        # A user stop must also fence routine actions on an older, session-less mandate.
        session = {"id": "session-" + str(uuid.uuid4()), "started_at": None, "request_ref": None}
    repeated_stop = action == "stop" and previous and previous["status"] == "stopped" and evidence == previous["evidence_ref"]
    if not repeated_stop:
        replay_error = "new_session_request_required" if action == "start" else "new_session_evidence_required"
        if previous and evidence in (previous.get("request_ref"), previous["evidence_ref"]):
            raise CheckError(replay_error)
        for row in connection.execute("SELECT detail FROM events WHERE command='session'"):
            archived = decode(row[0])
            if not isinstance(archived, dict):
                raise CheckError("invalid_session_history")
            control = archived.get("session")
            if not isinstance(control, dict):
                raise CheckError("invalid_session_history")
            if (evidence in (control.get("request_ref"), control.get("evidence_ref"))
                    or archived.get("session_action") == "stop" and archived.get("authority_ref") == evidence):
                raise CheckError(replay_error)
    session.update(status="stopped" if action == "stop" else "interrupted" if action == "interrupt" else "active",
                   updated_at=utc(now), evidence_ref=evidence, reason=reason)
    state["session"] = session
    loop = state.get("loop")
    if isinstance(loop, dict):
        loop.update(next_cycle_at=None, next_latch_check_at=None, next_wake_at=None, wake_reason=None)
        if session["status"] == "active":
            loop.update(next_wake_at=utc(now), wake_reason="session_check")
    result = {"ok": True, "decision": "session_saved", "may_dispatch": False,
              "may_continue": session["status"] == "active", "session": copy.deepcopy(session),
              "loop": copy.deepcopy(loop), "loop_health": loop_health(state, now)}
    return result, {"session": copy.deepcopy(session), "session_action": action,
                    "authority_ref": state["approval_ref"], "previous_session": previous}


def journal_entry(request, state, now):
    """Validate presentation metadata without observing or changing financial state."""
    allowed = set(JOURNAL_TEXT) | {"owner_id", "expected_revision", "snapshot_id", "as_of",
                                  "activity", "symbols", "source_refs", "intent_id", "pending_order_details"}
    if set(request) - allowed or len(encode(request).encode("utf-8")) > 131072:
        raise CheckError("invalid_journal_fields_or_size")
    current = state.get("last_snapshot")
    if (not current or request.get("snapshot_id") != current["id"]
            or request.get("as_of") != current["as_of"]):
        raise CheckError("journal_snapshot_mismatch")
    if request.get("activity") not in JOURNAL_ACTIVITIES:
        raise CheckError("invalid_journal_activity")
    result = {"version": DISPLAY_VERSION, "account": state["account"],
              "policy_id": state["policy"]["id"], "goal_id": state["goal"]["id"],
              "snapshot_id": current["id"], "as_of": current["as_of"], "recorded_at": utc(now),
              "activity": request["activity"], "intent_id": None}
    for field, limit in JOURNAL_TEXT.items():
        value = request.get(field)
        if field in ("summary", "reason", "next_step") or value is not None:
            result[field] = display_text(value, "journal_" + field, limit)
    for field in ("symbols", "source_refs"):
        values = request.get(field, [])
        if not isinstance(values, list) or len(values) > 64:
            raise CheckError("invalid_journal_" + field)
        normalize = display_reference if field == "source_refs" else display_text
        result[field] = [normalize(value, "journal_" + field) for value in values]
        if len(set(result[field])) != len(values):
            raise CheckError("duplicate_journal_" + field)
    if request.get("intent_id") is not None:
        result["intent_id"] = display_text(request["intent_id"], "journal_intent_id")

    details = request.get("pending_order_details", [])
    if not isinstance(details, list):
        raise CheckError("invalid_pending_order_details")
    orders = current.get("pending_orders")
    known = {}
    if details:
        if not isinstance(orders, list):
            raise CheckError("journal_orders_unavailable")
        for item in orders:
            if not isinstance(item, dict):
                raise CheckError("journal_orders_unavailable")
            ticket = text(item.get("ticket"), "ticket")
            if ticket in known:
                raise CheckError("duplicate_journal_order")
            known[ticket] = item
    result["pending_order_details"] = []
    seen = set()
    allowed_order = set(ORDER_NUMBERS) | {"ticket", "order_type", "side", "volume_unit", "placed_at",
                                         "expires_at", "ownership", "ownership_ref", "unset_fields"}
    for item in details:
        if not isinstance(item, dict) or set(item) - allowed_order:
            raise CheckError("invalid_order_display_fields")
        ticket = display_text(item.get("ticket"), "ticket")
        if ticket in seen or ticket not in known:
            raise CheckError("journal_order_mismatch")
        seen.add(ticket)
        normalized = {"ticket": ticket, "volume_unit": "lots", "ownership": item.get("ownership", "unknown")}
        if item.get("volume_unit", "lots") != "lots":
            raise CheckError("invalid_order_volume_unit")
        if normalized["ownership"] not in ("ace", "manual", "mixed", "unknown"):
            raise CheckError("invalid_order_ownership")
        if normalized["ownership"] != "unknown":
            normalized["ownership_ref"] = display_reference(item.get("ownership_ref"), "ownership_ref")
        if item.get("order_type") is not None:
            normalized["order_type"] = display_text(item["order_type"], "order_type", 64)
        if item.get("side") is not None:
            if item["side"] not in ("buy", "sell"):
                raise CheckError("invalid_order_side")
            normalized["side"] = item["side"]
        for field in ORDER_NUMBERS:
            value = item.get(field)
            if value is not None:
                if not isinstance(value, str):
                    raise CheckError("invalid_order_" + field)
                value = format(money(value, "order_" + field, nonnegative=field.startswith("volume_")), "f")
            normalized[field] = value
        if (normalized["volume_initial"] is not None and normalized["volume_remaining"] is not None
                and Decimal(normalized["volume_remaining"]) > Decimal(normalized["volume_initial"])):
            raise CheckError("invalid_order_remaining_volume")
        for field in ("placed_at", "expires_at"):
            value = item.get(field)
            if value is not None:
                parsed = stamp(value, "order_" + field)
                if field == "placed_at" and parsed > stamp(current["as_of"], "as_of"):
                    raise CheckError("future_order_placement")
            normalized[field] = value
        unset = item.get("unset_fields", [])
        if (not isinstance(unset, list) or any(not isinstance(field, str) or field not in ORDER_UNSET for field in unset)
                or len(set(unset)) != len(unset) or any(normalized.get(field) is not None for field in unset)):
            raise CheckError("invalid_order_unset_fields")
        normalized["unset_fields"] = unset
        result["pending_order_details"].append(normalized)
    return result


def display_event(state, result, detail, now):
    current = state.get("last_snapshot") if result.get("metrics") is not None else None
    return {"version": DISPLAY_VERSION, "account": state["account"],
            "policy_id": state["policy"]["id"] if state.get("policy") else None,
            "goal_id": state["goal"]["id"] if state.get("goal") else None,
            "recorded_at": utc(now), "snapshot_id": current["id"] if current else None,
            "as_of": current["as_of"] if current else None,
            "metrics": {field: result["metrics"].get(field) for field in METRIC_FIELDS} if current else None,
            "decision": result["decision"], "reason_codes": result.get("reason_codes", []),
            "loss_latched_at": state.get("loss_latched_at"), "target_latched_at": state.get("target_latched_at"),
            "closure_verified": result.get("closure_verified", False),
            "required_action": result.get("required_action", "none"), "intent_id": detail.get("intent_id")}


def load_state(connection):
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version not in READABLE_SCHEMA_VERSIONS:
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
    session = state.get("session")
    if session is not None:
        if not isinstance(session, dict) or session.get("status") not in SESSION_STATUSES:
            raise CheckError("invalid_session_state")
        for field in ("id", "evidence_ref"):
            display_reference(session.get(field), "session_" + field)
        display_text(session.get("reason"), "session_reason", 500)
        stamp(session.get("updated_at"), "session_updated_at")
        if session.get("started_at") is not None:
            # Revisions order controls; a wall-clock rollback must not corrupt a user stop.
            stamp(session["started_at"], "session_started_at")
            display_reference(session.get("request_ref"), "session_request_ref")
        elif session["status"] != "stopped" or session.get("request_ref") is not None:
            raise CheckError("invalid_session_state")
    state.setdefault("loop", None)
    return row[0], state


def save_state(connection, revision, state, command, detail, now):
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        previous = connection.execute("SELECT payload FROM state WHERE id = 1").fetchone()
        detail = dict(detail, migration={"from_version": version, "to_version": SCHEMA_VERSION,
                                        "legacy_loop": decode(previous[0], exact_numbers=False).get("loop") if previous else None})
    serialized = encode(state)
    connection.execute("INSERT INTO state VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision, payload=excluded.payload",
                       (revision, serialized))
    connection.execute("INSERT INTO events(at, command, detail, state_sha256) VALUES (?, ?, ?, ?)",
                       (utc(now), command, encode(detail), hashlib.sha256(serialized.encode("utf-8")).hexdigest()))
    connection.execute("PRAGMA user_version = " + str(SCHEMA_VERSION))


def pending(connection):
    return connection.execute("SELECT id, payload, status, outcome FROM intents WHERE status IN ('prepared', 'unknown') ORDER BY id").fetchall()


def context_page(connection, state, *, before=None, limit=20, origin_intent_id=None):
    """Bounded private recovery records; callers must sanitize them for display."""
    maximum = 9223372036854775807
    if before is not None and (type(before) is not int or not 0 < before <= maximum):
        raise CheckError("invalid_context_cursor")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise CheckError("invalid_context_limit")
    if origin_intent_id is not None:
        display_text(origin_intent_id, "context_origin")
    page = {"items": [], "next_cursor": None, "origin": None}
    if not state or not state.get("policy") or not state.get("goal"):
        return page
    paths = ("account.login", "account.server", "account.type", "account.currency", "policy_id", "goal_id")
    binding = tuple(state["account"][key] for key in ("login", "server", "type", "currency")) + (state["policy"]["id"], state["goal"]["id"])

    def scope(column, prefix=""):
        checks = " AND ".join("json_extract(" + column + ", '$." + prefix + path + "') = ?" for path in paths)
        return "CASE WHEN json_valid(" + column + ") THEN " + checks + " ELSE 0 END"

    def record(row):
        return {"id": row[0], "action": decode(row[1], exact_numbers=False), "status": row[2],
                "outcome": decode(row[3], exact_numbers=False) if row[3] else None}

    roots = "CASE WHEN json_valid(payload) THEN json_extract(payload, '$.kind') = 'entry' AND json_extract(payload, '$.context.origin_intent_id') IS NULL ELSE 0 END"
    related = "(id = ? OR CASE WHEN json_valid(payload) THEN json_extract(payload, '$.context.origin_intent_id') = ? ELSE 0 END)"
    selected, selection = roots, ()
    if origin_intent_id is not None:
        row = connection.execute("SELECT id, payload, status, outcome FROM intents WHERE " + scope("payload") + " AND " + roots + " AND id = ?",
                                 (*binding, origin_intent_id)).fetchone()
        if row is None:
            raise CheckError("context_origin_not_found")
        page["origin"] = record(row)
        selected, selection = related, (origin_intent_id, origin_intent_id)
    rows = connection.execute("SELECT rowid, id, payload, status, outcome FROM intents WHERE " + scope("payload") + " AND " + selected + " AND rowid < ? ORDER BY rowid DESC LIMIT ?",
                              (*binding, *selection, before if before is not None else maximum, limit + 1)).fetchall()
    if len(rows) > limit:
        page["next_cursor"] = rows[limit - 1][0]
    for row in rows[:limit]:
        intent = record(row[1:])
        relation, refs = (related, (intent["id"], intent["id"])) if origin_intent_id is None else ("id = ?", (intent["id"],))
        latest = connection.execute("SELECT id, payload, status, outcome FROM intents WHERE " + scope("payload") + " AND " + relation + " ORDER BY rowid DESC LIMIT 1",
                                    (*binding, *refs)).fetchone()
        journal = connection.execute("SELECT detail FROM events WHERE command = 'journal' AND " + scope("detail", "journal.") +
                                     " AND CASE WHEN json_valid(detail) THEN json_extract(detail, '$.journal.intent_id') IN (SELECT id FROM intents WHERE " + scope("payload") + " AND " + relation + ") ELSE 0 END ORDER BY id DESC LIMIT 1",
                                     (*binding, *binding, *refs)).fetchone()
        page["items"].append({"intent": intent, "latest_action": record(latest),
                              "latest_journal": decode(journal[0], exact_numbers=False).get("journal") if journal else None})
    return page


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
    approval_mode = request.get("approval_mode", state.get("approval_mode", "reviewed") if mode == "resume" else "reviewed")
    if approval_mode not in ("reviewed", "start_request"):
        raise CheckError("invalid_approval_mode")
    if mode == "resume" and approval_mode != state.get("approval_mode", "reviewed"):
        raise CheckError("resume_cannot_change_approval_mode")
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
        baseline_at = stamp(request["baseline"].get("as_of"), "baseline_as_of")
        if approval_mode == "reviewed" and baseline_at > approved_at:
            raise CheckError("baseline_not_in_approval")
        if approval_mode == "start_request" and baseline_at < approved_at:
            raise CheckError("baseline_predates_start_request")
        if replacement:
            state["last_snapshot"] = None
            state["history_anchor"] = request["baseline"].get("as_of")
        baseline_time = now if approval_mode == "start_request" else approved_at
        baseline = snapshot(request["baseline"], state, baseline_time, approved_baseline=approval_mode == "reviewed")
        if money(baseline["equity"], "equity") <= 0:
            raise CheckError("nonpositive_baseline")
        total = sum((money(f["amount"], "cashflow") for f in baseline["cashflows"]), Decimal(0))
        if replacement:
            if baseline["cashflows"]:
                raise CheckError("new_policy_requires_new_cashflow_boundary")
            state["policy"] = {"id": str(uuid.uuid4()), "budget": format(budget, "f"),
                               "started_at": baseline["as_of"], "start_equity": baseline["equity"],
                                "cashflow_anchor": format(total, "f"), "approval_ref": approval_ref,
                                "approved_at": request["approved_at"], "approval_mode": approval_mode}
            state["peak"] = baseline["equity"]
            state["loss_latched_at"] = None
            state["history_start_cursor"] = baseline["history_cursor"]
        else:
            observe(state, baseline, baseline_time, approved_baseline=True)
            if state["loss_latched_at"]:
                raise CheckError("loss_requires_replacement_policy")
        state["goal"] = {"id": str(uuid.uuid4()), "target": format(target, "f"),
                         "started_at": baseline["as_of"], "start_equity": baseline["equity"],
                          "cashflow_anchor": format(total, "f"), "approval_ref": approval_ref,
                          "approved_at": request["approved_at"], "approval_mode": approval_mode}
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
    state["approval_mode"] = approval_mode
    state["owner_id"] = request["owner_id"]
    loop = state.get("loop")
    if mode in ("start", "new_goal", "replace_policy"):
        state["loop"] = None
        if mode == "start":
            # The approved baseline is not an earlier live observation.
            state["observation"] = None
    elif isinstance(loop, dict):
        if any(loop.get(key) is not None and loop[key] != state[field]["id"]
               for key, field in (("policy_id", "policy"), ("goal_id", "goal"))):
            raise CheckError("loop_mandate_mismatch")
        if mode == "resume" and not loop.get("binding_verified_at"):
            loop.update(policy_id=state["policy"]["id"], goal_id=state["goal"]["id"],
                        binding_verified_at=current["as_of"], bar_high_water={}, clock=None,
                        bar_confirmed=False, bar_advanced=False,
                        last_cycle_snapshot_id=(previous.get("last_snapshot") or {}).get("id"),
                        last_cycle_as_of=(previous.get("last_snapshot") or {}).get("as_of"))
        timeframe = config.get("entry_timeframe", "M15")
        if loop.get("timeframe") != timeframe:
            loop.update(timeframe=timeframe, clock=None, bar_high_water={}, bar_open_time=None,
                        bar_close_time=None, bar_symbol=None, bar_confirmed=False, bar_advanced=False,
                        missing_bars=0, missing_boundary_at=None, closed_boundaries=0,
                        closed_boundary_at=None, closed_next_boundary_at=None, market_retry_at=None)
        if set(previous["mandate"]["symbols"]) != set(config["symbols"]):
            loop["bar_high_water"] = {symbol: value for symbol, value in loop.get("bar_high_water", {}).items()
                                      if symbol in config["symbols"]}
            loop.update(clock=None, market_state="unknown", market_retry_at=None,
                        missing_bars=0, missing_boundary_at=None, closed_boundaries=0,
                        closed_boundary_at=None, closed_next_boundary_at=None,
                        bar_confirmed=False, bar_advanced=False)
            if loop.get("bar_symbol") not in config["symbols"]:
                loop.update(bar_symbol=None, bar_open_time=None, bar_close_time=None)
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
                  **continuation_view(state, now),
                 "outstanding_intents": [{"id": row[0], "action": decode(row[1], exact_numbers=False),
                                          "status": row[2], "outcome": decode(row[3], exact_numbers=False) if row[3] else None}
                                         for row in pending(connection)]}
    if command == "context":
        if set(request) - {"before", "limit", "origin_intent_id"}:
            raise CheckError("invalid_context_request_fields")
        return {"ok": True, "decision": "cached" if state else "unconfigured", "may_dispatch": False,
                "revision": revision, "account": state["account"] if state else None,
                "policy_id": state["policy"]["id"] if state and state.get("policy") else None,
                "goal_id": state["goal"]["id"] if state and state.get("goal") else None,
                "context": context_page(connection, state, **request), **continuation_view(state, now)}
    if type(request.get("expected_revision")) is not int or request["expected_revision"] != revision:
        raise CheckError("revision_mismatch")
    owner = text(request.get("owner_id"), "owner_id")
    if state and owner != state["owner_id"] and command != "activate":
        raise CheckError("owner_mismatch")
    if command == "session":
        if not state or not state.get("policy") or not state.get("goal"):
            raise CheckError("setup_incomplete")
        result, detail = session_control(connection, state, request, now)
        detail["display"] = display_event(state, result, detail, now)
        save_state(connection, revision + 1, state, command, detail, now)
        result.update(revision=revision + 1, policy_id=state["policy"]["id"], goal_id=state["goal"]["id"])
        return result
    if command == "journal":
        if not state or not state.get("policy") or not state.get("goal"):
            raise CheckError("setup_incomplete")
        entry = journal_entry(request, state, now)
        if entry["intent_id"] is not None:
            row = connection.execute("SELECT payload FROM intents WHERE id = ?", (entry["intent_id"],)).fetchone()
            intent = decode(row[0], exact_numbers=False) if row else {}
            if any(intent.get(key) != entry[key] for key in ("account", "policy_id", "goal_id")):
                raise CheckError("journal_intent_mismatch")
        state["last_journal"] = entry
        save_state(connection, revision + 1, state, command, {"journal": entry}, now)
        return {"ok": True, "decision": "journal_saved", "may_dispatch": False, "revision": revision + 1,
                "policy_id": entry["policy_id"], "goal_id": entry["goal_id"], **continuation_view(state, now)}
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
                        baseline_time = now if request.get("approval_mode") == "start_request" else min(stamp(request.get("approved_at"), "approved_at"), now)
                        observe(state, request["baseline"], baseline_time,
                                approved_baseline=request.get("approval_mode", "reviewed") == "reviewed")
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
                    origin_id = (proposed.get("context") or {}).get("origin_intent_id")
                    if origin_id is not None:
                        try:
                            row = connection.execute("SELECT status, payload FROM intents WHERE id = ?", (origin_id,)).fetchone()
                            origin = decode(row[1], exact_numbers=False) if row else {}
                            if (not isinstance(origin, dict) or origin.get("kind") != "entry" or origin.get("id") != origin_id
                                    or origin.get("account") != state["account"]
                                    or any(origin.get(key + "_id") != state[key]["id"] for key in ("policy", "goal"))):
                                raise CheckError("context_origin_mismatch")
                            original_context = action_context(origin.get("context"))
                            if original_context["operation"] != "entry" or row[0] != "completed":
                                raise CheckError("context_origin_not_settled_entry")
                            if proposed["kind"] == "entry" and proposed["symbol"] != origin.get("symbol"):
                                raise CheckError("context_origin_symbol_mismatch")
                        except CheckError as error:
                            if proposed.get("reason") not in ("protection_failure", "loss", "target"):
                                raise
                            proposed.pop("context", None)
                            proposed["context_warning"] = str(error)
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
                    if proposed.get("context_warning"):
                        result["reason_codes"] = sorted(set(result["reason_codes"] + ["action_context_unavailable"]))
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
                    loop_cycle(state, request, now, result)
                elif command != "check":
                    raise CheckError("unknown_command")
            except CheckError as error:
                # Commit a valid observed breach even when its proposed order is rejected.
                errors.append(str(error))
                result = report(state, metrics, errors, len(pending(connection)))
                if command == "cycle":
                    result.update(loop=state.get("loop"),
                                   may_continue=not result["closure_verified"])
                detail["reason_codes"] = errors
        sync_loop(state, result, detail, now)
    state["last_result"] = {key: value for key, value in result.items() if key not in ("intent", "may_dispatch")}
    detail["display"] = display_event(state, result, detail, now)
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
    if not existed and command in READ_ONLY_COMMANDS:
        result = {"ok": True, "decision": "unconfigured", "may_dispatch": False,
                  "revision": 0, **continuation_view(None, now)}
        if command == "status":
            return dict(result, state=None, outstanding_intents=[])
        if set(request) - {"before", "limit", "origin_intent_id"}:
            raise CheckError("invalid_context_request_fields")
        return dict(result, account=None, policy_id=None, goal_id=None, context=context_page(None, None, **request))
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
    mode = "ro" if command in READ_ONLY_COMMANDS else "rwc" if create else "rw"
    connection = None
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=" + mode, uri=True, timeout=1)
        connection.execute("BEGIN" if command in READ_ONLY_COMMANDS else "BEGIN IMMEDIATE")
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
    parser.add_argument("--input", type=Path, help="Private JSON mutation request; status/context do not read stdin")
    parser.add_argument("--before", type=int, help="context only: earlier intent-row cursor")
    parser.add_argument("--limit", type=int, help="context only: page size from 1 to 100 (default 20)")
    parser.add_argument("--origin-intent-id", help="context only: original entry whose actions should be read")
    args = parser.parse_args(argv)
    options = {key: value for key, value in {"before": args.before, "limit": args.limit,
                                            "origin_intent_id": args.origin_intent_id}.items() if value is not None}
    if (options and args.command != "context") or (args.command == "context" and args.input is not None):
        parser.error("context uses --before, --limit and --origin-intent-id, not --input")
    try:
        request = options if args.command in READ_ONLY_COMMANDS else decode(args.input.read_text(encoding="utf-8-sig") if args.input else sys.stdin.read())
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
