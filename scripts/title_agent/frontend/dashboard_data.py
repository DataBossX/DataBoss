"""Dashboard read/resolve model — Phase 7 (testable core of the frontend).

Streamlit views should be thin. All the querying and every state-changing
action the Examiner can take lives here, in plain Python over the SQLite store,
so it can be unit-tested without a browser. ``app.py`` imports this module and
does nothing but render.

The read side derives the live scorecard from the audit trail and the open
escalation queue. The write side is exactly the three HITL resolutions from
blueprint section 6 — Gap Resolver, Factual Arbiter, Budget Override — each of
which funnels through ``EscalationStore.resolve`` and therefore always leaves
an ``EXAMINER_OVERRIDE`` in the append-only audit log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..api.okcounty import BudgetManager, BudgetStatus
from ..core.config import (
    COUNTY,
    GROSS_ACRE_TARGET,
    PROSPECT_ID,
    SECTION,
    STATE,
    TRACT_COUNT,
    WELL_NAME,
)
from ..core.memory import (
    ArtifactVersion,
    AuditLogger,
    AuditRecord,
    Escalation,
    EscalationStore,
    SQLiteManager,
    VersionController,
)
from ..core.taxonomy import FailureCategory, Gate

# Which HITL form handles which escalation category (blueprint section 6).
_GAP_RESOLVER = FailureCategory.TITLE_GAP.value
_FACTUAL_ARBITER = FailureCategory.SOURCE_UNVERIFIED.value
_BUDGET_OVERRIDE = FailureCategory.BUDGET_CAP_REACHED.value


@dataclass(frozen=True)
class GateCard:
    """One gate's tile on the scorecard."""

    gate: str
    status: str  # "PASS" or "ATTENTION"
    open_escalations: int

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass(frozen=True)
class Scorecard:
    prospect_id: str
    section: str
    county: str
    state: str
    well: str
    tract_count: int
    gross_acre_target: float
    loop_state: str
    certified: bool
    gates: tuple[GateCard, ...]
    latest_version: Optional[ArtifactVersion]
    budget: BudgetStatus
    open_escalation_count: int


@dataclass(frozen=True)
class QueueBundle:
    """Open escalations grouped by the HITL form that resolves them."""

    gap_resolver: tuple[Escalation, ...] = ()
    factual_arbiter: tuple[Escalation, ...] = ()
    budget_override: tuple[Escalation, ...] = ()
    other: tuple[Escalation, ...] = ()


class DashboardData:
    """Everything the Streamlit dashboard reads or writes."""

    def __init__(self, manager: SQLiteManager, artifact_key: str = "TitleReport") -> None:
        self._db = manager
        self._key = artifact_key
        self._audit = AuditLogger(manager)
        self._versions = VersionController(manager)
        self._escalations = EscalationStore(manager, self._audit)
        self._budget = BudgetManager(manager, self._audit)

    # ---- read side ------------------------------------------------------- #

    def scorecard(self) -> Scorecard:
        open_escs = self._escalations.list_open()
        by_gate: dict[str, int] = {}
        for e in open_escs:
            by_gate[e.gate] = by_gate.get(e.gate, 0) + 1

        gates = tuple(
            GateCard(
                gate=g.value,
                status="ATTENTION" if by_gate.get(g.value) else "PASS",
                open_escalations=by_gate.get(g.value, 0),
            )
            for g in Gate
        )
        loop_state = self._latest_loop_state()
        return Scorecard(
            prospect_id=PROSPECT_ID,
            section=SECTION,
            county=COUNTY,
            state=STATE,
            well=WELL_NAME,
            tract_count=TRACT_COUNT,
            gross_acre_target=GROSS_ACRE_TARGET,
            loop_state=loop_state,
            certified=(loop_state == "CERTIFIED" and not open_escs),
            gates=gates,
            latest_version=self._versions.get_latest_version(self._key),
            budget=self._budget.status(),
            open_escalation_count=len(open_escs),
        )

    def audit_trail(self, limit: int = 100) -> list[AuditRecord]:
        """Most-recent-first slice of the append-only audit log."""
        records = self._audit.read_all()
        return list(reversed(records))[:limit]

    def open_queue(self) -> QueueBundle:
        gap, arb, budget, other = [], [], [], []
        for e in self._escalations.list_open():
            if e.category == _GAP_RESOLVER:
                gap.append(e)
            elif e.category == _FACTUAL_ARBITER:
                arb.append(e)
            elif e.category == _BUDGET_OVERRIDE:
                budget.append(e)
            else:
                other.append(e)
        return QueueBundle(tuple(gap), tuple(arb), tuple(budget), tuple(other))

    def version_history(self) -> list[ArtifactVersion]:
        return self._versions.history(self._key)

    def _latest_loop_state(self) -> str:
        for rec in reversed(self._audit.read_all()):
            if rec.action in ("CERTIFIED", "HITL_HALT", "AUTO_REPAIR", "GATE_EVALUATION"):
                if rec.action == "CERTIFIED":
                    return "CERTIFIED"
                if rec.action == "HITL_HALT":
                    return "ESCALATED"
                return "RUNNING"
        return "NOT_STARTED"

    # ---- write side: the three HITL resolutions -------------------------- #

    def resolve_gap(
        self, escalation_id: int, examiner_id: str, *, book_page: Optional[str],
        title_defect_requirement: Optional[str],
    ) -> Escalation:
        """Gap Resolver. The Examiner either supplies the missing Book/Page or
        approves a Title Defect Requirement. Exactly one must be provided — the
        agent will not proceed on an empty resolution, and it never fabricates
        the missing conveyance itself."""
        self._require(_GAP_RESOLVER, escalation_id)
        if bool(book_page) == bool(title_defect_requirement):
            raise ValueError(
                "provide exactly one of book_page or title_defect_requirement"
            )
        resolution = (
            f"Missing conveyance supplied: {book_page}"
            if book_page
            else f"Title Defect Requirement approved: {title_defect_requirement}"
        )
        return self._escalations.resolve(escalation_id, examiner_id, resolution)

    def resolve_factual(
        self, escalation_id: int, examiner_id: str, *, ground_truth: str,
    ) -> Escalation:
        """Factual Arbiter. The Examiner selects the ground truth between the
        API value and the workbook value. The chosen value is recorded as-is."""
        self._require(_FACTUAL_ARBITER, escalation_id)
        if not ground_truth.strip():
            raise ValueError("ground_truth must be provided")
        return self._escalations.resolve(
            escalation_id, examiner_id, f"Ground truth selected: {ground_truth}"
        )

    def resolve_budget(
        self, escalation_id: int, examiner_id: str, *,
        authorize_increase_to: Optional[float] = None,
        manual_document_note: Optional[str] = None,
    ) -> Escalation:
        """Budget Override. The Examiner either authorizes a higher cap or notes
        that the required document was supplied manually. Exactly one path."""
        self._require(_BUDGET_OVERRIDE, escalation_id)
        if (authorize_increase_to is None) == (manual_document_note is None):
            raise ValueError(
                "provide exactly one of authorize_increase_to or manual_document_note"
            )
        if authorize_increase_to is not None:
            if authorize_increase_to <= self._budget.cap:
                raise ValueError("authorized cap must exceed the current cap")
            resolution = f"Budget cap increase authorized to ${authorize_increase_to:.2f}"
        else:
            resolution = f"Document supplied manually: {manual_document_note}"
        return self._escalations.resolve(escalation_id, examiner_id, resolution)

    def _require(self, expected_category: str, escalation_id: int) -> None:
        esc = self._escalations.get(escalation_id)
        if esc.category != expected_category:
            raise ValueError(
                f"escalation {escalation_id} is {esc.category}, not {expected_category}"
            )
