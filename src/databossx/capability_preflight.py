"""Stateless task-capability preflight helper.

Pure, dependency-free classification functions used to answer questions
like "does this claim actually describe what happened" before any receipt,
report, or status is written. This module holds no state, makes no network
or filesystem calls, and does not talk to any controller, dispatcher,
queue, or database — it only classifies evidence that the caller already
observed and passes in.

It exists to make five distinctions mechanical instead of a matter of
prose, each with its own classifier below:

  1. cloud repository access            vs. verified access to a designated PC
  2. unreadable input                   vs. empty input
  3. readable attachments               vs. unavailable Drive links
  4. independent direct-session tests   vs. managed dispatcher jobs
  5. unverified/stale observations      vs. current capability evidence

A sixth helper, `sanitize_for_public_output`, strips locators that should
never land in a public repository (private document IDs, session URLs,
loopback ports, local Windows paths) out of text before it is published.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# 1. Cloud repository access vs. verified access to a designated PC
# ---------------------------------------------------------------------------


class AccessLevel(str, Enum):
    CLOUD_CHECKOUT = "cloud_checkout"
    VERIFIED_LOCAL_PC = "verified_local_pc"


@dataclass(frozen=True)
class AccessEvidence:
    """Facts actually observed about the execution host.

    `designated_pc_marker_found` must come from something the caller
    verified directly (e.g. a signed marker file read from a specific
    authorized path, or a local service that answered a challenge) — never
    from a hostname, app name, OS name, or repository name, none of which
    prove PC identity.
    """

    designated_pc_marker_found: bool
    designated_pc_marker_source: str | None = None


def classify_access(evidence: AccessEvidence) -> AccessLevel:
    if evidence.designated_pc_marker_found:
        return AccessLevel.VERIFIED_LOCAL_PC
    return AccessLevel.CLOUD_CHECKOUT


def satisfies_local_pc_requirement(level: AccessLevel) -> bool:
    """A cloud clone can never satisfy a requirement that needs the PC."""
    return level == AccessLevel.VERIFIED_LOCAL_PC


# ---------------------------------------------------------------------------
# 2. Unreadable input vs. empty input
# ---------------------------------------------------------------------------


class InputState(str, Enum):
    UNREADABLE = "unreadable"
    EMPTY = "empty"
    READABLE = "readable"


@dataclass(frozen=True)
class FetchAttempt:
    """Outcome of trying to read some input (a URL, a file, a document)."""

    error: str | None
    content: bytes | None


def classify_input(attempt: FetchAttempt) -> InputState:
    if attempt.error is not None:
        return InputState.UNREADABLE
    if not attempt.content:
        return InputState.EMPTY
    return InputState.READABLE


# ---------------------------------------------------------------------------
# 3. Readable attachments vs. unavailable Drive links
# ---------------------------------------------------------------------------


class AttachmentState(str, Enum):
    ATTACHED_READABLE = "attached_readable"
    UNAVAILABLE_LINK = "unavailable_link"
    NONE = "none"


@dataclass(frozen=True)
class AttachmentCheck:
    local_bytes_available: bool
    remote_link_reachable: bool


def classify_attachment(check: AttachmentCheck) -> AttachmentState:
    if check.local_bytes_available:
        return AttachmentState.ATTACHED_READABLE
    if not check.remote_link_reachable:
        return AttachmentState.UNAVAILABLE_LINK
    return AttachmentState.NONE


def satisfies_input_requirement(state: AttachmentState) -> bool:
    return state == AttachmentState.ATTACHED_READABLE


# ---------------------------------------------------------------------------
# 4. Independent direct-session tests vs. managed dispatcher jobs
# ---------------------------------------------------------------------------


class TestExecutionKind(str, Enum):
    INDEPENDENT_DIRECT_SESSION = "independent_direct_session"
    MANAGED_DISPATCHER_JOB = "managed_dispatcher_job"
    NONE = "none"


@dataclass(frozen=True)
class TestExecutionEvidence:
    dispatcher_job_id: str | None
    ran_directly_in_session: bool


def classify_test_execution(evidence: TestExecutionEvidence) -> TestExecutionKind:
    if evidence.dispatcher_job_id:
        return TestExecutionKind.MANAGED_DISPATCHER_JOB
    if evidence.ran_directly_in_session:
        return TestExecutionKind.INDEPENDENT_DIRECT_SESSION
    return TestExecutionKind.NONE


@dataclass(frozen=True)
class RunningClaimEvidence:
    worker_ack_id: str | None
    heartbeat_seen: bool
    dispatcher_job_id: str | None


def can_claim_managed_running(evidence: RunningClaimEvidence) -> bool:
    """A managed 'RUNNING' status requires a real job ID, worker ACK, and
    heartbeat together. Missing any one of them means no such claim."""
    return bool(evidence.worker_ack_id) and bool(evidence.dispatcher_job_id) and evidence.heartbeat_seen


# ---------------------------------------------------------------------------
# 5. Unverified/stale observations vs. current capability evidence
# ---------------------------------------------------------------------------


class EvidenceFreshness(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class ObservedCapability:
    observed_at_epoch: float
    verified: bool
    max_age_seconds: float


def classify_freshness(capability: ObservedCapability, now_epoch: float) -> EvidenceFreshness:
    if not capability.verified:
        return EvidenceFreshness.UNVERIFIED
    age = now_epoch - capability.observed_at_epoch
    if age > capability.max_age_seconds:
        return EvidenceFreshness.STALE
    return EvidenceFreshness.CURRENT


# ---------------------------------------------------------------------------
# 6. Public-safe output
# ---------------------------------------------------------------------------

_DEFAULT_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"https?://drive\.google\.com/\S+"),
    re.compile(r"https?://claude\.ai/code/session_[A-Za-z0-9]+"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b"),  # loopback/host:port
    re.compile(r"[A-Za-z]:\\\\?[^\s]+|[A-Za-z]:\\[^\s]+"),  # Windows paths
)


def sanitize_for_public_output(text: str, extra_patterns: list[str] | None = None) -> str:
    """Redact locators that should never reach a public repository: private
    document links, session/telemetry identifiers, loopback service
    addresses, and local machine paths. Ordinary text passes through
    unchanged."""
    result = text
    patterns: list[re.Pattern[str]] = list(_DEFAULT_SENSITIVE_PATTERNS)
    if extra_patterns:
        patterns.extend(re.compile(pattern) for pattern in extra_patterns)
    for pattern in patterns:
        result = pattern.sub("[REDACTED]", result)
    return result
