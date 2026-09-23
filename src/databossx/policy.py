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


def _allow(reason: str, *considered: str) -> PolicyDecision:
    return PolicyDecision(allowed=True, reason=reason, considered=considered)


def _deny(reason: str, *rejected: str, considered: tuple[str, ...] = ()) -> PolicyDecision:
    return PolicyDecision(
        allowed=False,
        reason=reason,
        considered=considered,
        rejected=rejected,
    )


@dataclass
class PolicyEngine:
    """Deterministic policy checks. No network. No model routing."""

    profile: str = "default"
    allow_remote_processing: bool = False
    allowed_connector_types: tuple[str, ...] = ("local_disk", "google_drive", "github")
    allowed_egress: tuple[str, ...] = ()

    def decide(self, capability: str, *, write: bool = False, connector_type: str | None = None) -> PolicyDecision:
        considered = (capability, f"write={write}", f"connector={connector_type or '-'}")

        if capability in EXTERNAL_WRITE_CAPABILITIES or write:
            return _deny(
                "external writes require an exact, expiring human approval",
                "external_writes_disabled_by_default",
                considered=considered,
            )

        if connector_type and connector_type not in self.allowed_connector_types:
            return _deny(
                f"connector type {connector_type!r} is not in the allowlist",
                "connector_type_not_allowed",
                considered=considered,
            )

        if capability.startswith("model.") and not self.allow_remote_processing:
            return _deny(
                "local-only policy blocks remote model routing",
                "remote_processing_disabled",
                considered=considered,
            )

        if capability.startswith("egress.") and capability.removeprefix("egress.") not in self.allowed_egress:
            return _deny(
                "egress destination is not allowlisted",
                "egress_not_allowlisted",
                considered=considered,
            )

        return _allow("policy allow", *considered)

    def allow_connector_scan(self, connector_type: str, access_mode: str) -> PolicyDecision:
        if access_mode != "read_only":
            return _deny(
                "connector scans must be read_only unless a write approval exists",
                "access_mode_not_read_only",
            )
        return self.decide("connector.scan", connector_type=connector_type)

    def allow_vault_ingest(self) -> PolicyDecision:
        return _allow("copy into the append-only vault is an internal derivation", "vault.copy")

    def allow_external_write(
        self,
        approval: ApprovalRecord | None,
        payload_hash: str,
        destination: str,
    ) -> PolicyDecision:
        if approval is None:
            return _deny("no approval presented for external write", "missing_approval")
        if approval.artifact_hash != payload_hash:
            return _deny("approval hash does not bind the current payload", "approval_hash_mismatch")
        if approval.destination != destination:
            return _deny(
                "approval destination does not match the requested write",
                "approval_destination_mismatch",
            )
        if _expired(approval.expires_at):
            return _deny("approval has expired", "stale_approval")
        return _allow(
            "exact expiring approval binds destination and payload hash",
            "approval",
            approval.approval_id,
        )

    def require_human_for_conflicts(self, material_conflict_ids: Iterable[str]) -> PolicyDecision:
        ids = tuple(material_conflict_ids)
        if ids:
            return _deny(
                "material conflicts require qualified human resolution",
                "material_conflict_open",
                considered=ids,
            )
        return _allow("no open material conflicts")


def _expired(expires_at: str) -> bool:
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expiry
