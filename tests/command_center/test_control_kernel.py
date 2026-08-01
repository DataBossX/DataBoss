"""Invariant tests for the one-writer control kernel."""

from __future__ import annotations

import datetime as dt
import threading
import unittest

from command_center import db as dbmod
from command_center import state_machines as sm
from command_center.errors import (
    AcceptedArtifactImmutable,
    HoldRemovalForbidden,
    InvalidStateTransition,
    LeaseExpired,
    LeaseHeld,
    NotAuthorized,
    StaleFencingToken,
    WatcherPermissionDenied,
)
from command_center.kernel import Actor, ControlKernel

from .support import OPERATOR, OWNER, VIEWER, WATCHER, KernelTestCase


class LeaseInvariantTests(KernelTestCase):
    def test_only_one_active_lease_per_scope(self):
        self.kernel.claim_lease(OWNER, "project.alpha")
        with self.assertRaises(LeaseHeld):
            self.kernel.claim_lease(OPERATOR, "project.alpha")

    def test_different_scopes_may_be_leased_independently(self):
        a = self.kernel.claim_lease(OWNER, "project.alpha")
        b = self.kernel.claim_lease(OPERATOR, "project.beta")
        self.assertNotEqual(a["lease_id"], b["lease_id"])

    def test_database_constraint_rejects_a_second_active_lease_row(self):
        """The invariant survives even if application code is bypassed."""
        self.kernel.claim_lease(OWNER, "project.alpha")
        with self.assertRaises(dbmod.IntegrityError):
            self.kernel.conn.execute(
                "INSERT INTO writer_leases(lease_id, resource_scope, writer_identity, state,"
                " fencing_sequence, issued_at, expires_at, heartbeat_interval_seconds,"
                " stale_threshold_seconds) VALUES"
                " ('lease_forced','project.alpha','writer:attacker','ACTIVE',99,"
                " '2026-08-01T00:00:00Z','2026-08-01T01:00:00Z',15,45)"
            )

    def test_concurrent_claims_produce_exactly_one_winner(self):
        """Twelve threads, twelve independent connections, one winner."""
        results, errors = [], []
        barrier = threading.Barrier(12)

        def claim(index):
            kernel = ControlKernel(
                __import__("command_center.db", fromlist=["db"]).connect(self.db_path)
            )
            actor = Actor(f"racer{index}", "OPERATOR")
            kernel.upsert_user(actor.user_id, f"Racer {index}", "OPERATOR")
            barrier.wait()
            try:
                results.append(kernel.claim_lease(actor, "project.contested"))
            except Exception as exc:
                errors.append(exc)
            finally:
                kernel.conn.close()

        threads = [threading.Thread(target=claim, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(len(results), 1, f"expected exactly one winner, got {len(results)}")
        self.assertEqual(len(errors), 11)
        self.assertTrue(all(isinstance(e, LeaseHeld) for e in errors),
                        f"unexpected error types: {[type(e).__name__ for e in errors]}")

    def test_fencing_sequence_is_monotonic_and_never_reused(self):
        seen = []
        for _ in range(4):
            lease = self.kernel.claim_lease(OWNER, "project.alpha")
            seen.append(lease["fencing_sequence"])
            self.kernel.release_lease(OWNER, lease["lease_id"])
        self.assertEqual(seen, [1, 2, 3, 4])
        self.assertEqual(len(set(seen)), 4)

    def test_stale_fencing_sequence_fails_closed(self):
        first = self.kernel.claim_lease(OWNER, "project.alpha")
        self.kernel.release_lease(OWNER, first["lease_id"])
        self.kernel.claim_lease(OPERATOR, "project.alpha")
        with self.assertRaises(StaleFencingToken):
            self.kernel.assert_fencing_current("project.alpha", first["fencing_sequence"])

    def test_never_issued_fencing_sequence_fails_closed(self):
        self.kernel.claim_lease(OWNER, "project.alpha")
        with self.assertRaises(StaleFencingToken):
            self.kernel.assert_fencing_current("project.alpha", 9999)

    def test_lost_heartbeat_expires_the_lease_and_frees_the_scope(self):
        moment = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc)
        kernel = ControlKernel.open(self.db_path, clock=lambda: moment)
        kernel.upsert_user("ryan", "Ryan", "OWNER")
        first = kernel.claim_lease(OWNER, "project.gamma", stale_threshold=10)

        later = moment + dt.timedelta(seconds=600)
        kernel._clock = lambda: later
        second = kernel.claim_lease(OPERATOR, "project.gamma")

        self.assertGreater(second["fencing_sequence"], first["fencing_sequence"])
        with self.assertRaises(LeaseExpired):
            kernel.heartbeat(first["lease_id"])
        kernel.conn.close()

    def test_watcher_cannot_claim_a_lease(self):
        with self.assertRaises(WatcherPermissionDenied):
            self.kernel.claim_lease(WATCHER, "project.alpha")

    def test_viewer_cannot_claim_a_lease(self):
        with self.assertRaises(NotAuthorized):
            self.kernel.claim_lease(VIEWER, "project.alpha")

    def test_force_release_requires_owner_and_is_audited(self):
        lease = self.kernel.claim_lease(OPERATOR, "project.alpha")
        with self.assertRaises(NotAuthorized):
            self.kernel.release_lease(OPERATOR, lease["lease_id"], force=True)
        self.kernel.release_lease(OWNER, lease["lease_id"], force=True)
        events = [e for e in self.kernel.audit_tail(50) if e["event_type"] == "LEASE_FORCE_RELEASED"]
        self.assertEqual(len(events), 1)
        self.assertEqual(self.kernel.get_lease(lease["lease_id"])["state"], "FORCE_RELEASED")


class HoldTests(KernelTestCase):
    def test_baseline_holds_exist(self):
        labels = self.kernel.hold_labels()
        for expected in ("Horizon Section 32", "Penterra Section 20", "Penterra Section 17"):
            self.assertIn(expected, labels)

    def test_hold_removal_is_refused_for_every_role(self):
        for actor in (OWNER, OPERATOR, VIEWER, WATCHER):
            with self.assertRaises(HoldRemovalForbidden):
                self.kernel.attempt_remove_hold(actor, "hold_section32")

    def test_hold_removal_attempt_is_always_audited_as_deny(self):
        with self.assertRaises(HoldRemovalForbidden):
            self.kernel.attempt_remove_hold(OWNER, "hold_section32")
        events = [e for e in self.kernel.audit_tail(50)
                  if e["event_type"] == "HOLD_REMOVAL_ATTEMPT"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["outcome"], "DENY")

    def test_direct_sql_delete_of_a_hold_is_rejected(self):
        with self.assertRaises(dbmod.DatabaseError):
            self.kernel.conn.execute("DELETE FROM holds WHERE hold_id='hold_section32'")

    def test_direct_sql_downgrade_of_a_hold_is_rejected(self):
        with self.assertRaises(dbmod.DatabaseError):
            self.kernel.conn.execute("UPDATE holds SET immutable=0 WHERE hold_id='hold_section32'")


class AuditTests(KernelTestCase):
    def test_chain_is_valid_after_normal_operation(self):
        self.issue_task()
        self.assertTrue(self.kernel.verify_audit_chain())

    def test_audit_events_cannot_be_updated_or_deleted(self):
        self.kernel.claim_lease(OWNER, "project.alpha")
        with self.assertRaises(dbmod.DatabaseError):
            self.kernel.conn.execute("UPDATE audit_events SET actor='forged' WHERE audit_id=1")
        with self.assertRaises(dbmod.DatabaseError):
            self.kernel.conn.execute("DELETE FROM audit_events WHERE audit_id=1")

    def test_state_change_and_audit_share_a_transaction(self):
        """If the audit write fails, the state change must not survive."""
        before = self.kernel.get_lease(
            self.kernel.claim_lease(OWNER, "project.alpha")["lease_id"]
        )["state"]
        self.assertEqual(before, "ACTIVE")

        original_audit = self.kernel._audit

        def exploding_audit(*args, **kwargs):
            raise RuntimeError("injected audit failure")

        self.kernel._audit = exploding_audit
        try:
            with self.assertRaises(RuntimeError):
                self.kernel.claim_lease(OPERATOR, "project.delta")
        finally:
            self.kernel._audit = original_audit

        # The lease row must have been rolled back with the failed audit.
        rows = self.kernel.conn.execute(
            "SELECT COUNT(*) FROM writer_leases WHERE resource_scope='project.delta'"
        ).fetchone()[0]
        self.assertEqual(rows, 0)
        # And the scope is still claimable afterwards.
        self.assertTrue(self.kernel.claim_lease(OPERATOR, "project.delta"))

    def test_outbox_event_is_written_with_the_state_change(self):
        self.kernel.claim_lease(OWNER, "project.alpha")
        count = self.kernel.conn.execute(
            "SELECT COUNT(*) FROM outbox WHERE topic='lease.claimed'"
        ).fetchone()[0]
        self.assertEqual(count, 1)


class StateMachineTests(unittest.TestCase):
    def test_declared_command_path_is_legal(self):
        path = ["DRAFT", "TRANSCRIBED", "INTERPRETED", "CONFIRMED", "CLASSIFIED", "DISPATCHED"]
        for current, target in zip(path, path[1:]):
            sm.assert_transition("command", current, target)

    def test_skipping_a_command_state_is_rejected(self):
        with self.assertRaises(InvalidStateTransition):
            sm.assert_transition("command", "DRAFT", "DISPATCHED")

    def test_job_cannot_execute_without_approval_step(self):
        with self.assertRaises(InvalidStateTransition):
            sm.assert_transition("job", "QUEUED", "EXECUTING")

    def test_terminal_states_have_no_exits(self):
        for machine, states in sm.TERMINAL.items():
            for state in states:
                self.assertEqual(sm.MACHINES[machine][state], frozenset())

    def test_accepted_artifact_may_only_be_superseded(self):
        self.assertEqual(sm.ARTIFACT["ACCEPTED"], frozenset({"SUPERSEDED"}))

    def test_reviewer_path_ends_in_pass_or_request_changes(self):
        sm.assert_transition("review", "REVIEWED", "PASS")
        sm.assert_transition("review", "REVIEWED", "REQUEST_CHANGES")
        with self.assertRaises(InvalidStateTransition):
            sm.assert_transition("review", "CLAIMED_READ_ONLY", "PASS")


class ArtifactTests(KernelTestCase):
    def test_registering_the_same_logical_id_creates_a_new_version(self):
        first = self.kernel.register_artifact(logical_id="a1", sha256="a" * 64, byte_size=10)
        second = self.kernel.register_artifact(logical_id="a1", sha256="b" * 64, byte_size=12)
        self.assertEqual(first["version_number"], 1)
        self.assertEqual(second["version_number"], 2)
        self.assertEqual(first["artifact_id"], second["artifact_id"])

    def test_accepted_version_cannot_be_overwritten(self):
        version = self.kernel.register_artifact(logical_id="a1", sha256="a" * 64, byte_size=10)
        self.kernel.accept_artifact_version(version["version_id"], OWNER)
        with self.assertRaises(AcceptedArtifactImmutable):
            self.kernel.overwrite_accepted_version(version["version_id"], "c" * 64)

    def test_accepted_version_cannot_be_deleted(self):
        version = self.kernel.register_artifact(logical_id="a1", sha256="a" * 64, byte_size=10)
        self.kernel.accept_artifact_version(version["version_id"], OWNER)
        with self.assertRaises(dbmod.DatabaseError):
            self.kernel.conn.execute(
                "DELETE FROM artifact_versions WHERE version_id=?", (version["version_id"],)
            )

    def test_only_owner_may_accept(self):
        version = self.kernel.register_artifact(logical_id="a1", sha256="a" * 64, byte_size=10)
        with self.assertRaises(NotAuthorized):
            self.kernel.accept_artifact_version(version["version_id"], OPERATOR)


if __name__ == "__main__":
    unittest.main()
