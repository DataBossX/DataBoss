"""Deterministic, fail-closed release gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReleaseStatus(str, Enum):
    DRAFT = "DRAFT"
    INTERNAL_WORKING = "INTERNAL_WORKING"
    SOURCE_LIMITED = "SOURCE_LIMITED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
    READY_FOR_EXAMINER = "READY_FOR_EXAMINER"
    APPROVED_FOR_DELIVERY = "APPROVED_FOR_DELIVERY"
    DELIVERED = "DELIVERED"


@dataclass(frozen=True)
class ReleaseContext:
    """Explicit release facts. Defaults intentionally describe no proven work."""

    inventory_complete: bool = False
    corrupt_sources: bool = False
    evidence_conflicts: bool = False
    missing_exhibits: bool = False
    missing_schedules: bool = False
    unresolved_owner: bool = False
    acreage_mismatch: bool = False
    negative_values: bool = False
    forced_balance: bool = False
    tract_overlaps: bool = False
    unsupported_lease_terms: bool = False
    unsupported_working_interest: bool = False
    unsupported_net_revenue_interest: bool = False
    workbook_defects: bool = False
    workbook_external_links: bool = False
    template_mismatch: bool = False
    critical_open_items: int = 0
    approvals_complete: bool = False
    source_scope_limited: bool = True
    internal_source_limited_approved: bool = False
    external_release_requested: bool = True
    delivered: bool = False

    def __post_init__(self) -> None:
        if (
            isinstance(self.critical_open_items, bool)
            or not isinstance(self.critical_open_items, int)
            or self.critical_open_items < 0
        ):
            raise ValueError("critical_open_items must be a non-negative integer")


@dataclass(frozen=True)
class GateResult:
    gate: str
    passed: bool
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReleaseDecision:
    status: ReleaseStatus
    gates: tuple[GateResult, ...]
    blockers: tuple[str, ...]
    external_release_allowed: bool

    @property
    def passed(self) -> bool:
        return self.status is ReleaseStatus.APPROVED_FOR_DELIVERY


def _gate(name: str, failures: tuple[str, ...]) -> GateResult:
    return GateResult(name, not failures, failures)


def _failure_reasons(*checks: tuple[bool, str]) -> tuple[str, ...]:
    return tuple(reason for failed, reason in checks if failed)


def evaluate_release(context: ReleaseContext) -> ReleaseDecision:
    """Evaluate every gate in stable order; no score can override a failure."""

    gates = (
        _gate(
            "INVENTORY",
            () if context.inventory_complete else ("inventory is incomplete",),
        ),
        _gate(
            "SOURCE_INTEGRITY",
            _failure_reasons(
                (context.corrupt_sources, "corrupt source files"),
                (context.evidence_conflicts, "unresolved evidence conflicts"),
                (context.missing_exhibits, "missing exhibits"),
                (context.missing_schedules, "missing schedules"),
            ),
        ),
        _gate(
            "OWNERSHIP",
            ("unresolved owner",) if context.unresolved_owner else (),
        ),
        _gate(
            "ACREAGE_AND_BALANCE",
            _failure_reasons(
                (context.acreage_mismatch, "acreage mismatch"),
                (context.negative_values, "negative calculated value"),
                (context.forced_balance, "forced balance present"),
                (context.tract_overlaps, "tract overlap present"),
            ),
        ),
        _gate(
            "LEASE_WI_NRI_SUPPORT",
            _failure_reasons(
                (context.unsupported_lease_terms, "unsupported lease terms"),
                (context.unsupported_working_interest, "unsupported working interest"),
                (
                    context.unsupported_net_revenue_interest,
                    "unsupported net revenue interest",
                ),
            ),
        ),
        _gate(
            "WORKBOOK",
            _failure_reasons(
                (context.workbook_defects, "workbook defects"),
                (context.workbook_external_links, "workbook external links"),
                (context.template_mismatch, "workbook template mismatch"),
            ),
        ),
        _gate(
            "OPEN_ITEMS",
            (
                (f"{context.critical_open_items} critical open item(s)",)
                if context.critical_open_items
                else ()
            ),
        ),
    )
    blockers = tuple(reason for gate in gates for reason in gate.blockers)
    if blockers:
        return ReleaseDecision(ReleaseStatus.BLOCKED, gates, blockers, False)
    if context.source_scope_limited:
        source_notice = "source scope is limited; external release prohibited"
        if (
            not context.external_release_requested
            and context.internal_source_limited_approved
        ):
            return ReleaseDecision(
                ReleaseStatus.SOURCE_LIMITED,
                gates,
                (source_notice,),
                False,
            )
        return ReleaseDecision(
            ReleaseStatus.REVIEW_REQUIRED,
            gates,
            (source_notice, "explicit internal source-limited approval is missing"),
            False,
        )
    if not context.approvals_complete:
        return ReleaseDecision(
            ReleaseStatus.READY_FOR_EXAMINER,
            gates,
            ("technical gates are clear; required examiner/delivery approvals are missing",),
            False,
        )
    if not context.external_release_requested:
        return ReleaseDecision(
            ReleaseStatus.REVIEW_REQUIRED,
            gates,
            ("external release was not requested",),
            False,
        )
    if context.delivered:
        return ReleaseDecision(ReleaseStatus.DELIVERED, gates, (), False)
    return ReleaseDecision(
        ReleaseStatus.APPROVED_FOR_DELIVERY,
        gates,
        (),
        True,
    )
