"""Typed failures for the Command Brain.

Every refusal in the Command Brain raises one of these. Nothing fails open:
a code path that cannot prove authority must raise, never return a permissive
default.
"""

from __future__ import annotations


class CommandBrainError(Exception):
    """Base class for every Command Brain refusal."""

    code = "COMMAND_BRAIN_ERROR"

    def __init__(self, message: str, *, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = dict(detail or {})

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "detail": self.detail}


class SchemaViolation(CommandBrainError):
    """A structured payload failed validation against its declared schema."""

    code = "SCHEMA_VIOLATION"


class PolicyViolation(CommandBrainError):
    """The policy engine refused the requested action."""

    code = "POLICY_VIOLATION"


class AutonomyViolation(PolicyViolation):
    """The action requires a higher autonomy level than is currently permitted."""

    code = "AUTONOMY_VIOLATION"


class HoldActive(PolicyViolation):
    """A release/global hold blocks the requested action."""

    code = "HOLD_ACTIVE"


class ToolNotRegistered(CommandBrainError):
    """A tool ID was requested that is not in the allowlist."""

    code = "TOOL_NOT_REGISTERED"


class ToolInputRejected(CommandBrainError):
    """Tool input contained a shell command, path, credential, or unbound value."""

    code = "TOOL_INPUT_REJECTED"


class RegistryFrozen(CommandBrainError):
    """An attempt was made to widen a frozen registry at runtime."""

    code = "REGISTRY_FROZEN"


class AuthorityError(CommandBrainError):
    """Required writer authority (envelope, approval, lease, token) is missing."""

    code = "AUTHORITY_ERROR"


class ApprovalError(AuthorityError):
    """Approval missing, expired, or bound to a different scope."""

    code = "APPROVAL_ERROR"


class LeaseError(AuthorityError):
    """Lease missing, expired, or held by another worker."""

    code = "LEASE_ERROR"


class FencingTokenError(AuthorityError):
    """A stale fencing token was presented for a write lane."""

    code = "FENCING_TOKEN_ERROR"


class WriterCollision(AuthorityError):
    """Two writers attempted the same worktree or artifact lane."""

    code = "WRITER_COLLISION"


class AgentNotRegistered(CommandBrainError):
    """An unregistered agent role or adapter was requested."""

    code = "AGENT_NOT_REGISTERED"


class ModelUnavailable(CommandBrainError):
    """A model endpoint is not verified, offline, or quarantined."""

    code = "MODEL_UNAVAILABLE"


class EgressDenied(PolicyViolation):
    """Local-only mode blocked a remote model or network call."""

    code = "EGRESS_DENIED"


class BudgetExceeded(CommandBrainError):
    """A cost, token, iteration, or timeout budget was exhausted."""

    code = "BUDGET_EXCEEDED"


class ClarificationRequired(CommandBrainError):
    """A consequential request was ambiguous and needs operator clarification."""

    code = "CLARIFICATION_REQUIRED"


class QuarantineError(CommandBrainError):
    """An operation was attempted against a quarantined artifact or candidate."""

    code = "QUARANTINE_ERROR"


class MemoryRejected(CommandBrainError):
    """A memory write was refused (unsourced, or private chain-of-thought)."""

    code = "MEMORY_REJECTED"
