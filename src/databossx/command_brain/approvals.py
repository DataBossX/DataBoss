"""Approval ledger.

An approval is bound to an exact envelope hash, is single-use, and expires.
Three separate failures are therefore possible and each is distinct: *no
approval*, *expired approval*, and *approval for a different scope* (someone
edited the envelope after it was approved).

The ``method`` field records how the operator authenticated. A transcript is
never a method — :class:`ApprovalService` refuses to mint an approval from one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .envelope import TaskEnvelope
from .errors import ApprovalError
from .policy import AuthoritySource
from .util import Clock, is_expired

#: Ways the operator can actually authorize something. Speech and chat are not
#: on this list, and cannot be added at runtime.
AUTHENTICATED_METHODS = frozenset({"authenticated_ui", "authenticated_api"})


@dataclass(frozen=True)
class Approval:
    approval_id: str
    envelope_id: str
    scope_hash: str
    approver_id: str
    method: str
    granted_at: str
    expires_at: str | None

    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id,
            "envelope_id": self.envelope_id,
            "scope_hash": self.scope_hash,
            "approver_id": self.approver_id,
            "method": self.method,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
        }


class ApprovalService:
    def __init__(self, store, clock: Clock | None = None):
        self.store = store
        self.clock = clock or store.clock

    def approve(
        self,
        envelope: TaskEnvelope,
        approver_id: str,
        *,
        method: str = "authenticated_ui",
        ttl_seconds: int = 900,
        authority_source: AuthoritySource = AuthoritySource.AUTHENTICATED_APPROVAL,
    ) -> Approval:
        if method not in AUTHENTICATED_METHODS:
            raise ApprovalError(
                f"{method!r} is not an authenticated approval method. "
                "Voice and chat can request an approval; they cannot be one.",
                detail={"method": method, "accepted": sorted(AUTHENTICATED_METHODS)},
            )
        if authority_source is not AuthoritySource.AUTHENTICATED_APPROVAL:
            raise ApprovalError(
                f"Approval cannot originate from {authority_source.value}.",
                detail={"authority_source": authority_source.value},
            )
        approval_id = self.store.new_id("apr")
        granted_at = self.clock.now_iso()
        expires_at = self.clock.plus_iso(ttl_seconds)
        self.store.execute(
            """
            INSERT INTO cb_approvals (
                approval_id, envelope_id, scope_hash, approver_id, method, granted_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval_id,
                envelope.task_id,
                envelope.envelope_hash,
                approver_id,
                method,
                granted_at,
                expires_at,
            ),
        )
        self.store.execute(
            "UPDATE cb_task_envelopes SET state = 'APPROVED' WHERE envelope_id = ?",
            (envelope.task_id,),
        )
        approval = Approval(
            approval_id,
            envelope.task_id,
            envelope.envelope_hash,
            approver_id,
            method,
            granted_at,
            expires_at,
        )
        self.store.audit(
            "approval.granted",
            "task_envelope",
            envelope.task_id,
            approval.to_dict(),
            project_id=envelope.project_id,
            actor_type="operator",
            actor_id=approver_id,
        )
        return approval

    def _row(self, approval_id: str):
        return self.store.fetchone(
            "SELECT * FROM cb_approvals WHERE approval_id = ?", (approval_id,)
        )

    def verify(self, approval_id: str, envelope: TaskEnvelope) -> Approval:
        """Verify an approval covers this exact envelope, right now, unused."""
        row = self._row(approval_id)
        if row is None:
            raise ApprovalError(
                f"Approval {approval_id!r} does not exist.", detail={"approval_id": approval_id}
            )
        if row["revoked"]:
            raise ApprovalError(
                f"Approval {approval_id!r} was revoked.", detail={"approval_id": approval_id}
            )
        if row["consumed_at"] is not None:
            raise ApprovalError(
                f"Approval {approval_id!r} was already used at {row['consumed_at']}. "
                "Approval scope cannot be reused.",
                detail={"approval_id": approval_id, "consumed_at": row["consumed_at"]},
            )
        if is_expired(row["expires_at"], self.clock):
            raise ApprovalError(
                f"Approval {approval_id!r} expired at {row['expires_at']}.",
                detail={"approval_id": approval_id, "expires_at": row["expires_at"]},
            )
        if row["scope_hash"] != envelope.envelope_hash:
            raise ApprovalError(
                "Approval is bound to a different envelope scope. The task changed after approval.",
                detail={
                    "approval_id": approval_id,
                    "approved_scope": row["scope_hash"],
                    "presented_scope": envelope.envelope_hash,
                },
            )
        return Approval(
            row["approval_id"],
            row["envelope_id"],
            row["scope_hash"],
            row["approver_id"],
            row["method"],
            row["granted_at"],
            row["expires_at"],
        )

    def consume(self, approval_id: str, envelope: TaskEnvelope) -> Approval:
        approval = self.verify(approval_id, envelope)
        self.store.execute(
            "UPDATE cb_approvals SET consumed_at = ? WHERE approval_id = ?",
            (self.clock.now_iso(), approval_id),
        )
        self.store.audit(
            "approval.consumed",
            "task_envelope",
            envelope.task_id,
            {"approval_id": approval_id, "scope_hash": approval.scope_hash},
            project_id=envelope.project_id,
        )
        return approval

    def revoke(self, approval_id: str, reason: str) -> None:
        self.store.execute(
            "UPDATE cb_approvals SET revoked = 1 WHERE approval_id = ?", (approval_id,)
        )
        self.store.audit("approval.revoked", "approval", approval_id, {"reason": reason})

    def pending(self) -> list[dict]:
        rows = self.store.fetchall(
            """
            SELECT e.envelope_id, e.project_id, e.envelope_hash, e.autonomy_level,
                   e.created_at, e.expires_at
              FROM cb_task_envelopes e
             WHERE e.state = 'DRAFT'
             ORDER BY e.created_at
            """
        )
        return [dict(row) for row in rows]
