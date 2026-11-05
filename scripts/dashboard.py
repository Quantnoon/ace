"""Loopback-only, read-only viewer of Ace's saved observations. Never contacts MT5."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import errno
import hashlib
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import math
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
from urllib.parse import parse_qs, urlsplit

if __package__:
    from . import account_check as checker
else:
    import account_check as checker


ROOT = Path(__file__).resolve().parents[1]
PAGE_SIZE = 100
ASSETS = {
    "/": (ROOT / "ui" / "index.html", "text/html; charset=utf-8"),
    "/dashboard.css": (ROOT / "ui" / "dashboard.css", "text/css; charset=utf-8"),
    "/dashboard.mjs": (ROOT / "ui" / "dashboard.mjs", "text/javascript; charset=utf-8"),
    "/assets/logo.png": (ROOT / "assets" / "logo.png", "image/png"),
}
DECISIONS = ("draft", "draft_saved", "prepared", "within_budget", "blocked",
             "reconciliation_required", "loss_stop", "target_stop")


def decimal_text(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 160 or not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise checker.CheckError("invalid_saved_number")
    number = Decimal(value)
    if not number.is_finite():
        raise checker.CheckError("invalid_saved_number")
    return format(number, "f")


def timestamp(value):
    if value is not None:
        checker.stamp(value, "saved_timestamp")
    return value


def string_list(value):
    if not isinstance(value, list):
        raise checker.CheckError("invalid_saved_list")
    return [checker.display_text(item, "saved_text") for item in value]


def metric_values(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise checker.CheckError("invalid_saved_metrics")
    return {field: decimal_text(value.get(field)) for field in checker.METRIC_FIELDS}


def matches_scope(value, state):
    return (isinstance(value, dict) and value.get("account") == state["account"]
            and value.get("policy_id") == (state.get("policy") or {}).get("id")
            and value.get("goal_id") == (state.get("goal") or {}).get("id"))


def journal_summary(value, state, warnings):
    if value is None:
        return None
    try:
        if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != checker.DISPLAY_VERSION:
            raise checker.CheckError("unsupported_display_version")
        if not matches_scope(value, state):
            return None
        if value.get("activity") not in checker.JOURNAL_ACTIVITIES:
            raise checker.CheckError("invalid_journal_activity")
        result = {field: value[field] for field in ("version", "activity", "policy_id", "goal_id")}
        for field, limit in checker.JOURNAL_TEXT.items():
            if field in ("summary", "reason", "next_step") or value.get(field) is not None:
                result[field] = checker.display_text(value.get(field), "journal_" + field, limit)
        for field in ("as_of", "recorded_at"):
            if not value.get(field):
                raise checker.CheckError("missing_journal_time")
            result[field] = timestamp(value[field])
        result["snapshot_id"] = checker.display_text(value.get("snapshot_id"), "snapshot_id")
        result["intent_id"] = checker.display_text(value["intent_id"], "intent_id") if value.get("intent_id") else None
        result["symbols"] = string_list(value.get("symbols", []))
        result["source_refs"] = [checker.display_reference(item, "source_ref") for item in string_list(value.get("source_refs", []))]
        if len(result["symbols"]) > 64 or len(result["source_refs"]) > 64:
            raise checker.CheckError("invalid_journal_list")
        return result
    except (checker.CheckError, KeyError, TypeError):
        warnings.add("Some decision reporting is unavailable or uses an unsupported format.")
        return None


def intent_view(row, state, warnings):
    try:
        value = checker.decode(row[1], exact_numbers=False)
        if not matches_scope(value, state):
            return None
        if row[2] not in (*checker.UNRESOLVED, "completed", "not_executed") or value.get("kind") not in ("entry", "reduce"):
            raise checker.CheckError("invalid_intent_status")
        outcome = checker.decode(row[3], exact_numbers=False) if row[3] else None
        if outcome is not None:
            if not isinstance(outcome, dict) or outcome.get("outcome") not in ("completed", "not_executed", "unknown"):
                raise checker.CheckError("invalid_intent_outcome")
            outcome = {"outcome": outcome["outcome"], "at": timestamp(outcome.get("at")),
                       "snapshot_at": timestamp(outcome.get("snapshot_at")),
                       "broker_tickets": string_list(outcome.get("broker_tickets", []))}
        return {"id": checker.display_text(row[0], "intent_id"), "kind": value["kind"], "status": row[2],
                "symbol": checker.display_text(value["symbol"], "symbol") if value.get("symbol") else None,
                "tickets": string_list(value.get("tickets", [])), "risk": decimal_text(value.get("risk")),
                "created_at": timestamp(value.get("created_at")), "snapshot_at": timestamp(value.get("snapshot_at")),
                "outcome": outcome}
    except (checker.CheckError, TypeError, KeyError, InvalidOperation):
        warnings.add("Some action details are unavailable; no execution outcome is assumed.")
        return None


def pending_view(state, note, warnings):
    current = state.get("last_snapshot") or {}
    orders = current.get("pending_orders")
    if not isinstance(orders, list):
        return None
    enrichment = {}
    if (note and note["snapshot_id"] == current.get("id") and note["as_of"] == current.get("as_of")):
        try:
            saved = state["last_journal"]
            fields = set(checker.JOURNAL_TEXT) | {"snapshot_id", "as_of", "activity", "symbols", "source_refs", "intent_id", "pending_order_details"}
            request = {field: saved[field] for field in fields if field in saved}
            checked = checker.journal_entry(request, state, checker.stamp(note["recorded_at"], "recorded_at"))
            enrichment = {item["ticket"]: item for item in checked["pending_order_details"]}
        except (checker.CheckError, ValueError, KeyError, TypeError):
            warnings.add("Pending-order details are unavailable; canonical orders are still shown.")
    result, seen = [], set()
    try:
        for order in orders:
            if not isinstance(order, dict):
                raise checker.CheckError("invalid_saved_order")
            ticket = checker.display_text(order.get("ticket"), "ticket")
            if ticket in seen:
                raise checker.CheckError("duplicate_saved_order")
            seen.add(ticket)
            details = enrichment.get(ticket)
            if details:
                keys = (*checker.ORDER_NUMBERS, "order_type", "side", "volume_unit", "placed_at", "expires_at", "ownership", "unset_fields")
                details = {key: details.get(key) for key in keys}
            kind = order.get("kind") if order.get("kind") in ("entry", "protective") else None
            risk = None
            try:
                value = order.get("risk")
                if value is not None:
                    risk = format(checker.money(value, "order_risk", nonnegative=True), "f")
            except checker.CheckError:
                warnings.add("Some saved order risk is unverified or unavailable.")
            result.append({"ticket": ticket, "symbol": checker.display_text(order.get("symbol"), "symbol"),
                           "kind": kind, "protected": order.get("protected") if type(order.get("protected")) is bool else None,
                           "risk": risk, "position_ticket": checker.display_text(order["position_ticket"], "position_ticket") if order.get("position_ticket") else None,
                           "details": details})
        return result
    except (checker.CheckError, TypeError):
        warnings.add("The saved pending-order list is inconsistent; its count is unavailable.")
        return None


def progress_view(points, state, before, next_cursor, warnings, failures=()):
    current = state.get("last_snapshot")
    if not points and before is None and current and state.get("last_metrics"):
        metrics = metric_values(state["last_metrics"])
        if state.get("goal"):
            points.append({"event_id": None, "snapshot_id": current["id"], "as_of": current["as_of"],
                           "gain": metrics["estimated_goal_gain"], "pct": metrics["progress_pct"],
                           "target": metrics["target"], "legacy": True})
            warnings.add("Only a cached progress point is available in this window; missing history is not reconstructed.")
    unique = {}
    for point in points:
        unique.setdefault((point["snapshot_id"], point["as_of"]), point)
    points = sorted(unique.values(), key=lambda item: checker.stamp(item["as_of"], "as_of"))
    with localcontext() as context:
        context.prec = 64
        values = [Decimal(0), Decimal(100)] + [Decimal(point["pct"]) for point in points if point["pct"] is not None]
        low, high = min(values), max(values)
        padding = (high - low) / 10
        low, high = low - padding, high + padding
        span = high - low
        first = checker.stamp(points[0]["as_of"], "as_of") if points else None
        last = checker.stamp(points[-1]["as_of"], "as_of") if points else None
        seconds = (last - first).total_seconds() if first else 0
        max_age = (state.get("mandate") or {}).get("max_snapshot_age_seconds")
        previous, previous_id = None, None
        for point in points:
            at = checker.stamp(point["as_of"], "as_of")
            point["x"] = (at - first).total_seconds() / seconds if seconds else 0.5
            point["y"] = float((high - Decimal(point["pct"])) / span) if point["pct"] is not None else None
            failed_between = previous_id is not None and point["event_id"] is not None and any(previous_id < event_id < point["event_id"] for event_id in failures)
            point["gap_before"] = bool(previous and (type(max_age) is not int or (at - previous).total_seconds() > max_age or failed_between))
            previous, previous_id = at, point["event_id"]
        return {"points": points, "target_y": float((high - 100) / span), "zero_y": float(high / span),
                "min_pct": format(low, "f"), "max_pct": format(high, "f"),
                "incomplete": bool(next_cursor or any(point["legacy"] or point["pct"] is None or point["gap_before"] for point in points)),
                "from": points[0]["as_of"] if points else None, "to": points[-1]["as_of"] if points else None,
                "next_cursor": next_cursor}


def empty_dashboard(now):
    return {"ok": True, "api_version": 1, "status": "unconfigured", "generated_at": checker.utc(now), "revision": 0,
            "account": None, "scope": None, "snapshot": None, "policy": None, "goal": None, "draft": None,
            "metrics": None, "result": None, "loop": None, "latest_journal": None, "pending_orders": None,
            "stops": {"loss_latched_at": None, "target_latched_at": None, "target_trigger_gain": None, "closure_verified": False},
            "exposure": {"positions_count": None, "orders_count": None, "entry_orders_count": None, "protective_orders_count": None},
            "unresolved_intents": {"count": 0, "items": []}, "activity": {"items": [], "next_cursor": None},
            "progress": progress_view([], {}, None, None, set()), "warnings": []}


def read_dashboard(db_path=checker.DEFAULT_DB, *, before=None, now=None):
    """Take one bounded, consistent read; release SQLite before rendering or HTTP IO."""
    if before is not None and (type(before) is not int or not 0 < before <= 9223372036854775807):
        raise checker.CheckError("invalid_cursor")
    now = now or datetime.now(timezone.utc)
    response = empty_dashboard(now)
    path = Path(db_path).resolve()
    if not path.exists():
        return response
    connection = None
    warnings = set()
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
        connection.execute("BEGIN")
        revision, state = checker.load_state(connection)
        if state is None:
            return response
        rows = connection.execute("SELECT id, at, command, detail FROM events WHERE id < ? ORDER BY id DESC LIMIT ?",
                                  (before if before is not None else 9223372036854775807, PAGE_SIZE + 1)).fetchall()
        next_cursor = rows[PAGE_SIZE - 1][0] if len(rows) > PAGE_SIZE else None
        events, ids = [], set()
        for row in rows[:PAGE_SIZE]:
            try:
                detail = checker.decode(row[3], exact_numbers=False)
                if not isinstance(detail, dict):
                    raise checker.CheckError("invalid_event")
                events.append((row[0], row[1], row[2], detail))
                reference = detail.get("intent_id") or (detail.get("journal") or {}).get("intent_id")
                if isinstance(reference, str):
                    ids.add(reference)
            except (checker.CheckError, TypeError, AttributeError):
                warnings.add("Some recorded activity is unavailable.")
        count = connection.execute("SELECT count(*) FROM intents WHERE status IN ('prepared','unknown')").fetchone()[0]
        unresolved = connection.execute("SELECT id, payload, status, outcome FROM intents WHERE status IN ('prepared','unknown') ORDER BY id LIMIT ?", (PAGE_SIZE,)).fetchall()
        linked = connection.execute("SELECT id, payload, status, outcome FROM intents WHERE id IN (" + ",".join("?" for _ in ids) + ")", tuple(ids)).fetchall() if ids else []
        connection.commit()
    except sqlite3.Error:
        raise checker.CheckError("database_unavailable_or_corrupt") from None
    finally:
        if connection is not None:
            connection.close()

    try:
        response["revision"] = revision
        response["account"] = checker.account(state["account"])
        policy, goal = state.get("policy"), state.get("goal")
        response["status"] = "configured" if policy and goal else "draft"
        response["scope"] = {"policy_id": policy["id"] if policy else None, "goal_id": goal["id"] if goal else None}
        if policy:
            response["policy"] = {"id": checker.text(policy["id"], "policy_id"), "budget": decimal_text(policy["budget"]), "started_at": timestamp(policy["started_at"])}
        if goal:
            response["goal"] = {"id": checker.text(goal["id"], "goal_id"), "target": decimal_text(goal["target"]),
                                "start_equity": decimal_text(goal["start_equity"]), "started_at": timestamp(goal["started_at"]),
                                "approved_at": timestamp(goal["approved_at"])}
        response["draft"] = {field: decimal_text(state.get("draft", {}).get(field)) for field in ("budget", "target")}
        response["metrics"] = metric_values(state.get("last_metrics"))
        current = state.get("last_snapshot")
        if current:
            as_of = timestamp(current["as_of"])
            age = (now - checker.stamp(as_of, "as_of")).total_seconds()
            max_age = (state.get("mandate") or {}).get("max_snapshot_age_seconds")
            freshness = "future" if age < 0 else "unavailable" if type(max_age) is not int or max_age <= 0 else "stale" if age > max_age else "fresh"
            response["snapshot"] = {"id": checker.text(current["id"], "snapshot_id"), "as_of": as_of,
                                    "max_age_seconds": max_age, "freshness": freshness, "age_seconds": age}
            positions = current.get("positions")
            if isinstance(positions, list):
                tickets = [item.get("ticket") for item in positions if isinstance(item, dict)]
                if len(tickets) == len(positions) and all(isinstance(ticket, str) and ticket for ticket in tickets) and len(set(tickets)) == len(tickets):
                    response["exposure"]["positions_count"] = len(positions)
        raw_result = state.get("last_result") or {}
        response["result"] = {"decision": raw_result.get("decision") if raw_result.get("decision") in DECISIONS else None,
                              "reason_codes": string_list(raw_result.get("reason_codes", [])),
                              "closure_verified": raw_result.get("closure_verified") is True,
                              "required_action": raw_result.get("required_action") if raw_result.get("required_action") in ("none", "remain_stopped", "cancel_entries_and_close_all") else None,
                              "last_verified_at": timestamp(raw_result.get("last_verified_at"))}
        closure = response["result"]["closure_verified"]
        # A later unapproved draft replaces last_result, but not a recorded final settlement.
        if "closure_verified" not in raw_result and response["metrics"] and current:
            closure = bool(response["metrics"]["final_net"] is not None and current.get("positions") == []
                           and current.get("pending_orders") == [] and current.get("costs_final") is True
                           and response["metrics"]["remaining_close_costs"] is not None
                           and Decimal(response["metrics"]["remaining_close_costs"]) == 0 and count == 0)
        response["stops"] = {"loss_latched_at": timestamp(state.get("loss_latched_at")),
                             "target_latched_at": timestamp(state.get("target_latched_at")),
                             "target_trigger_gain": decimal_text(state.get("target_trigger_gain")), "closure_verified": closure}
        loop = state.get("loop")
        if isinstance(loop, dict):
            gap = loop.get("max_gap_seconds")
            response["loop"] = {"id": checker.display_text(loop.get("id"), "loop_id"),
                                "status": loop.get("status") if loop.get("status") in ("active", "closing", "closed") else None,
                                "cycles": loop.get("cycles") if type(loop.get("cycles")) is int else None,
                                "timeframe": loop.get("timeframe") if loop.get("timeframe") in checker.PERIODS else None,
                                "last_cycle_at": timestamp(loop.get("last_cycle_at")), "next_cycle_at": timestamp(loop.get("next_cycle_at")),
                                "max_gap_seconds": gap if type(gap) in (int, float) and math.isfinite(gap) and gap >= 0 else None,
                                "end_reason": loop.get("end_reason") if loop.get("end_reason") in ("loss_latch", "target_latch") else None}
        response["latest_journal"] = journal_summary(state.get("last_journal"), state, warnings)
        response["pending_orders"] = pending_view(state, response["latest_journal"], warnings)
        orders = response["pending_orders"]
        if orders is not None:
            response["exposure"].update(orders_count=len(orders),
                                       entry_orders_count=sum(item["kind"] == "entry" for item in orders) if all(item["kind"] for item in orders) else None,
                                       protective_orders_count=sum(item["kind"] == "protective" for item in orders) if all(item["kind"] for item in orders) else None)
        intents = {row[0]: intent_view(row, state, warnings) for row in linked + unresolved}
        response["unresolved_intents"] = {"count": count, "items": [intents[row[0]] for row in unresolved if intents.get(row[0])]}
        if len(response["unresolved_intents"]["items"]) != count:
            warnings.add("Unresolved action details are limited or unavailable; the total count still includes them.")
        activity, points, failures = [], [], []
        for event_id, at, command, detail in events:
            try:
                journal = journal_summary(detail.get("journal"), state, warnings)
                display = detail.get("display")
                intent = intents.get(detail.get("intent_id") or (journal or {}).get("intent_id"))
                if display is not None:
                    if not isinstance(display, dict) or type(display.get("version")) is not int or display["version"] != checker.DISPLAY_VERSION:
                        warnings.add("Some activity uses an unsupported display format.")
                        continue
                    if not matches_scope(display, state):
                        continue
                elif not journal and not intent:
                    continue
                sample = detail.get("snapshot") or {}
                source_at = timestamp(display.get("as_of")) if display else journal["as_of"] if journal else timestamp(sample.get("as_of"))
                activity.append({"id": event_id, "command": command, "at": timestamp(at), "snapshot_at": source_at,
                                 "decision": display.get("decision") if display and display.get("decision") in DECISIONS else None,
                                 "reason_codes": string_list(display.get("reason_codes", [])) if display else [],
                                 "closure_verified": bool(display and display.get("closure_verified") is True),
                                 "journal": journal, "intent": intent})
                if display and display.get("metrics") is not None and source_at:
                    metrics = metric_values(display["metrics"])
                    points.append({"event_id": event_id, "snapshot_id": checker.text(display.get("snapshot_id"), "snapshot_id"),
                                   "as_of": source_at, "gain": metrics["estimated_goal_gain"], "pct": metrics["progress_pct"],
                                   "target": metrics["target"], "legacy": False})
                elif display and command in ("activate", "check", "cycle", "prepare", "resolve"):
                    failures.append(event_id)
            except (checker.CheckError, KeyError, TypeError, AttributeError, InvalidOperation):
                warnings.add("Some recorded activity or progress is unavailable.")
        response["activity"] = {"items": activity, "next_cursor": next_cursor}
        response["progress"] = progress_view(points, state, before, next_cursor, warnings, failures)
        response["warnings"] = sorted(warnings)
        return response
    except (TypeError, KeyError, AttributeError, InvalidOperation, OverflowError):
        raise checker.CheckError("invalid_account_state") from None


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "AceDashboard"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, _format, *args):
        pass

    def send_body(self, status, body, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        if status == 405:
            self.send_header("Allow", "GET, HEAD")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass

    def send_json(self, status, value):
        self.send_body(status, checker.encode(value).encode("utf-8"))

    def allowed_origin(self):
        hosts = self.headers.get_all("Host", [])
        origins = self.headers.get_all("Origin", [])
        allowed = {"127.0.0.1:" + str(self.server.server_port), "localhost:" + str(self.server.server_port)}
        if len(hosts) != 1 or hosts[0].lower() not in allowed or len(origins) > 1 or (origins and origins[0] not in {"http://" + host for host in allowed}):
            self.send_json(403, {"ok": False, "error": "origin_not_allowed"})
            return False
        return True

    def do_GET(self):
        if not self.allowed_origin():
            return
        try:
            url = urlsplit(self.path)
            if url.scheme or url.netloc or url.fragment:
                raise ValueError
            query = parse_qs(url.query, keep_blank_values=True, strict_parsing=True, max_num_fields=1)
            if url.path == "/api/health" and not query:
                self.send_json(200, self.server.identity)
            elif url.path == "/api/dashboard":
                if set(query) - {"before"}:
                    raise ValueError
                before = None
                if query:
                    raw = query["before"][0]
                    if not re.fullmatch(r"[1-9][0-9]{0,18}", raw) or int(raw) > 9223372036854775807:
                        raise ValueError
                    before = int(raw)
                result = read_dashboard(self.server.db_path, before=before)
                if result["status"] == "unconfigured" and getattr(self.server, "had_checkpoint", False):
                    raise checker.CheckError("account_state_missing")
                if result["status"] != "unconfigured":
                    self.server.had_checkpoint = True
                self.send_json(200, result)
            elif url.path in ASSETS and not query:
                path, content_type = ASSETS[url.path]
                self.send_body(200, path.read_bytes(), content_type)
            else:
                self.send_json(404, {"ok": False, "error": "not_found"})
        except ValueError as error:
            if isinstance(error, checker.CheckError):
                self.send_json(503, {"ok": False, "status": "unavailable", "error": str(error), "generated_at": checker.utc(datetime.now(timezone.utc))})
            else:
                self.send_json(400, {"ok": False, "error": "invalid_request"})
        except (OSError, sqlite3.Error):
            self.send_json(503, {"ok": False, "status": "unavailable", "error": "reader_unavailable", "generated_at": checker.utc(datetime.now(timezone.utc))})

    do_HEAD = do_GET

    def unsupported_method(self):
        if self.allowed_origin():
            self.send_json(405, {"ok": False, "error": "read_only"})

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = unsupported_method


def dashboard_identity(db_path):
    paths = [os.path.normcase(str(path.resolve())) for path in (ROOT, Path(db_path))]
    return {"service": "ace-dashboard", "api_version": 1, "read_only": True,
            "instance_id": hashlib.sha256(checker.encode(paths).encode("utf-8")).hexdigest()}


class DashboardServer(ThreadingHTTPServer):
    def server_bind(self):
        # SO_REUSEADDR alone can allow two listeners on the same Windows port.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.allow_reuse_address = False
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(db_path=checker.DEFAULT_DB, port=8765):
    server = DashboardServer(("127.0.0.1", port), DashboardHandler)
    server.db_path = Path(db_path).resolve()
    server.identity = dashboard_identity(server.db_path)
    return server


def is_dashboard_running(db_path, port):
    connection = HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        connection.request("GET", "/api/health", headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200 or response.getheader("Content-Type", "").split(";")[0].strip() != "application/json":
            return False
        body = response.read(4097)
        if len(body) > 4096:
            return False
        identity = checker.decode(body.decode("utf-8"), exact_numbers=False)
        return (isinstance(identity, dict) and type(identity.get("api_version")) is int
                and identity.get("read_only") is True and identity == dashboard_identity(db_path))
    except (OSError, HTTPException, ValueError, TypeError):
        return False
    finally:
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=checker.DEFAULT_DB, help="Existing checkpoint path; never created or modified")
    parser.add_argument("--port", type=int, default=8765, help="Loopback HTTP port (default: 8765)")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        server = create_server(args.db, args.port)
    except OSError as error:
        occupied = error.errno in (errno.EADDRINUSE, 10048) or getattr(error, "winerror", None) == 10048
        if occupied and is_dashboard_running(args.db, args.port):
            print("Ace dashboard already running: http://127.0.0.1:" + str(args.port), flush=True)
            return 0
        print("Unable to start the local dashboard. Check the port and local permissions.", file=sys.stderr)
        return 1
    print("Ace dashboard: http://127.0.0.1:" + str(server.server_port), flush=True)
    print("Read-only saved observations. Refreshing does not contact MT5 or run the agent.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
