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

    def start(self, budget="5", target="15", equity="100", config=None, approval_mode="reviewed", **snapshot_changes):
        config = MANDATE if config is None else config
        self.draft(budget=budget, target=target, mandate=config)
        self.anchor = None
        requested_at = checker.utc(self.now)
        sample = self.snap(equity, **snapshot_changes)
        result = self.call("activate", mode="start", mandate=config, baseline=sample, snapshot=sample,
                           approval_ref="synthetic-final-approval", approval_mode=approval_mode,
                           approved_at=requested_at if approval_mode == "start_request" else checker.utc(self.now))
        self.assertIsNotNone(self.state()["policy"])
        return result

    def control(self, action, evidence_ref=None, **changes):
        return self.call("session", action=action, evidence_ref=evidence_ref or "synthetic:user-" + action,
                         reason="Synthetic session " + action, **changes)

    def entry(self, action_id="a1", risk="1", **changes):
        state = self.state()
        result = {"id": action_id, "kind": "entry", "tool": "synthetic_mcp.place_order",
                  "authority_ref": "synthetic-final-approval", "tool_permission": True,
                  "policy_id": state["policy"]["id"], "goal_id": state["goal"]["id"],
                  "symbol": "EURUSD", "analysis_ref": "synthetic-h1-trend-read", "signal_id": "signal-" + action_id,
                   "risk": risk, "margin": "10",
                   "broker_checks_passed": True, "protective_stop_in_request": True,
                   "parameters": {"symbol": "EURUSD", "volume": Decimal("0.01"), "sl": Decimal("1.09"), "side": "buy"},
                   "context": {"version": 1, "operation": "entry", "rationale": "Confirmed pullback within the original risk allocation.",
                               "source_refs": ["synthetic:closed-bar"], "origin_intent_id": None,
                               "strategy": {"name": "Trend pullback", "thesis": "Confirmed support holds within the higher-timeframe trend.",
                                            "side": "buy", "timeframe": state["mandate"].get("entry_timeframe", "M15"),
                                            "invalidation": "Close below confirmed support.", "expiry_rule": "Cancel at the verified session close.",
                                            "breakeven_rule": "After a confirmed favorable move with costs covered.",
                                            "trailing_rule": "Tighten behind confirmed higher lows.",
                                            "addition_rule": "Only profitable, protected earlier legs within the original allocation."}}}
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
        with closing(sqlite3.connect(self.db)) as connection:
            display = json.loads(connection.execute("SELECT detail FROM events ORDER BY id DESC LIMIT 1").fetchone()[0])["display"]
        self.assertTrue(display["closure_verified"])
        self.assertEqual(display["metrics"]["final_net"], "14.7")
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

    def clock(self, minutes=15, symbol="EURUSD"):
        # Synthetic broker boundaries, not the production scheduling algorithm.
        boundary = self.now.replace(minute=self.now.minute // minutes * minutes, second=0, microsecond=0)
        return {"symbol": symbol, "source_ref": "synthetic:broker-calendar", "as_of": checker.utc(self.now),
                "last_boundary_at": checker.utc(boundary),
                "next_boundary_at": checker.utc(boundary + timedelta(minutes=minutes))}

    def bar(self, minutes_ago=0, minutes=15, symbol="EURUSD"):
        closed = checker.stamp(self.clock(minutes, symbol)["last_boundary_at"], "boundary") - timedelta(minutes=minutes_ago)
        return {"symbol": symbol, "source_ref": "synthetic:closed-bar", "confirmed": True,
                "open_time": checker.utc(closed - timedelta(minutes=minutes)), "close_time": checker.utc(closed)}

    def test_cycle_opens_session_and_schedules_next_candle(self):
        self.start()
        self.now += timedelta(seconds=5)
        result = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar(), market_state="open")
        loop = result["loop"]
        self.assertTrue(result["may_continue"])
        self.assertEqual(loop["status"], "active")
        self.assertEqual(loop["cycles"], 1)
        self.assertEqual(loop["timeframe"], "M15")
        self.assertEqual(loop["market_state"], "open")
        self.assertTrue(loop["bar_confirmed"])
        self.assertEqual(loop["next_cycle_at"], "2026-11-03T20:15:05Z")
        self.assertEqual(loop["next_wake_at"], "2026-11-03T20:15:05Z")
        self.assertEqual(loop["wake_reason"], "candle")
        self.assertEqual(loop["policy_id"], self.state()["policy"]["id"])
        self.assertGreater(loop["next_cycle_at"], self.state()["last_snapshot"]["as_of"])

    def test_cycle_records_gap_and_missing_bar_without_ending(self):
        self.start()
        self.now += timedelta(seconds=5)
        closed_bar = self.bar()
        first = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=closed_bar)
        self.assertEqual(first["loop"]["cycles"], 1)
        self.now += timedelta(minutes=20)
        second = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=closed_bar)
        loop = second["loop"]
        self.assertTrue(second["may_continue"])
        self.assertEqual(loop["status"], "active")
        self.assertEqual(loop["cycles"], 2)
        self.assertEqual(loop["missing_bars"], 1)
        self.assertFalse(loop["bar_advanced"])
        self.assertGreaterEqual(loop["gap_seconds"], 1200)
        self.assertGreaterEqual(loop["max_gap_seconds"], loop["gap_seconds"])

    def test_cycle_market_closed_and_no_bar_still_continues(self):
        self.start()
        result = self.call("cycle", snapshot=self.snap(), clock=self.clock(),
                           market_state="closed")
        self.assertTrue(result["may_continue"])
        self.assertEqual(result["loop"]["status"], "active")
        self.assertEqual(result["loop"]["market_state"], "closed")

    def test_cycle_latches_and_closes_only_after_verified_flat(self):
        self.start(budget="5", target="15")
        sample = self.snap(equity="94", pending_orders=[{"ticket": "o1", "symbol": "EURUSD",
                                                         "kind": "entry", "protected": True, "risk": "1"}])
        result = self.call("cycle", snapshot=sample, bar=self.bar())
        self.assertTrue(result["may_continue"])
        self.assertEqual(result["loop"]["status"], "closing")
        self.assertEqual(result["loop"]["end_reason"], "loss_latch")
        self.assertIsNone(result["loop"]["ended_at"])
        final = self.call("cycle", snapshot=self.snap(equity="94"), bar=self.bar())
        self.assertEqual(final["loop"]["status"], "closed")
        self.assertEqual(final["loop"]["end_reason"], "loss_latch")
        self.assertIsNotNone(final["loop"]["ended_at"])
        self.assertFalse(final["may_continue"])

    def test_cycle_rejects_invalid_timing_inputs(self):
        self.start()
        for timeframe in ("M7", "m15", "", None, 15):
            with self.subTest(timeframe=repr(timeframe)):
                result = self.call("cycle", snapshot=self.snap(), timeframe=timeframe)
                self.assertIn("invalid_timeframe", result["reason_codes"])
                self.assertTrue(result["may_continue"])
                self.assertEqual(result["loop"]["timeframe"], "M15")
                self.assertIsNone(result["loop"]["next_cycle_at"])
        result = self.call("cycle", snapshot=self.snap(), buffer_seconds=90)
        self.assertIn("invalid_buffer_seconds", result["reason_codes"])
        result = self.call("cycle", snapshot=self.snap(), market_state="holiday")
        self.assertIn("invalid_market_state", result["reason_codes"])
        future = self.now + timedelta(minutes=5)
        result = self.call("cycle", snapshot=self.snap(),
                           clock=self.clock(),
                           bar={"open_time": checker.utc(future), "confirmed": True})
        self.assertIn("future_bar", result["reason_codes"])
        self.assertEqual(self.state()["loop"]["status"], "active")

    def test_cycle_rejects_stale_snapshot_without_counting_a_cycle(self):
        self.start()
        self.call("cycle", snapshot=self.snap(), bar=self.bar())
        cycles = self.state()["loop"]["cycles"]
        stale = self.snap()
        self.now += timedelta(seconds=120)
        result = self.call("cycle", snapshot=stale, bar=self.bar())
        self.assertIn("stale_or_future_snapshot", result["reason_codes"])
        self.assertTrue(result["may_continue"])
        self.assertEqual(self.state()["loop"]["cycles"], cycles)

    def test_schema_v1_state_migrates_on_next_write(self):
        self.start()
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("PRAGMA user_version = 1")
        result = self.call("cycle", snapshot=self.snap(), bar=self.bar())
        self.assertTrue(result["may_continue"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], checker.SCHEMA_VERSION)
        self.assertEqual(self.state()["loop"]["cycles"], 1)

    def test_start_request_batch_journal_and_settlement_continue_until_user_stop(self):
        config = dict(MANDATE, entry_timeframe="M5", latch_check_seconds=60)
        self.start(config=config, approval_mode="start_request")
        self.assertIsNone(self.state()["loop"])
        approval = self.state()["approval_ref"]
        session = self.control("start", approval)["session"]
        self.now += timedelta(seconds=5)
        first = self.call("cycle", snapshot=self.snap(), clock=self.clock(5), bar=self.bar(minutes=5))
        loop_id = first["loop"]["id"]
        self.assertTrue(first["may_continue"])
        prepared = self.call("prepare", snapshot=self.snap(), action=self.entry())
        self.assertTrue(prepared["may_dispatch"])
        orders = [position("pending-1", "1", kind="entry")]
        resolved = self.call("resolve", intent_id="a1", outcome="completed", readback_verified=True,
                             broker_tickets=["pending-1"], evidence_ref="synthetic:pending-readback",
                             snapshot=self.snap(pending_orders=orders))
        self.assertTrue(resolved["may_continue"])
        self.assertEqual(resolved["loop"]["cycles"], 1)
        journal = self.call("journal", **self.journal_request(activity="entry"))
        self.assertTrue(journal["may_continue"])
        self.assertEqual(journal["loop"], resolved["loop"])
        self.assertTrue(self.state()["last_result"]["may_continue"])
        for _ in range(7):
            self.now = checker.stamp(journal["loop"]["next_wake_at"], "wake")
            risk_check = self.call("check", snapshot=self.snap(pending_orders=orders))
            self.assertTrue(risk_check["may_continue"])
            self.assertEqual(risk_check["loop"]["cycles"], self.state()["loop"]["cycles"])
            self.now += timedelta(minutes=5)
            result = self.call("cycle", snapshot=self.snap(pending_orders=orders),
                               clock=self.clock(5), bar=self.bar(minutes=5))
            self.assertTrue(result["may_continue"])
            self.assertEqual(result["required_action"], "none")
            self.assertEqual(result["loop"]["id"], loop_id)
            self.assertEqual(self.state()["approval_ref"], approval)
            journal = self.call("journal", **self.journal_request())
            self.assertTrue(journal["may_continue"])
        self.assertEqual(self.state()["loop"]["cycles"], 8)
        triggered = self.call("check", snapshot=self.snap("115", pending_orders=orders))
        self.assertTrue(triggered["may_continue"])
        self.assertEqual(triggered["loop"]["status"], "closing")
        permitted = self.call("prepare", snapshot=self.snap("115", pending_orders=orders),
                              action=self.reduction(ticket="pending-1", reason="target"))
        self.assertTrue(permitted["may_dispatch"])
        final = self.call("resolve", intent_id="r1", outcome="completed", readback_verified=True,
                          broker_tickets=["pending-1"], evidence_ref="synthetic:cancelled-flat", snapshot=self.snap("114.7"))
        self.assertTrue(final["may_continue"])
        self.assertEqual(final["loop"]["id"], loop_id)
        self.assertEqual(final["loop"]["cycles"], 8)
        self.assertEqual(final["loop"]["status"], "closed")
        self.assertEqual(final["metrics"]["final_shortfall"], "0.3")
        self.assertEqual(final["loop"]["wake_reason"], "monitor")
        self.call("journal", **self.journal_request(activity="exit"))
        self.now += timedelta(minutes=5)
        monitor = self.call("check", snapshot=self.snap("114.7"))
        self.assertTrue(monitor["may_continue"])
        self.assertTrue(monitor["closure_verified"])
        self.assertEqual(monitor["session"]["id"], session["id"])
        self.assertEqual(monitor["loop"]["cycles"], 8)
        self.assertIsNone(monitor["loop"]["next_cycle_at"])
        stopped = self.control("stop")
        self.assertFalse(stopped["may_continue"])
        self.assertEqual(stopped["loop"]["status"], "closed")
        self.assertIsNone(stopped["loop"]["next_wake_at"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM events WHERE command='activate'").fetchone()[0], 1)

    def test_closed_identity_late_fill_and_invalid_read_do_not_fabricate_completion(self):
        self.start()
        first = self.call("cycle", snapshot=self.snap("95"))
        self.assertFalse(first["may_continue"])
        original = self.state()["loop"]
        repeated = self.call("cycle", snapshot=self.snap("95"))
        self.assertEqual(repeated["loop"], original)
        stale = self.snap("95")
        self.now += timedelta(seconds=61)
        failed = self.call("cycle", snapshot=stale)
        self.assertTrue(failed["may_continue"])
        self.assertFalse(failed["closure_verified"])
        self.assertEqual(failed["loop"], original)
        late = self.call("check", snapshot=self.snap("95", positions=[position()]))
        self.assertEqual(late["loop"]["id"], original["id"])
        self.assertEqual(late["loop"]["status"], "closing")
        self.assertIsNone(late["loop"]["ended_at"])
        self.assertTrue(late["may_continue"])
        self.assertEqual(late["loop"]["wake_reason"], "closure")
        with closing(sqlite3.connect(self.db)) as connection:
            detail = json.loads(connection.execute("SELECT detail FROM events ORDER BY id DESC LIMIT 1").fetchone()[0])
        self.assertEqual(detail["previous_loop_lifecycle"]["ended_at"], original["ended_at"])
        final = self.call("check", snapshot=self.snap("94.9"))
        self.assertEqual(final["loop"]["id"], original["id"])
        self.assertNotEqual(final["loop"]["ended_at"], original["ended_at"])
        self.assertIsNone(final["loop"]["next_wake_at"])
        self.assertFalse(final["may_continue"])

    def test_loop_lifecycle_converges_on_prepare_rejected_activation_and_both_latches(self):
        self.start()
        initial = self.call("cycle", snapshot=self.snap())
        self.call("check", snapshot=self.snap("120", remaining_close_costs="10", costs_final=False))
        result = self.call("prepare", snapshot=self.snap("115", positions=[position()]),
                           action=self.reduction(reason="loss"))
        self.assertTrue(result["may_dispatch"])
        self.assertTrue(result["may_continue"])
        self.assertEqual(result["loop"]["end_reason"], "loss_latch")
        self.assertIsNotNone(result["target_latched_at"])
        self.assertEqual(result["loop"]["cycles"], initial["loop"]["cycles"])
        denied = self.activate_again("new_goal", self.snap("115", positions=[position()]))
        self.assertEqual(denied["loop"]["id"], initial["loop"]["id"])
        self.assertEqual(denied["loop"]["status"], "closing")
        self.assertTrue(denied["may_continue"])

    def test_approved_timeframe_and_settling_window_control_the_deadline(self):
        self.start()
        early = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        self.assertFalse(early["loop"]["bar_advanced"])
        self.assertEqual(early["loop"]["next_cycle_at"], "2026-11-03T20:00:05Z")
        self.assertEqual(early["loop"]["next_wake_at"], "2026-11-03T20:00:05Z")
        self.now = datetime(2026, 11, 3, 20, 0, 5, tzinfo=timezone.utc)
        settled = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        self.assertTrue(settled["loop"]["bar_advanced"])
        self.assertEqual(settled["loop"]["next_cycle_at"], "2026-11-03T20:15:05Z")
        mismatch = self.call("cycle", snapshot=self.snap(), timeframe="H4", clock=self.clock(), bar=self.bar())
        self.assertIn("timeframe_mismatch", mismatch["reason_codes"])
        self.assertEqual(mismatch["loop"]["timeframe"], "M15")
        self.assertEqual(self.state()["mandate"], MANDATE)
        self.assertNotIn("entry_timeframe", self.state()["mandate"])
        for buffer in (0, 2, 6, 60, True):
            result = self.call("cycle", snapshot=self.snap(), clock=self.clock(), buffer_seconds=buffer)
            self.assertIn("invalid_buffer_seconds", result["reason_codes"])

    def test_broker_offsets_dst_and_calendar_boundaries_are_not_utc_guesses(self):
        self.start()
        cases = [
            ("H4", "2026-11-04T18:00:00Z", "2026-11-04T22:00:00Z", "2026-11-05T02:00:00Z", "2026-11-05T02:00:05Z"),
            ("D1", "2027-03-26T22:00:00Z", "2027-03-27T22:00:00Z", "2027-03-28T21:00:00Z", "2027-03-28T21:00:05Z"),
            ("W1", "2027-03-21T22:00:00Z", "2027-03-28T21:00:00Z", "2027-04-04T21:00:00Z", "2027-04-04T21:00:05Z"),
            ("MN1", "2027-03-31T21:00:00Z", "2027-04-30T21:00:00Z", "2027-05-31T21:00:00Z", "2027-05-31T21:00:05Z"),
        ]
        for timeframe, opened, boundary, following, expected in cases:
            with self.subTest(timeframe=timeframe):
                config = dict(MANDATE, entry_timeframe=timeframe)
                self.now = checker.stamp(boundary, "synthetic_boundary") + timedelta(seconds=5)
                self.draft(mandate=config)
                self.activate_again("reauthorize", mandate=config)
                sample = self.snap()
                clock = {"symbol": "EURUSD", "source_ref": "synthetic:calendar", "as_of": sample["as_of"],
                         "last_boundary_at": boundary, "next_boundary_at": following}
                bar = {"symbol": "EURUSD", "source_ref": "synthetic:bar", "confirmed": True,
                       "open_time": opened, "close_time": boundary}
                result = self.call("cycle", snapshot=sample, clock=clock, bar=bar)
                self.assertEqual(result["decision"], "within_budget")
                self.assertEqual(result["loop"]["next_cycle_at"], expected)
                self.assertEqual(result["loop"]["next_wake_at"], expected)

    def test_duplicate_and_missing_bars_do_not_replay_candle_progress_or_health(self):
        self.start(config=dict(MANDATE, latch_check_seconds=300))
        self.now += timedelta(seconds=5)
        sample = self.snap()
        first = self.call("cycle", snapshot=sample, clock=self.clock(), bar=self.bar())
        observation = self.state()["observation"]
        self.now += timedelta(seconds=3)
        replay = self.call("cycle", snapshot=sample, clock=self.clock(), bar=self.bar())
        self.assertIn("duplicate_cycle_snapshot", replay["reason_codes"])
        self.assertEqual(replay["loop"]["cycles"], 1)
        self.assertFalse(replay["loop"]["bar_advanced"])
        self.assertEqual(self.state()["observation"], observation)
        self.assertEqual(replay["loop"]["next_latch_check_at"], first["loop"]["next_latch_check_at"])
        repeat = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        self.assertEqual(repeat["loop"]["cycles"], 2)
        self.assertFalse(repeat["loop"]["bar_advanced"])
        high_water = repeat["loop"]["bar_high_water"]
        missing = self.call("cycle", snapshot=self.snap(), clock=self.clock())
        self.assertFalse(missing["loop"]["bar_confirmed"])
        self.assertFalse(missing["loop"]["bar_advanced"])
        self.assertEqual(missing["loop"]["bar_high_water"], high_water)
        regressing = self.bar()
        regressing["open_time"] = "2026-11-03T19:30:00Z"
        rejected = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=regressing)
        self.assertIn("regressing_bar", rejected["reason_codes"])
        self.assertEqual(rejected["loop"]["bar_high_water"], high_water)
        conflicting = dict(self.bar(), open_time="2026-11-03T19:50:00Z")
        rejected = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=conflicting)
        self.assertIn("conflicting_bar", rejected["reason_codes"])
        self.assertFalse(rejected["loop"]["bar_advanced"])
        self.assertEqual(rejected["loop"]["bar_high_water"], high_water)
        other = self.call("cycle", snapshot=self.snap(), clock=self.clock(symbol="GBPUSD"), bar=self.bar(symbol="GBPUSD"))
        self.assertTrue(other["loop"]["bar_advanced"])
        self.assertEqual(set(other["loop"]["bar_high_water"]), {"EURUSD", "GBPUSD"})

    def test_missing_unconfirmed_and_in_progress_bars_are_not_confirmed_advances(self):
        self.start()
        self.now += timedelta(seconds=5)
        sample = self.snap()
        clock = self.clock()
        forming = dict(self.bar(), open_time=clock["last_boundary_at"], close_time=clock["next_boundary_at"], confirmed=False)
        result = self.call("cycle", snapshot=sample, clock=clock, bar=forming)
        self.assertFalse(result["loop"]["bar_advanced"])
        self.assertFalse(result["loop"]["bar_confirmed"])
        self.assertEqual(result["loop"]["wake_reason"], "bar_retry")
        invalid = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=dict(forming, confirmed=True))
        self.assertIn("invalid_bar_clock", invalid["reason_codes"])
        legacy = self.call("cycle", snapshot=self.snap(), clock=self.clock(),
                           bar={"open_time": self.bar()["open_time"], "confirmed": True})
        self.assertIn("bar_evidence_unavailable", legacy["reason_codes"])
        self.assertEqual(legacy["loop"]["bar_high_water"], {})

    def test_closed_market_backoff_counts_boundaries_not_polls_and_never_delays_tripwire(self):
        self.start()
        self.now += timedelta(seconds=5)
        first = self.call("cycle", snapshot=self.snap(), clock=self.clock(), market_state="closed")
        self.assertEqual(first["loop"]["missing_bars"], 1)
        repeated = self.call("cycle", snapshot=self.snap(), clock=self.clock(), market_state="closed")
        self.assertEqual(repeated["loop"]["missing_bars"], 1)
        self.assertEqual(repeated["loop"]["closed_boundaries"], 1)
        self.now = datetime(2026, 11, 3, 20, 15, 6, tzinfo=timezone.utc)
        second = self.call("cycle", snapshot=self.snap(), clock=self.clock(), market_state="closed")
        self.assertEqual(second["loop"]["closed_boundaries"], 2)
        self.assertEqual(second["loop"]["wake_reason"], "market_closed")
        self.assertEqual(second["loop"]["next_wake_at"], "2026-11-03T20:20:07Z")
        config = dict(MANDATE, latch_check_seconds=30)
        self.draft(mandate=config)
        reauthorized = self.activate_again("reauthorize", mandate=config)
        self.assertEqual(reauthorized["loop"]["wake_reason"], "latch_check")
        self.assertEqual(reauthorized["loop"]["next_latch_check_at"], "2026-11-03T20:15:38Z")
        mixed = self.call("cycle", snapshot=self.snap(), clock=self.clock(), market_state="unknown")
        self.assertEqual(mixed["loop"]["closed_boundaries"], 0)
        self.assertEqual(mixed["loop"]["wake_reason"], "bar_retry")
        self.assertEqual(mixed["loop"]["next_wake_at"], "2026-11-03T20:15:24Z")

    def test_observation_health_differs_from_cycle_spacing_and_journal_is_not_a_heartbeat(self):
        self.start(config=dict(MANDATE, latch_check_seconds=300))
        self.now += timedelta(seconds=5)
        first = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        self.assertEqual(first["loop"]["wake_reason"], "latch_check")
        self.assertEqual(first["loop"]["next_wake_at"], "2026-11-03T20:05:07Z")
        for minute in (5, 10):
            self.now = datetime(2026, 11, 3, 20, minute, 6, tzinfo=timezone.utc)
            sample = self.snap()
            self.now += timedelta(seconds=10)
            self.call("check", snapshot=sample)
        self.now = datetime(2026, 11, 3, 20, 15, 6, tzinfo=timezone.utc)
        result = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        self.assertEqual(result["loop"]["gap_seconds"], 900)
        self.assertEqual(result["loop_health"]["observation_gap_seconds"], 300)
        self.assertEqual(result["loop_health"]["max_observation_gap_seconds"], 300)
        self.assertEqual(result["loop_health"]["max_observation_gap_at"], "2026-11-03T20:05:07Z")
        before = self.state()
        self.now += timedelta(minutes=6)
        self.call("journal", **self.journal_request())
        after = self.state()
        after.pop("last_journal")
        self.assertEqual(after, before)
        status = self.call("status")
        self.assertEqual(status["loop_health"]["execution"], "unverified")
        self.assertEqual(status["loop_health"]["observation_age_seconds"], 360)
        self.assertEqual(status["loop_health"]["wake_overdue_seconds"], 60)

    def test_initial_live_receipt_schedules_tripwire_but_snapshot_reuse_does_not_refresh_it(self):
        self.now = datetime(2026, 11, 3, 20, 0, 9, tzinfo=timezone.utc)
        self.start(config=dict(MANDATE, latch_check_seconds=300))
        sample = self.state()["last_snapshot"]
        observation = self.state()["observation"]
        first = self.call("cycle", snapshot=sample, clock=self.clock(), bar=self.bar())
        self.assertEqual(first["loop"]["next_latch_check_at"], "2026-11-03T20:05:10Z")
        self.now += timedelta(seconds=30)
        checked = self.call("check", snapshot=sample)
        self.assertEqual(self.state()["observation"], observation)
        self.assertEqual(checked["loop"]["next_latch_check_at"], "2026-11-03T20:05:10Z")

    def test_invalid_clock_and_failed_observation_preserve_breach_and_revision_contract(self):
        self.start()
        first = self.call("cycle", snapshot=self.snap())
        self.assertIn("broker_clock_unavailable", first["reason_codes"])
        self.assertEqual(first["loop"]["market_state"], "unknown")
        self.assertIsNone(first["loop"]["next_cycle_at"])
        self.assertTrue(first["may_continue"])
        sample = self.snap()
        revision = self.revision
        before = self.state()
        self.now += timedelta(seconds=61)
        rejected = self.call("cycle", snapshot=sample)
        self.assertEqual(rejected["revision"], revision + 1)
        self.assertEqual(self.state()["observation"], before["observation"])
        self.assertEqual(self.state()["loop"]["cycles"], 1)
        bad_clock = dict(self.clock(), symbol="UNAPPROVED")
        breached = self.call("cycle", snapshot=self.snap("95", positions=[position()]), clock=bad_clock)
        self.assertIn("unapproved_clock_symbol", breached["reason_codes"])
        self.assertEqual(breached["decision"], "loss_stop")
        self.assertTrue(breached["may_continue"])
        self.assertEqual(breached["loop"]["status"], "closing")
        self.assertEqual(breached["loop"]["wake_reason"], "closure")
        self.assertTrue(self.call("prepare", snapshot=self.snap("95", positions=[position()]),
                                  action=self.reduction(reason="loss"))["may_dispatch"])

    def test_clock_expired_at_a_boundary_cannot_advance_the_superseded_candle(self):
        self.start()
        self.now = datetime(2026, 11, 3, 20, 15, 6, tzinfo=timezone.utc)
        sample = self.snap()
        clock = {"symbol": "EURUSD", "source_ref": "synthetic:before-boundary", "as_of": "2026-11-03T20:14:59Z",
                 "last_boundary_at": "2026-11-03T20:00:00Z", "next_boundary_at": "2026-11-03T20:15:00Z"}
        bar = {"symbol": "EURUSD", "source_ref": "synthetic:old-bar", "confirmed": True,
               "open_time": "2026-11-03T19:45:00Z", "close_time": "2026-11-03T20:00:00Z"}
        result = self.call("cycle", snapshot=sample, clock=clock, bar=bar)
        self.assertIn("invalid_or_stale_broker_clock", result["reason_codes"])
        self.assertFalse(result["loop"]["bar_advanced"])
        self.assertEqual(result["loop"]["bar_high_water"], {})
        self.assertIsNone(result["loop"]["next_cycle_at"])
        self.assertEqual(result["loop"]["wake_reason"], "clock_refresh")
        self.assertEqual(result["loop"]["cycles"], 1)
        self.assertTrue(result["may_continue"])

    def test_symbol_reauthorization_discards_out_of_scope_clock_and_closed_market_evidence(self):
        self.start()
        self.now += timedelta(seconds=5)
        original = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())["loop"]
        self.call("cycle", snapshot=self.snap(), clock=self.clock(symbol="GBPUSD"), bar=self.bar(symbol="GBPUSD"))
        config = dict(MANDATE, symbols=["GBPUSD", "XAUUSD"])
        self.draft(mandate=config)
        changed = self.activate_again("reauthorize", mandate=config)
        self.assertEqual(changed["loop"]["id"], original["id"])
        self.assertEqual(set(changed["loop"]["bar_high_water"]), {"GBPUSD"})
        self.assertIsNone(changed["loop"]["clock"])
        self.assertIsNone(changed["loop"]["next_cycle_at"])
        self.assertEqual(changed["loop"]["wake_reason"], "clock_refresh")
        for minute in (15, 30):
            self.now = datetime(2026, 11, 3, 20, minute, 6, tzinfo=timezone.utc)
            closed = self.call("cycle", snapshot=self.snap(), clock=self.clock(symbol="GBPUSD"), market_state="closed")
        self.assertEqual(closed["loop"]["wake_reason"], "market_closed")
        self.draft(mandate=MANDATE)
        expanded = self.activate_again("reauthorize", mandate=MANDATE)
        self.assertEqual(expanded["loop"]["market_state"], "unknown")
        self.assertEqual(expanded["loop"]["closed_boundaries"], 0)
        self.assertEqual(expanded["loop"]["wake_reason"], "clock_refresh")
        self.assertEqual(expanded["loop"]["next_wake_at"], checker.utc(self.now))
        self.assertEqual(expanded["loop"]["cycles"], closed["loop"]["cycles"])

    def test_reviewed_baseline_latch_prioritizes_closure_without_refreshing_legacy_health(self):
        self.start()
        self.now += timedelta(seconds=5)
        self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        legacy = self.state()
        legacy.pop("observation")
        with closing(sqlite3.connect(self.db)) as connection, connection:
            checker.save_state(connection, self.revision, legacy, "synthetic-legacy-observation", {}, self.now)
            connection.execute("PRAGMA user_version=2")
        source_before = legacy["last_snapshot"]["as_of"]
        baseline = self.snap("95")
        self.draft(target="20")
        result = self.call("activate", mode="new_goal", mandate=MANDATE, baseline=baseline, snapshot=None,
                           approval_ref="synthetic:reviewed-baseline", approved_at=checker.utc(self.now))
        self.assertIsNone(result["metrics"])
        self.assertIsNotNone(result["loss_latched_at"])
        self.assertEqual(result["loop"]["status"], "closing")
        self.assertEqual(result["loop"]["wake_reason"], "closure")
        self.assertEqual(result["loop"]["next_wake_at"], checker.utc(self.now))
        self.assertIsNone(result["loop"]["next_cycle_at"])
        self.assertTrue(result["may_continue"])
        self.assertEqual(result["loop_health"]["last_observation_at"], source_before)
        self.assertIsNone(result["loop_health"]["last_observation_received_at"])
        self.assertIsNone(result["loop_health"]["max_observation_gap_seconds"])

    def test_goal_and_timeframe_transitions_preserve_or_supersede_the_right_loop(self):
        self.start()
        self.now += timedelta(seconds=5)
        self.call("cycle", snapshot=self.snap("104"), clock=self.clock(), bar=self.bar())
        original = self.state()
        config = dict(MANDATE, entry_timeframe="H1")
        self.draft(mandate=config)
        changed = self.activate_again("reauthorize", self.snap("103"), mandate=config)
        self.assertEqual(changed["loop"]["id"], original["loop"]["id"])
        self.assertEqual(changed["loop"]["timeframe"], "H1")
        self.assertEqual(changed["loop"]["bar_high_water"], {})
        self.assertEqual(self.state()["policy"], original["policy"])
        self.assertEqual(self.state()["peak"], "104")
        self.draft(target="20")
        self.activate_again("new_goal", self.snap("103"), mandate=config)
        self.assertIsNone(self.state()["loop"])
        self.assertEqual(self.state()["policy"], original["policy"])
        with closing(sqlite3.connect(self.db)) as connection:
            detail = json.loads(connection.execute("SELECT detail FROM events WHERE command='activate' ORDER BY id DESC LIMIT 1").fetchone()[0])
        self.assertEqual(detail["previous_state"]["loop"]["id"], original["loop"]["id"])
        new = self.call("cycle", snapshot=self.snap("103"), clock=self.clock(60), bar=self.bar(minutes=60))
        self.assertNotEqual(new["loop"]["id"], original["loop"]["id"])
        self.assertEqual(new["loop"]["cycles"], 1)
        self.assertEqual(new["loop"]["goal_id"], self.state()["goal"]["id"])

    def test_v2_loop_journal_upgrade_preserves_history_until_prospective_resume_binding(self):
        self.start()
        self.now += timedelta(seconds=5)
        self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        self.call("prepare", snapshot=self.snap(), action=self.entry())
        self.call("resolve", intent_id="a1", outcome="unknown", evidence_ref="synthetic:timeout", snapshot=self.snap())
        self.call("journal", **self.journal_request(intent_id="a1"))
        state = self.state()
        legacy_fields = ("id", "status", "started_at", "cycles", "last_cycle_at", "timeframe", "bar_open_time",
                         "bar_confirmed", "bar_advanced", "gap_seconds", "max_gap_seconds", "max_gap_at",
                         "missing_bars", "market_state", "next_cycle_at", "end_reason", "ended_at")
        legacy_loop = {key: state["loop"].get(key) for key in legacy_fields}
        legacy_loop["timeframe"] = "H1"  # The v2 request override could disagree with the approved M15 default.
        state["loop"] = legacy_loop
        state.pop("observation")
        state["last_result"].pop("loop_health", None)
        state["last_result"]["loop"] = copy.deepcopy(legacy_loop)
        with closing(sqlite3.connect(self.db)) as connection, connection:
            checker.save_state(connection, self.revision, state, "synthetic-v2", {}, self.now)
            connection.execute("PRAGMA user_version=2")
            intents = connection.execute("SELECT * FROM intents").fetchall()
        self.assertEqual(self.state(), state)
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
        self.call("journal", **self.journal_request(intent_id="a1"))
        self.assertEqual(self.state()["loop"], legacy_loop)
        self.assertNotIn("observation", self.state())
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], checker.SCHEMA_VERSION)
            self.assertEqual(connection.execute("SELECT * FROM intents").fetchall(), intents)
            detail = json.loads(connection.execute("SELECT detail FROM events ORDER BY id DESC LIMIT 1").fetchone()[0])
        self.assertEqual(detail["migration"]["legacy_loop"], legacy_loop)
        denied = self.call("prepare", snapshot=self.snap(), action=self.entry("a2"))
        self.assertIn("loop_resume_required", denied["reason_codes"])
        resumed = self.activate_again("resume", self.snap(), owner_id="new-owner", takeover_ref="synthetic:owner-stopped",
                                      approval_ref=state["approval_ref"], approved_at=state["approved_at"])
        self.assertEqual(resumed["loop"]["id"], legacy_loop["id"])
        self.assertEqual(resumed["loop"]["cycles"], legacy_loop["cycles"])
        self.assertEqual(resumed["loop"]["timeframe"], "M15")
        self.assertEqual(resumed["loop"]["binding_verified_at"], self.state()["last_snapshot"]["as_of"])
        self.assertEqual(self.state()["policy"], state["policy"])
        self.assertEqual(self.state()["goal"], state["goal"])
        self.assertEqual(self.state()["peak"], state["peak"])
        self.assertEqual(self.call("status")["outstanding_intents"][0]["outcome"]["evidence_ref"], "synthetic:timeout")
        next_cycle = self.call("cycle", owner_id="new-owner", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        self.assertEqual(next_cycle["loop"]["id"], legacy_loop["id"])
        self.assertEqual(next_cycle["loop"]["cycles"], legacy_loop["cycles"] + 1)
        self.assertEqual(next_cycle["loop"]["next_cycle_at"], "2026-11-03T20:15:05Z")

    def test_start_request_baseline_is_fresh_after_request_and_preserves_activation_loss(self):
        self.draft(budget="5", target="15", mandate=MANDATE)
        requested_at = checker.utc(self.now)
        baseline = self.snap("100")
        current = self.snap("95", positions=[position()])
        result = self.call("activate", mode="start", approval_mode="start_request", mandate=MANDATE,
                           baseline=baseline, snapshot=current, approval_ref="synthetic:user-trade", approved_at=requested_at)
        self.assertEqual(result["decision"], "loss_stop")
        state = self.state()
        self.assertEqual(state["approval_mode"], "start_request")
        self.assertEqual(state["goal"]["approved_at"], requested_at)
        self.assertEqual(state["goal"]["started_at"], baseline["as_of"])
        self.assertEqual(state["policy"]["start_equity"], "100")
        self.assertEqual(state["peak"], "100")
        self.assertIsNone(state["loop"])
        self.assertNotIn("session", state)
        self.control("start", "synthetic:user-trade")
        result = self.call("cycle", snapshot=self.snap("95", positions=[position()]))
        self.assertTrue(result["may_continue"])
        self.assertEqual(result["loop"]["wake_reason"], "closure")
        self.assertTrue(self.call("prepare", snapshot=self.snap("95", positions=[position()]),
                                  action=self.reduction(reason="loss"))["may_dispatch"])

    def test_start_request_rejects_old_future_or_unapproved_baselines(self):
        self.draft(budget="5", target="15", mandate=MANDATE)
        requested_at = checker.utc(self.now)
        baseline = self.snap()
        current = self.snap()
        request = dict(mode="start", approval_mode="start_request", mandate=MANDATE, baseline=baseline,
                       snapshot=current, approval_ref="synthetic:user-trade", approved_at=requested_at)
        before = self.state()
        for changes, code in (({"approval_mode": "infer"}, "invalid_approval_mode"),
                              ({"approval_ref": ""}, "invalid_approval_ref"),
                              ({"approved_at": current["as_of"]}, "baseline_predates_start_request"),
                              ({"approved_at": checker.utc(self.now + timedelta(seconds=1))}, "future_approval"),
                              ({"baseline": dict(baseline, as_of=checker.utc(self.now + timedelta(seconds=1)))}, "future_snapshot")):
            with self.subTest(code=code):
                with self.assertRaisesRegex(checker.CheckError, code):
                    self.call("activate", **dict(request, **changes))
                self.assertEqual(self.state(), before)
        self.now += timedelta(seconds=61)
        with self.assertRaisesRegex(checker.CheckError, "stale_or_future_snapshot"):
            self.call("activate", **dict(request, snapshot=self.snap()))
        self.assertEqual(self.state(), before)

    def test_rejected_start_request_goal_transition_still_observes_existing_loss(self):
        self.start(approval_mode="start_request")
        self.control("start")
        self.call("cycle", snapshot=self.snap())
        self.draft(target="20", mandate=MANDATE)
        requested_at = checker.utc(self.now)
        result = self.call("activate", mode="new_goal", mandate=MANDATE, approval_mode="start_request",
                           baseline=self.snap("95"), snapshot=None,
                           approval_ref="synthetic:new-target", approved_at=requested_at)
        self.assertEqual(result["decision"], "loss_stop")
        self.assertIsNotNone(result["loss_latched_at"])
        self.assertEqual(self.state()["goal"]["target"], "15")
        self.assertEqual(result["loop"]["status"], "closing")
        self.assertTrue(result["may_continue"])

    def test_rejected_stale_start_request_baseline_cannot_ratchet_existing_peak(self):
        self.start()
        self.control("start")
        self.call("cycle", snapshot=self.snap())
        self.draft(target="20", mandate=MANDATE)
        requested_at = checker.utc(self.now)
        baseline = self.snap("110")
        self.now += timedelta(seconds=61)
        result = self.call("activate", mode="new_goal", mandate=MANDATE, approval_mode="start_request",
                           baseline=baseline, snapshot=self.snap("100"),
                           approval_ref="synthetic:new-target", approved_at=requested_at)
        self.assertIn("stale_or_future_snapshot", result["reason_codes"])
        self.assertEqual(self.state()["peak"], "100")
        self.assertIsNone(self.state()["loss_latched_at"])
        self.assertTrue(result["may_continue"])

    def test_session_control_does_not_observe_and_stop_fences_routine_actions(self):
        self.start()
        self.control("start")
        self.now += timedelta(seconds=5)
        self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        before = self.state()
        self.now += timedelta(minutes=10)
        with patch.object(checker, "observe", side_effect=AssertionError("control must not observe")), \
                patch.object(checker, "report", side_effect=AssertionError("control must not check money")):
            stopped = self.control("stop")
        after = self.state()
        for field in before.keys() - {"session", "loop"}:
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(after["loop"]["cycles"], before["loop"]["cycles"])
        self.assertEqual(after["loop"]["status"], "active")
        self.assertFalse(stopped["may_continue"])
        self.assertFalse(stopped["may_dispatch"])
        self.assertIsNone(stopped["loop"]["next_wake_at"])
        self.assertEqual(stopped["loop_health"]["execution"], "unverified")
        checked = self.call("check", snapshot=self.snap())
        self.assertFalse(checked["may_continue"])
        self.assertIsNone(checked["loop"]["next_wake_at"])
        cycled = self.call("cycle", snapshot=self.snap(), clock=self.clock(), bar=self.bar())
        self.assertIn("session_not_active", cycled["reason_codes"])
        self.assertEqual(cycled["loop"]["cycles"], before["loop"]["cycles"])
        for action in (self.entry(), self.reduction()):
            rejected = self.call("prepare", snapshot=self.snap(positions=[position()]), action=action)
            self.assertIn("session_not_active", rejected["reason_codes"])
            self.assertFalse(rejected["may_dispatch"])
            self.assertFalse(rejected["may_continue"])
        self.assertEqual(self.call("status")["outstanding_intents"], [])
        resumed = self.activate_again("resume")
        self.assertFalse(resumed["may_continue"])
        self.assertEqual(self.state()["session"]["status"], "stopped")
        self.assertIsNone(resumed["loop"]["next_wake_at"])

    def test_financial_activation_modes_and_owner_handoff_never_clear_user_stop(self):
        self.start(approval_mode="start_request")
        self.control("start")
        self.call("cycle", snapshot=self.snap())
        self.control("stop")
        stop = self.state()["session"]
        prior = self.state()
        result = self.activate_again("resume", owner_id="new-owner", takeover_ref="synthetic:old-writer-stopped",
                                     approval_ref=prior["approval_ref"], approved_at=prior["approved_at"])
        self.assertFalse(result["may_continue"])
        config = dict(MANDATE, entry_timeframe="H1")
        self.draft(budget="5", target="15", mandate=config, owner_id="new-owner")
        self.activate_again("reauthorize", mandate=config, owner_id="new-owner", approval_mode="start_request")
        self.assertEqual(self.state()["session"], stop)
        self.draft(target="20", mandate=config, owner_id="new-owner")
        self.activate_again("new_goal", mandate=config, owner_id="new-owner", approval_mode="start_request")
        self.assertEqual(self.state()["session"], stop)
        self.draft(budget="10", mandate=config, owner_id="new-owner")
        self.anchor = None
        result = self.activate_again("replace_policy", mandate=config, owner_id="new-owner", approval_mode="start_request",
                                     reset_reason="Synthetic explicit replacement")
        self.assertFalse(result["may_continue"])
        self.assertEqual(self.state()["session"], stop)
        self.assertNotEqual(self.state()["policy"]["id"], prior["policy"]["id"])
        denied = self.call("prepare", owner_id="new-owner", snapshot=self.snap(), action=self.entry())
        self.assertIn("session_not_active", denied["reason_codes"])

    def test_session_stop_preserves_pending_recovery_and_authorized_safety_reductions(self):
        self.start()
        self.control("start")
        self.call("cycle", snapshot=self.snap())
        self.call("prepare", snapshot=self.snap(), action=self.entry())
        self.control("stop")
        unknown = self.call("resolve", intent_id="a1", outcome="unknown", evidence_ref="synthetic:timeout", snapshot=self.snap())
        self.assertFalse(unknown["may_continue"])
        self.assertEqual(len(self.call("status")["outstanding_intents"]), 1)
        self.call("resolve", intent_id="a1", outcome="not_executed", readback_verified=True,
                  evidence_ref="synthetic:terminal-rejection", snapshot=self.snap())
        safety = self.call("prepare", snapshot=self.snap("95", positions=[position()]), action=self.reduction(reason="loss"))
        self.assertTrue(safety["may_dispatch"])
        self.assertFalse(safety["may_continue"])
        settled = self.call("resolve", intent_id="r1", outcome="completed", readback_verified=True,
                            broker_tickets=["p1"], evidence_ref="synthetic:flat", snapshot=self.snap("95"))
        self.assertTrue(settled["closure_verified"])
        self.assertFalse(settled["may_continue"])
        self.assertIsNone(settled["loop"]["next_wake_at"])
        self.assertEqual(self.state()["session"]["status"], "stopped")

    def test_interruption_can_resume_but_user_stop_cannot_be_overridden_or_replayed(self):
        self.start()
        first = self.control("start")["session"]
        self.call("cycle", snapshot=self.snap())
        paused = self.control("interrupt")
        self.assertFalse(paused["may_continue"])
        self.assertIsNone(paused["loop"]["next_wake_at"])
        self.assertIn("session_not_active", self.call("prepare", snapshot=self.snap(), action=self.entry())["reason_codes"])
        before = self.state()
        resumed = self.control("resume")
        self.assertEqual(resumed["session"]["id"], first["id"])
        self.assertEqual(resumed["session"]["request_ref"], first["request_ref"])
        self.assertEqual(self.state()["last_result"], before["last_result"])
        self.assertEqual(resumed["loop"]["wake_reason"], "session_check")
        self.assertEqual(resumed["loop"]["next_wake_at"], checker.utc(self.now))
        self.control("stop")
        for action in ("resume", "interrupt", "start"):
            with self.assertRaises(checker.CheckError):
                self.control(action)
        second = self.control("start", "synthetic:new-user-start")["session"]
        self.assertNotEqual(second["id"], first["id"])
        self.control("stop", "synthetic:second-user-stop")
        with self.assertRaisesRegex(checker.CheckError, "new_session_request_required"):
            self.control("start", first["request_ref"])
        self.assertEqual(self.state()["session"]["status"], "stopped")

    def test_control_evidence_cannot_be_replayed_across_sessions_or_recoveries(self):
        self.start()
        self.control("start", "synthetic:start-A")
        self.control("stop", "synthetic:stop-A")
        self.control("start", "synthetic:start-B")
        self.control("interrupt", "synthetic:interruption-B")
        before = self.state()
        for evidence in ("synthetic:start-A", "synthetic:stop-A", "synthetic:start-B", "synthetic:interruption-B", before["approval_ref"]):
            with self.subTest(evidence=evidence):
                with self.assertRaisesRegex(checker.CheckError, "new_session_evidence_required"):
                    self.control("resume", evidence)
                self.assertEqual(self.state(), before)
        self.control("resume", "synthetic:recovery-B")
        with self.assertRaisesRegex(checker.CheckError, "new_session_evidence_required"):
            self.control("interrupt", "synthetic:interruption-B")
        with self.assertRaisesRegex(checker.CheckError, "new_session_evidence_required"):
            self.control("stop", "synthetic:stop-A")
        self.control("interrupt", "synthetic:second-interruption-B")
        with self.assertRaisesRegex(checker.CheckError, "new_session_evidence_required"):
            self.control("resume", "synthetic:recovery-B")
        self.control("resume", "synthetic:second-recovery-B")
        stopped = self.control("stop", "synthetic:stop-B")
        self.assertFalse(self.control("stop", "synthetic:stop-B")["may_continue"])
        self.assertEqual(self.state()["session"]["id"], stopped["session"]["id"])

    def test_clock_rollback_keeps_user_stop_and_recovery_readable(self):
        self.start()
        started = self.control("start")["session"]
        self.call("cycle", snapshot=self.snap())
        before = self.state()
        self.now = checker.stamp(started["started_at"], "started_at") - timedelta(seconds=1)
        stopped = self.control("stop")
        saved = self.state()
        self.assertEqual(saved["session"]["status"], "stopped")
        self.assertEqual(saved["session"]["updated_at"], checker.utc(self.now))
        self.assertEqual(saved["session"]["started_at"], started["started_at"])
        self.assertEqual(saved["last_result"], before["last_result"])
        self.assertEqual(saved["observation"], before["observation"])
        self.assertFalse(stopped["may_continue"])
        self.assertIsNone(stopped["loop"]["next_wake_at"])
        self.now += timedelta(seconds=10)
        self.control("start", "synthetic:new-user-start")
        self.control("interrupt")
        self.now -= timedelta(seconds=1)
        resumed = self.control("resume")
        self.assertTrue(resumed["may_continue"])
        self.assertEqual(self.state()["session"]["updated_at"], checker.utc(self.now))
        self.assertEqual(self.state()["observation"], before["observation"])

    def test_session_control_requires_configured_state_valid_input_and_single_writer(self):
        with self.assertRaisesRegex(checker.CheckError, "setup_incomplete"):
            self.control("start")
        self.assertFalse(self.db.exists())
        self.draft(budget="5", target="15")
        with self.assertRaisesRegex(checker.CheckError, "setup_incomplete"):
            self.control("start")
        self.start()
        before = self.state()
        variants = ({"owner_id": "other"}, {"expected_revision": 0}, {"snapshot": self.snap()},
                    {"action": "continue"}, {"evidence_ref": "C:\\private\\receipt.json"}, {"reason": "x" * 501})
        request = {"action": "start", "evidence_ref": "synthetic:user-start", "reason": "User requested trading"}
        for changes in variants:
            with self.subTest(changes=list(changes)):
                with self.assertRaises(checker.CheckError):
                    self.call("session", **dict(request, **changes))
                self.assertEqual(self.state(), before)
        stopped = self.control("stop")
        self.assertIsNone(stopped["session"]["started_at"])
        self.assertIsNone(stopped["session"]["request_ref"])
        self.assertIn("session_not_active", self.call("prepare", snapshot=self.snap(), action=self.entry())["reason_codes"])
        with self.assertRaisesRegex(checker.CheckError, "new_session_request_required"):
            self.control("start", before["approval_ref"])

    def test_closed_monitoring_preserves_latches_counters_and_receipt_based_deadlines(self):
        for interval, seconds in ((0, 300), (30, 30), (600, 300)):
            with self.subTest(interval=interval):
                self.db = Path(self.temp.name) / (str(interval) + ".sqlite3")
                self.revision = 0
                self.start(config=dict(MANDATE, latch_check_seconds=interval))
                self.control("start")
                self.call("cycle", snapshot=self.snap())
                flat = self.call("check", snapshot=self.snap("95"))
                loop = flat["loop"]
                self.assertTrue(flat["may_continue"])
                self.assertTrue(flat["closure_verified"])
                self.assertEqual(loop["wake_reason"], "monitor")
                self.assertEqual(loop["next_wake_at"], checker.utc(self.now + timedelta(seconds=seconds)))
                self.call("journal", **self.journal_request(activity="exit"))
                self.assertEqual(self.state()["loop"], loop)
                self.now += timedelta(seconds=10)
                replay = self.call("check", snapshot=self.state()["last_snapshot"])
                self.assertEqual(replay["loop"], loop)
                self.now += timedelta(seconds=max(seconds, 61))
                self.assertEqual(self.call("status")["loop_health"]["wake_overdue_seconds"], 10 + max(seconds, 61) - seconds)
                stale = self.call("check", snapshot=self.state()["last_snapshot"])
                self.assertTrue(stale["may_continue"])
                self.assertFalse(stale["closure_verified"])
                closed = self.call("cycle", snapshot=self.snap("95"))
                for field in ("id", "cycles", "last_cycle_at", "ended_at", "bar_high_water"):
                    self.assertEqual(closed["loop"][field], loop[field])
                self.assertEqual(closed["loop"]["next_wake_at"], checker.utc(self.now + timedelta(seconds=seconds)))
                late = self.call("check", snapshot=self.snap("95", positions=[position("late-fill")]))
                self.assertEqual(late["loop"]["id"], loop["id"])
                self.assertEqual(late["loop"]["status"], "closing")
                self.assertEqual(late["loop"]["wake_reason"], "closure")
                self.assertIsNotNone(late["loss_latched_at"])

    def test_malformed_saved_session_fails_closed_instead_of_becoming_legacy(self):
        self.start()
        original = self.state()
        for invalid in ({}, False, {"status": "running"}, {"status": "active"}):
            with self.subTest(invalid=invalid):
                state = dict(original, session=invalid)
                with closing(sqlite3.connect(self.db)) as connection, connection:
                    checker.save_state(connection, self.revision, state, "synthetic-corruption", {}, self.now)
                with self.assertRaises(checker.CheckError):
                    self.call("status")
                with self.assertRaises(checker.CheckError):
                    self.call("prepare", snapshot=self.snap(), action={})

    def journal_request(self, **changes):
        sample = self.state()["last_snapshot"]
        request = {"snapshot_id": sample["id"], "as_of": sample["as_of"], "activity": "wait",
                   "summary": "Waiting for a confirmed setup", "reason": "Spread exceeds the planned entry allowance.",
                   "next_step": "Review the next confirmed candle.", "symbols": ["EURUSD"],
                   "source_refs": ["synthetic:analysis-1"]}
        request.update(changes)
        return request

    def test_journal_is_separate_from_observation_and_financial_result(self):
        self.start()
        self.call("cycle", snapshot=self.snap("103"), bar=self.bar())
        before = self.state()
        request = self.journal_request(market_summary="Range with fading momentum.")
        self.now += timedelta(minutes=10)
        with patch.object(checker, "observe", side_effect=AssertionError("journal must not observe")), \
                patch.object(checker, "report", side_effect=AssertionError("journal must not report risk")), \
                patch.object(checker, "sync_loop", side_effect=AssertionError("journal must not synchronize financial state")), \
                patch.object(checker, "loop_wake", side_effect=AssertionError("journal must not replan deadlines")):
            revision = self.revision
            result = self.call("journal", **request)
        self.assertFalse(result["may_dispatch"])
        self.assertEqual(result["decision"], "journal_saved")
        self.assertEqual(result["revision"], revision + 1)
        self.assertTrue(result["may_continue"])
        self.assertEqual(result["loop"], before["loop"])
        self.assertEqual(result["loop_health"]["last_observation_at"], before["last_snapshot"]["as_of"])
        after = self.state()
        note = after.pop("last_journal")
        self.assertEqual(after, before)
        self.assertEqual(note["version"], 1)
        self.assertEqual(note["as_of"], before["last_snapshot"]["as_of"])
        self.assertEqual(note["recorded_at"], checker.utc(self.now))
        self.assertEqual(note["account"], ACCOUNT)
        self.assertEqual(note["goal_id"], before["goal"]["id"])

    def test_cached_continuation_uses_current_control_not_historical_last_result(self):
        self.start(approval_mode="start_request")
        self.control("start")
        self.call("cycle", snapshot=self.snap())
        historical = self.state()["last_result"]
        for action in ("interrupt", "resume", "stop"):
            self.control(action)
            expected = action == "resume"
            canonical = self.state()
            self.assertEqual(canonical["last_result"], historical)
            journal = self.call("journal", **self.journal_request())
            self.assertEqual(journal["may_continue"], expected)
            self.assertEqual(journal["session"], canonical["session"])
            self.assertEqual(journal["loop"], canonical["loop"])
            before = self.db.read_bytes()
            for command in checker.READ_ONLY_COMMANDS:
                result = checker.run(command, db_path=self.db, now=self.now)
                self.assertEqual(result["may_continue"], expected)
                self.assertFalse(result["may_dispatch"])
                self.assertEqual(result["session"], canonical["session"])
                self.assertEqual(result["loop"], canonical["loop"])
            self.assertEqual(self.db.read_bytes(), before)

    def test_context_is_atomic_and_recovers_resolved_strategy_after_later_reports(self):
        self.start()
        proposed = self.entry(risk="1.250000000001")
        prepared = self.call("prepare", snapshot=self.snap(), action=proposed)
        self.assertTrue(prepared["may_dispatch"])
        self.assertNotIn("last_journal", self.state())
        self.assertNotIn("context", prepared["intent"]["parameters"])
        initial = checker.run("context", db_path=self.db, now=self.now)["context"]["items"][0]
        self.assertEqual(initial["intent"]["action"]["context"], proposed["context"])
        self.assertEqual(initial["intent"]["status"], "prepared")
        self.assertIsNone(initial["latest_journal"])
        self.call("resolve", snapshot=self.snap(positions=[position()]), intent_id="a1", outcome="completed",
                  readback_verified=True, broker_tickets=["p1"], evidence_ref="synthetic:entry-filled")
        original = checker.run("context", db_path=self.db, now=self.now)["context"]["items"][0]["intent"]["action"]
        self.assertEqual(checker.run("status", db_path=self.db, now=self.now)["outstanding_intents"], [])
        trail = {"version": 1, "operation": "trail", "rationale": "New confirmed higher low permits a tighter stop.",
                 "origin_intent_id": "a1", "source_refs": ["synthetic:new-higher-low"]}
        changed = self.call("prepare", snapshot=self.snap(positions=[position()]),
                            action=self.reduction("trail-1", tool="synthetic_mcp.modify_sl",
                                                  parameters={"ticket": "p1", "sl": Decimal("1.095")}, context=trail))
        self.assertTrue(changed["may_dispatch"])
        self.call("resolve", snapshot=self.snap(positions=[position()]), intent_id="trail-1", outcome="unknown",
                  evidence_ref="synthetic:modify-timeout")
        self.call("journal", **self.journal_request(intent_id="trail-1", activity="blocked",
                                                   summary="Stop change remains unverified"))
        for _ in range(3):
            self.call("journal", **self.journal_request())
        before = self.db.read_bytes()
        page = checker.run("context", db_path=self.db, now=self.now)["context"]
        item = page["items"][0]
        self.assertEqual(item["intent"]["action"], original)
        self.assertEqual(item["intent"]["action"]["risk"], "1.250000000001")
        self.assertEqual(item["latest_action"]["id"], "trail-1")
        self.assertEqual(item["latest_action"]["status"], "unknown")
        self.assertEqual(item["latest_journal"]["summary"], "Stop change remains unverified")
        related = checker.run("context", {"origin_intent_id": "a1", "limit": 1}, self.db, self.now)["context"]
        self.assertEqual(related["origin"]["action"], original)
        self.assertEqual(related["items"][0]["intent"]["id"], "trail-1")
        older = checker.run("context", {"origin_intent_id": "a1", "before": related["next_cursor"]}, self.db, self.now)["context"]
        self.assertEqual([row["intent"]["id"] for row in older["items"]], ["a1"])
        self.assertEqual(self.db.read_bytes(), before)

    def test_context_validation_blocks_new_risk_without_discarding_observed_loss(self):
        self.start()
        context = self.entry()["context"]
        variants = [None, {}, dict(context, version=True), dict(context, version=2), dict(context, operation="hedge"),
                    dict(context, rationale=""), dict(context, rationale="x" * 2001), dict(context, rationale="\x00bad"),
                    dict(context, source_refs=[]), dict(context, source_refs=["https://private.example/token"]),
                    dict(context, source_refs=["same", "same"]), dict(context, source_refs=[str(i) for i in range(65)]),
                    dict(context, credential="not-allowed"), dict(context, origin_intent_id="other"),
                    dict(context, strategy=dict(context["strategy"], budget="100")),
                    dict(context, strategy=dict(context["strategy"], side="hold")),
                    dict(context, strategy=dict(context["strategy"], trailing_rule=None)),
                    dict(context, strategy=dict(context["strategy"], addition_rule=True)),
                    dict(context, strategy=dict(context["strategy"], timeframe="H1"))]
        for index, invalid in enumerate(variants):
            with self.subTest(index=index):
                result = self.call("prepare", snapshot=self.snap(), action=self.entry("invalid-" + str(index), context=invalid))
                self.assertFalse(result["may_dispatch"])
                self.assertTrue(result["reason_codes"])
        self.assertEqual(checker.run("status", db_path=self.db, now=self.now)["outstanding_intents"], [])
        disabled = copy.deepcopy(context)
        disabled["strategy"].update({field: False for field in checker.STRATEGY_RULES})
        self.assertEqual(checker.action_context(disabled)["strategy"]["addition_rule"], False)
        breached = self.call("prepare", snapshot=self.snap("95", positions=[position()]), action=self.entry(context=None))
        self.assertFalse(breached["may_dispatch"])
        self.assertIsNotNone(self.state()["loss_latched_at"])
        emergency = self.call("prepare", snapshot=self.snap("95", positions=[position()]), action=self.reduction(reason="loss"))
        self.assertTrue(emergency["may_dispatch"])

    def test_related_context_requires_settled_original_plan_and_matching_scope(self):
        self.start()
        self.call("prepare", snapshot=self.snap(), action=self.entry())
        self.call("resolve", snapshot=self.snap(positions=[position(risk="0.1")]), intent_id="a1", outcome="completed",
                  broker_tickets=["p1"], readback_verified=True, evidence_ref="synthetic:root-filled")
        addition = {"version": 1, "operation": "add", "rationale": "Fresh continuation with all previous legs protected.",
                    "origin_intent_id": "a1", "source_refs": ["synthetic:continuation"]}
        wrong_symbol = self.call("prepare", snapshot=self.snap(), action=self.entry("wrong-symbol", symbol="GBPUSD", context=addition))
        self.assertIn("context_origin_symbol_mismatch", wrong_symbol["reason_codes"])
        for root in ("missing", "foreign-account", "foreign-goal", "unsettled", "legacy"):
            if root != "missing":
                original = checker.run("context", db_path=self.db, now=self.now)["context"]["items"][0]["intent"]["action"]
                original = copy.deepcopy(original)
                original["id"] = root
                if root == "foreign-account":
                    original["account"]["server"] = "other-broker"
                elif root == "foreign-goal":
                    original["goal_id"] = "old-goal"
                elif root == "legacy":
                    original.pop("context")
                with closing(sqlite3.connect(self.db)) as connection, connection:
                    connection.execute("INSERT INTO intents(id, status, payload) VALUES (?, ?, ?)",
                                       (root, "not_executed" if root == "unsettled" else "completed", checker.encode(original)))
            invalid = self.call("prepare", snapshot=self.snap(), action=self.entry("add-" + root, context=dict(addition, origin_intent_id=root)))
            self.assertFalse(invalid["may_dispatch"])
        valid = self.call("prepare", snapshot=self.snap(positions=[position(risk="0.1")]), action=self.entry("addition", risk="0.2", context=addition))
        self.assertTrue(valid["may_dispatch"])
        self.assertIsNone(valid["intent"]["context"]["strategy"])
        self.call("resolve", snapshot=self.snap(), intent_id="addition", outcome="completed", readback_verified=True,
                  broker_tickets=["p2"], evidence_ref="synthetic:add-settled")
        chained = self.call("prepare", snapshot=self.snap(), action=self.entry("chained", context=dict(addition, origin_intent_id="addition")))
        self.assertIn("context_origin_not_settled_entry", chained["reason_codes"])
        with self.assertRaisesRegex(checker.CheckError, "strategy_only_on_original_entry"):
            checker.action_context(dict(addition, strategy=self.entry()["context"]["strategy"]))

    def test_management_requires_context_but_unusable_emergency_metadata_never_grants_or_blocks_authority(self):
        self.start()
        for context in (None, {}, {"version": 1, "operation": "close", "rationale": "Exit condition met.",
                                   "source_refs": ["synthetic:exit"], "origin_intent_id": None}):
            rejected = self.call("prepare", snapshot=self.snap(positions=[position()]), action=self.reduction(context=context))
            self.assertFalse(rejected["may_dispatch"])
        for reason, equity in (("loss", "95"), ("target", "115"), ("protection_failure", "100")):
            fixture = AccountCheckTests()
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            fixture.start()
            legacy = fixture.entry("legacy")
            legacy.pop("context")
            legacy.update(account=ACCOUNT, owner_id="synthetic-owner", created_at=checker.utc(fixture.now),
                          snapshot_at=checker.utc(fixture.now))
            with closing(sqlite3.connect(fixture.db)) as connection, connection:
                connection.execute("INSERT INTO intents(id, status, payload) VALUES (?, ?, ?)",
                                   ("legacy", "completed", checker.encode(legacy)))
            contexts = [{}, {"version": 999}, {"version": 1, "operation": "close", "rationale": "Close exposure safely.",
                                            "source_refs": ["synthetic:emergency"], "origin_intent_id": "legacy"},
                        {"version": 1, "operation": "close", "rationale": "Close exposure safely.",
                         "source_refs": ["synthetic:emergency"], "origin_intent_id": "missing"}]
            for index, invalid in enumerate(contexts):
                with self.subTest(reason=reason, index=index):
                    action = fixture.reduction("emergency-" + str(index), reason=reason, context=invalid)
                    denied = fixture.call("prepare", snapshot=fixture.snap(equity, positions=[position()]),
                                          action=dict(action, tool_permission=False))
                    self.assertFalse(denied["may_dispatch"])
                    self.assertIn("missing_tool_permission", denied["reason_codes"])
                    result = fixture.call("prepare", snapshot=fixture.snap(equity, positions=[position()]), action=action)
                    self.assertTrue(result["may_dispatch"])
                    self.assertIn("action_context_unavailable", result["reason_codes"])
                    self.assertTrue(result["intent"]["context_warning"])
                    self.assertNotIn("context", result["intent"])
                    self.assertEqual(result["intent"]["parameters"], action["parameters"])
                    fixture.call("resolve", snapshot=fixture.snap(equity, positions=[position()]),
                                 intent_id=action["id"], outcome="not_executed", readback_verified=True,
                                 evidence_ref="synthetic:terminal-rejection")

    def test_context_pages_are_scoped_bounded_and_read_only_including_legacy_versions(self):
        with patch.object(sqlite3, "connect", side_effect=AssertionError("absent read must not open SQLite")):
            absent = checker.run("context", db_path=self.db, now=self.now)
        self.assertEqual(absent["decision"], "unconfigured")
        self.assertFalse(absent["may_continue"])
        self.assertFalse(self.db.exists())
        self.start()
        for entry_id in ("first", "second", "third"):
            self.call("prepare", snapshot=self.snap(), action=self.entry(entry_id))
            self.call("resolve", snapshot=self.snap(), intent_id=entry_id, outcome="completed", readback_verified=True,
                      broker_tickets=["ticket-" + entry_id], evidence_ref="synthetic:settled-" + entry_id)
        before = self.db.read_bytes()
        ids, cursor = [], None
        while True:
            page = checker.run("context", {"before": cursor, "limit": 1}, self.db, self.now)["context"]
            ids.extend(row["intent"]["id"] for row in page["items"])
            if page["next_cursor"] is None:
                break
            self.assertTrue(cursor is None or page["next_cursor"] < cursor)
            cursor = page["next_cursor"]
        self.assertEqual(ids, ["third", "second", "first"])
        for invalid in ({"limit": 0}, {"limit": 101}, {"limit": True}, {"before": 0}, {"before": True},
                        {"before": 9223372036854775808}, {"account": ACCOUNT}, {"owner_id": "other"},
                        {"origin_intent_id": "missing"}):
            with self.subTest(invalid=invalid), self.assertRaises(checker.CheckError):
                checker.run("context", invalid, self.db, self.now)
        self.assertEqual(self.db.read_bytes(), before)
        for version in (1, 2, 3, 4, 5):
            with closing(sqlite3.connect(self.db)) as connection, connection:
                connection.execute("PRAGMA user_version = " + str(version))
            before = self.db.read_bytes()
            self.assertEqual(len(checker.run("context", db_path=self.db, now=self.now)["context"]["items"]), 3)
            self.assertEqual(self.db.read_bytes(), before)
        with patch.multiple(checker, SCHEMA_VERSION=4, READABLE_SCHEMA_VERSIONS=(1, 2, 3, 4)), \
                self.assertRaisesRegex(checker.CheckError, "unsupported_schema"):
            checker.run("check", {"owner_id": "synthetic-owner", "expected_revision": self.revision,
                                  "snapshot": self.snap()}, self.db, self.now)
        self.assertEqual(self.db.read_bytes(), before)
        self.draft(budget="5", target="20", mandate=MANDATE)
        self.activate_again("new_goal")
        self.assertEqual(checker.run("context", db_path=self.db, now=self.now)["context"]["items"], [])
        with self.assertRaisesRegex(checker.CheckError, "context_origin_not_found"):
            checker.run("context", {"origin_intent_id": "first"}, self.db, self.now)

    def test_context_cli_needs_no_stdin_and_legacy_upgrade_never_invents_a_plan(self):
        self.start()
        self.call("prepare", snapshot=self.snap(), action=self.entry())
        self.call("resolve", snapshot=self.snap(), intent_id="a1", outcome="completed", readback_verified=True,
                  broker_tickets=["pending-1"], evidence_ref="synthetic:pending-accepted")
        with closing(sqlite3.connect(self.db)) as connection, connection:
            action = checker.decode(connection.execute("SELECT payload FROM intents WHERE id='a1'").fetchone()[0], exact_numbers=False)
            action.pop("context")
            connection.execute("UPDATE intents SET payload = ? WHERE id='a1'", (checker.encode(action),))
            connection.execute("PRAGMA user_version = 4")
        before = self.db.read_bytes()
        command = [sys.executable, "-B", checker.__file__, "context", "--db", str(self.db), "--limit", "1", "--origin-intent-id", "a1"]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd=self.temp.name, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        readback = json.loads(result.stdout)
        self.assertNotIn("context", readback["context"]["origin"]["action"])
        self.assertFalse(readback["may_dispatch"])
        self.assertEqual(self.db.read_bytes(), before)
        self.call("journal", **self.journal_request())
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 5)
            self.assertEqual(checker.decode(connection.execute("SELECT payload FROM intents WHERE id='a1'").fetchone()[0], exact_numbers=False), action)

    def test_journal_cannot_create_or_activate_state(self):
        request = {"snapshot_id": "missing", "as_of": checker.utc(self.now)}
        with self.assertRaisesRegex(checker.CheckError, "setup_incomplete"):
            self.call("journal", **request)
        self.assertFalse(self.db.exists())
        self.draft(budget="5", target="15")
        before = self.state()
        with self.assertRaisesRegex(checker.CheckError, "setup_incomplete"):
            self.call("journal", **request)
        self.assertEqual(self.state(), before)

    def test_journal_rejects_bad_binding_and_metadata_without_mutating_state(self):
        self.start()
        request = self.journal_request()
        self.call("check", snapshot=self.snap("95", positions=[position()]))
        with self.assertRaisesRegex(checker.CheckError, "journal_snapshot_mismatch"):
            self.call("journal", **request)
        before = self.state()
        variants = [{"owner_id": "other"}, {"expected_revision": 0}, {"snapshot_id": "old"},
                    {"as_of": checker.utc(self.now + timedelta(seconds=1))}, {"intent_id": "not-an-intent"},
                    {"summary": "x" * 241}, {"summary": "\x00bad"}, {"activity": "may_dispatch"},
                    {"source_refs": ["C:\\private\\receipt.json"]}, {"symbols": ["EURUSD", "EURUSD"]},
                    {"peak": "0"}, {"summary": "x" * 131073}, {"pending_order_details": {}}]
        for changes in variants:
            with self.subTest(changes=list(changes)):
                with self.assertRaises(checker.CheckError):
                    self.call("journal", **self.journal_request(**changes))
                self.assertEqual(self.state(), before)
        self.assertIsNotNone(self.state()["loss_latched_at"])
        self.assertEqual(self.state()["last_result"]["decision"], "loss_stop")

    def test_journal_records_unknown_and_stopped_outcomes_after_owner_handoff(self):
        self.start()
        self.call("prepare", snapshot=self.snap(), action=self.entry())
        self.call("resolve", intent_id="a1", outcome="unknown", evidence_ref="synthetic-timeout", snapshot=self.snap())
        self.activate_again("resume", self.snap("95"), owner_id="new-owner", takeover_ref="synthetic-handoff")
        before = self.state()
        with closing(sqlite3.connect(self.db)) as connection:
            intents = connection.execute("SELECT * FROM intents").fetchall()
        self.call("journal", **self.journal_request(owner_id="new-owner", intent_id="a1", activity="blocked"))
        after = self.state()
        after.pop("last_journal")
        self.assertEqual(after, before)
        self.assertEqual(after["last_result"]["decision"], "loss_stop")
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT * FROM intents").fetchall(), intents)

    def test_journal_order_enrichment_is_exact_and_cannot_override_risk(self):
        self.start(pending_orders=[position("00042", "1", kind="entry")])
        details = {"ticket": "00042", "order_type": "buy_limit", "side": "buy", "volume_initial": "0.020",
                   "volume_remaining": "0.010", "entry_price": "1.090010000001", "stop_loss": "1.08",
                   "take_profit": None, "unset_fields": ["take_profit", "expires_at"],
                   "placed_at": self.state()["last_snapshot"]["as_of"], "ownership": "ace", "ownership_ref": "synthetic:entry-42"}
        before = self.state()
        self.call("journal", **self.journal_request(pending_order_details=[details]))
        recorded = self.state()["last_journal"]["pending_order_details"][0]
        self.assertEqual(recorded["ticket"], "00042")
        self.assertEqual(recorded["entry_price"], "1.090010000001")
        self.assertEqual(recorded["volume_remaining"], "0.010")
        self.assertEqual(self.state()["last_snapshot"], before["last_snapshot"])
        self.assertEqual(self.state()["last_metrics"], before["last_metrics"])
        for changes in ({"ticket": "not-in-snapshot"}, {"symbol": "GBPUSD"}, {"risk": "0"},
                        {"side": "hold"}, {"volume_unit": "USD"}, {"volume_remaining": "0.03"},
                        {"entry_price": 1.09}, {"entry_price": "NaN"}, {"ownership_ref": None},
                        {"stop_loss": "1.08", "unset_fields": ["stop_loss"]}, {"unset_fields": [42]},
                        {"placed_at": checker.utc(self.now + timedelta(seconds=1))}):
            with self.subTest(changes=changes):
                with self.assertRaises(checker.CheckError):
                    self.call("journal", **self.journal_request(pending_order_details=[dict(details, **changes)]))
        with self.assertRaisesRegex(checker.CheckError, "journal_order_mismatch"):
            self.call("journal", **self.journal_request(pending_order_details=[details, details]))

    def test_journal_v1_normalization_does_not_change_financial_state(self):
        self.start()
        before = self.state()
        legacy = copy.deepcopy(before)
        legacy.pop("loop", None)
        with closing(sqlite3.connect(self.db)) as connection, connection:
            checker.save_state(connection, self.revision, legacy, "synthetic-legacy", {}, self.now)
            connection.execute("PRAGMA user_version = 1")
        self.call("journal", **self.journal_request())
        after = self.state()
        after.pop("last_journal")
        self.assertEqual(after, before)
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], checker.SCHEMA_VERSION)

    def test_display_history_captures_final_accepted_results_not_stale_metrics(self):
        activated = self.start()
        with closing(sqlite3.connect(self.db)) as connection:
            first = json.loads(connection.execute("SELECT detail FROM events ORDER BY id DESC LIMIT 1").fetchone()[0])["display"]
        self.assertEqual(first["metrics"], activated["metrics"])
        self.assertEqual(first["as_of"], self.state()["last_snapshot"]["as_of"])
        self.assertNotIn("may_dispatch", first)
        sample = self.snap("103", remaining_close_costs=None)
        rejected_action = self.call("prepare", snapshot=sample, action=self.entry())
        self.assertIsNotNone(rejected_action["metrics"])
        with closing(sqlite3.connect(self.db)) as connection:
            display = json.loads(connection.execute("SELECT detail FROM events ORDER BY id DESC LIMIT 1").fetchone()[0])["display"]
        self.assertEqual(display["metrics"], rejected_action["metrics"])
        self.assertIsNone(display["metrics"]["progress_pct"])
        self.assertEqual(display["snapshot_id"], sample["id"])
        self.now += timedelta(seconds=61)
        self.call("check", snapshot=sample)
        with closing(sqlite3.connect(self.db)) as connection:
            display = json.loads(connection.execute("SELECT detail FROM events ORDER BY id DESC LIMIT 1").fetchone()[0])["display"]
        self.assertIsNone(display["metrics"])
        self.assertIsNone(display["as_of"])
        self.assertIsNone(display["snapshot_id"])
        self.assertEqual(self.state()["last_snapshot"]["id"], sample["id"])

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
