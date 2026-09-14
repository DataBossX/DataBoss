"""Tests for the stateless task-capability preflight helper.

Dependency-free: uses only the standard library (unittest). Run with:

    python3 -m unittest tests.test_capability_preflight -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from databossx.capability_preflight import (  # noqa: E402
    AccessEvidence,
    AccessLevel,
    AttachmentCheck,
    AttachmentState,
    EvidenceFreshness,
    FetchAttempt,
    InputState,
    ObservedCapability,
    RunningClaimEvidence,
    TestExecutionEvidence,
    TestExecutionKind,
    can_claim_managed_running,
    classify_access,
    classify_attachment,
    classify_freshness,
    classify_input,
    classify_test_execution,
    sanitize_for_public_output,
    satisfies_input_requirement,
    satisfies_local_pc_requirement,
)


class ClassifyAccessTests(unittest.TestCase):
    def test_cloud_checkout_cannot_satisfy_local_pc_requirement(self) -> None:
        """Test 1: a cloud clone cannot satisfy a local-PC requirement."""
        evidence = AccessEvidence(designated_pc_marker_found=False)
        level = classify_access(evidence)
        self.assertEqual(level, AccessLevel.CLOUD_CHECKOUT)
        self.assertFalse(satisfies_local_pc_requirement(level))

    def test_verified_pc_marker_satisfies_local_pc_requirement(self) -> None:
        evidence = AccessEvidence(
            designated_pc_marker_found=True,
            designated_pc_marker_source="C:\\DataBoss\\_CONTROL\\TASKS\\ping.ok",
        )
        level = classify_access(evidence)
        self.assertEqual(level, AccessLevel.VERIFIED_LOCAL_PC)
        self.assertTrue(satisfies_local_pc_requirement(level))


class ClassifyInputTests(unittest.TestCase):
    def test_blocked_fetch_is_unreadable_not_empty(self) -> None:
        """Test 2: a blocked Drive request does not mean the document is empty."""
        attempt = FetchAttempt(error="EGRESS_BLOCKED", content=None)
        state = classify_input(attempt)
        self.assertEqual(state, InputState.UNREADABLE)
        self.assertNotEqual(state, InputState.EMPTY)

    def test_zero_byte_successful_fetch_is_empty(self) -> None:
        attempt = FetchAttempt(error=None, content=b"")
        self.assertEqual(classify_input(attempt), InputState.EMPTY)

    def test_successful_fetch_with_bytes_is_readable(self) -> None:
        attempt = FetchAttempt(error=None, content=b"hello")
        self.assertEqual(classify_input(attempt), InputState.READABLE)


class ClassifyTestExecutionTests(unittest.TestCase):
    def test_missing_dispatcher_does_not_block_independent_tests(self) -> None:
        """Test 3: a missing dispatcher does not block independent synthetic tests."""
        evidence = TestExecutionEvidence(dispatcher_job_id=None, ran_directly_in_session=True)
        kind = classify_test_execution(evidence)
        self.assertEqual(kind, TestExecutionKind.INDEPENDENT_DIRECT_SESSION)

    def test_dispatcher_job_id_present_is_managed(self) -> None:
        evidence = TestExecutionEvidence(dispatcher_job_id="job-123", ran_directly_in_session=False)
        self.assertEqual(classify_test_execution(evidence), TestExecutionKind.MANAGED_DISPATCHER_JOB)

    def test_neither_present_is_none(self) -> None:
        evidence = TestExecutionEvidence(dispatcher_job_id=None, ran_directly_in_session=False)
        self.assertEqual(classify_test_execution(evidence), TestExecutionKind.NONE)


class ClassifyAttachmentTests(unittest.TestCase):
    def test_local_attachment_satisfies_input_without_drive(self) -> None:
        """Test 4: an attachment can satisfy an input requirement without Drive."""
        check = AttachmentCheck(local_bytes_available=True, remote_link_reachable=False)
        state = classify_attachment(check)
        self.assertEqual(state, AttachmentState.ATTACHED_READABLE)
        self.assertTrue(satisfies_input_requirement(state))

    def test_no_local_bytes_and_unreachable_link_is_unavailable(self) -> None:
        check = AttachmentCheck(local_bytes_available=False, remote_link_reachable=False)
        state = classify_attachment(check)
        self.assertEqual(state, AttachmentState.UNAVAILABLE_LINK)
        self.assertFalse(satisfies_input_requirement(state))

    def test_no_local_bytes_but_reachable_link_is_not_yet_attached(self) -> None:
        check = AttachmentCheck(local_bytes_available=False, remote_link_reachable=True)
        state = classify_attachment(check)
        self.assertEqual(state, AttachmentState.NONE)
        self.assertFalse(satisfies_input_requirement(state))


class ManagedRunningClaimTests(unittest.TestCase):
    def test_no_worker_ack_means_no_managed_running_claim(self) -> None:
        """Test 5: no genuine managed-worker ACK means no managed RUNNING claim."""
        evidence = RunningClaimEvidence(worker_ack_id=None, heartbeat_seen=False, dispatcher_job_id=None)
        self.assertFalse(can_claim_managed_running(evidence))

    def test_partial_evidence_still_refuses_the_claim(self) -> None:
        evidence = RunningClaimEvidence(
            worker_ack_id="worker-9",
            heartbeat_seen=False,
            dispatcher_job_id="job-123",
        )
        self.assertFalse(can_claim_managed_running(evidence))

    def test_full_genuine_evidence_permits_the_claim(self) -> None:
        evidence = RunningClaimEvidence(
            worker_ack_id="worker-9",
            heartbeat_seen=True,
            dispatcher_job_id="job-123",
        )
        self.assertTrue(can_claim_managed_running(evidence))


class SanitizeForPublicOutputTests(unittest.TestCase):
    def test_public_output_excludes_sensitive_locators_and_telemetry(self) -> None:
        """Test 6: public output excludes sensitive locators and telemetry."""
        raw = (
            "See https://drive.google.com/file/d/1blfeXczHlIz3kkSzHJ8MYgedKX_cEdF2/view "
            "and session https://claude.ai/code/session_015b1RpVhtJ1XdXpE9mtQxte, "
            "reachable at 127.0.0.1:4210, checkout C:\\DataBoss\\Files\\DataBossXLandmanHelper."
        )
        sanitized = sanitize_for_public_output(raw)
        self.assertNotIn("drive.google.com", sanitized)
        self.assertNotIn("session_015b1RpVhtJ1XdXpE9mtQxte", sanitized)
        self.assertNotIn("127.0.0.1:4210", sanitized)
        self.assertNotIn("C:\\DataBoss", sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_ordinary_text_is_left_untouched(self) -> None:
        raw = "Working tree is clean on branch main."
        self.assertEqual(sanitize_for_public_output(raw), raw)


class FreshnessTests(unittest.TestCase):
    def test_unverified_observation_is_not_current(self) -> None:
        capability = ObservedCapability(observed_at_epoch=1000.0, verified=False, max_age_seconds=60.0)
        self.assertEqual(classify_freshness(capability, now_epoch=1000.0), EvidenceFreshness.UNVERIFIED)

    def test_stale_observation_is_not_current(self) -> None:
        capability = ObservedCapability(observed_at_epoch=1000.0, verified=True, max_age_seconds=60.0)
        self.assertEqual(classify_freshness(capability, now_epoch=1200.0), EvidenceFreshness.STALE)

    def test_recent_verified_observation_is_current(self) -> None:
        capability = ObservedCapability(observed_at_epoch=1000.0, verified=True, max_age_seconds=60.0)
        self.assertEqual(classify_freshness(capability, now_epoch=1010.0), EvidenceFreshness.CURRENT)


if __name__ == "__main__":
    unittest.main()
