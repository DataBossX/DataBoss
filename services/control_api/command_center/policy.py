"""Deterministic policy engine.

This module owns eligibility and vetoes. A model may *propose* candidates and
write explanations, but nothing here consults a model, and no model score can
reach these decisions. Everything is pure functions over declared tables so the
same input always classifies the same way and the result is auditable.

Order of evaluation is significant: prohibitions are checked before anything
else, so a prohibited request can never be talked into a lower risk class.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from . import POLICY_VERSION
from .errors import (
    AdapterNotAllowed,
    HoldRemovalForbidden,
    PathNotAllowed,
    ProhibitedOperation,
)

RISK_READ_ONLY = "READ_ONLY"
RISK_SIMULATION = "SIMULATION"
RISK_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
RISK_PROHIBITED = "PROHIBITED"

ROLE_RANK = {"VIEWER": 0, "RUNNER": 1, "REVIEWER": 2, "OPERATOR": 3, "OWNER": 4}


@dataclass(frozen=True)
class AdapterSpec:
    """An allowlisted unit of work. Anything not listed cannot be executed."""

    name: str
    description: str
    risk_class: str
    modes: frozenset  # subset of READ_ONLY / SIMULATED / REAL
    required_role: str
    step_up_required: bool
    reversible: bool
    required_parameters: frozenset = frozenset()


#: The complete adapter allowlist. There is no generic "run shell" or "run SQL"
#: adapter, so arbitrary command execution is not representable in a
#: TaskEnvelope, not merely blocked at the edge.
ADAPTER_ALLOWLIST: Mapping[str, AdapterSpec] = {
    spec.name: spec
    for spec in (
        AdapterSpec(
            name="status.read_posture",
            description="Read current system posture, holds, and lease state.",
            risk_class=RISK_READ_ONLY,
            modes=frozenset({"READ_ONLY"}),
            required_role="VIEWER",
            step_up_required=False,
            reversible=True,
        ),
        AdapterSpec(
            name="project.read_summary",
            description="Read a synthetic project summary and its open decisions.",
            risk_class=RISK_READ_ONLY,
            modes=frozenset({"READ_ONLY"}),
            required_role="VIEWER",
            step_up_required=False,
            reversible=True,
            required_parameters=frozenset({"project_id"}),
        ),
        AdapterSpec(
            name="artifact.verify_hashes",
            description="Recompute and compare hashes for registered synthetic artifacts.",
            risk_class=RISK_READ_ONLY,
            modes=frozenset({"READ_ONLY"}),
            required_role="REVIEWER",
            step_up_required=False,
            reversible=True,
        ),
        AdapterSpec(
            name="title.simulate_interest_rollup",
            description="Simulate an exact-fraction interest roll-up over synthetic tracts.",
            risk_class=RISK_SIMULATION,
            modes=frozenset({"SIMULATED"}),
            required_role="OPERATOR",
            step_up_required=False,
            reversible=True,
            required_parameters=frozenset({"project_id"}),
        ),
        AdapterSpec(
            name="report.simulate_draft_build",
            description="Build a SIMULATED draft report artifact from synthetic inputs.",
            risk_class=RISK_SIMULATION,
            modes=frozenset({"SIMULATED"}),
            required_role="OPERATOR",
            step_up_required=False,
            reversible=True,
            required_parameters=frozenset({"project_id"}),
        ),
        AdapterSpec(
            name="drive.publish_receipt",
            description="Stage, hash, upload, and read back a receipt in the control room.",
            risk_class=RISK_APPROVAL_REQUIRED,
            modes=frozenset({"SIMULATED", "REAL"}),
            required_role="OWNER",
            step_up_required=True,
            reversible=False,
            required_parameters=frozenset({"receipt_id"}),
        ),
        AdapterSpec(
            name="artifact.promote_candidate",
            description="Promote a reviewed synthetic artifact version to CANDIDATE.",
            risk_class=RISK_APPROVAL_REQUIRED,
            modes=frozenset({"SIMULATED", "REAL"}),
            required_role="OWNER",
            step_up_required=True,
            reversible=False,
            required_parameters=frozenset({"artifact_id"}),
        ),
    )
}

#: Operations that are refused unconditionally. No role, approval, lease, or
#: model score can raise any of these into an executable class.
PROHIBITED_OPERATIONS: Mapping[str, str] = {
    "hold.remove": "Holds may not be removed by UI, model, watcher, or writer.",
    "hold.weaken": "Weakening FOR REVIEW / HOLD / NO EXTERNAL RELEASE is prohibited.",
    "release.publish_external": "No external release is authorized.",
    "client.mutate_evidence": "Client evidence is never mutated in this lane.",
    "artifact.overwrite_accepted": "Accepted artifacts are never overwritten in place.",
    "repo.push_other_branch": "Another agent's branch may not be written.",
    "shell.execute": "Arbitrary shell execution is not an available capability.",
    "sql.execute": "Arbitrary SQL execution is not an available capability.",
    "runner.open_inbound_port": "The local runner is outbound-only.",
    "secrets.read": "Secret material is never returned to a client.",
    "secrets.probe_status": "Secret-existence probing is refused.",
}

#: Resource scopes under permanent hold in this lane.
HELD_SCOPES: Sequence[str] = (
    "client.horizon.section32",
    "client.penterra.section20",
    "client.penterra.section17",
)

_SCOPE_RE = re.compile(r"^[a-z0-9]+(?:\.[a-z0-9_-]+)*$")

#: Windows drive letters, UNC paths, POSIX absolutes, and traversal segments.
_ABSOLUTE_PATH_RE = re.compile(r"^(?:[a-zA-Z]:[\\/]|\\\\|/)")


@dataclass
class Decision:
    """Result of classification. ``allowed`` is the only executable signal."""

    risk_class: str
    allowed: bool
    reasons: list = field(default_factory=list)
    requires_approval: bool = False
    requires_step_up: bool = False
    execution_mode: str = "READ_ONLY"
    policy_version: str = POLICY_VERSION


def validate_scope(scope: str) -> str:
    """Reject anything that is not a dotted logical scope."""
    if not isinstance(scope, str) or not scope:
        raise PathNotAllowed("resource scope is required")
    if _ABSOLUTE_PATH_RE.match(scope):
        raise PathNotAllowed("absolute filesystem paths are not valid resource scopes")
    if ".." in scope.split("/") or ".." in scope.split("\\"):
        raise PathNotAllowed("path traversal is rejected")
    if "\x00" in scope:
        raise PathNotAllowed("null byte in resource scope")
    if not _SCOPE_RE.match(scope):
        raise PathNotAllowed(f"resource scope {scope!r} is not a valid dotted logical scope")
    return scope


def resolve_relative_path(root: str, candidate: str) -> str:
    """Map a runner-relative path safely inside ``root``.

    Traversal, absolutes, and symlink-style escapes all resolve outside the
    root and are refused. The runner never accepts a caller-supplied absolute
    path; it only ever joins server-mapped relatives onto its own working root.
    """
    if not isinstance(candidate, str) or not candidate:
        raise PathNotAllowed("empty path")
    if _ABSOLUTE_PATH_RE.match(candidate):
        raise PathNotAllowed("absolute paths are rejected")
    if "\x00" in candidate:
        raise PathNotAllowed("null byte in path")
    normalized_root = posixpath.normpath(root)
    joined = posixpath.normpath(posixpath.join(normalized_root, candidate.replace("\\", "/")))
    if joined != normalized_root and not joined.startswith(normalized_root + "/"):
        raise PathNotAllowed("path escapes the permitted working root")
    return joined


def scope_is_held(scope: str, extra_holds: Sequence[str] = ()) -> bool:
    patterns = list(HELD_SCOPES) + list(extra_holds)
    for pattern in patterns:
        if scope == pattern or scope.startswith(pattern + "."):
            return True
    return False


def role_permits(role: str, required: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK.get(required, 99)


def get_adapter(name: str) -> AdapterSpec:
    try:
        return ADAPTER_ALLOWLIST[name]
    except KeyError as exc:
        raise AdapterNotAllowed(f"adapter {name!r} is not in the allowlist") from exc


def classify(
    *,
    operation: str,
    resource_scope: str,
    role: str,
    parameters: Mapping | None = None,
    unresolved: Sequence[str] = (),
    requested_mode: str | None = None,
    extra_holds: Sequence[str] = (),
) -> Decision:
    """Classify a request into exactly one risk class.

    Prohibitions win, then holds, then unresolved ambiguity, then the adapter
    allowlist, then role. Nothing later in the chain can undo an earlier veto.
    """
    reasons: list = []

    # 1. Unconditional prohibitions.
    if operation in PROHIBITED_OPERATIONS:
        return Decision(
            risk_class=RISK_PROHIBITED,
            allowed=False,
            reasons=[PROHIBITED_OPERATIONS[operation]],
        )

    # 2. Scope shape. An invalid scope is never coerced into a valid one.
    try:
        validate_scope(resource_scope)
    except PathNotAllowed as exc:
        return Decision(risk_class=RISK_PROHIBITED, allowed=False, reasons=[str(exc)])

    # 3. Holds. A held scope is readable but never writable.
    held = scope_is_held(resource_scope, extra_holds)
    if held:
        reasons.append(f"Scope {resource_scope} is under an active release hold.")

    # 4. Adapter allowlist.
    try:
        adapter = get_adapter(operation)
    except AdapterNotAllowed as exc:
        return Decision(risk_class=RISK_PROHIBITED, allowed=False, reasons=[str(exc)])

    # 5. Required parameters are never inferred.
    params = dict(parameters or {})
    missing = sorted(adapter.required_parameters - set(params))
    if missing:
        return Decision(
            risk_class=RISK_PROHIBITED,
            allowed=False,
            reasons=[f"Missing required parameters, which are never inferred: {', '.join(missing)}"],
        )

    # 6. Unresolved ambiguity blocks dispatch rather than guessing.
    if unresolved:
        return Decision(
            risk_class=RISK_PROHIBITED,
            allowed=False,
            reasons=[f"Unresolved fields must be answered by a human: {', '.join(unresolved)}"],
        )

    # 7. A held scope may only be read.
    if held and adapter.risk_class != RISK_READ_ONLY:
        return Decision(
            risk_class=RISK_PROHIBITED,
            allowed=False,
            reasons=reasons + ["Only read-only operations are permitted on a held scope."],
        )

    # 8. Role floor.
    if not role_permits(role, adapter.required_role):
        return Decision(
            risk_class=RISK_PROHIBITED,
            allowed=False,
            reasons=reasons + [f"Role {role} is below the required role {adapter.required_role}."],
        )

    # 9. Execution mode must be one the adapter actually supports.
    mode = requested_mode or sorted(adapter.modes)[0]
    if mode not in adapter.modes:
        return Decision(
            risk_class=RISK_PROHIBITED,
            allowed=False,
            reasons=reasons + [f"Adapter {adapter.name} does not support mode {mode}."],
        )

    reasons.append(adapter.description)
    return Decision(
        risk_class=adapter.risk_class,
        allowed=True,
        reasons=reasons,
        requires_approval=adapter.risk_class == RISK_APPROVAL_REQUIRED,
        requires_step_up=adapter.step_up_required,
        execution_mode=mode,
    )


def assert_hold_not_targeted(operation: str) -> None:
    """Guard used at the API edge so hold removal fails loudly and audibly."""
    if operation in ("hold.remove", "hold.weaken"):
        raise HoldRemovalForbidden(PROHIBITED_OPERATIONS[operation])


def assert_operation_permitted(operation: str) -> None:
    if operation in PROHIBITED_OPERATIONS:
        raise ProhibitedOperation(PROHIBITED_OPERATIONS[operation])
