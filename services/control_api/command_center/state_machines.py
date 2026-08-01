"""Explicit, validated state machines.

Transitions are declared once here and enforced in two places: the service
layer calls :func:`assert_transition`, and the database rejects the same
impossible moves via triggers created in ``db.py``. Two layers because a bug in
one should not be able to corrupt durable state.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Mapping

from .errors import InvalidStateTransition

Transitions = Mapping[str, FrozenSet[str]]


def _t(mapping: Dict[str, set]) -> Transitions:
    return {state: frozenset(nexts) for state, nexts in mapping.items()}


#: DRAFT -> TRANSCRIBED -> INTERPRETED -> CONFIRMED -> CLASSIFIED -> DISPATCHED
COMMAND: Transitions = _t(
    {
        "DRAFT": {"TRANSCRIBED", "CANCELLED", "QUARANTINED"},
        "TRANSCRIBED": {"INTERPRETED", "CANCELLED", "REJECTED", "EXPIRED", "QUARANTINED"},
        "INTERPRETED": {"CONFIRMED", "CANCELLED", "REJECTED", "EXPIRED", "QUARANTINED"},
        "CONFIRMED": {"CLASSIFIED", "CANCELLED", "REJECTED", "EXPIRED", "QUARANTINED"},
        "CLASSIFIED": {"DISPATCHED", "REJECTED", "CANCELLED", "EXPIRED", "QUARANTINED"},
        "DISPATCHED": set(),
        "CANCELLED": set(),
        "REJECTED": set(),
        "EXPIRED": set(),
        "QUARANTINED": set(),
    }
)

JOB: Transitions = _t(
    {
        "CREATED": {"QUEUED", "CANCELLED", "REJECTED", "QUARANTINED"},
        "QUEUED": {"PENDING_APPROVAL", "APPROVED", "CANCELLED", "EXPIRED", "REJECTED", "QUARANTINED"},
        "PENDING_APPROVAL": {"APPROVED", "REJECTED", "EXPIRED", "CANCELLED", "QUARANTINED"},
        "APPROVED": {"RUNNER_CLAIMED", "EXPIRED", "CANCELLED", "QUARANTINED"},
        "RUNNER_CLAIMED": {"EXECUTING", "FAILED", "EXPIRED", "CANCELLED", "QUARANTINED"},
        "EXECUTING": {"VERIFYING", "FAILED", "ROLLBACK_REQUIRED", "QUARANTINED"},
        "VERIFYING": {"COMPLETED", "FAILED", "ROLLBACK_REQUIRED", "QUARANTINED"},
        "COMPLETED": set(),
        "REJECTED": set(),
        "EXPIRED": set(),
        "FAILED": {"ROLLBACK_REQUIRED", "QUARANTINED"},
        "QUARANTINED": set(),
        "ROLLBACK_REQUIRED": {"QUARANTINED", "COMPLETED"},
        "CANCELLED": set(),
    }
)

APPROVAL: Transitions = _t(
    {
        "NONE": {"REQUESTED"},
        "REQUESTED": {"CHALLENGE_ISSUED", "REJECTED", "TIMED_OUT", "REVOKED"},
        "CHALLENGE_ISSUED": {"SIGNED_BY_HUMAN", "REJECTED", "TIMED_OUT", "REVOKED", "EXPIRED"},
        "SIGNED_BY_HUMAN": {"VALIDATED_BY_RUNNER", "REVOKED", "EXPIRED", "TIMED_OUT"},
        "VALIDATED_BY_RUNNER": {"CONSUMED", "REVOKED", "EXPIRED"},
        "CONSUMED": set(),
        "REVOKED": set(),
        "TIMED_OUT": set(),
        "REJECTED": set(),
        "EXPIRED": set(),
    }
)

ARTIFACT: Transitions = _t(
    {
        "DISCOVERED": {"HASHED", "QUARANTINED", "REJECTED"},
        "HASHED": {"REGISTERED", "QUARANTINED", "REJECTED"},
        "REGISTERED": {"CANDIDATE", "QUARANTINED", "REJECTED", "HOLD"},
        "CANDIDATE": {"REVIEWED", "REJECTED", "QUARANTINED", "HOLD"},
        "REVIEWED": {"ACCEPTED", "REJECTED", "QUARANTINED", "HOLD"},
        # ACCEPTED is terminal apart from supersession: accepted artifacts are
        # never overwritten in place.
        "ACCEPTED": {"SUPERSEDED"},
        "REJECTED": set(),
        "SUPERSEDED": set(),
        "QUARANTINED": set(),
        "HOLD": {"CANDIDATE", "REVIEWED", "QUARANTINED", "REJECTED"},
    }
)

REVIEW: Transitions = _t(
    {
        "REQUESTED": {"CLAIMED_READ_ONLY", "REJECTED"},
        "CLAIMED_READ_ONLY": {"REVIEWED"},
        "REVIEWED": {"PASS", "REQUEST_CHANGES"},
        "PASS": set(),
        "REQUEST_CHANGES": set(),
        "REJECTED": set(),
    }
)

MACHINES: Mapping[str, Transitions] = {
    "command": COMMAND,
    "job": JOB,
    "approval": APPROVAL,
    "artifact": ARTIFACT,
    "review": REVIEW,
}

#: States from which nothing may move again. Used by the database triggers.
TERMINAL = {
    name: frozenset(state for state, nexts in machine.items() if not nexts)
    for name, machine in MACHINES.items()
}


def assert_transition(machine: str, current: str, target: str) -> None:
    """Raise :class:`InvalidStateTransition` unless the move is declared legal."""
    try:
        table = MACHINES[machine]
    except KeyError as exc:
        raise InvalidStateTransition(f"unknown state machine {machine!r}") from exc
    if current not in table:
        raise InvalidStateTransition(f"{machine}: unknown current state {current!r}")
    if target not in table:
        raise InvalidStateTransition(f"{machine}: unknown target state {target!r}")
    if target not in table[current]:
        raise InvalidStateTransition(f"{machine}: {current} -> {target} is not a permitted transition")


def is_terminal(machine: str, state: str) -> bool:
    return state in TERMINAL.get(machine, frozenset())
