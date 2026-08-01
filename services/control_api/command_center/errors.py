"""Control-kernel failure taxonomy.

Every error here is a *fail-closed* outcome. Silent partial success is treated
as a defect, so each condition that stops an operation raises rather than
degrading into a warning.
"""

from __future__ import annotations


class ControlKernelError(Exception):
    """Base class for all control-kernel refusals."""

    code = "CONTROL_KERNEL_ERROR"


class AuthorityError(ControlKernelError):
    code = "AUTHORITY_ERROR"


class NotAuthenticated(AuthorityError):
    code = "NOT_AUTHENTICATED"


class NotAuthorized(AuthorityError):
    code = "NOT_AUTHORIZED"


class StepUpRequired(AuthorityError):
    code = "STEP_UP_REQUIRED"


class LeaseError(ControlKernelError):
    code = "LEASE_ERROR"


class LeaseHeld(LeaseError):
    """Another writer already holds an ACTIVE lease on this resource scope."""

    code = "LEASE_HELD"


class LeaseNotHeld(LeaseError):
    code = "LEASE_NOT_HELD"


class LeaseExpired(LeaseError):
    code = "LEASE_EXPIRED"


class StaleFencingToken(LeaseError):
    """A write arrived carrying a fencing sequence older than the current one."""

    code = "STALE_FENCING_TOKEN"


class ApprovalError(ControlKernelError):
    code = "APPROVAL_ERROR"


class ApprovalRequired(ApprovalError):
    code = "APPROVAL_REQUIRED"


class ApprovalExpired(ApprovalError):
    code = "APPROVAL_EXPIRED"


class ApprovalAlreadyConsumed(ApprovalError):
    """Replay attempt: this single-use approval was already spent."""

    code = "APPROVAL_ALREADY_CONSUMED"


class ApprovalScopeMismatch(ApprovalError):
    """The approval was issued for a different operation, scope, or parameters."""

    code = "APPROVAL_SCOPE_MISMATCH"


class PolicyViolation(ControlKernelError):
    code = "POLICY_VIOLATION"


class ProhibitedOperation(PolicyViolation):
    code = "PROHIBITED_OPERATION"


class HoldRemovalForbidden(PolicyViolation):
    """A hold may not be removed by UI, model, watcher, or writer."""

    code = "HOLD_REMOVAL_FORBIDDEN"


class HoldInEffect(PolicyViolation):
    code = "HOLD_IN_EFFECT"


class AdapterNotAllowed(PolicyViolation):
    code = "ADAPTER_NOT_ALLOWED"


class PathNotAllowed(PolicyViolation):
    """Absolute paths, traversal, and unmapped logical resources are rejected."""

    code = "PATH_NOT_ALLOWED"


class IntegrityError(ControlKernelError):
    code = "INTEGRITY_ERROR"


class HashMismatch(IntegrityError):
    code = "HASH_MISMATCH"


class ArtifactChanged(IntegrityError):
    """Input artifact changed between approval and execution."""

    code = "ARTIFACT_CHANGED"


class ReadbackMismatch(IntegrityError):
    """Uploaded bytes did not match on read-back from the artifact store."""

    code = "READBACK_MISMATCH"


class AcceptedArtifactImmutable(IntegrityError):
    code = "ACCEPTED_ARTIFACT_IMMUTABLE"


class InvalidStateTransition(ControlKernelError):
    code = "INVALID_STATE_TRANSITION"


class WatcherPermissionDenied(ControlKernelError):
    """Watchers observe. They never write, lease, approve, or clear holds."""

    code = "WATCHER_PERMISSION_DENIED"


class NonceReplay(ControlKernelError):
    code = "NONCE_REPLAY"


class SchemaValidationError(ControlKernelError):
    code = "SCHEMA_VALIDATION_ERROR"
