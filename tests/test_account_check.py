"""Synthetic account fixtures only. No MT5, credentials, or production state."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import account_check as checker


ACCOUNT = {"login": "synthetic-001", "server": "synthetic-broker", "type": "demo", "currency": "USD"}
MANDATE = {
    "symbols": ["EURUSD", "GBPUSD", "XAUUSD"],
    "max_snapshot_age_seconds": 60, "safety_margin": "0.5",
    "allow_entries": True, "allow_management": True, "close_all_on_loss": True,
    "close_all_on_target": True, "accept_observed_only": True,
}


def position(ticket="p1", risk="1", **changes):
    result = {"ticket": ticket, "symbol": "EURUSD", "protected": True, "risk": risk}
    result.update(changes)
    return result


class AccountCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-test-", dir=os.environ.get("ACE_TEST_TMPDIR"))
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "state.sqlite3"
        self.now = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
        self.anchor = None
        self.sequence = 0
        self.revision = 0

    def call(self, command, **request):
        request.setdefault("owner_id", "synthetic-owner")
        request.setdefault("expected_revision", self.revision)
        result = checker.run(command, request, self.db, self.now)
        self.revision = result["revision"]
        return result

    def state(self):
        return checker.run("status", db_path=self.db, now=self.now)["state"]

    def snap(self, equity="100", **changes):
        self.now += timedelta(seconds=1)
        self.sequence += 1
        as_of = checker.utc(self.now)
        if self.anchor is None:
            self.anchor = as_of
        result = {"id": "synthetic-snapshot-" + str(self.sequence), "account": ACCOUNT,
                  "source_ref": "synthetic-mcp-read-" + str(self.sequence), "as_of": as_of,
                  "history_anchor": self.anchor, "history_through": as_of,
                  "history_cursor": "synthetic-history-" + str(self.sequence), "history_complete": True,
                  "cashflows": [], "balance": equity, "equity": equity, "free_margin": "100",
                  "remaining_close_costs": "0", "costs_final": True, "trading_enabled": True,
                  "positions": [], "pending_orders": []}
        result.update(changes)
        return result

    def draft(self, **values):
        return self.call("draft", account=ACCOUNT, source_ref="synthetic-account-read", **values)

    def start(self, budget="5", target="15", equity="100", **snapshot_changes):
        self.draft(budget=budget, target=target, mandate=MANDATE)
        self.anchor = None
        sample = self.snap(equity, **snapshot_changes)
        result = self.call("activate", mode="start", mandate=MANDATE, baseline=sample, snapshot=sample,
                           approval_ref="synthetic-final-approval", approved_at=checker.utc(self.now))
        self.assertIsNotNone(self.state()["policy"])
        return result

    def entry(self, action_id="a1", risk="1", **changes):
        state = self.state()
        result = {"id": action_id, "kind": "entry", "tool": "synthetic_mcp.place_order",
                  "authority_ref": "synthetic-final-approval", "tool_permission": True,
                  "policy_id": state["policy"]["id"], "goal_id": state["goal"]["id"],
                  "symbol": "EURUSD", "analysis_ref": "synthetic-h1-trend-read", "signal_id": "signal-" + action_id,
                  "risk": risk, "margin": "10",
                  "broker_checks_passed": True, "protective_stop_in_request": True,
                  "parameters": {"symbol": "EURUSD", "volume": Decimal("0.01"), "sl": Decimal("1.09"), "side": "buy"}}
        result.update(changes)
        return result

    def reduction(self, action_id="r1", ticket="p1", reason="management", **changes):
        state = self.state()
        result = {"id": action_id, "kind": "reduce", "tool": "synthetic_mcp.close_position",
                  "authority_ref": "synthetic-final-approval", "tool_permission": True,
                  "policy_id": state["policy"]["id"], "goal_id": state["goal"]["id"],
                  "reason": reason, "tickets": [ticket], "reduction_verified": True,
                  "parameters": {"ticket": ticket}}
        result.update(changes)
        return result

    def activate_again(self, mode, sample=None, **changes):
        if sample is None:
            sample = self.snap()
        if mode == "start":
            self.anchor = sample["as_of"]
            sample["history_anchor"] = self.anchor
        request = {"mode": mode, "mandate": MANDATE, "snapshot": sample,
                   "approval_ref": "synthetic-new-approval", "approved_at": checker.utc(self.now)}
        if mode not in ("resume", "reauthorize"):
            request["baseline"] = copy.deepcopy(sample)
        request.update(changes)
        return self.call("activate", **request)

    def test_import_help_and_absent_status_do_not_create_state(self):
        result = self.call("status")
        self.assertEqual(result["decision"], "unconfigured")
        self.assertFalse(self.db.exists())
        with patch("sqlite3.connect", side_effect=AssertionError("import must not open a DB")):
            spec = importlib.util.spec_from_file_location("isolated_checker", checker.__file__)
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
        self.assertEqual(checker.DEFAULT_DB, Path(checker.__file__).resolve().parents[1] / "ace_state.sqlite3")
        process = subprocess.run([sys.executable, checker.__file__, "--help", "--db", str(self.db)],
                                 cwd=self.temp.name, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0)
        self.assertFalse(self.db.exists())

    def test_draft_accepts_both_or_one_amount_without_approval(self):
        self.draft(budget="5")
        self.draft(target="15")
        state = self.state()
        self.assertEqual(state["draft"]["budget"], "5")
        self.assertEqual(state["draft"]["target"], "15")
        self.assertIsNone(state["policy"])
        with self.assertRaisesRegex(checker.CheckError, "setup_incomplete"):
            self.call("check", snapshot=self.snap())
        with self.assertRaisesRegex(checker.CheckError, "invalid_approval_ref"):
            self.activate_again("start", approval_ref="")
        self.assertIsNone(self.state()["policy"])

    def test_invalid_money_never_creates_first_database(self):
        for value in ("0", "-1", "NaN", "Infinity", "1e9999", "1e-99", "1_000", " 5 ", "$5", True, 5.0, None):
            with self.subTest(value=repr(value)):
                with self.assertRaises(checker.CheckError):
                    self.draft(budget=value, target="15")
                self.assertFalse(self.db.exists())
        self.draft(budget="5", target="15")
        self.assertTrue(self.db.exists())

    def test_baseline_approval_and_required_mandate(self):
        self.draft(budget="5", target="15", mandate=MANDATE)
        for field in ("close_all_on_loss", "close_all_on_target", "accept_observed_only", "symbols", "safety_margin"):
            with self.subTest(field=field):
                config = copy.deepcopy(MANDATE)
                config.pop(field)
                with self.assertRaises(checker.CheckError):
                    self.activate_again("start", mandate=config)
        sample = self.snap()
        with self.assertRaisesRegex(checker.CheckError, "baseline_not_in_approval"):
            self.activate_again("start", sample, approved_at=checker.utc(self.now - timedelta(seconds=1)))
        with self.assertRaisesRegex(checker.CheckError, "nonpositive_baseline"):
            self.activate_again("start", self.snap("0"))

    def test_trailing_money_and_equality(self):
        initial = self.start()
        self.assertEqual(initial["metrics"]["account_stop_floor"], "95")
        self.call("check", snapshot=self.snap("110"))
        lower = self.call("check", snapshot=self.snap("108"))
        self.assertEqual(lower["metrics"]["peak"], "110")
        self.assertEqual(lower["metrics"]["remaining_risk"], "3")
        self.assertEqual(lower["metrics"]["account_stop_floor"], "105")
        stopped = self.call("check", snapshot=self.snap("105"))
        self.assertEqual(stopped["decision"], "loss_stop")
        self.assertEqual(stopped["metrics"]["remaining_risk"], "0")
        overshot = self.call("check", snapshot=self.snap("103"))
        self.assertEqual(overshot["metrics"]["remaining_risk"], "-2")

    def test_only_observed_peaks_and_cashflows_do_not_duplicate(self):
        self.start()
        deposited = self.snap("300")
        flow = {"id": "deposit", "at": deposited["as_of"], "amount": "200"}
        deposited["cashflows"] = [flow]
        report = self.call("check", snapshot=deposited)
        self.assertEqual(report["metrics"]["peak"], "100")
        self.assertEqual(report["metrics"]["estimated_goal_gain"], "0")
        withdrawal = self.snap("250")
        withdrawal["cashflows"] = [flow, {"id": "withdrawal", "at": withdrawal["as_of"], "amount": "-50"}]
        report = self.call("check", snapshot=withdrawal)
        self.assertEqual(report["metrics"]["drawdown"], "0")
        self.assertEqual(report["metrics"]["goal_cashflows"], "150")
        repeated = self.call("check", snapshot=withdrawal)
        self.assertEqual(repeated["metrics"]["goal_cashflows"], "150")
        duplicate = self.snap("250", cashflows=[flow, flow])
        self.assertIn("duplicate_or_out_of_window_cashflow", self.call("check", snapshot=duplicate)["reason_codes"])
        removed = self.call("check", snapshot=self.snap("250"))
        self.assertIn("cashflow_history_changed", removed["reason_codes"])
        self.assertEqual(self.state()["peak"], "100")

    def test_incomplete_history_cannot_turn_deposit_into_profit(self):
        self.start()
        result = self.call("check", snapshot=self.snap("300", history_complete=False))
        self.assertIsNone(result["metrics"])
        self.assertEqual(self.state()["peak"], "100")
        self.assertIsNone(self.state()["target_latched_at"])

    def test_backdated_cashflow_cannot_expand_headroom(self):
        self.start()
        previous = self.snap("110")
        self.call("check", snapshot=previous)
        sample = self.snap("108", cashflows=[{"id": "late-withdrawal", "at": previous["as_of"], "amount": "-5"}])
        result = self.call("prepare", snapshot=sample, action=self.entry(risk="4"))
        self.assertFalse(result["may_dispatch"])
        self.assertIn("backdated_cashflow_requires_reconciliation", result["reason_codes"])
        self.assertEqual(self.state()["peak"], "110")
        self.assertEqual(self.state()["last_snapshot"]["as_of"], previous["as_of"])

    def test_slow_approval_preserves_frozen_baseline_with_fresh_readback(self):
        self.draft(budget="5", target="15", mandate=MANDATE)
        baseline = self.snap()
        self.now += timedelta(minutes=3)
        approved_at = checker.utc(self.now)
        current = self.snap("308")
        current["cashflows"] = [{"id": "deposit-during-review", "at": approved_at, "amount": "200"}]
        result = self.call("activate", mode="start", mandate=MANDATE, baseline=baseline, snapshot=current,
                           approval_ref="synthetic-reviewed-baseline", approved_at=approved_at)
        self.assertEqual(self.state()["goal"]["start_equity"], "100")
        self.assertEqual(self.state()["policy"]["started_at"], baseline["as_of"])
        self.assertEqual(result["metrics"]["peak"], "108")
        self.assertEqual(result["metrics"]["estimated_goal_gain"], "8")
        self.assertEqual(result["decision"], "within_budget")

    def test_loss_at_activation_is_not_hidden_by_rebasing(self):
        self.draft(budget="5", target="15", mandate=MANDATE)
        baseline = self.snap()
        self.now += timedelta(minutes=2)
        approved_at = checker.utc(self.now)
        result = self.call("activate", mode="start", mandate=MANDATE, baseline=baseline, snapshot=self.snap("95"),
                           approval_ref="synthetic-reviewed-baseline", approved_at=approved_at)
        self.assertEqual(result["decision"], "loss_stop")
        self.assertEqual(self.state()["peak"], "100")

    def test_invalid_activation_objects_are_json_errors(self):
        self.draft(budget="5", target="15", mandate=MANDATE)
        baseline = self.snap()
        for value in (None, [], "invalid"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(checker.CheckError, "missing_snapshot"):
                    self.call("activate", mode="start", mandate=MANDATE, baseline=baseline, snapshot=value,
                              approval_ref="synthetic-approval", approved_at=checker.utc(self.now))
                with self.assertRaisesRegex(checker.CheckError, "missing_approval_baseline"):
                    self.call("activate", mode="start", mandate=MANDATE, baseline=value, snapshot=baseline,
                              approval_ref="synthetic-approval", approved_at=checker.utc(self.now))
        body = {"owner_id": "synthetic-owner", "expected_revision": self.revision, "mode": "start", "mandate": MANDATE,
                "baseline": baseline, "snapshot": None, "approval_ref": "synthetic-approval",
                "approved_at": checker.utc(datetime.now(timezone.utc))}
        process = subprocess.run([sys.executable, checker.__file__, "activate", "--db", str(self.db)],
                                 input=json.dumps(body), text=True, capture_output=True, cwd=self.temp.name, check=False)
        self.assertEqual(process.returncode, 2)
        self.assertIn("missing_snapshot", json.loads(process.stdout)["reason_codes"])
        self.assertNotIn("Traceback", process.stderr)

    def test_new_goal_preserves_policy_and_separate_flow_windows(self):
        self.start()
        deposited = self.snap("300")
        flow = {"id": "deposit", "at": deposited["as_of"], "amount": "200"}
        deposited["cashflows"] = [flow]
        self.call("check", snapshot=deposited)
        policy = copy.deepcopy(self.state()["policy"])
        self.draft(target="20")
        self.activate_again("new_goal", self.snap("300", cashflows=[flow]))
        sample = self.snap("350")
        sample["cashflows"] = [flow, {"id": "deposit2", "at": sample["as_of"], "amount": "50"}]
        report = self.call("check", snapshot=sample)
        self.assertEqual(self.state()["policy"], policy)
        self.assertEqual(report["metrics"]["policy_cashflows"], "250")
        self.assertEqual(report["metrics"]["goal_cashflows"], "50")
        self.assertEqual(report["metrics"]["estimated_goal_gain"], "0")
        self.assertEqual(self.state()["peak"], "100")

    def test_proposal_shares_remaining_risk_and_rejects_equality(self):
        self.start()
        self.call("check", snapshot=self.snap("110"))
        sample = self.snap("108", positions=[position()])
        denied = self.call("prepare", snapshot=sample, action=self.entry(risk="1.5"))
        self.assertFalse(denied["may_dispatch"])
        self.assertIn("insufficient_headroom", denied["reason_codes"])
        self.assertEqual(self.call("status")["outstanding_intents"], [])
        accepted = self.call("prepare", snapshot=sample, action=self.entry(risk="1.49"))
        self.assertTrue(accepted["may_dispatch"])

    def test_pending_risk_and_floating_gain_reversal_count(self):
        self.start()
        sample = self.snap("103", positions=[position(risk="3")],
                           pending_orders=[position("order1", "1", kind="entry")])
        result = self.call("prepare", snapshot=sample, action=self.entry(risk="0.5"))
        self.assertEqual(result["metrics"]["existing_risk"], "4")
        self.assertIn("insufficient_headroom", result["reason_codes"])

    def test_unknown_exposure_and_costs_block_entries_not_loss_latch(self):
        self.start()
        sample = self.snap("95", positions=None, remaining_close_costs=None, free_margin=None)
        result = self.call("prepare", snapshot=sample, action=self.entry())
        self.assertEqual(result["decision"], "loss_stop")
        self.assertFalse(result["may_dispatch"])
        self.assertIsNotNone(self.state()["loss_latched_at"])
        self.assertEqual(result["required_action"], "cancel_entries_and_close_all")

    def test_invalid_execution_inputs_and_unapproved_scope(self):
        self.start()
        for changes, code in (({"risk": "5"}, "insufficient_headroom"),
                              ({"margin": "101"}, "insufficient_margin"),
                              ({"symbol": "UNAPPROVED"}, "unapproved_symbol"),
                              ({"analysis_ref": ""}, "invalid_analysis_ref"),
                              ({"tool_permission": False}, "missing_tool_permission"),
                              ({"broker_checks_passed": False}, "missing_broker_checks_passed"),
                              ({"protective_stop_in_request": False}, "missing_protective_stop_in_request"),
                              ({"goal_id": "wrong"}, "action_mandate_mismatch")):
            with self.subTest(code=code):
                result = self.call("prepare", snapshot=self.snap(), action=self.entry(**changes))
                self.assertFalse(result["may_dispatch"])
                self.assertIn(code, result["reason_codes"])
        result = self.call("prepare", snapshot=self.snap(positions=[position(protected=False)]), action=self.entry())
        self.assertIn("unprotected_exposure", result["reason_codes"])

    def test_real_dispatch_path_is_enabled_without_reapproval_per_trade(self):
        self.start()
        original_approval = self.state()["approval_ref"]
        prepared = self.call("prepare", snapshot=self.snap(), action=self.entry())
        self.assertTrue(prepared["may_dispatch"])
        self.assertEqual(prepared["intent"]["tool"], "synthetic_mcp.place_order")
        self.assertEqual(prepared["intent"]["account"], ACCOUNT)
        self.assertEqual(prepared["intent"]["parameters"]["sl"], 1.09)
        self.assertIsInstance(prepared["intent"]["parameters"]["volume"], float)
        # This represents verified MCP readback, not an actual network call.
        resolved = self.call("resolve", intent_id="a1", outcome="completed", evidence_ref="synthetic-fill-and-stops",
                             readback_verified=True, broker_tickets=["p1"], snapshot=self.snap(positions=[position()]))
        self.assertNotIn("unresolved_intents", resolved["reason_codes"])
        second = self.call("prepare", snapshot=self.snap(positions=[position()]), action=self.entry("a2"))
        self.assertTrue(second["may_dispatch"])
        self.assertEqual(self.state()["approval_ref"], original_approval)
        cached = self.call("status")
        self.assertFalse(cached["may_dispatch"])

    def test_unknown_intent_and_missing_readback_block_reuse(self):
        self.start()
        sample = self.snap()
        self.call("prepare", snapshot=sample, action=self.entry())
        unknown = self.call("resolve", intent_id="a1", outcome="unknown", evidence_ref="synthetic-timeout", snapshot=sample)
        self.assertIn("unresolved_intents", unknown["reason_codes"])
        blocked = self.call("prepare", snapshot=self.snap(), action=self.entry("a2"))
        self.assertFalse(blocked["may_dispatch"])
        self.assertIn("unresolved_intents", blocked["reason_codes"])
        unresolved = self.call("resolve", intent_id="a1", outcome="not_executed", evidence_ref="empty-orders-is-not-proof",
                               snapshot=self.snap())
        self.assertIn("outcome_readback_required", unresolved["reason_codes"])
        self.assertEqual(len(self.call("status")["outstanding_intents"]), 1)
        self.call("resolve", intent_id="a1", outcome="not_executed", evidence_ref="synthetic-authoritative-rejection",
                  readback_verified=True, snapshot=self.snap())
        duplicate = self.call("prepare", snapshot=self.snap(), action=self.entry())
        self.assertIn("duplicate_action_or_signal", duplicate["reason_codes"])

    def test_pre_preparation_snapshot_cannot_settle_an_intent(self):
        self.start()
        old = self.snap()
        self.now += timedelta(seconds=30)
        prepared = self.call("prepare", snapshot=old, action=self.entry())
        not_post_action = dict(old, id="still-before-preparation", source_ref="synthetic-old-read",
                               as_of=checker.utc(checker.stamp(old["as_of"], "as_of") + timedelta(seconds=1)),
                               history_through=checker.utc(self.now), history_cursor="synthetic-old-cursor")
        result = self.call("resolve", intent_id="a1", outcome="completed", readback_verified=True,
                           broker_tickets=["p1"], evidence_ref="synthetic-not-post-action", snapshot=not_post_action)
        self.assertIn("post_action_snapshot_required", result["reason_codes"])
        self.assertLess(not_post_action["as_of"], prepared["intent"]["created_at"])
        self.assertEqual(len(self.call("status")["outstanding_intents"]), 1)
        self.assertFalse(self.call("prepare", snapshot=self.snap(), action=self.entry("a2"))["may_dispatch"])

    def test_owner_handoff_retains_and_can_reconcile_unknown_intents(self):
        self.start()
        self.call("prepare", snapshot=self.snap(), action=self.entry())
        self.call("resolve", intent_id="a1", outcome="unknown", evidence_ref="synthetic-timeout", snapshot=self.snap())
        original = self.state()
        self.draft(target="20")  # An unapproved draft must not prevent ownership recovery.
        result = self.activate_again("resume", self.snap(), owner_id="new-owner", takeover_ref="synthetic-old-owner-stopped")
        self.assertEqual(self.state()["owner_id"], "new-owner")
        self.assertEqual(self.state()["policy"], original["policy"])
        self.assertEqual(self.state()["goal"], original["goal"])
        self.assertIn("unresolved_intents", result["reason_codes"])
        status = self.call("status")
        self.assertEqual(status["outstanding_intents"][0]["status"], "unknown")
        self.assertEqual(status["outstanding_intents"][0]["outcome"]["evidence_ref"], "synthetic-timeout")
        resolved = self.call("resolve", owner_id="new-owner", intent_id="a1", outcome="not_executed",
                             evidence_ref="synthetic-terminal-rejection", readback_verified=True, snapshot=self.snap())
        self.assertNotIn("unresolved_intents", resolved["reason_codes"])

    def test_mcp_numeric_parameter_types_and_secret_rejection(self):
        self.start()
        denied = self.call("prepare", snapshot=self.snap(), action=self.entry(parameters={"password": "synthetic-do-not-store"}))
        self.assertIn("credentials_in_parameters", denied["reason_codes"])
        self.assertNotIn("synthetic-do-not-store", checker.encode(self.state()))
        prepared = self.call("prepare", snapshot=self.snap(), action=self.entry())
        wire = json.loads(checker.encode(prepared))
        self.assertIsInstance(wire["intent"]["parameters"]["volume"], float)
        persisted = self.call("status")["outstanding_intents"][0]["action"]["parameters"]
        self.assertEqual(persisted["volume"], 0.01)
        self.assertEqual(persisted["sl"], 1.09)

    def test_saved_proposal_binding_and_mandate_reauthorization_preserve_money(self):
        self.start()
        self.call("check", snapshot=self.snap("104"))
        old = self.state()
        changed = dict(MANDATE, symbols=["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"])
        denied = self.activate_again("reauthorize", self.snap("103"), mandate=changed)
        self.assertIn("mandate_differs_from_saved_proposal", denied["reason_codes"])
        self.draft(mandate=changed)
        approved = self.activate_again("reauthorize", self.snap("102"), mandate=changed)
        self.assertEqual(approved["decision"], "within_budget")
        self.assertEqual(self.state()["policy"], old["policy"])
        self.assertEqual(self.state()["goal"], old["goal"])
        self.assertEqual(self.state()["peak"], "104")
        self.assertEqual(self.state()["mandate"], changed)
        self.assertEqual(approved["metrics"]["estimated_goal_gain"], "2")

    def test_partial_fill_is_reconciled_not_treated_as_flat(self):
        self.start()
        self.call("prepare", snapshot=self.snap(), action=self.entry())
        resolved = self.call("resolve", intent_id="a1", outcome="completed", evidence_ref="synthetic-terminal-partial-fill",
                             readback_verified=True, broker_tickets=["p1", "remaining-order"],
                             snapshot=self.snap(positions=[position(risk="0.5")],
                                                pending_orders=[position("remaining-order", "0.5", kind="entry")]))
        self.assertFalse(resolved["closure_verified"])
        self.assertEqual(resolved["metrics"]["existing_risk"], "1.0")

    def test_goal_cost_boundary_and_final_shortfall_stay_stopped(self):
        self.start()
        not_yet = self.call("check", snapshot=self.snap("115", remaining_close_costs="0.5"))
        self.assertEqual(not_yet["metrics"]["estimated_goal_gain"], "14.5")
        self.assertIsNone(not_yet["target_latched_at"])
        crossing = self.call("check", snapshot=self.snap("115.5", remaining_close_costs="0.5",
                                                        positions=[position("manual", "2")], costs_final=False))
        self.assertEqual(crossing["decision"], "target_stop")
        self.assertEqual(crossing["required_action"], "cancel_entries_and_close_all")
        sample = self.snap("115.5", positions=[position("manual", "2")], remaining_close_costs="0.5", costs_final=False)
        prepared = self.call("prepare", snapshot=sample, action=self.reduction(ticket="manual", reason="target"))
        self.assertTrue(prepared["may_dispatch"])
        final = self.call("resolve", intent_id="r1", outcome="completed", readback_verified=True,
                          broker_tickets=["manual"], evidence_ref="synthetic-flat-readback", snapshot=self.snap("114.7"))
        self.assertEqual(final["decision"], "target_stop")
        self.assertTrue(final["closure_verified"])
        self.assertEqual(final["metrics"]["final_net"], "14.7")
        self.assertEqual(final["metrics"]["final_shortfall"], "0.3")
        self.assertFalse(self.call("prepare", snapshot=self.snap("114.7"), action=self.entry())["may_dispatch"])

    def test_carry_in_equity_and_unknown_costs_are_not_profit(self):
        self.start(equity="110", positions=[position()])
        report = self.call("check", snapshot=self.snap("115", positions=[position()]))
        self.assertEqual(report["metrics"]["estimated_goal_gain"], "5")
        unknown = self.call("check", snapshot=self.snap("130", remaining_close_costs=None))
        self.assertIsNone(unknown["metrics"]["estimated_goal_gain"])
        self.assertIsNone(unknown["target_latched_at"])

    def test_latches_survive_midnight_recovery_resume_and_corrections(self):
        self.start()
        loss = self.call("check", snapshot=self.snap("95"))["loss_latched_at"]
        self.now += timedelta(days=1)
        recovered = self.activate_again("resume", self.snap("101"), approved_at="2026-11-03T20:00:01Z")
        self.assertEqual(recovered["loss_latched_at"], loss)
        self.assertEqual(recovered["decision"], "loss_stop")
        denied = self.activate_again("new_goal", self.snap("101"))
        self.assertIn("loss_requires_replacement_policy", denied["reason_codes"])
        old_policy = self.state()["policy"]["id"]
        sample = self.snap("101")
        sample["history_anchor"] = sample["as_of"]
        reset = self.activate_again("replace_policy", sample, reset_reason="synthetic-explicit-reset-approval")
        self.assertIsNone(reset["loss_latched_at"])
        self.assertNotEqual(reset["policy_id"], old_policy)
        self.assertEqual(reset["metrics"]["peak"], "101")
        with closing(sqlite3.connect(self.db)) as connection, connection:
            detail = json.loads(connection.execute("SELECT detail FROM events WHERE command='activate' ORDER BY id DESC LIMIT 1").fetchone()[0])
        self.assertEqual(detail["previous_state"]["loss_latched_at"], loss)

    def test_rejected_activation_still_records_a_new_breach(self):
        self.start()
        result = self.activate_again("new_goal", self.snap("95"))
        self.assertEqual(result["decision"], "loss_stop")
        self.assertIsNotNone(self.state()["loss_latched_at"])

    def test_loss_precedes_target_and_safety_reductions_remain_available(self):
        self.start()
        self.call("check", snapshot=self.snap("120", remaining_close_costs="10", costs_final=False))
        sample = self.snap("115", positions=[position(protected=False)])
        stopped = self.call("check", snapshot=sample)
        self.assertEqual(stopped["decision"], "loss_stop")
        self.assertIsNotNone(stopped["target_latched_at"])
        reduction = self.call("prepare", snapshot=sample, action=self.reduction(reason="loss"))
        self.assertTrue(reduction["may_dispatch"])
        repeated = self.call("prepare", snapshot=self.snap("115", positions=[position(protected=False)]),
                             action=self.reduction("r2", reason="loss"))
        self.assertIn("overlapping_reduction", repeated["reason_codes"])

    def test_stale_future_mixed_account_and_conflicting_snapshot_rejected(self):
        self.start()
        sample = self.snap("104")
        self.call("check", snapshot=sample)
        peak = self.state()["peak"]
        variants = [dict(sample, equity="150"),
                    dict(sample, account=dict(ACCOUNT, currency="EUR")),
                    dict(sample, as_of=checker.utc(self.now + timedelta(seconds=1))),
                    dict(sample, as_of=checker.utc(self.now - timedelta(seconds=61))),
                    dict(sample, as_of=checker.utc(self.now - timedelta(seconds=1)))]
        for invalid in variants:
            result = self.call("check", snapshot=invalid)
            self.assertIsNone(result["metrics"])
            self.assertFalse(result["may_dispatch"])
            self.assertEqual(self.state()["peak"], peak)

    def test_two_competing_preparations_cannot_spend_same_headroom(self):
        self.start()
        sample = self.snap()
        requests = [{"expected_revision": self.revision, "owner_id": "synthetic-owner", "snapshot": sample,
                     "action": self.entry(name, "3")} for name in ("a1", "a2")]

        def prepare(request):
            try:
                return checker.run("prepare", request, self.db, self.now)
            except checker.CheckError as error:
                return str(error)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(prepare, requests))
        self.assertEqual(sum(isinstance(result, dict) and result["may_dispatch"] for result in results), 1)
        self.assertIn("revision_mismatch", results)
        self.assertEqual(len(checker.run("status", db_path=self.db)["outstanding_intents"]), 1)

    def test_owner_and_schema_and_local_tampering_fail_closed(self):
        self.start()
        with self.assertRaisesRegex(checker.CheckError, "owner_mismatch"):
            self.call("check", owner_id="other-owner", snapshot=self.snap())
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("PRAGMA user_version=999")
        with self.assertRaisesRegex(checker.CheckError, "unsupported_schema"):
            self.call("status")
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("PRAGMA user_version=1")
            connection.execute("UPDATE state SET payload='{}'")
        with self.assertRaisesRegex(checker.CheckError, "state_audit_mismatch"):
            self.call("status")

    def test_sqlite_contention_and_missing_state_do_not_reinitialize(self):
        with self.assertRaisesRegex(checker.CheckError, "setup_incomplete"):
            self.call("check", snapshot=self.snap())
        self.assertFalse(self.db.exists())
        self.start()
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(checker.CheckError, "database_unavailable_or_corrupt"):
                self.call("check", snapshot=self.snap())
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("DELETE FROM state")
        with self.assertRaisesRegex(checker.CheckError, "missing_account_state"):
            self.call("status")

    def test_csv_is_not_read_imported_or_required(self):
        legacy = Path(self.temp.name) / "risk_management.csv"
        legacy.write_text("untrusted,legacy,records\nnot,new,approval\n", encoding="utf-8")
        result = self.start()
        self.assertEqual(result["decision"], "within_budget")
        self.assertEqual(legacy.read_text(encoding="utf-8"), "untrusted,legacy,records\nnot,new,approval\n")
        self.assertNotIn("untrusted", checker.encode(self.state()))

    def test_cli_json_path_independence_and_invalid_requests(self):
        base = [sys.executable, checker.__file__]
        body = {"owner_id": "synthetic-owner", "expected_revision": 0, "account": ACCOUNT,
                "source_ref": "synthetic-account", "budget": "5", "target": "15"}
        result = subprocess.run(base + ["draft", "--db", str(self.db)], input=json.dumps(body),
                                text=True, capture_output=True, cwd=self.temp.name, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "draft_saved")
        for invalid in ('{"budget":NaN}', '{"budget":"5","budget":"6"}', '[]', '{'):
            result = subprocess.run(base + ["draft", "--db", str(self.db)], input=invalid,
                                    text=True, capture_output=True, cwd=self.temp.name, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["may_dispatch"])
        decimal_request = checker.decode('{"budget": 0.1}')
        self.assertEqual(decimal_request["budget"], Decimal("0.1"))


if __name__ == "__main__":
    unittest.main()
