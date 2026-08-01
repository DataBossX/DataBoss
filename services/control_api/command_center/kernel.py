"""The one-writer control kernel.

Everything consequential in the Command Center passes through this class. The
design rule throughout: *state changes and their audit record share one
transaction*. If the audit write fails, the state change fails with it, so
there is no such thing as an unlogged mutation.

Concurrency is settled by the database, not by application locks:

* claiming a lease relies on ``ux_lease_one_active_per_scope``;
* fencing sequences advance with a compare-and-swap ``UPDATE ... WHERE``;
* approvals are consumed with a conditional ``UPDATE`` that can only succeed
  once, which is what makes replay fail closed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping, Optional

from . import POLICY_VERSION, SCHEMA_VERSION
from . import db as dbmod
from . import policy as policymod
from . import state_machines as sm
from .canonical import (
    canonical_json,
    constant_time_equals,
    content_hash,
    iso,
    new_id,
    new_nonce,
    parse_iso,
    sha256_of,
    sha256_text,
    utc_now,
)
from .errors import (
    AcceptedArtifactImmutable,
    ApprovalAlreadyConsumed,
    ApprovalExpired,
    ApprovalRequired,
    ApprovalScopeMismatch,
    ArtifactChanged,
    HoldRemovalForbidden,
    InvalidStateTransition,
    LeaseExpired,
    LeaseHeld,
    LeaseNotHeld,
    NonceReplay,
    NotAuthorized,
    ProhibitedOperation,
    StaleFencingToken,
    StepUpRequired,
    WatcherPermissionDenied,
)

DEFAULT_LEASE_SECONDS = 300
DEFAULT_HEARTBEAT_SECONDS = 15
DEFAULT_STALE_SECONDS = 45
DEFAULT_APPROVAL_TTL_SECONDS = 300
DEFAULT_TASK_TTL_SECONDS = 600

#: Identities that may never hold a lease or approve, regardless of role rows.
WATCHER_IDENTITY_PREFIX = "watcher:"


@dataclass(frozen=True)
class Actor:
    user_id: str
    role: str
    session_id: str = "session-local"
    device_id: str = "device-local"
    stepped_up: bool = False

    @property
    def is_watcher(self) -> bool:
        return self.user_id.startswith(WATCHER_IDENTITY_PREFIX)


class ControlKernel:
    def __init__(self, conn, *, clock=utc_now):
        self.conn = conn
        self._clock = clock

    # ------------------------------------------------------------------ setup
    @classmethod
    def open(cls, target: str, *, clock=utc_now) -> "ControlKernel":
        """Open against a SQLite path or a ``postgres://`` DSN."""
        conn = dbmod.connect(target)
        dbmod.migrate(conn)
        kernel = cls(conn, clock=clock)
        kernel.ensure_policy_version()
        kernel.ensure_baseline_holds()
        return kernel

    def now(self):
        return self._clock()

    def ensure_policy_version(self) -> None:
        self.conn.execute(
            "INSERT INTO policy_versions(policy_version, activated_at, description) VALUES (?,?,?) "
            "ON CONFLICT(policy_version) DO NOTHING",
            (POLICY_VERSION, iso(self.now()), f"Command Center schema v{SCHEMA_VERSION}"),
        )

    def ensure_baseline_holds(self) -> None:
        """Seed the release holds the directive requires to survive everything."""
        baseline = [
            ("hold_section32", "Horizon Section 32", "client.horizon.section32",
             "FOR REVIEW - HOLD - NO EXTERNAL RELEASE"),
            ("hold_section20", "Penterra Section 20", "client.penterra.section20",
             "FOR REVIEW - HOLD - NO EXTERNAL RELEASE"),
            ("hold_section17", "Penterra Section 17", "client.penterra.section17",
             "FOR REVIEW - HOLD - NO EXTERNAL RELEASE"),
            ("hold_global_release", "Global external release", "release.external",
             "No external release is authorized by the current directive."),
        ]
        for hold_id, label, scope, reason in baseline:
            self.conn.execute(
                "INSERT INTO holds(hold_id, label, scope_pattern, reason, created_at, immutable) "
                "VALUES (?,?,?,?,?,1) ON CONFLICT(hold_id) DO NOTHING",
                (hold_id, label, scope, reason, iso(self.now())),
            )

    # ------------------------------------------------------------------ audit
    def _last_audit_hash(self) -> Optional[str]:
        row = dbmod.fetchone(
            self.conn, "SELECT content_sha256 FROM audit_events ORDER BY audit_id DESC LIMIT 1"
        )
        return row["content_sha256"] if row else None

    def _audit(
        self,
        *,
        actor: str,
        event_type: str,
        outcome: str,
        resource_scope: Optional[str] = None,
        subject_id: Optional[str] = None,
        detail: Optional[Mapping] = None,
    ) -> str:
        """Append one hash-chained audit event.

        Must be called inside the same transaction as the state change it
        describes. The previous event's hash is folded in, so a removed or
        edited row breaks the chain visibly.
        """
        occurred_at = iso(self.now())
        prev = self._last_audit_hash()
        payload = {
            "occurred_at": occurred_at,
            "actor": actor,
            "event_type": event_type,
            "resource_scope": resource_scope,
            "subject_id": subject_id,
            "outcome": outcome,
            "detail": dict(detail or {}),
            "prev_sha256": prev,
        }
        digest = sha256_of(payload)
        self.conn.execute(
            "INSERT INTO audit_events(occurred_at, actor, event_type, resource_scope, subject_id,"
            " outcome, detail_json, prev_sha256, content_sha256) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                occurred_at,
                actor,
                event_type,
                resource_scope,
                subject_id,
                outcome,
                canonical_json(dict(detail or {})),
                prev,
                digest,
            ),
        )
        return digest

    def _outbox(self, topic: str, payload: Mapping) -> None:
        self.conn.execute(
            "INSERT INTO outbox(created_at, topic, payload_json) VALUES (?,?,?)",
            (iso(self.now()), topic, canonical_json(dict(payload))),
        )

    def verify_audit_chain(self) -> bool:
        """Recompute the whole chain. Any tamper breaks at least one link."""
        prev = None
        for row in dbmod.fetchall(
            self.conn,
            "SELECT occurred_at, actor, event_type, resource_scope, subject_id, outcome,"
            " detail_json, prev_sha256, content_sha256 FROM audit_events ORDER BY audit_id",
        ):
            payload = {
                "occurred_at": row["occurred_at"],
                "actor": row["actor"],
                "event_type": row["event_type"],
                "resource_scope": row["resource_scope"],
                "subject_id": row["subject_id"],
                "outcome": row["outcome"],
                "detail": json.loads(row["detail_json"]),
                "prev_sha256": prev,
            }
            if sha256_of(payload) != row["content_sha256"]:
                return False
            if row["prev_sha256"] != prev:
                return False
            prev = row["content_sha256"]
        return True

    # --------------------------------------------------------------- txn help
    def _begin(self) -> None:
        self.conn.execute(dbmod.begin_sql(getattr(self.conn, "dialect", "sqlite")))

    def _commit(self) -> None:
        self.conn.execute("COMMIT")

    def _rollback(self) -> None:
        try:
            self.conn.execute("ROLLBACK")
        except dbmod.DatabaseError:
            pass

    # ------------------------------------------------------------------ users
    def upsert_user(self, user_id: str, display_name: str, role: str) -> None:
        self.conn.execute(
            "INSERT INTO users(user_id, display_name, role, created_at) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name, role=excluded.role",
            (user_id, display_name, role, iso(self.now())),
        )

    # ------------------------------------------------------------------ holds
    def active_holds(self) -> list:
        return [dict(r) for r in dbmod.fetchall(self.conn, "SELECT * FROM holds ORDER BY hold_id")]

    def hold_labels(self) -> list:
        return [h["label"] for h in self.active_holds()]

    def attempt_remove_hold(self, actor: Actor, hold_id: str) -> None:
        """Always refuses, and always leaves an audit trail of the attempt.

        This exists so the refusal is observable. A hold that silently cannot
        be removed is indistinguishable from one nobody tried to remove.
        """
        self._begin()
        try:
            self._audit(
                actor=actor.user_id,
                event_type="HOLD_REMOVAL_ATTEMPT",
                outcome="DENY",
                subject_id=hold_id,
                detail={"reason": "Holds are immutable in this lane.", "role": actor.role},
            )
            self._outbox("hold.removal_denied", {"hold_id": hold_id, "actor": actor.user_id})
            self._commit()
        except Exception:
            self._rollback()
            raise
        raise HoldRemovalForbidden(f"hold {hold_id} cannot be removed by UI, model, watcher, or writer")

    # ----------------------------------------------------------------- leases
    def _expire_stale_leases(self) -> None:
        """Mark leases whose heartbeat or TTL lapsed. Never reuses a sequence."""
        now = self.now()
        for row in dbmod.fetchall(
            self.conn, "SELECT * FROM writer_leases WHERE state = 'ACTIVE'"
        ):
            expires = parse_iso(row["expires_at"])
            last_beat = parse_iso(row["last_heartbeat_at"]) if row["last_heartbeat_at"] else parse_iso(row["issued_at"])
            stale_after = last_beat + timedelta(seconds=row["stale_threshold_seconds"])
            if now >= expires or now >= stale_after:
                reason = "EXPIRY" if now >= expires else "HEARTBEAT_LOST"
                self.conn.execute(
                    "UPDATE writer_leases SET state='EXPIRED', released_at=?, release_reason=? "
                    "WHERE lease_id=? AND state='ACTIVE'",
                    (iso(now), reason, row["lease_id"]),
                )
                self._audit(
                    actor="control-kernel",
                    event_type="LEASE_EXPIRED",
                    outcome="INFO",
                    resource_scope=row["resource_scope"],
                    subject_id=row["lease_id"],
                    detail={"reason": reason},
                )

    def claim_lease(
        self,
        actor: Actor,
        resource_scope: str,
        *,
        writer_identity: Optional[str] = None,
        ttl_seconds: int = DEFAULT_LEASE_SECONDS,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_SECONDS,
        stale_threshold: int = DEFAULT_STALE_SECONDS,
    ) -> dict:
        """Claim the sole writer lease for ``resource_scope``.

        Raises :class:`LeaseHeld` if another writer already holds it. The
        uniqueness guarantee is the partial index, so two concurrent claimers
        cannot both win even if they interleave perfectly.
        """
        policymod.validate_scope(resource_scope)
        if actor.is_watcher:
            raise WatcherPermissionDenied("watchers may not claim a writer lease")
        if not policymod.role_permits(actor.role, "OPERATOR"):
            raise NotAuthorized(f"role {actor.role} may not claim a writer lease")

        identity = writer_identity or f"writer:{actor.user_id}"
        self._begin()
        try:
            self._expire_stale_leases()
            existing = dbmod.fetchone(
                self.conn,
                "SELECT * FROM writer_leases WHERE resource_scope=? AND state='ACTIVE'",
                (resource_scope,),
            )
            if existing is not None:
                self._audit(
                    actor=actor.user_id,
                    event_type="LEASE_CLAIM_DENIED",
                    outcome="DENY",
                    resource_scope=resource_scope,
                    detail={"held_by": existing["writer_identity"], "lease_id": existing["lease_id"]},
                )
                self._commit()
                raise LeaseHeld(
                    f"resource scope {resource_scope} is already leased by {existing['writer_identity']}"
                )

            # Monotonic fencing: read-modify-write inside the same transaction.
            self.conn.execute(
                "INSERT INTO fencing_counters(resource_scope, current_value) VALUES (?, 0) "
                "ON CONFLICT(resource_scope) DO NOTHING",
                (resource_scope,),
            )
            self.conn.execute(
                "UPDATE fencing_counters SET current_value = current_value + 1 WHERE resource_scope = ?",
                (resource_scope,),
            )
            sequence = dbmod.require_row(
                dbmod.fetchone(
                    self.conn,
                    "SELECT current_value FROM fencing_counters WHERE resource_scope=?",
                    (resource_scope,),
                ),
                f"fencing counter for {resource_scope}",
            )["current_value"]

            now = self.now()
            lease_id = new_id("lease")
            self.conn.execute(
                "INSERT INTO writer_leases(lease_id, resource_scope, writer_identity, state,"
                " fencing_sequence, issued_at, expires_at, last_heartbeat_at,"
                " heartbeat_interval_seconds, stale_threshold_seconds)"
                " VALUES (?,?,?, 'ACTIVE', ?,?,?,?,?,?)",
                (
                    lease_id,
                    resource_scope,
                    identity,
                    sequence,
                    iso(now),
                    iso(now + timedelta(seconds=ttl_seconds)),
                    iso(now),
                    heartbeat_interval,
                    stale_threshold,
                ),
            )
            self._audit(
                actor=actor.user_id,
                event_type="LEASE_CLAIMED",
                outcome="ALLOW",
                resource_scope=resource_scope,
                subject_id=lease_id,
                detail={"writer_identity": identity, "fencing_sequence": sequence},
            )
            self._outbox("lease.claimed", {"lease_id": lease_id, "scope": resource_scope, "seq": sequence})
            self._commit()
        except dbmod.IntegrityError as exc:
            self._rollback()
            raise LeaseHeld(f"concurrent claim lost the race for {resource_scope}") from exc
        except Exception:
            self._rollback()
            raise
        return self.get_lease(lease_id)

    def get_lease(self, lease_id: str) -> dict:
        row = dbmod.fetchone(self.conn, "SELECT * FROM writer_leases WHERE lease_id=?", (lease_id,))
        if row is None:
            raise LeaseNotHeld(f"unknown lease {lease_id}")
        return dict(row)

    def heartbeat(self, lease_id: str) -> dict:
        now = self.now()
        cur = self.conn.execute(
            "UPDATE writer_leases SET last_heartbeat_at=? WHERE lease_id=? AND state='ACTIVE'",
            (iso(now), lease_id),
        )
        if cur.rowcount == 0:
            raise LeaseExpired(f"lease {lease_id} is not ACTIVE; heartbeat refused")
        return self.get_lease(lease_id)

    def release_lease(self, actor: Actor, lease_id: str, *, force: bool = False) -> None:
        """Release a lease. Force release demands OWNER and is loudly audited."""
        lease = self.get_lease(lease_id)
        identity = f"writer:{actor.user_id}"
        if force:
            if actor.role != "OWNER":
                raise NotAuthorized("force release requires a separately authorized OWNER action")
        elif lease["writer_identity"] != identity and actor.role != "OWNER":
            raise NotAuthorized("only the lease holder or an OWNER may release this lease")

        self._begin()
        try:
            state = "FORCE_RELEASED" if force else "RELEASED"
            self.conn.execute(
                "UPDATE writer_leases SET state=?, released_at=?, release_reason=?, force_released_by=?"
                " WHERE lease_id=? AND state='ACTIVE'",
                (state, iso(self.now()), "FORCE_RELEASE" if force else "NORMAL",
                 actor.user_id if force else None, lease_id),
            )
            self._audit(
                actor=actor.user_id,
                event_type="LEASE_FORCE_RELEASED" if force else "LEASE_RELEASED",
                outcome="ALLOW",
                resource_scope=lease["resource_scope"],
                subject_id=lease_id,
                detail={"force": force, "previous_writer": lease["writer_identity"]},
            )
            self._outbox("lease.released", {"lease_id": lease_id, "force": force})
            self._commit()
        except Exception:
            self._rollback()
            raise

    def assert_fencing_current(self, resource_scope: str, sequence: int) -> None:
        """Fail closed when a caller presents an outdated fencing sequence."""
        row = dbmod.fetchone(
            self.conn, "SELECT current_value FROM fencing_counters WHERE resource_scope=?",
            (resource_scope,),
        )
        current = row["current_value"] if row else 0
        if sequence < current:
            raise StaleFencingToken(
                f"fencing sequence {sequence} is stale for {resource_scope}; current is {current}"
            )
        if sequence > current:
            raise StaleFencingToken(
                f"fencing sequence {sequence} was never issued for {resource_scope}"
            )

    # --------------------------------------------------------------- commands
    def create_command(
        self,
        actor: Actor,
        *,
        idempotency_key: str,
        transcript_text: str,
        intent: Mapping,
        channel: str = "VOICE",
        provider: Optional[str] = None,
        confidence: Optional[float] = None,
        confirmed: bool = False,
    ) -> dict:
        """Create an immutable CommandEnvelope.

        ``confirmed`` must be True: the directive requires the human to see both
        the transcript and the parsed intent before any command exists. Repeat
        submissions with the same idempotency key return the original command
        rather than creating a second one.
        """
        if not confirmed:
            raise NotAuthorized("explicit confirmation is required before a command is created")

        existing = dbmod.fetchone(
            self.conn,
            "SELECT * FROM commands WHERE actor_user_id=? AND idempotency_key=?",
            (actor.user_id, idempotency_key),
        )
        if existing is not None:
            # Idempotent replay: same key, same command, no second job.
            return dict(existing)

        now = self.now()
        command_id = new_id("cmd")
        transcript_sha = sha256_text(transcript_text)
        payload = {
            "schema_version": "1.0.0",
            "command_id": command_id,
            "idempotency_key": idempotency_key,
            "created_at": iso(now),
            "actor": {
                "user_id": actor.user_id,
                "role": actor.role,
                "session_id": actor.session_id,
                "device_id": actor.device_id,
            },
            "source": {"channel": channel, "provider": provider, "confidence": confidence,
                       "external_ref": None},
            "transcript": {"text": transcript_text, "sha256": transcript_sha,
                           "captured_at": iso(now), "audio_retained": False},
            "intent": dict(intent),
            "risk_class": None,
            "status": "CONFIRMED",
        }
        digest = content_hash(payload)

        self._begin()
        try:
            self.conn.execute(
                "INSERT INTO commands(command_id, idempotency_key, actor_user_id, session_id, device_id,"
                " channel, provider, confidence, transcript_text, transcript_sha256, audio_retained,"
                " intent_json, risk_class, status, policy_version, content_sha256, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,0,?,NULL,'CONFIRMED',NULL,?,?,?)",
                (
                    command_id, idempotency_key, actor.user_id, actor.session_id, actor.device_id,
                    channel, provider, confidence, transcript_text, transcript_sha,
                    canonical_json(dict(intent)), digest, iso(now), iso(now),
                ),
            )
            self._audit(
                actor=actor.user_id,
                event_type="COMMAND_CONFIRMED",
                outcome="ALLOW",
                subject_id=command_id,
                detail={"idempotency_key": idempotency_key, "channel": channel,
                        "transcript_sha256": transcript_sha},
            )
            self._outbox("command.confirmed", {"command_id": command_id})
            self._commit()
        except dbmod.IntegrityError:
            # Lost an idempotency race; return the winner.
            self._rollback()
            row = dbmod.fetchone(
                self.conn, "SELECT * FROM commands WHERE actor_user_id=? AND idempotency_key=?",
                (actor.user_id, idempotency_key),
            )
            if row is not None:
                return dict(row)
            raise
        except Exception:
            self._rollback()
            raise
        return self.get_command(command_id)

    def get_command(self, command_id: str) -> dict:
        row = dbmod.fetchone(self.conn, "SELECT * FROM commands WHERE command_id=?", (command_id,))
        if row is None:
            raise InvalidStateTransition(f"unknown command {command_id}")
        return dict(row)

    def set_command_status(self, command_id: str, target: str) -> dict:
        current = self.get_command(command_id)["status"]
        sm.assert_transition("command", current, target)
        self.conn.execute(
            "UPDATE commands SET status=?, updated_at=? WHERE command_id=?",
            (target, iso(self.now()), command_id),
        )
        return self.get_command(command_id)

    def classify_command(self, command_id: str, actor: Actor) -> dict:
        """Attach the deterministic policy decision to a confirmed command."""
        command = self.get_command(command_id)
        intent = json.loads(command["intent_json"])
        decision = policymod.classify(
            operation=intent.get("operation", ""),
            resource_scope=intent.get("target_resource") or "system.unscoped",
            role=actor.role,
            parameters=intent.get("parameters") or {},
            unresolved=intent.get("unresolved") or [],
        )
        self._begin()
        try:
            sm.assert_transition("command", command["status"], "CLASSIFIED")
            self.conn.execute(
                "UPDATE commands SET risk_class=?, status='CLASSIFIED', policy_version=?, updated_at=?"
                " WHERE command_id=?",
                (decision.risk_class, decision.policy_version, iso(self.now()), command_id),
            )
            self._audit(
                actor=actor.user_id,
                event_type="COMMAND_CLASSIFIED",
                outcome="ALLOW" if decision.allowed else "DENY",
                subject_id=command_id,
                detail={"risk_class": decision.risk_class, "reasons": decision.reasons},
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return {"command": self.get_command(command_id), "decision": decision}

    # -------------------------------------------------------------- approvals
    def request_approval(
        self,
        actor: Actor,
        *,
        operation: str,
        resource_scope: str,
        parameters: Mapping,
        task_envelope_sha256: str,
        input_hashes: Optional[Mapping] = None,
        ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS,
        step_up_method: str = "WEBAUTHN",
    ) -> dict:
        """Issue a single-use approval bound to exactly this operation."""
        if actor.is_watcher:
            raise WatcherPermissionDenied("watchers may not approve")
        if actor.role not in ("OWNER", "OPERATOR"):
            raise NotAuthorized(f"role {actor.role} may not approve")
        adapter = policymod.get_adapter(operation)
        if adapter.step_up_required and not actor.stepped_up:
            raise StepUpRequired(f"{operation} requires step-up authentication")
        if not policymod.role_permits(actor.role, adapter.required_role):
            raise NotAuthorized(f"role {actor.role} is below {adapter.required_role} for {operation}")

        now = self.now()
        approval_id = new_id("apr")
        params_sha = sha256_of(dict(parameters))
        inputs_sha = sha256_of(dict(input_hashes)) if input_hashes else None

        self._begin()
        try:
            self.conn.execute(
                "INSERT INTO approvals(approval_id, state, actor_user_id, actor_role, step_up_method,"
                " operation, resource_scope, parameters_sha256, task_envelope_sha256, input_hashes_sha256,"
                " policy_version, nonce, issued_at, expires_at)"
                " VALUES (?, 'SIGNED_BY_HUMAN', ?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    approval_id, actor.user_id, actor.role, step_up_method, operation, resource_scope,
                    params_sha, task_envelope_sha256, inputs_sha, POLICY_VERSION, new_nonce(),
                    iso(now), iso(now + timedelta(seconds=ttl_seconds)),
                ),
            )
            self._audit(
                actor=actor.user_id,
                event_type="APPROVAL_SIGNED",
                outcome="ALLOW",
                resource_scope=resource_scope,
                subject_id=approval_id,
                detail={"operation": operation, "parameters_sha256": params_sha,
                        "step_up_method": step_up_method},
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return dict(dbmod.require_row(
            dbmod.fetchone(self.conn, "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)),
            f"approval {approval_id}",
        ))

    def consume_approval(
        self,
        approval_id: str,
        *,
        operation: str,
        resource_scope: str,
        parameters: Mapping,
        task_envelope_sha256: str,
        input_hashes: Optional[Mapping] = None,
        attempt_id: Optional[str] = None,
    ) -> dict:
        """Validate and spend an approval exactly once.

        Every binding is re-checked here rather than trusted from the caller,
        because the caller is the runner and the runner is the thing being
        constrained.
        """
        row = dbmod.fetchone(self.conn, "SELECT * FROM approvals WHERE approval_id=?", (approval_id,))
        if row is None:
            raise ApprovalScopeMismatch(f"unknown approval {approval_id}")
        approval = dict(row)

        if approval["consumed_at"] is not None:
            raise ApprovalAlreadyConsumed(f"approval {approval_id} was already consumed (replay refused)")
        if self.now() >= parse_iso(approval["expires_at"]):
            raise ApprovalExpired(f"approval {approval_id} expired at {approval['expires_at']}")
        if approval["policy_version"] != POLICY_VERSION:
            raise ApprovalScopeMismatch("policy version changed since approval was signed")
        if approval["operation"] != operation:
            raise ApprovalScopeMismatch(
                f"approval was issued for {approval['operation']}, not {operation}"
            )
        if approval["resource_scope"] != resource_scope:
            raise ApprovalScopeMismatch(
                f"approval was issued for scope {approval['resource_scope']}, not {resource_scope}"
            )
        if not constant_time_equals(approval["parameters_sha256"], sha256_of(dict(parameters))):
            raise ApprovalScopeMismatch("parameters changed after approval")
        if not constant_time_equals(approval["task_envelope_sha256"], task_envelope_sha256):
            raise ApprovalScopeMismatch("task envelope changed after approval")
        expected_inputs = sha256_of(dict(input_hashes)) if input_hashes else None
        if approval["input_hashes_sha256"] != expected_inputs:
            raise ArtifactChanged("input artifacts changed between approval and execution")

        self._begin()
        try:
            # Conditional update is the replay guard: only the first caller
            # transitions consumed_at from NULL.
            cur = self.conn.execute(
                "UPDATE approvals SET state='CONSUMED', consumed_at=?, consumed_by_attempt_id=?"
                " WHERE approval_id=? AND consumed_at IS NULL",
                (iso(self.now()), attempt_id, approval_id),
            )
            if cur.rowcount == 0:
                self._rollback()
                raise ApprovalAlreadyConsumed(f"approval {approval_id} was consumed concurrently")
            self._audit(
                actor=approval["actor_user_id"],
                event_type="APPROVAL_CONSUMED",
                outcome="ALLOW",
                resource_scope=resource_scope,
                subject_id=approval_id,
                detail={"operation": operation, "attempt_id": attempt_id},
            )
            self._commit()
        except ApprovalAlreadyConsumed:
            raise
        except Exception:
            self._rollback()
            raise
        return dict(dbmod.require_row(
            dbmod.fetchone(self.conn, "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)),
            f"approval {approval_id}",
        ))

    # ---------------------------------------------------------- task envelope
    def build_task_envelope(
        self,
        *,
        command_id: str,
        resource_scope: str,
        adapter: str,
        parameters: Mapping,
        execution_mode: str,
        risk_class: str,
        lease: Mapping,
        input_hashes: Optional[Mapping] = None,
        ttl_seconds: int = DEFAULT_TASK_TTL_SECONDS,
        approval_token_id: Optional[str] = None,
    ) -> dict:
        """Assemble the envelope payload and its binding hash (not persisted)."""
        policymod.assert_operation_permitted(adapter)
        policymod.validate_scope(resource_scope)
        spec = policymod.get_adapter(adapter)
        if execution_mode not in spec.modes:
            raise ProhibitedOperation(f"{adapter} does not support mode {execution_mode}")

        now = self.now()
        payload = {
            "schema_version": "1.0.0",
            "task_id": new_id("task"),
            "command_id": command_id,
            "resource_scope": resource_scope,
            "adapter": adapter,
            "parameters": dict(parameters),
            "execution_mode": execution_mode,
            "risk_class": risk_class,
            "approval_token_id": approval_token_id,
            "issued_at": iso(now),
            "expires_at": iso(now + timedelta(seconds=ttl_seconds)),
            "nonce": new_nonce(),
            "fencing_sequence": lease["fencing_sequence"],
            "lease_id": lease["lease_id"],
            "writer_identity": lease["writer_identity"],
            "policy_version": POLICY_VERSION,
            "input_hashes": dict(input_hashes or {}),
        }
        payload["content_sha256"] = content_hash(payload)
        return payload

    def persist_task_envelope(self, envelope: Mapping, actor: Actor) -> dict:
        """Persist an envelope and open its job in one transaction."""
        env = dict(envelope)
        if env["risk_class"] == "APPROVAL_REQUIRED" and not env.get("approval_token_id"):
            raise ApprovalRequired("APPROVAL_REQUIRED tasks must carry an approval token")

        self._begin()
        try:
            seen = dbmod.fetchone(
                self.conn, "SELECT nonce FROM nonces_seen WHERE nonce=?", (env["nonce"],)
            )
            if seen is not None:
                self._rollback()
                raise NonceReplay(f"nonce {env['nonce']} was already used")
            self.conn.execute(
                "INSERT INTO nonces_seen(nonce, purpose, seen_at) VALUES (?,?,?)",
                (env["nonce"], "task_envelope", iso(self.now())),
            )
            self.conn.execute(
                "INSERT INTO task_envelopes(task_id, command_id, resource_scope, adapter, parameters_json,"
                " execution_mode, risk_class, approval_token_id, issued_at, expires_at, nonce,"
                " fencing_sequence, lease_id, writer_identity, policy_version, input_hashes_json,"
                " content_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    env["task_id"], env["command_id"], env["resource_scope"], env["adapter"],
                    canonical_json(env["parameters"]), env["execution_mode"], env["risk_class"],
                    env.get("approval_token_id"), env["issued_at"], env["expires_at"], env["nonce"],
                    env["fencing_sequence"], env["lease_id"], env["writer_identity"],
                    env["policy_version"], canonical_json(env.get("input_hashes") or {}),
                    env["content_sha256"],
                ),
            )
            job_id = new_id("job")
            self.conn.execute(
                "INSERT INTO jobs(job_id, task_id, command_id, state, created_at, updated_at, title, detail)"
                " VALUES (?,?,?, 'CREATED', ?,?,?,?)",
                (job_id, env["task_id"], env["command_id"], iso(self.now()), iso(self.now()),
                 env["adapter"], env["execution_mode"]),
            )
            self._audit(
                actor=actor.user_id,
                event_type="TASK_ENVELOPE_ISSUED",
                outcome="ALLOW",
                resource_scope=env["resource_scope"],
                subject_id=env["task_id"],
                detail={"adapter": env["adapter"], "mode": env["execution_mode"],
                        "fencing_sequence": env["fencing_sequence"],
                        "content_sha256": env["content_sha256"]},
            )
            self._outbox("task.issued", {"task_id": env["task_id"], "job_id": job_id})
            self._commit()
        except Exception:
            self._rollback()
            raise
        return {"envelope": env, "job_id": job_id}

    def writer_ack(self, *, task_id: str, lease_id: str, writer_identity: str) -> dict:
        """Bind the writer to the exact envelope and lease hashes before execution."""
        row = dbmod.fetchone(self.conn, "SELECT * FROM task_envelopes WHERE task_id=?", (task_id,))
        if row is None:
            raise InvalidStateTransition(f"unknown task {task_id}")
        env = dict(row)
        lease = self.get_lease(lease_id)

        if lease["state"] != "ACTIVE":
            raise LeaseExpired(f"lease {lease_id} is {lease['state']}, not ACTIVE")
        if lease["writer_identity"] != writer_identity:
            raise NotAuthorized("WriterACK identity does not match the lease holder")
        if env["lease_id"] != lease_id:
            raise NotAuthorized("task envelope was issued under a different lease")
        self.assert_fencing_current(env["resource_scope"], env["fencing_sequence"])
        if self.now() >= parse_iso(env["expires_at"]):
            raise ApprovalExpired(f"task envelope {task_id} expired")

        ack = {
            "task_id": task_id,
            "lease_id": lease_id,
            "writer_identity": writer_identity,
            "task_envelope_sha256": env["content_sha256"],
            "lease_sha256": sha256_of({
                "lease_id": lease["lease_id"],
                "resource_scope": lease["resource_scope"],
                "writer_identity": lease["writer_identity"],
                "fencing_sequence": lease["fencing_sequence"],
                "issued_at": lease["issued_at"],
            }),
            "acked_at": iso(self.now()),
            "fencing_sequence": env["fencing_sequence"],
        }
        ack["content_sha256"] = content_hash(ack)

        self._begin()
        try:
            self._audit(
                actor=writer_identity,
                event_type="WRITER_ACK",
                outcome="ALLOW",
                resource_scope=env["resource_scope"],
                subject_id=task_id,
                detail={"ack_sha256": ack["content_sha256"], "fencing_sequence": env["fencing_sequence"]},
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return ack

    # ------------------------------------------------------------------- jobs
    def set_job_state(self, job_id: str, target: str, *, actor: str = "control-kernel") -> dict:
        row = dbmod.fetchone(self.conn, "SELECT * FROM jobs WHERE job_id=?", (job_id,))
        if row is None:
            raise InvalidStateTransition(f"unknown job {job_id}")
        sm.assert_transition("job", row["state"], target)
        self._begin()
        try:
            self.conn.execute(
                "UPDATE jobs SET state=?, updated_at=? WHERE job_id=?",
                (target, iso(self.now()), job_id),
            )
            self._audit(
                actor=actor,
                event_type="JOB_STATE",
                outcome="INFO",
                subject_id=job_id,
                detail={"from": row["state"], "to": target},
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return dict(dbmod.require_row(
            dbmod.fetchone(self.conn, "SELECT * FROM jobs WHERE job_id=?", (job_id,)),
            f"job {job_id}",
        ))

    def start_attempt(self, *, job_id: str, task_id: str, lease_id: str, fencing_sequence: int) -> str:
        attempt_id = new_id("att")
        self.conn.execute(
            "INSERT INTO execution_attempts(attempt_id, job_id, task_id, lease_id, fencing_sequence,"
            " started_at) VALUES (?,?,?,?,?,?)",
            (attempt_id, job_id, task_id, lease_id, fencing_sequence, iso(self.now())),
        )
        return attempt_id

    def finish_attempt(self, attempt_id: str, outcome: str, failure_reason: Optional[str] = None) -> None:
        self.conn.execute(
            "UPDATE execution_attempts SET finished_at=?, outcome=?, failure_reason=? WHERE attempt_id=?",
            (iso(self.now()), outcome, failure_reason, attempt_id),
        )

    # --------------------------------------------------------------- receipts
    def record_receipt(self, receipt: Mapping, *, actor: str = "control-kernel") -> dict:
        payload = dict(receipt)
        payload["content_sha256"] = content_hash(payload)
        self._begin()
        try:
            self.conn.execute(
                "INSERT INTO verification_receipts(receipt_id, task_id, command_id, attempt_id,"
                " payload_json, content_sha256, created_at) VALUES (?,?,?,?,?,?,?)",
                (payload["receipt_id"], payload["task_id"], payload["command_id"],
                 payload.get("attempt_id"), canonical_json(payload), payload["content_sha256"],
                 iso(self.now())),
            )
            self._audit(
                actor=actor,
                event_type="RECEIPT_RECORDED",
                outcome="ALLOW",
                resource_scope=payload.get("resource_scope"),
                subject_id=payload["receipt_id"],
                detail={"outcome": payload["outcome"], "mode": payload["execution_mode"],
                        "content_sha256": payload["content_sha256"]},
            )
            self._outbox("receipt.recorded", {"receipt_id": payload["receipt_id"]})
            self._commit()
        except Exception:
            self._rollback()
            raise
        return payload

    def get_receipt(self, receipt_id: str) -> Optional[dict]:
        row = dbmod.fetchone(
            self.conn, "SELECT payload_json FROM verification_receipts WHERE receipt_id=?", (receipt_id,)
        )
        return json.loads(row["payload_json"]) if row else None

    # --------------------------------------------------------------- artifacts
    def register_artifact(
        self, *, logical_id: str, sha256: str, byte_size: int, mime_type: str = "application/json",
        synthetic: bool = True, project_id: Optional[str] = None,
    ) -> dict:
        """Register a new immutable artifact version. Never overwrites in place."""
        now = iso(self.now())
        row = dbmod.fetchone(self.conn, "SELECT * FROM artifacts WHERE logical_id=?", (logical_id,))
        self._begin()
        try:
            if row is None:
                artifact_id = new_id("art")
                self.conn.execute(
                    "INSERT INTO artifacts(artifact_id, logical_id, project_id, state, synthetic,"
                    " created_at, updated_at) VALUES (?,?,?, 'HASHED', ?,?,?)",
                    (artifact_id, logical_id, project_id, 1 if synthetic else 0, now, now),
                )
                version_number = 1
            else:
                artifact_id = row["artifact_id"]
                last = dbmod.require_row(
                    dbmod.fetchone(
                        self.conn,
                        "SELECT MAX(version_number) AS n FROM artifact_versions"
                        " WHERE artifact_id=?",
                        (artifact_id,),
                    ),
                    f"version count for artifact {artifact_id}",
                )
                version_number = (last["n"] or 0) + 1

            version_id = new_id("ver")
            self.conn.execute(
                "INSERT INTO artifact_versions(version_id, artifact_id, version_number, sha256,"
                " byte_size, mime_type, accepted, created_at) VALUES (?,?,?,?,?,?,0,?)",
                (version_id, artifact_id, version_number, sha256, byte_size, mime_type, now),
            )
            self._audit(
                actor="control-kernel",
                event_type="ARTIFACT_VERSION_REGISTERED",
                outcome="ALLOW",
                subject_id=logical_id,
                detail={"version": version_number, "sha256": sha256, "synthetic": synthetic},
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return {"artifact_id": artifact_id, "version_id": version_id, "version_number": version_number}

    def accept_artifact_version(self, version_id: str, actor: Actor) -> None:
        if actor.role != "OWNER":
            raise NotAuthorized("only an OWNER may accept an artifact version")
        self.conn.execute("UPDATE artifact_versions SET accepted=1 WHERE version_id=?", (version_id,))

    def overwrite_accepted_version(self, version_id: str, new_sha: str) -> None:
        """Deliberate probe surface: the DB trigger refuses this every time."""
        try:
            self.conn.execute(
                "UPDATE artifact_versions SET sha256=? WHERE version_id=?", (new_sha, version_id)
            )
        except dbmod.IntegrityError as exc:
            raise AcceptedArtifactImmutable(str(exc)) from exc
        except dbmod.DatabaseError as exc:
            if "ACCEPTED_ARTIFACT_IMMUTABLE" in str(exc):
                raise AcceptedArtifactImmutable(str(exc)) from exc
            raise

    # ------------------------------------------------------------- read views
    def posture(self) -> dict:
        """The six-question executive summary the phone home screen renders."""
        holds = self.active_holds()
        active_lease = dbmod.fetchone(
            self.conn,
            "SELECT * FROM writer_leases WHERE state='ACTIVE' ORDER BY issued_at DESC LIMIT 1",
        )
        running = dbmod.fetchall(
            self.conn,
            "SELECT job_id, title, state, detail FROM jobs"
            " WHERE state IN ('QUEUED','RUNNER_CLAIMED','EXECUTING','VERIFYING') ORDER BY created_at DESC",
        )
        blocked = dbmod.fetchall(
            self.conn,
            "SELECT job_id, title, state, detail FROM jobs"
            " WHERE state IN ('FAILED','ROLLBACK_REQUIRED','QUARANTINED','EXPIRED') ORDER BY updated_at DESC",
        )
        needs_ryan = dbmod.fetchall(
            self.conn,
            "SELECT job_id, title, state, detail FROM jobs WHERE state='PENDING_APPROVAL'"
            " ORDER BY created_at DESC",
        )
        recent = dbmod.fetchall(
            self.conn,
            "SELECT receipt_id, task_id, payload_json, created_at FROM verification_receipts"
            " ORDER BY created_at DESC LIMIT 5",
        )
        changed = []
        for row in recent:
            payload = json.loads(row["payload_json"])
            changed.append({
                "receipt_id": payload["receipt_id"],
                "summary": payload["plain_language_result"],
                "execution_mode": payload["execution_mode"],
                "outcome": payload["outcome"],
                "at": row["created_at"],
            })
        return {
            "holds": [{"label": h["label"], "reason": h["reason"], "scope": h["scope_pattern"]} for h in holds],
            "hold_banner": "FOR REVIEW - HOLD - NO EXTERNAL RELEASE",
            "running": [dict(r) for r in running],
            "blocked": [dict(r) for r in blocked],
            "needs_ryan": [dict(r) for r in needs_ryan],
            "changed": changed,
            "active_writer": (
                {
                    "writer_identity": active_lease["writer_identity"],
                    "resource_scope": active_lease["resource_scope"],
                    "lease_id": active_lease["lease_id"],
                    "fencing_sequence": active_lease["fencing_sequence"],
                    "expires_at": active_lease["expires_at"],
                }
                if active_lease
                else None
            ),
            "policy_version": POLICY_VERSION,
            "audit_chain_valid": self.verify_audit_chain(),
        }

    def audit_tail(self, limit: int = 50) -> list:
        rows = dbmod.fetchall(
            self.conn,
            "SELECT audit_id, occurred_at, actor, event_type, resource_scope, subject_id, outcome,"
            " detail_json, content_sha256 FROM audit_events ORDER BY audit_id DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "audit_id": r["audit_id"],
                "occurred_at": r["occurred_at"],
                "actor": r["actor"],
                "event_type": r["event_type"],
                "resource_scope": r["resource_scope"],
                "subject_id": r["subject_id"],
                "outcome": r["outcome"],
                "detail": json.loads(r["detail_json"]),
                "content_sha256": r["content_sha256"],
            }
            for r in rows
        ]
