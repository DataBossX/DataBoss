"""Fail-closed policy engine for the DataBossX trusted kernel.

Hard filters run before any connector, worker, or external write. Unknown
permissions are denials. External mutation is off by default and requires an
exact, expiring human approval bound to a payload hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


POLICY_VERSION = "1.0.0"

EXTERNAL_WRITE_CAPABILITIES = frozenset(
    {
        "drive.write",
        "drive.delete",
        "drive.share",
        "dropbox.write",
        "github.write",
        "original.mutate",
        "report.release",
    }
)

LOCAL_ONLY_CAPABILITIES = frozenset(
    {
        "inventory.hash",
        "vault.copy",
        "title.math",
        "workbook.compare",
        "task.orchestrate",
    }
)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    policy_version: str = POLICY_VERSION
    considered: tuple[str, ...] = ()
    rejected: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    artifact_hash: str
    destination: str
    expires_at: str
    approver_id: str
    payload_json: str = "{}"


@dataclass
class PolicyEngine:
    """Deterministic policy checks. No network. No model routing."""

    profile: str = "default"
    allow_remote_processing: bool = False
    allowed_connector_types: tuple[str, ...] = ("local_disk", "google_drive", "github")
    allowed_egress: tuple[str, ...] = ()

    def decide(self, capability: str, *, write: bool = False, connector_type: str | None = None) -> PolicyDecision:
        considered = (capability, f"write={write}", f"connector={connector_type or '-'}")
        rejected: list[str] = []

        if capability in EXTERNAL_WRITE_CAPABILITIES or write:
            rejected.append("external_writes_disabled_by_default")
            return PolicyDecision(
                allowed=False,
                reason="external writes require an exact, expiring human approval",
                considered=considered,
                rejected=tuple(rejected),
            )

        if connector_type and connector_type not in self.allowed_connector_types:
            rejected.append("connector_type_not_allowed")
            return PolicyDecision(
                allowed=False,
                reason=f"connector type {connector_type!r} is not in the allowlist",
                considered=considered,
                rejected=tuple(rejected),
            )

        if capability.startswith("model.") and not self.allow_remote_processing:
            rejected.append("remote_processing_disabled")
            return PolicyDecision(
                allowed=False,
                reason="local-only policy blocks remote model routing",
                considered=considered,
                rejected=tuple(rejected),
            )

        if capability.startswith("egress.") and capability.removeprefix("egress.") not in self.allowed_egress:
            rejected.append("egress_not_allowlisted")
            return PolicyDecision(
                allowed=False,
                reason="egress destination is not allowlisted",
                considered=considered,
                rejected=tuple(rejected),
            )

        return PolicyDecision(allowed=True, reason="policy allow", considered=considered)

    def allow_connector_scan(self, connector_type: str, access_mode: str) -> PolicyDecision:
        if access_mode != "read_only":
            return PolicyDecision(
                allowed=False,
                reason="connector scans must be read_only unless a write approval exists",
                rejected=("access_mode_not_read_only",),
            )
        return self.decide("connector.scan", connector_type=connector_type)

    def allow_vault_ingest(self) -> PolicyDecision:
        return PolicyDecision(
            allowed=True,
            reason="copy into the append-only vault is an internal derivation",
            considered=("vault.copy",),
        )

    def allow_external_write(self, approval: ApprovalRecord | None, payload_hash: str, destination: str) -> PolicyDecision:
        if approval is None:
            return PolicyDecision(
                allowed=False,
                reason="no approval presented for external write",
                rejected=("missing_approval",),
            )
        if approval.artifact_hash != payload_hash:
            return PolicyDecision(
                allowed=False,
                reason="approval hash does not bind the current payload",
                rejected=("approval_hash_mismatch",),
            )
        if approval.destination != destination:
            return PolicyDecision(
                allowed=False,
                reason="approval destination does not match the requested write",
                rejected=("approval_destination_mismatch",),
            )
        if _expired(approval.expires_at):
            return PolicyDecision(
                allowed=False,
                reason="approval has expired",
                rejected=("stale_approval",),
            )
        return PolicyDecision(
            allowed=True,
            reason="exact expiring approval binds destination and payload hash",
            considered=("approval", approval.approval_id),
        )

    def require_human_for_conflicts(self, material_conflict_ids: Iterable[str]) -> PolicyDecision:
        ids = tuple(material_conflict_ids)
        if ids:
            return PolicyDecision(
                allowed=False,
                reason="material conflicts require qualified human resolution",
                considered=ids,
                rejected=("material_conflict_open",),
            )
        return PolicyDecision(allowed=True, reason="no open material conflicts")


def _expired(expires_at: str) -> bool:
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    now = datetime.now(timezone.utc)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return now >= expiry
