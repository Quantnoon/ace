"""Read-only dashboard checks with synthetic temporary checkpoints only."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
from datetime import timedelta
from decimal import Decimal
import errno
import http.client
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock, patch

from scripts import account_check as checker
from scripts import dashboard
import test_account_check as fixtures


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.AccountCheckTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def read(self, **options):
        options.setdefault("now", self.f.now)
        return dashboard.read_dashboard(self.f.db, **options)

    def server(self):
        server = dashboard.create_server(self.f.db, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            thread.join(5)
            server.server_close()

        self.addCleanup(cleanup)
        return server

    def request(self, server, path="/api/dashboard", method="GET", headers=None):
        with closing(http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as connection:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()

    def rewrite_state(self, update):
        state = self.f.state()
        update(state)
        with closing(sqlite3.connect(self.f.db)) as connection, connection:
            checker.save_state(connection, self.f.revision, state, "synthetic-state-fixture", {}, self.f.now)

    def test_absent_state_import_help_and_server_start_do_not_create_database(self):
        with patch.object(sqlite3, "connect", side_effect=AssertionError("must not open an absent database")):
            self.assertEqual(self.read()["status"], "unconfigured")
            spec = importlib.util.spec_from_file_location("scripts.isolated_dashboard", dashboard.__file__)
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
            server = self.server()
            status, _, body = self.request(server)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["status"], "unconfigured")
        process = subprocess.run([sys.executable, dashboard.__file__, "--help", "--db", str(self.f.db)],
                                 cwd=self.f.temp.name, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertFalse(self.f.db.exists())

    def test_v1_v2_v3_reads_preserve_state_and_version_one_display_envelopes(self):
        self.f.start()
        self.f.call("journal", **self.f.journal_request())
        original = self.f.state()
        for version, status in ((1, None), (2, "active"), (2, "closing"), (2, "closed"),
                                (3, "active"), (3, "closing"), (3, "closed")):
            with self.subTest(version=version, status=status):
                saved = copy.deepcopy(original)
                saved.pop("loop", None)
                if version < 3:
                    saved.pop("observation", None)
                if status:
                    saved["loop"] = {"id": "synthetic-loop", "status": status, "cycles": 3,
                                     "timeframe": "M15", "last_cycle_at": saved["last_snapshot"]["as_of"],
                                     "next_cycle_at": None, "max_gap_seconds": 901,
                                     "end_reason": None if status == "active" else "target_latch"}
                    if version == 3:
                        saved["loop"].update(policy_id=saved["policy"]["id"], goal_id=saved["goal"]["id"],
                                             binding_verified_at=checker.utc(self.f.now))
                with closing(sqlite3.connect(self.f.db)) as connection, connection:
                    checker.save_state(connection, self.f.revision, saved, "synthetic-reader-fixture", {}, self.f.now)
                    connection.execute("PRAGMA user_version = " + str(version))
                before = self.f.db.read_bytes()
                with closing(sqlite3.connect(self.f.db.as_uri() + "?mode=ro", uri=True)) as connection:
                    revision, loaded = checker.load_state(connection)
                expected = dict(saved, loop=saved.get("loop"))
                self.assertEqual(loaded, expected)
                with patch.object(checker, "load_state", return_value=(revision, loaded)):
                    for _ in range(2):
                        data = self.read()
                        self.assertEqual(data["revision"], self.f.revision)
                        self.assertEqual(data["api_version"], 1)
                        self.assertEqual(data["latest_journal"]["version"], 1)
                        self.assertTrue(data["progress"]["points"])
                        self.assertFalse(data["progress"]["points"][0]["legacy"])
                self.assertEqual(loaded, expected)
                self.assertEqual(self.f.db.read_bytes(), before)
                with closing(sqlite3.connect(self.f.db.as_uri() + "?mode=ro", uri=True)) as connection:
                    self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], version)
                if status is None:
                    self.assertIsNone(data["loop"])
                    continue
                self.assertEqual(data["loop"]["status"], status)
                self.assertEqual(data["loop"]["cycles"], 3)
                self.assertEqual(data["loop"]["max_gap_seconds"], 901)
                self.assertEqual(data["loop"]["execution"], "unverified")
                if version == 2:
                    self.assertEqual(data["loop"]["last_observation_at"], saved["last_snapshot"]["as_of"])
                    for field in ("policy_id", "goal_id", "binding_verified_at", "next_latch_check_at",
                                  "next_wake_at", "wake_reason", "last_observation_received_at",
                                  "observation_gap_seconds", "max_observation_gap_seconds", "max_observation_gap_at",
                                  "wake_overdue_seconds"):
                        self.assertIsNone(data["loop"][field], field)
                else:
                    self.assertEqual(data["loop"]["policy_id"], saved["policy"]["id"])
                    self.assertEqual(data["loop"]["goal_id"], saved["goal"]["id"])
                    self.assertEqual(data["loop"]["binding_verified_at"], checker.utc(self.f.now))

    def test_loop_projection_allowlists_wakes_and_shared_observation_health(self):
        self.f.start()
        at = checker.utc(self.f.now)
        candle = checker.utc(self.f.now + timedelta(minutes=15, seconds=5))
        wake = checker.utc(self.f.now + timedelta(minutes=5))
        raw_loop = {"id": "synthetic-loop", "status": "active", "cycles": 3, "timeframe": "M15",
                    "last_cycle_at": at, "next_cycle_at": candle, "next_latch_check_at": wake,
                    "next_wake_at": wake, "wake_reason": "latch_check", "max_gap_seconds": 901,
                    "end_reason": None, "policy_id": "synthetic-policy", "goal_id": "synthetic-goal",
                    "binding_verified_at": at, "raw_clock_evidence": {"private": "not-for-display"}}
        self.rewrite_state(lambda state: state.update(loop=raw_loop))
        health = {"last_observation_at": at, "last_observation_received_at": at,
                  "observation_age_seconds": 320, "observation_gap_seconds": 300,
                  "max_observation_gap_seconds": 600, "max_observation_gap_at": at,
                  "wake_overdue_seconds": 20, "execution": "unverified", "raw_history": "not-for-display"}
        state = self.f.state()
        now = self.f.now + timedelta(seconds=320)
        before = self.f.db.read_bytes()
        with patch.object(checker, "loop_health", return_value=health) as shared_health:
            data = self.read(now=now)
        shared_health.assert_called_once_with(state, now)
        expected = {key: value for key, value in raw_loop.items() if key != "raw_clock_evidence"}
        expected.update({key: value for key, value in health.items() if key != "raw_history"})
        self.assertEqual(data["loop"], expected)
        self.assertEqual(self.f.db.read_bytes(), before)
        self.assertNotIn("not-for-display", checker.encode(data))

    def test_unknown_loop_health_scalars_are_not_zero_or_execution_claims(self):
        self.f.start()
        raw_loop = {"id": "synthetic-loop", "status": "active", "policy_id": [], "goal_id": False,
                    "binding_verified_at": "invalid", "next_latch_check_at": [], "next_wake_at": False,
                    "wake_reason": {}, "max_gap_seconds": "901"}
        self.rewrite_state(lambda state: state.update(loop=raw_loop))
        seconds = ("observation_age_seconds", "observation_gap_seconds", "max_observation_gap_seconds", "wake_overdue_seconds")
        for value in (None, True, "0", -1, float("nan"), float("inf")):
            with self.subTest(value=value):
                health = dict.fromkeys(seconds, value)
                health.update(last_observation_at=[], last_observation_received_at="invalid",
                              max_observation_gap_at=False, execution="running")
                with patch.object(checker, "loop_health", return_value=health):
                    data = self.read()
                self.assertEqual(data["loop"]["execution"], "unverified")
                for field in (*seconds, "policy_id", "goal_id", "binding_verified_at", "next_latch_check_at",
                              "next_wake_at", "wake_reason", "max_gap_seconds", "last_observation_at",
                              "last_observation_received_at", "max_observation_gap_at"):
                    self.assertIsNone(data["loop"][field], field)
                self.assertEqual(data["metrics"]["equity"], "100")
                self.assertTrue(data["warnings"])
        self.rewrite_state(lambda state: state["loop"].update(wake_reason="future_unknown_reason"))
        self.assertIsNone(self.read()["loop"]["wake_reason"])

    def test_health_and_repeated_start_do_not_open_or_create_account_state(self):
        with patch.object(sqlite3, "connect", side_effect=AssertionError("health must not open account state")):
            server = self.server()
            status, headers, body = self.request(server, "/api/health")
            identity = json.loads(body)
            self.assertEqual(status, 200)
            self.assertEqual(identity, dashboard.dashboard_identity(self.f.db))
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertNotIn(str(self.f.db), body.decode())
            self.assertNotIn(str(dashboard.ROOT), body.decode())
            self.assertNotIn("account", identity)
            self.assertTrue(dashboard.is_dashboard_running(self.f.db, server.server_port))
            with self.assertRaises(OSError):
                dashboard.create_server(self.f.db, server.server_port)
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                result = dashboard.main(["--db", str(self.f.db), "--port", str(server.server_port)])
            self.assertEqual(result, 0)
            self.assertIn("already running", output.getvalue())
            self.assertEqual(self.request(server, "/api/health")[0], 200)
        self.assertFalse(self.f.db.exists())

    def test_cli_reuses_the_same_workspace_and_database_from_another_directory(self):
        self.f.start()
        before = self.f.db.read_bytes()
        server = self.server()
        result = subprocess.run([sys.executable, dashboard.__file__, "--db", str(self.f.db), "--port", str(server.server_port)],
                                cwd=self.f.temp.name, capture_output=True, text=True, timeout=5, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already running", result.stdout)
        self.assertEqual(self.f.db.read_bytes(), before)

    def test_other_checkpoint_or_workspace_is_not_reused_or_stopped(self):
        server = self.server()
        other_db = self.f.db.with_name("different.sqlite3")
        self.assertFalse(dashboard.is_dashboard_running(other_db, server.server_port))
        with patch.object(dashboard, "ROOT", self.f.db.parent / "different-workspace"):
            self.assertFalse(dashboard.is_dashboard_running(self.f.db, server.server_port))
        with patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(dashboard.main(["--db", str(other_db), "--port", str(server.server_port)]), 1)
        self.assertTrue(dashboard.is_dashboard_running(self.f.db, server.server_port))
        self.assertFalse(other_db.exists())
        self.assertFalse(self.f.db.exists())

    def test_readiness_rejects_foreign_redirected_malformed_and_oversized_responses(self):
        identity = dashboard.dashboard_identity(self.f.db)
        response = Mock()
        connection = Mock()
        connection.getresponse.return_value = response
        variants = [(302, "application/json", checker.encode(identity).encode()),
                    (200, "text/html", checker.encode(identity).encode()),
                    (200, "application/json", b"not JSON"),
                    (200, "application/json", b"x" * 4097),
                    (200, "application/json", checker.encode(dict(identity, service="another-app")).encode()),
                    (200, "application/json", checker.encode(dict(identity, api_version=True)).encode()),
                    (200, "application/json", checker.encode(dict(identity, read_only=1)).encode())]
        with patch.object(dashboard, "HTTPConnection", return_value=connection):
            for status, content_type, body in variants:
                with self.subTest(status=status, content_type=content_type, size=len(body)):
                    response.status = status
                    response.getheader.return_value = content_type
                    response.read.return_value = body
                    self.assertFalse(dashboard.is_dashboard_running(self.f.db, 8765))
                    connection.request.assert_called_with("GET", "/api/health", headers={"Accept": "application/json"})
                    connection.close.assert_called()
            connection.request.side_effect = TimeoutError
            self.assertFalse(dashboard.is_dashboard_running(self.f.db, 8765))
        with patch.object(dashboard, "create_server", side_effect=OSError(errno.EACCES, "denied")), \
                patch.object(dashboard, "is_dashboard_running") as probe, patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(dashboard.main(["--db", str(self.f.db)]), 1)
            probe.assert_not_called()

    def test_health_has_the_same_origin_and_method_restrictions(self):
        server = self.server()
        self.assertEqual(self.request(server, "/api/health", headers={"Host": "foreign.example"})[0], 403)
        self.assertEqual(self.request(server, "/api/health", headers={"Origin": "https://foreign.example"})[0], 403)
        self.assertEqual(self.request(server, "/api/health", method="POST")[0], 405)
        self.assertEqual(self.request(server, "/api/health", method="HEAD")[2], b"")
        self.assertEqual(self.request(server, "/api/health?before=1")[0], 404)

    def test_draft_and_active_targets_are_distinct(self):
        self.f.draft(budget="5", target="15")
        draft = self.read()
        self.assertEqual(draft["status"], "draft")
        self.assertEqual(draft["draft"]["target"], "15")
        self.assertIsNone(draft["goal"])
        self.assertIsNone(draft["metrics"])
        self.assertEqual(draft["progress"]["points"], [])
        self.f.start()
        self.f.draft(target="99")
        current = self.read()
        self.assertEqual(current["goal"]["target"], "15")
        self.assertEqual(current["metrics"]["target"], "15")
        self.assertEqual(current["draft"]["target"], "99")

    def test_progress_uses_net_gain_cashflows_and_exact_decimal_strings(self):
        self.f.start()
        sample = self.f.snap("300")
        flow = {"id": "deposit", "at": sample["as_of"], "amount": "200"}
        sample["cashflows"] = [flow]
        self.f.call("check", snapshot=sample)
        self.assertEqual(self.read()["metrics"]["estimated_goal_gain"], "0")
        self.f.call("check", snapshot=self.f.snap("315", cashflows=[flow], remaining_close_costs="0.5"))
        data = self.read()
        self.assertEqual(data["metrics"]["estimated_goal_gain"], "14.5")
        self.assertEqual(data["metrics"]["remaining_target"], "0.5")
        self.assertIsNone(data["stops"]["target_latched_at"])
        self.assertEqual(data["progress"]["points"][-1]["gain"], "14.5")
        self.assertEqual(data["progress"]["points"][-1]["pct"], data["metrics"]["progress_pct"])
        self.assertEqual(dashboard.decimal_text("9007199254740993.000000000001"), "9007199254740993.000000000001")

    def test_signed_progress_above_target_and_final_shortfall_remain_stopped(self):
        self.f.start()
        self.f.call("check", snapshot=self.f.snap("99.999999999999"))
        self.assertLess(Decimal(self.read()["metrics"]["progress_pct"]), 0)
        self.f.call("check", snapshot=self.f.snap("116", positions=[fixtures.position()]))
        triggered = self.read()
        self.assertGreater(Decimal(triggered["metrics"]["progress_pct"]), 100)
        self.assertFalse(triggered["stops"]["closure_verified"])
        self.f.call("check", snapshot=self.f.snap("114.7"))
        final = self.read()
        self.assertTrue(final["stops"]["closure_verified"])
        self.assertEqual(final["metrics"]["final_net"], "14.7")
        self.assertEqual(final["metrics"]["final_shortfall"], "0.3")
        self.assertIsNotNone(final["stops"]["target_latched_at"])
        self.f.draft(target="30")
        self.assertTrue(self.read()["stops"]["closure_verified"])

    def test_rejected_observation_retains_last_good_values_and_breaks_history(self):
        self.f.start()
        sample = self.f.snap("104")
        self.f.call("check", snapshot=sample)
        self.f.call("check", snapshot=self.f.snap("999", history_complete=False))
        failed = self.read()
        self.assertEqual(failed["metrics"]["equity"], "104")
        self.assertEqual(failed["snapshot"]["id"], sample["id"])
        self.assertIn("incomplete_history", failed["result"]["reason_codes"])
        self.assertEqual(len(failed["progress"]["points"]), 2)
        self.f.call("check", snapshot=self.f.snap("104.5"))
        self.assertTrue(self.read()["progress"]["points"][-1]["gap_before"])
        self.f.now += timedelta(seconds=90)
        self.assertEqual(self.read()["snapshot"]["freshness"], "stale")
        self.assertEqual(self.read(now=self.f.now - timedelta(days=1))["snapshot"]["freshness"], "future")

    def test_journal_and_revision_do_not_refresh_observation_or_duplicate_points(self):
        self.f.start()
        sample = self.f.snap("102")
        self.f.call("cycle", snapshot=sample)
        self.f.call("check", snapshot=sample)
        self.f.now += timedelta(seconds=70)
        before = self.read()
        self.f.call("journal", **self.f.journal_request())
        data = self.read()
        self.assertEqual(data["loop"], before["loop"])
        self.assertEqual(data["snapshot"], before["snapshot"])
        self.assertEqual(data["revision"], before["revision"] + 1)
        self.assertEqual(data["loop"]["last_observation_at"], sample["as_of"])
        self.assertEqual(data["loop"]["observation_age_seconds"], 70)
        self.assertEqual(len(data["progress"]["points"]), 2)
        self.assertEqual(data["snapshot"]["freshness"], "stale")
        self.assertEqual(data["latest_journal"]["as_of"], sample["as_of"])
        self.assertGreater(data["latest_journal"]["recorded_at"], sample["as_of"])
        self.assertEqual(data["activity"]["items"][0]["command"], "journal")
        with self.assertRaisesRegex(checker.CheckError, "journal_snapshot_mismatch"):
            self.f.call("journal", **self.f.journal_request(snapshot_id="synthetic-missing"))
        self.assertEqual(self.read()["loop"], data["loop"])
        later = self.read(now=self.f.now + timedelta(seconds=10))
        self.assertEqual(later["loop"]["observation_age_seconds"], 80)
        self.assertEqual(later["loop"]["last_cycle_at"], data["loop"]["last_cycle_at"])
        self.assertEqual(later["loop"]["next_wake_at"], data["loop"]["next_wake_at"])

    def test_pending_orders_unknown_empty_protective_and_enrichment(self):
        self.f.start(pending_orders=None)
        self.assertIsNone(self.read()["pending_orders"])
        self.assertIsNone(self.read()["exposure"]["orders_count"])
        orders = [fixtures.position("00042", "1", kind="entry"),
                  {"ticket": "protect", "symbol": "EURUSD", "kind": "protective", "reduce_only": True, "position_ticket": "p1"}]
        self.f.call("check", snapshot=self.f.snap(positions=[fixtures.position()], pending_orders=orders))
        self.f.call("journal", **self.f.journal_request(pending_order_details=[
            {"ticket": "00042", "side": "buy", "order_type": "buy_limit", "volume_remaining": "0.010",
             "entry_price": "1.090000000001", "unset_fields": ["take_profit", "expires_at"],
             "ownership": "manual", "ownership_ref": "synthetic:manual-order"}]))
        data = self.read()
        self.assertEqual(data["exposure"], {"positions_count": 1, "orders_count": 2, "entry_orders_count": 1, "protective_orders_count": 1})
        self.assertEqual(data["pending_orders"][0]["ticket"], "00042")
        self.assertEqual(data["pending_orders"][0]["details"]["entry_price"], "1.090000000001")
        self.assertEqual(data["pending_orders"][0]["details"]["ownership"], "manual")
        self.assertIn("take_profit", data["pending_orders"][0]["details"]["unset_fields"])
        self.assertIsNone(data["pending_orders"][1]["risk"])
        self.f.call("check", snapshot=self.f.snap(positions=[fixtures.position()], pending_orders=orders))
        newer = self.read()
        self.assertIsNotNone(newer["latest_journal"])
        self.assertIsNone(newer["pending_orders"][0]["details"])
        self.f.call("check", snapshot=self.f.snap())
        self.assertEqual(self.read()["pending_orders"], [])
        self.assertEqual(self.read()["exposure"]["orders_count"], 0)

    def test_intents_are_not_broker_orders_and_parameters_are_not_exposed(self):
        self.f.start()
        self.f.call("prepare", snapshot=self.f.snap(), action=self.f.entry(
            authority_ref="private-approval-prose", parameters={"symbol": "EURUSD", "debug": "private-raw-tool-value"}))
        prepared = self.read()
        self.assertEqual(prepared["pending_orders"], [])
        self.assertEqual(prepared["unresolved_intents"]["count"], 1)
        self.assertEqual(prepared["unresolved_intents"]["items"][0]["status"], "prepared")
        self.f.call("resolve", intent_id="a1", outcome="completed", evidence_ref="private-receipt-path",
                    broker_tickets=["order1"], readback_verified=True,
                    snapshot=self.f.snap(pending_orders=[fixtures.position("order1", kind="entry")]))
        settled = self.read()
        self.assertEqual(settled["unresolved_intents"]["count"], 0)
        self.assertEqual(settled["exposure"]["orders_count"], 1)
        self.assertFalse(settled["stops"]["closure_verified"])
        self.assertEqual(settled["activity"]["items"][0]["intent"]["status"], "completed")
        serialized = checker.encode(settled)
        for value in ("private-approval-prose", "private-raw-tool-value", "private-receipt-path", "parameters", "authority_ref", "approval_ref"):
            self.assertNotIn(value, serialized)

    def test_pagination_is_bounded_and_scoped_to_the_current_goal(self):
        self.f.start()
        old_goal = self.f.state()["goal"]["id"]
        self.f.call("journal", **self.f.journal_request())
        self.f.draft(target="20")
        self.f.activate_again("new_goal", self.f.snap("102"))
        for value in range(5):
            self.f.call("check", snapshot=self.f.snap(str(102 + value)))
        with patch.object(dashboard, "PAGE_SIZE", 3):
            first = self.read()
            second = self.read(before=first["activity"]["next_cursor"])
        self.assertLessEqual(len(first["activity"]["items"]), 3)
        self.assertNotEqual(first["scope"]["goal_id"], old_goal)
        self.assertIsNone(first["latest_journal"])
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertFalse({row["id"] for row in first["activity"]["items"]} & {row["id"] for row in second["activity"]["items"]})
        self.assertEqual({point["target"] for point in second["progress"]["points"]}, {"20"})
        for invalid in (0, -1, True, "1", 9223372036854775808):
            with self.assertRaisesRegex(checker.CheckError, "invalid_cursor"):
                self.read(before=invalid)

    def test_legacy_history_is_not_reconstructed_and_bad_optional_metadata_is_ignored(self):
        self.f.start()
        self.f.call("check", snapshot=self.f.snap("103"))
        with closing(sqlite3.connect(self.f.db)) as connection, connection:
            for event_id, raw in connection.execute("SELECT id, detail FROM events").fetchall():
                detail = json.loads(raw)
                detail.pop("display", None)
                connection.execute("UPDATE events SET detail = ? WHERE id = ?", (checker.encode(detail), event_id))
        legacy = self.read()
        self.assertEqual(len(legacy["progress"]["points"]), 1)
        self.assertTrue(legacy["progress"]["points"][0]["legacy"])
        self.assertEqual(legacy["progress"]["points"][0]["as_of"], self.f.state()["last_snapshot"]["as_of"])
        self.rewrite_state(lambda state: state.update(last_journal=["malformed-report"]))
        self.assertIsNone(self.read()["latest_journal"])
        self.assertTrue(self.read()["warnings"])
        self.assertEqual(self.read()["metrics"]["equity"], "103")

    def test_loss_and_target_flags_are_canonical_not_agent_prose(self):
        self.f.start()
        self.f.call("check", snapshot=self.f.snap("120", remaining_close_costs="10"))
        self.f.call("check", snapshot=self.f.snap("115", positions=[fixtures.position()]))
        self.f.call("journal", **self.f.journal_request(activity="entry", summary="An explanation, not execution authority"))
        data = self.read()
        self.assertIsNotNone(data["stops"]["loss_latched_at"])
        self.assertIsNotNone(data["stops"]["target_latched_at"])
        self.assertEqual(data["result"]["decision"], "loss_stop")
        self.assertFalse(data["stops"]["closure_verified"])

    def test_http_routes_methods_origins_and_security_headers(self):
        self.f.start()
        original = self.f.db.read_bytes()
        server = self.server()
        status, headers, body = self.request(server)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["account"]["login"], fixtures.ACCOUNT["login"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        for path in ("/ace_state.sqlite3", "/../AGENTS.md", "/%2e%2e/AGENTS.md", "/scripts/account_check.py", "/api/journal"):
            with self.subTest(path=path):
                self.assertEqual(self.request(server, path)[0], 404)
        for path in ("/api/dashboard?db=private", "/api/dashboard?before=0", "/api/dashboard?before=1&before=2",
                     "/api/dashboard?before=9223372036854775808"):
            self.assertEqual(self.request(server, path)[0], 400)
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            self.assertEqual(self.request(server, method=method)[0], 405)
        for headers in ({"Host": "attacker.example"}, {"Origin": "https://attacker.example"}, {"Origin": "null"}):
            self.assertEqual(self.request(server, headers=headers)[0], 403)
        self.assertEqual(self.request(server, headers={"Origin": "http://127.0.0.1:" + str(server.server_port)})[0], 200)
        status, headers, body = self.request(server, method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)
        self.assertEqual(self.f.db.read_bytes(), original)

    def test_static_assets_are_explicit_and_never_read_account_state(self):
        server = self.server()
        with patch.object(dashboard, "read_dashboard", side_effect=AssertionError("static assets must not read state")):
            for path, content_type in (("/", "text/html"), ("/dashboard.css", "text/css"),
                                       ("/dashboard.mjs", "text/javascript"), ("/assets/logo.png", "image/png")):
                status, headers, body = self.request(server, path)
                self.assertEqual(status, 200)
                self.assertTrue(headers["Content-Type"].startswith(content_type))
                self.assertTrue(body)
        self.assertFalse(self.f.db.exists())

    def test_unsupported_corrupt_busy_and_missing_after_load_fail_honestly(self):
        self.f.start()
        server = self.server()
        self.assertEqual(self.request(server)[0], 200)
        with closing(sqlite3.connect(self.f.db)) as connection, connection:
            connection.execute("BEGIN EXCLUSIVE")
            status, _, body = self.request(server)
            self.assertEqual(status, 503)
            self.assertEqual(json.loads(body)["status"], "unavailable")
            self.assertNotIn(str(self.f.db), body.decode())
        with closing(sqlite3.connect(self.f.db)) as connection, connection:
            connection.execute("PRAGMA user_version = 999")
        with self.assertRaisesRegex(checker.CheckError, "unsupported_schema"):
            self.read()
        with closing(sqlite3.connect(self.f.db)) as connection, connection:
            connection.execute("PRAGMA user_version = 2")
            connection.execute("UPDATE state SET payload = '{}'")
        with self.assertRaisesRegex(checker.CheckError, "state_audit_mismatch"):
            self.read()
        self.f.db.unlink()
        status, _, body = self.request(server)
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error"], "account_state_missing")
        self.assertFalse(self.f.db.exists())

    def test_reader_is_consistent_with_a_concurrent_writer(self):
        self.f.start()

        def writer():
            for value in range(1, 7):
                self.f.call("check", snapshot=self.f.snap(str(100 + value)))

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(writer)
            for _ in range(8):
                data = dashboard.read_dashboard(self.f.db, now=self.f.now + timedelta(seconds=1))
                self.assertEqual(data["snapshot"]["as_of"], data["progress"]["points"][-1]["as_of"])
                self.assertEqual(data["metrics"]["estimated_goal_gain"], data["progress"]["points"][-1]["gain"])
            future.result()


if __name__ == "__main__":
    unittest.main()
