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

    def server(self, module=dashboard):
        server = module.create_server(self.f.db, 0)
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

    def test_v1_v2_v3_v4_v5_reads_preserve_state_and_version_one_display_envelopes(self):
        self.f.start()
        self.f.call("journal", **self.f.journal_request())
        original = self.f.state()
        for version, status in ((1, None), (2, "active"), (2, "closing"), (2, "closed"),
                                (3, "active"), (3, "closing"), (3, "closed"),
                                (4, "active"), (4, "closing"), (4, "closed"),
                                (5, "active"), (5, "closing"), (5, "closed")):
            with self.subTest(version=version, status=status):
                saved = copy.deepcopy(original)
                saved.pop("loop", None)
                if version < 4:
                    saved.pop("approval_mode", None)
                    saved["policy"].pop("approval_mode", None)
                    saved["goal"].pop("approval_mode", None)
                if version < 3:
                    saved.pop("observation", None)
                if status:
                    saved["loop"] = {"id": "synthetic-loop", "status": status, "cycles": 3,
                                     "timeframe": "M15", "last_cycle_at": saved["last_snapshot"]["as_of"],
                                     "next_cycle_at": None, "max_gap_seconds": 901,
                                     "end_reason": None if status == "active" else "target_latch"}
                    if version >= 3:
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
                        self.assertIsNone(data["session"])
                        self.assertTrue(data["progress"]["points"])
                        self.assertFalse(data["progress"]["points"][0]["legacy"])
                        self.assertEqual(data["strategies"], {"items": [], "next_cursor": None})
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

    def test_session_control_is_allowlisted_and_not_an_observation_or_progress_point(self):
        self.f.start(approval_mode="start_request")
        self.f.control("start")
        self.f.call("cycle", snapshot=self.f.snap())
        before = self.read()
        self.f.now += timedelta(minutes=10)
        control = self.f.control("interrupt", "synthetic:private-runtime-reference")
        raw = self.f.db.read_bytes()
        data = self.read()
        self.assertEqual(self.f.db.read_bytes(), raw)
        self.assertEqual(data["session"]["id"], control["session"]["id"])
        self.assertEqual(data["session"]["status"], "interrupted")
        self.assertEqual(data["session"]["execution"], "unverified")
        self.assertNotIn("request_ref", data["session"])
        self.assertNotIn("evidence_ref", data["session"])
        self.assertEqual(data["snapshot"]["as_of"], before["snapshot"]["as_of"])
        self.assertEqual(data["snapshot"]["freshness"], "stale")
        self.assertEqual(data["metrics"], before["metrics"])
        self.assertEqual(data["result"], before["result"])
        self.assertEqual(data["progress"], before["progress"])
        self.assertIsNone(data["loop"]["next_wake_at"])
        event = data["activity"]["items"][0]
        self.assertEqual(event["command"], "session")
        self.assertEqual(event["decision"], "session_saved")
        self.assertIsNone(event["snapshot_at"])
        self.assertFalse(event["closure_verified"])
        self.assertEqual(event["session"], data["session"])
        self.assertNotIn("private-runtime-reference", checker.encode(data))
        self.f.control("resume", "synthetic:host-restored")
        self.assertEqual(self.read()["loop"]["wake_reason"], "session_check")
        self.f.call("check", snapshot=self.f.snap())
        self.assertTrue(self.read()["progress"]["points"][-1]["gap_before"])

    def test_financial_settlement_retains_session_and_visible_monitor_wake_until_user_end(self):
        self.f.start(config=dict(fixtures.MANDATE, latch_check_seconds=30))
        self.f.control("start")
        self.f.call("cycle", snapshot=self.f.snap("95"))
        data = self.read()
        self.assertEqual(data["session"]["status"], "active")
        self.assertEqual(data["session"]["execution"], "unverified")
        self.assertEqual(data["loop"]["status"], "closed")
        self.assertEqual(data["loop"]["wake_reason"], "monitor")
        self.assertEqual(data["loop"]["next_wake_at"], checker.utc(self.f.now + timedelta(seconds=30)))
        self.assertTrue(data["stops"]["closure_verified"])
        self.f.now += timedelta(seconds=31)
        self.assertEqual(self.read()["loop"]["wake_overdue_seconds"], 1)
        self.f.control("stop")
        stopped = self.read()
        self.assertEqual(stopped["session"]["status"], "stopped")
        self.assertIsNone(stopped["loop"]["next_wake_at"])
        self.assertIsNone(stopped["loop"]["wake_overdue_seconds"])
        self.assertEqual(stopped["stops"], data["stops"])

    def test_session_events_do_not_create_a_false_gap_between_real_observations(self):
        self.f.start()
        self.f.control("start")
        self.f.call("check", snapshot=self.f.snap("101"))
        self.f.control("interrupt")
        self.f.control("resume")
        self.f.call("check", snapshot=self.f.snap("102"))
        data = self.read()
        self.assertEqual(len(data["progress"]["points"]), 3)
        self.assertFalse(any(point["gap_before"] for point in data["progress"]["points"]))
        self.assertFalse(data["progress"]["incomplete"])

    def test_health_and_repeated_start_do_not_open_or_create_account_state(self):
        with patch.object(sqlite3, "connect", side_effect=AssertionError("health must not open account state")):
            server = self.server()
            status, headers, body = self.request(server, "/api/health")
            identity = json.loads(body)
            self.assertEqual(status, 200)
            self.assertEqual(identity, dashboard.dashboard_identity(self.f.db))
            self.assertEqual(identity["readable_schemas"], [1, 2, 3, 4, 5])
            self.assertEqual(identity["reader_build"], checker.READER_BUILD)
            self.assertEqual(identity["viewer_build"], 4)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertNotIn(str(self.f.db), body.decode())
            self.assertNotIn(str(dashboard.ROOT), body.decode())
            self.assertNotIn("account", identity)
            self.assertEqual(dashboard.probe_dashboard(self.f.db, server.server_port), "compatible")
            with self.assertRaises(OSError):
                dashboard.create_server(self.f.db, server.server_port)
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                result = dashboard.main(["--db", str(self.f.db), "--port", str(server.server_port)])
            self.assertEqual(result, 0)
            self.assertIn("already running", output.getvalue())
            self.assertEqual(self.request(server, "/api/health")[0], 200)
        self.assertFalse(self.f.db.exists())

    def test_build_four_rejects_a_build_three_viewer_without_opening_state(self):
        identity = dashboard.dashboard_identity(self.f.db)
        self.assertEqual(identity["viewer_build"], 4)
        response = Mock(status=200)
        response.getheader.return_value = "application/json"
        response.read.return_value = checker.encode(dict(identity, viewer_build=3)).encode()
        connection = Mock()
        connection.getresponse.return_value = response
        with patch.object(dashboard, "HTTPConnection", return_value=connection), \
                patch.object(dashboard, "create_server", side_effect=OSError(errno.EADDRINUSE, "in use")) as create, \
                patch.object(sqlite3, "connect", side_effect=AssertionError("reuse must not open state")), \
                patch("sys.stderr", new_callable=io.StringIO) as error, \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(dashboard.probe_dashboard(self.f.db, 8765), "restart_required")
            self.assertEqual(dashboard.main(["--db", str(self.f.db)]), 1)
        create.assert_called_once_with(self.f.db, 8765)
        self.assertIn("restart required", error.getvalue())
        self.assertIn("restart only this viewer", error.getvalue())
        self.assertIn("Leave the trading agent and checkpoint unchanged", error.getvalue())
        self.assertEqual(output.getvalue(), "")
        connection.request.assert_called_with("GET", "/api/health", headers={"Accept": "application/json"})
        connection.close.assert_called()
        self.assertFalse(self.f.db.exists())

    def test_health_is_frozen_without_rereading_deployed_files_or_account_state(self):
        server = self.server()
        original = copy.deepcopy(server.identity)
        with patch.object(checker, "READER_BUILD", checker.READER_BUILD + 1), \
                patch.object(checker, "READABLE_SCHEMA_VERSIONS", (1, 2, 3, 4, 5, 6)), \
                patch.object(dashboard, "VIEWER_BUILD", dashboard.VIEWER_BUILD + 1), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("health must not read deployed code")), \
                patch.object(Path, "read_text", side_effect=AssertionError("health must not read VERSION")), \
                patch.object(sqlite3, "connect", side_effect=AssertionError("health must not open state")):
            self.assertEqual(json.loads(self.request(server, "/api/health")[2]), original)
            self.assertEqual(dashboard.dashboard_identity(self.f.db)["instance_id"], original["instance_id"])
            self.assertEqual(dashboard.probe_dashboard(self.f.db, server.server_port), "restart_required")
        self.assertEqual(dashboard.probe_dashboard(self.f.db, server.server_port), "compatible")
        self.assertFalse(self.f.db.exists())

    def test_legacy_or_incompatible_loaded_capabilities_require_viewer_only_restart(self):
        self.f.start()
        before = self.f.db.read_bytes()
        server = self.server()
        current = server.identity
        legacy = {key: value for key, value in current.items()
                  if key not in ("reader_build", "viewer_build", "readable_schemas")}
        variants = [legacy]
        for field in ("reader_build", "viewer_build", "readable_schemas"):
            variants.append({key: value for key, value in current.items() if key != field})
        for field in ("reader_build", "viewer_build"):
            for value in (None, True, 1.0, "1", current[field] + 1):
                variants.append(dict(current, **{field: value}))
        for schemas in (None, {}, "1,2,3,4,5", [1, 2, 3, 4], [True, 2, 3, 4, 5], [1.0, 2, 3, 4, 5], [1, 2, 3, 4, "5"]):
            variants.append(dict(current, readable_schemas=schemas))
        with patch.object(sqlite3, "connect", side_effect=AssertionError("reuse must not open state")):
            for identity in variants:
                with self.subTest(identity=identity):
                    server.identity = identity
                    self.assertEqual(dashboard.probe_dashboard(self.f.db, server.server_port), "restart_required")
                    with patch("sys.stderr", new_callable=io.StringIO) as error, \
                            patch("sys.stdout", new_callable=io.StringIO) as output:
                        result = dashboard.main(["--db", str(self.f.db), "--port", str(server.server_port)])
                    self.assertEqual(result, 1)
                    self.assertIn("restart required", error.getvalue())
                    self.assertIn("restart only this viewer", error.getvalue())
                    self.assertIn("Leave the trading agent and checkpoint unchanged", error.getvalue())
                    self.assertNotIn("already running", output.getvalue())
                    self.assertEqual(json.loads(self.request(server, "/api/health")[2]), identity)
        server.identity = current
        self.assertEqual(dashboard.probe_dashboard(self.f.db, server.server_port), "compatible")
        self.assertEqual(self.f.db.read_bytes(), before)

    def test_isolated_old_reader_rejects_a_new_writer_upgrade_until_viewer_replacement(self):
        self.f.start()
        with closing(sqlite3.connect(self.f.db)) as connection, connection:
            connection.execute("PRAGMA user_version = 4")
        spec = importlib.util.spec_from_file_location("isolated_old_checker", checker.__file__)
        old_checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old_checker)
        old_checker.SCHEMA_VERSION = 4
        old_checker.READABLE_SCHEMA_VERSIONS = (1, 2, 3, 4)
        old_checker.READER_BUILD = 0
        spec = importlib.util.spec_from_file_location("scripts.isolated_old_dashboard", dashboard.__file__)
        old_dashboard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old_dashboard)
        old_dashboard.checker = old_checker
        old_dashboard.VIEWER_BUILD = 0
        old_server = self.server(old_dashboard)
        old_health = copy.deepcopy(old_server.identity)
        self.assertEqual(self.request(old_server)[0], 200)

        self.f.call("check", snapshot=self.f.snap("101"))
        before = self.f.db.read_bytes()
        with closing(sqlite3.connect(self.f.db.as_uri() + "?mode=ro", uri=True)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 5)
        status, _, body = self.request(old_server)
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error"], "unsupported_schema")
        self.assertEqual(json.loads(self.request(old_server, "/api/health")[2]), old_health)
        self.assertEqual(dashboard.probe_dashboard(self.f.db, old_server.server_port), "restart_required")
        with patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(dashboard.main(["--db", str(self.f.db), "--port", str(old_server.server_port)]), 1)
        self.assertEqual(self.request(old_server)[0], 503)
        self.assertEqual(self.read()["metrics"]["equity"], "101")
        current_server = self.server()
        self.assertEqual(dashboard.probe_dashboard(self.f.db, current_server.server_port), "compatible")
        status, _, body = self.request(current_server)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["metrics"]["equity"], "101")
        self.assertEqual(self.f.db.read_bytes(), before)

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
        self.assertEqual(dashboard.probe_dashboard(other_db, server.server_port), "unavailable")
        with patch.object(dashboard, "ROOT", self.f.db.parent / "different-workspace"):
            self.assertEqual(dashboard.probe_dashboard(self.f.db, server.server_port), "unavailable")
        with patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(dashboard.main(["--db", str(other_db), "--port", str(server.server_port)]), 1)
        self.assertEqual(dashboard.probe_dashboard(self.f.db, server.server_port), "compatible")
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
                    (200, "application/json", b"[]"),
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
                    self.assertEqual(dashboard.probe_dashboard(self.f.db, 8765), "unavailable")
                    connection.request.assert_called_with("GET", "/api/health", headers={"Accept": "application/json"})
                    connection.close.assert_called()
            connection.request.side_effect = TimeoutError
            self.assertEqual(dashboard.probe_dashboard(self.f.db, 8765), "unavailable")
        with patch.object(dashboard, "create_server", side_effect=OSError(errno.EACCES, "denied")), \
                patch.object(dashboard, "probe_dashboard") as probe, patch("sys.stderr", new_callable=io.StringIO):
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

    def test_recorded_strategy_survives_prepare_gap_completion_and_unlinked_reports(self):
        self.f.start()
        action = self.f.entry(risk="1.250000000001", authority_ref="private-strategy-approval",
                              parameters={"symbol": "EURUSD", "private": "private-strategy-parameters"})
        action["context"]["strategy"]["addition_rule"] = False
        prepared = self.f.call("prepare", snapshot=self.f.snap(), action=action)
        self.assertTrue(prepared["may_dispatch"])
        data = self.read()
        item = data["strategies"]["items"][0]
        self.assertEqual(item["intent"]["context"], checker.action_context(action["context"]))
        self.assertEqual(item["intent"]["risk"], "1.250000000001")
        self.assertEqual(item["intent"], data["unresolved_intents"]["items"][0])
        self.assertEqual(item["latest_action"], item["intent"])
        self.assertIsNone(item["latest_journal"])
        self.f.call("resolve", intent_id="a1", outcome="completed", evidence_ref="private-strategy-receipt",
                    broker_tickets=["still-pending"], readback_verified=True,
                    snapshot=self.f.snap(pending_orders=[fixtures.position("still-pending", kind="entry")]))
        self.f.call("journal", **self.f.journal_request(intent_id="a1", activity="entry",
                                                       summary="Pending entry verified, not filled"))
        linked_note = self.read()["latest_journal"]
        for _ in range(3):
            self.f.call("journal", **self.f.journal_request(summary="Unlinked wait assessment"))
        later = self.read(now=self.f.now + timedelta(minutes=10))
        saved = later["strategies"]["items"][0]
        self.assertEqual(saved["intent"]["context"], item["intent"]["context"])
        self.assertEqual(saved["intent"]["status"], "completed")
        self.assertEqual(saved["intent"]["outcome"]["broker_tickets"], ["still-pending"])
        self.assertEqual(saved["latest_journal"], linked_note)
        self.assertNotEqual(saved["latest_journal"], later["latest_journal"])
        self.assertEqual(saved["intent"]["snapshot_at"], item["intent"]["snapshot_at"])
        self.assertEqual(later["snapshot"]["freshness"], "stale")
        self.assertEqual(later["exposure"]["orders_count"], 1)
        self.assertEqual(later["unresolved_intents"]["count"], 0)
        serialized = checker.encode(later)
        for private in ("private-strategy-approval", "private-strategy-parameters", "private-strategy-receipt",
                        "parameters", "authority_ref", "approval_ref", "analysis_ref", "evidence_ref", "owner_id"):
            self.assertNotIn(private, serialized)

    def test_linked_management_keeps_fixed_origin_risk_and_same_symbol_ideas_separate(self):
        self.f.start()
        for intent_id, risk in (("idea-a", "2.25"), ("idea-b", "0.75")):
            self.assertTrue(self.f.call("prepare", snapshot=self.f.snap(),
                                       action=self.f.entry(intent_id, risk=risk))["may_dispatch"])
            self.f.call("resolve", intent_id=intent_id, outcome="completed", evidence_ref="synthetic:receipt",
                        broker_tickets=["p1"], readback_verified=True, snapshot=self.f.snap(positions=[fixtures.position()]))
        context = {"version": 1, "operation": "trail", "rationale": "Tighten the profitable leg; submission is not verification.",
                   "source_refs": ["synthetic:stop-read"], "origin_intent_id": "idea-a", "strategy": None}
        self.assertTrue(self.f.call("prepare", snapshot=self.f.snap(positions=[fixtures.position()]),
                                   action=self.f.reduction("trail-a", context=context))["may_dispatch"])
        self.f.call("resolve", intent_id="trail-a", outcome="unknown", evidence_ref="private-partial-receipt",
                    snapshot=self.f.snap(positions=[fixtures.position()]))
        self.f.call("journal", **self.f.journal_request(intent_id="trail-a", activity="management",
                                                       summary="Stop update remains unverified"))
        self.f.call("journal", **self.f.journal_request(summary="A later unlinked wait"))
        data = self.read()
        first, second = data["strategies"]["items"]
        self.assertEqual(first["intent"]["id"], "idea-b")
        self.assertIsNone(first["latest_journal"])
        self.assertEqual(second["intent"]["id"], "idea-a")
        self.assertEqual(second["intent"]["risk"], "2.25")
        self.assertEqual(second["latest_action"]["risk"], "0")
        self.assertEqual(second["latest_action"]["status"], "unknown")
        self.assertEqual(second["latest_action"]["context"], context)
        self.assertEqual(second["latest_journal"]["intent_id"], "trail-a")
        self.assertEqual(data["unresolved_intents"]["items"][0], second["latest_action"])
        linked_events = [item for item in data["activity"]["items"] if item["intent"] and item["intent"]["id"] == "trail-a"]
        self.assertTrue(linked_events)
        self.assertTrue(all(item["intent"]["context"]["operation"] == "trail" for item in linked_events))
        self.assertTrue(all(item["intent"]["outcome"]["at"] == second["latest_action"]["outcome"]["at"] for item in linked_events))
        self.assertNotIn("private-partial-receipt", checker.encode(data))

    def test_legacy_and_malformed_context_remain_unavailable_without_hiding_money(self):
        self.f.start()
        self.f.call("prepare", snapshot=self.f.snap(), action=self.f.entry())
        with closing(sqlite3.connect(self.f.db)) as connection:
            original = checker.decode(connection.execute("SELECT payload FROM intents WHERE id='a1'").fetchone()[0], exact_numbers=False)
        initial = self.read()
        context = original["context"]
        variants = [None, [], dict(context, version=2), dict(context, version=True), dict(context, rationale="\x1bmalformed"),
                    dict(context, source_refs=["../private-receipt"]), dict(context, approval_ref="private-extra"),
                    dict(context, strategy=dict(context["strategy"], trailing_rule=None))]
        for value in variants:
            with self.subTest(context=value):
                changed = dict(original, context=value)
                with closing(sqlite3.connect(self.f.db)) as connection, connection:
                    connection.execute("UPDATE intents SET payload=? WHERE id='a1'", (checker.encode(changed),))
                before = self.f.db.read_bytes()
                data = self.read()
                self.assertEqual(data["metrics"], initial["metrics"])
                self.assertEqual(data["stops"], initial["stops"])
                self.assertIsNone(data["strategies"]["items"][0]["intent"]["context"])
                self.assertIsNone(data["unresolved_intents"]["items"][0]["context"])
                self.assertEqual(self.f.db.read_bytes(), before)
                if value is not None:
                    self.assertTrue(any("strategy context" in warning for warning in data["warnings"]))
                self.assertNotIn("private-extra", checker.encode(data))
        original.pop("context")
        with closing(sqlite3.connect(self.f.db)) as connection, connection:
            connection.execute("UPDATE intents SET payload=? WHERE id='a1'", (checker.encode(original),))
            connection.execute("PRAGMA user_version=4")
        before = self.f.db.read_bytes()
        legacy = self.read()["strategies"]["items"][0]["intent"]
        self.assertEqual(legacy["risk"], "1")
        self.assertIsNone(legacy["context"])
        self.assertEqual(self.f.db.read_bytes(), before)
        with closing(sqlite3.connect(self.f.db)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 4)

    def test_strategy_pages_are_bounded_current_campaign_only_and_read_in_one_transaction(self):
        self.f.start()
        for index in range(22):
            intent_id = "idea-" + str(index)
            self.assertTrue(self.f.call("prepare", snapshot=self.f.snap(), action=self.f.entry(intent_id))["may_dispatch"])
            self.f.call("resolve", intent_id=intent_id, outcome="not_executed", evidence_ref="synthetic:none",
                        readback_verified=True, snapshot=self.f.snap())
        with closing(sqlite3.connect(self.f.db)) as connection, connection:
            base = checker.decode(connection.execute("SELECT payload FROM intents WHERE id='idea-0'").fetchone()[0], exact_numbers=False)
            for field in ("login", "server", "type", "currency", "policy_id", "goal_id"):
                foreign = copy.deepcopy(base)
                foreign["id"] = "foreign-" + field
                (foreign["account"] if field in fixtures.ACCOUNT else foreign)[field] = "different-scope"
                connection.execute("INSERT INTO intents(id,signal_key,status,payload) VALUES (?,NULL,'completed',?)",
                                   (foreign["id"], checker.encode(foreign)))
        before = self.f.db.read_bytes()
        real_page = checker.context_page
        calls = []

        def read_page(connection, state, **options):
            self.assertTrue(connection.in_transaction)
            with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
                connection.execute("UPDATE intents SET status='completed'")
            calls.append(options)
            return real_page(connection, state, **options)

        with patch.object(checker, "context_page", side_effect=read_page):
            first = self.read()
            second = self.read(strategy_before=first["strategies"]["next_cursor"])
        self.assertEqual(calls, [{"before": None, "limit": 20}, {"before": first["strategies"]["next_cursor"], "limit": 20}])
        self.assertEqual(len(first["strategies"]["items"]), 20)
        self.assertEqual(len(second["strategies"]["items"]), 2)
        self.assertIsNone(second["strategies"]["next_cursor"])
        ids = [item["intent"]["id"] for item in first["strategies"]["items"] + second["strategies"]["items"]]
        self.assertEqual(ids, ["idea-" + str(index) for index in reversed(range(22))])
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertEqual(first["revision"], second["revision"])
        self.assertEqual(self.f.db.read_bytes(), before)
        self.f.draft(target="20")
        self.f.activate_again("new_goal", self.f.snap())
        self.assertEqual(self.read()["strategies"], {"items": [], "next_cursor": None})
        for invalid in (0, -1, True, "1", 9223372036854775808):
            with self.assertRaisesRegex(checker.CheckError, "invalid_cursor"):
                self.read(strategy_before=invalid)
        with self.assertRaisesRegex(checker.CheckError, "conflicting_cursors"):
            self.read(before=2, strategy_before=2)

    def test_optional_strategy_lookup_failure_does_not_hide_canonical_loss_status(self):
        self.f.start()
        self.f.call("check", snapshot=self.f.snap("95"))
        expected = self.read()
        for failed_page in (None, {"items": "invalid", "next_cursor": None}):
            with patch.object(checker, "context_page", return_value=failed_page):
                data = self.read()
                self.assertEqual(data["stops"], expected["stops"])
                self.assertEqual(data["metrics"], expected["metrics"])
                self.assertIsNone(data["strategies"])
        with patch.object(checker, "context_page", side_effect=checker.CheckError("invalid_optional_context")):
            data = self.read()
            self.assertEqual(data["result"]["decision"], "loss_stop")
            self.assertIsNone(data["strategies"])
            self.assertTrue(data["warnings"])

    def test_http_strategy_pagination_is_read_only_and_rejects_scope_overrides(self):
        self.f.start()
        for intent_id in ("first", "second", "third"):
            self.f.call("prepare", snapshot=self.f.snap(), action=self.f.entry(intent_id))
            self.f.call("resolve", intent_id=intent_id, outcome="not_executed", evidence_ref="synthetic:none",
                        readback_verified=True, snapshot=self.f.snap())
        before = self.f.db.read_bytes()
        server = self.server()
        with patch.object(dashboard, "STRATEGY_PAGE_SIZE", 2):
            status, _, body = self.request(server)
            self.assertEqual(status, 200)
            page = json.loads(body)
            self.assertEqual(len(page["strategies"]["items"]), 2)
            route = "/api/dashboard?strategy_before=" + str(page["strategies"]["next_cursor"])
            status, _, body = self.request(server, route)
            self.assertEqual(status, 200)
            older = json.loads(body)
            self.assertEqual(older["strategies"]["items"][0]["intent"]["id"], "first")
            self.assertEqual(older["revision"], page["revision"])
            self.assertEqual(older["metrics"], page["metrics"])
            self.assertIsNone(older["strategies"]["next_cursor"])
        for query in ("strategy_before=0", "strategy_before=-1", "strategy_before=1.5", "strategy_before=01",
                      "strategy_before=9223372036854775808", "strategy_before=1&strategy_before=2",
                      "strategy_before=2&before=2", "strategy_before=1%20OR%201=1", "origin_intent_id=first",
                      "account=foreign", "goal_id=old", "limit=100000"):
            self.assertEqual(self.request(server, "/api/dashboard?" + query)[0], 400, query)
        self.assertEqual(self.request(server, route, method="POST")[0], 405)
        self.assertEqual(self.request(server, route, headers={"Origin": "https://foreign.example"})[0], 403)
        self.assertEqual(self.request(server, route, method="HEAD")[2], b"")
        self.assertEqual(self.f.db.read_bytes(), before)

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
        for version in (0, 6, 999):
            with self.subTest(version=version):
                with closing(sqlite3.connect(self.f.db)) as connection, connection:
                    connection.execute("PRAGMA user_version = " + str(version))
                before = self.f.db.read_bytes()
                with self.assertRaisesRegex(checker.CheckError, "unsupported_schema"):
                    self.read()
                status, _, body = self.request(server)
                error = json.loads(body)
                self.assertEqual(status, 503)
                self.assertEqual(error["error"], "unsupported_schema")
                self.assertFalse(error["ok"])
                self.assertEqual(error["status"], "unavailable")
                self.assertNotIn(str(self.f.db), body.decode())
                self.assertEqual(dashboard.probe_dashboard(self.f.db, server.server_port), "compatible")
                self.assertEqual(self.f.db.read_bytes(), before)
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
