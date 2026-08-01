"""Vertical-slice acceptance test and Best Moves determinism."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from command_center import best_moves as bm
from command_center.slice import run_slice

from .support import KernelTestCase

CONTRACTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "packages", "contracts",
)


class VerticalSliceTests(unittest.TestCase):
    """The exact fifteen-step story the directive requires."""

    @classmethod
    def setUpClass(cls):
        cls.workdir = tempfile.mkdtemp(prefix="dbx-cc-slice-test-")
        cls.trace = run_slice(cls.workdir)
        cls.kernel = cls.trace.pop("kernel")
        cls.summary = cls.trace["summary"]
        cls.steps = {s["step"]: s for s in cls.trace["steps"]}

    @classmethod
    def tearDownClass(cls):
        cls.kernel.conn.close()
        shutil.rmtree(cls.workdir, ignore_errors=True)

    def test_hold_is_visible_at_sign_in(self):
        step = self.steps["authenticated_and_saw_hold"]
        self.assertIn("Horizon Section 32", step["holds"])
        self.assertIn("NO EXTERNAL RELEASE", step["banner"])

    def test_transcript_and_intent_are_confirmed_before_creation(self):
        step = self.steps["voice_intake_awaiting_confirmation"]
        self.assertTrue(step["requires_confirmation"])
        self.assertFalse(step["audio_retained"])
        self.assertEqual(len(step["transcript_sha256"]), 64)

    def test_best_moves_are_ranked_and_the_held_scope_is_withheld(self):
        step = self.steps["best_moves_ranked"]
        self.assertGreaterEqual(step["eligible"], 3)
        vetoed_ids = [v[0] for v in step["vetoed"]]
        self.assertIn("mv_section32_report", vetoed_ids)

    def test_a_single_writer_holds_a_lease_with_a_fencing_sequence(self):
        step = self.steps["writer_lease_claimed"]
        self.assertGreaterEqual(step["fencing_sequence"], 1)
        self.assertTrue(step["writer"].startswith("writer:"))

    def test_two_or_more_watchers_reviewed_read_only(self):
        step = self.steps["watchers_reviewed_read_only"]
        self.assertGreaterEqual(len(step["watchers"]), 2)

    def test_runner_completed_a_simulated_allowlisted_task(self):
        step = self.steps["runner_executed"]
        self.assertEqual(step["outcome"], "COMPLETED")
        self.assertEqual(step["mode"], "SIMULATED")
        self.assertTrue(step["artifacts"])

    def test_receipt_was_published_and_read_back(self):
        step = self.steps["drive_receipt_published_and_read_back"]
        self.assertTrue(step["verified"])
        self.assertEqual(step["local_sha256"], step["readback_sha256"])
        self.assertTrue(step["pointer_updated"])
        # No Drive folder was created, because no authority exists.
        self.assertEqual(step["folder_plan_created"], [])
        self.assertIn("NOT_GRANTED", step["folder_authority"])

    def test_repeating_the_command_does_not_execute_twice(self):
        self.assertTrue(self.steps["idempotency_proven"]["same_command"])

    def test_section32_hold_removal_failed_closed_with_an_audit_event(self):
        step = self.steps["section32_hold_removal_failed_closed"]
        self.assertTrue(step["refused"])
        self.assertGreaterEqual(step["audit_events"], 1)
        self.assertEqual(step["outcome"], "DENY")

    def test_all_holds_survived_the_run(self):
        for expected in ("Horizon Section 32", "Penterra Section 20", "Penterra Section 17"):
            self.assertIn(expected, self.summary["holds_preserved"])

    def test_audit_chain_is_intact_at_the_end(self):
        self.assertTrue(self.summary["audit_chain_valid"])

    def test_every_watcher_passed(self):
        for name, verdict in self.summary["watcher_verdicts"]:
            self.assertEqual(verdict, "PASS", f"{name} did not pass")

    def test_receipt_is_retrievable_and_hash_stable(self):
        from command_center.canonical import content_hash

        stored = self.kernel.get_receipt(self.summary["receipt_id"])
        self.assertIsNotNone(stored)
        self.assertEqual(content_hash(stored), self.summary["receipt_sha256"])


class BestMovesTests(KernelTestCase):
    def test_ranking_is_deterministic(self):
        posture = self.kernel.posture()
        first = [r.candidate.move_id for r in bm.rank_for(posture, role="OWNER")]
        second = [r.candidate.move_id for r in bm.rank_for(posture, role="OWNER")]
        self.assertEqual(first, second)

    def test_a_veto_removes_a_move_even_with_a_perfect_score(self):
        ranked = bm.rank_for(self.kernel.posture(), role="OWNER")
        section32 = next(r for r in ranked if r.candidate.move_id == "mv_section32_report")
        # Every scoring factor on this candidate is maximal by construction.
        self.assertFalse(section32.eligible)
        self.assertTrue(section32.vetoes)
        best = bm.best_next_move(ranked)
        self.assertNotEqual(best.candidate.move_id, "mv_section32_report")

    def test_eligible_moves_always_sort_ahead_of_vetoed_moves(self):
        ranked = bm.rank_for(self.kernel.posture(), role="OWNER")
        seen_ineligible = False
        for move in ranked:
            if not move.eligible:
                seen_ineligible = True
            elif seen_ineligible:
                self.fail("an eligible move sorted after a vetoed move")

    def test_stale_lease_vetoes_a_move(self):
        ranked = bm.rank_for(self.kernel.posture(), role="OWNER",
                             stale_lease_scopes=["project.synthetic-alpha"])
        move = next(r for r in ranked if r.candidate.move_id == "mv_sim_rollup")
        self.assertFalse(move.eligible)
        self.assertIn("stale", " ".join(move.vetoes).lower())

    def test_failed_hash_vetoes_a_move(self):
        ranked = bm.rank_for(self.kernel.posture(), role="OWNER",
                             failed_hash_scopes=["project.synthetic-alpha"])
        move = next(r for r in ranked if r.candidate.move_id == "mv_sim_rollup")
        self.assertFalse(move.eligible)

    def test_security_gate_failure_withholds_every_move(self):
        ranked = bm.rank_for(self.kernel.posture(), role="OWNER", security_gate_failed=True)
        self.assertTrue(all(not r.eligible for r in ranked))
        self.assertIsNone(bm.best_next_move(ranked))

    def test_every_move_explains_itself_completely(self):
        required = ("exact_action", "why_now", "expected_benefit", "risk", "confidence",
                    "owner", "prerequisites", "evidence_used", "approval_required",
                    "verification_method", "if_it_fails", "exact_next_click")
        for move in bm.rank_for(self.kernel.posture(), role="OWNER"):
            payload = move.to_dict()
            for field in required:
                self.assertIn(field, payload)
                self.assertIsNotNone(payload[field])

    def test_score_breakdown_sums_to_the_reported_score(self):
        for move in bm.rank_for(self.kernel.posture(), role="OWNER"):
            payload = move.to_dict()
            total = sum(payload["score_breakdown"].values())
            self.assertAlmostEqual(max(0.0, total), payload["score"], places=3)

    def test_weights_are_normalised(self):
        self.assertAlmostEqual(sum(bm.WEIGHTS.values()), 1.0, places=6)

    def test_viewer_sees_fewer_eligible_moves_than_owner(self):
        posture = self.kernel.posture()
        owner = [r for r in bm.rank_for(posture, role="OWNER") if r.eligible]
        viewer = [r for r in bm.rank_for(posture, role="VIEWER") if r.eligible]
        self.assertLess(len(viewer), len(owner))


class ContractTests(unittest.TestCase):
    REQUIRED = (
        "COMMAND_ENVELOPE_SCHEMA.json",
        "TASK_ENVELOPE_SCHEMA.json",
        "APPROVAL_SCHEMA.json",
        "WRITER_LEASE_SCHEMA.json",
        "VERIFICATION_RECEIPT_SCHEMA.json",
    )

    def test_all_required_schemas_exist_and_parse(self):
        for name in self.REQUIRED:
            path = os.path.join(CONTRACTS_DIR, name)
            self.assertTrue(os.path.isfile(path), f"missing contract {name}")
            with open(path) as handle:
                schema = json.load(handle)
            self.assertIn("$schema", schema)
            self.assertIn("title", schema)
            self.assertIn("required", schema)

    def test_task_envelope_requires_fencing_and_lease(self):
        with open(os.path.join(CONTRACTS_DIR, "TASK_ENVELOPE_SCHEMA.json")) as handle:
            schema = json.load(handle)
        for field in ("fencing_sequence", "lease_id", "nonce", "expires_at", "content_sha256"):
            self.assertIn(field, schema["required"])

    def test_approval_is_single_use_by_contract(self):
        with open(os.path.join(CONTRACTS_DIR, "APPROVAL_SCHEMA.json")) as handle:
            schema = json.load(handle)
        self.assertEqual(schema["properties"]["single_use"]["const"], True)
        self.assertIn("single_use", schema["required"])

    def test_receipt_records_holds_and_execution_mode(self):
        with open(os.path.join(CONTRACTS_DIR, "VERIFICATION_RECEIPT_SCHEMA.json")) as handle:
            schema = json.load(handle)
        self.assertIn("holds_in_effect", schema["required"])
        self.assertIn("execution_mode", schema["required"])
        statuses = schema["properties"]["checks"]["items"]["properties"]["status"]["enum"]
        self.assertIn("NOT_RUN", statuses)


if __name__ == "__main__":
    unittest.main()
