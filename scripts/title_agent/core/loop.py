"""The Perfection Loop and Taxonomy Router — Phase 6, orchestration.

``PerfectionLoop`` is the state machine of blueprint section 3: ingest the
latest version, evaluate all gates, and either certify (all gates pass), auto-
repair (failures are all Category A) and iterate, or halt for the Examiner
(any Category B failure). ``TaxonomyRouter`` performs the A/B split on the same
``FailureCategory`` enum the validators emit, so the boundary is defined once.

The loop depends on two injected strategies rather than reaching into the Excel
and validator layers directly:

* ``GateEvaluator`` — given the current version, returns the list of gate
  failures (this is where the deployment binds the real column layout of the
  Roger Mills workbook to the Phase-5 validators and the Phase-3 recalc).
* ``Repairer`` — given the Category A failures and a freshly minted N+1 version
  path, writes the repaired workbook (Phase-3 XML surgery + recalc).

This boundary is deliberate: the orchestration logic — versioning, routing,
escalation, resume — is what must be proven correct and is fully tested here
with in-memory fakes; the concrete adapters are thin and layout-specific.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence

from .memory import (
    ArtifactVersion,
    AuditLogger,
    Escalation,
    EscalationStore,
    SQLiteManager,
    VersionController,
)
from .taxonomy import FailureCategory, is_auto_repairable
from ..validators.rules import Failure

# --------------------------------------------------------------------------- #
# Strategy protocols
# --------------------------------------------------------------------------- #


class GateEvaluator(Protocol):
    """Runs every quality gate against a workbook version and returns the
    failures found (empty tuple == all gates pass)."""

    def evaluate(self, version: ArtifactVersion) -> Sequence[Failure]: ...


class Repairer(Protocol):
    """Writes the repaired workbook for the given Category A failures to
    ``new_version.file_path`` (which does not yet exist). Must not modify
    ``old_version``."""

    def apply(
        self,
        failures: Sequence[Failure],
        old_version: ArtifactVersion,
        new_version: ArtifactVersion,
    ) -> None: ...


# --------------------------------------------------------------------------- #
# TaxonomyRouter
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RoutingDecision:
    """The split of a failure set into auto-repairs and escalations."""

    auto_repairs: tuple[Failure, ...]
    escalations: tuple[Failure, ...]

    @property
    def has_escalations(self) -> bool:
        return bool(self.escalations)

    @property
    def has_auto_repairs(self) -> bool:
        return bool(self.auto_repairs)


class TaxonomyRouter:
    """Splits failures into Category A (auto-repair) and Category B (escalate).

    The rule is asymmetric on purpose: only explicitly Category A failures are
    routed to auto-repair; everything else — including any category we don't
    recognize — escalates. A failure can never be auto-repaired by accident.
    """

    def route(self, failures: Sequence[Failure]) -> RoutingDecision:
        auto: list[Failure] = []
        escalate: list[Failure] = []
        for f in failures:
            if is_auto_repairable(f.category):
                auto.append(f)
            else:
                escalate.append(f)
        return RoutingDecision(tuple(auto), tuple(escalate))


# --------------------------------------------------------------------------- #
# Loop outcome
# --------------------------------------------------------------------------- #


class LoopState(str, Enum):
    CERTIFIED = "CERTIFIED"          # all gates pass — done
    ESCALATED = "ESCALATED"          # halted for the Examiner (Category B)
    MAX_ITERATIONS = "MAX_ITERATIONS"  # safety cap hit without convergence


@dataclass(frozen=True)
class LoopOutcome:
    state: LoopState
    iterations: int
    final_version: Optional[ArtifactVersion]
    escalations: tuple[Escalation, ...] = ()
    unresolved_failures: tuple[Failure, ...] = ()

    @property
    def certified(self) -> bool:
        return self.state == LoopState.CERTIFIED


# --------------------------------------------------------------------------- #
# PerfectionLoop
# --------------------------------------------------------------------------- #


class PerfectionLoop:
    """Drives a workbook to certification or a HITL halt."""

    def __init__(
        self,
        manager: SQLiteManager,
        artifact_key: str,
        evaluator: GateEvaluator,
        repairer: Repairer,
        *,
        max_iterations: int = 50,
        audit: Optional[AuditLogger] = None,
        versions: Optional[VersionController] = None,
        escalations: Optional[EscalationStore] = None,
        on_certified: Optional[Callable[[ArtifactVersion], None]] = None,
    ) -> None:
        self._db = manager
        self._key = artifact_key
        self._evaluator = evaluator
        self._repairer = repairer
        self._max = max_iterations
        self._audit = audit or AuditLogger(manager)
        self._versions = versions or VersionController(manager)
        self._escalations = escalations or EscalationStore(manager, self._audit)
        self._router = TaxonomyRouter()
        # Called with the certified version on success — the loop's output step
        # (Certified Workbook + Audit Report). Optional so the core loop stays
        # testable without the reporting layer.
        self._on_certified = on_certified

    def run(self) -> LoopOutcome:
        """Run the loop from the latest version until it certifies, escalates,
        or hits the iteration cap. Idempotent to re-invoke: after the Examiner
        resolves an escalation and a corrected version is minted, calling
        ``run`` again resumes from that new latest version."""
        latest = self._versions.get_latest_version(self._key)
        if latest is None:
            raise RuntimeError(
                f"no versions exist for {self._key!r}; register the initial "
                "workbook with VersionController.mint_new_version first."
            )

        iterations = 0
        last_signature: Optional[frozenset[tuple[str, str]]] = None
        while iterations < self._max:
            iterations += 1
            current = self._versions.get_latest_version(self._key)
            assert current is not None  # a version always exists inside the loop

            failures = tuple(self._evaluator.evaluate(current))
            self._audit.log_action(
                "GATE_EVALUATION", f"{self._key} {current.version_label}",
                "PASS" if not failures else f"{len(failures)} failure(s)",
                metadata={"failures": [f.category.value for f in failures]},
            )

            if not failures:
                self._audit.log_action(
                    "CERTIFIED", f"{self._key} {current.version_label}", "PASS"
                )
                if self._on_certified is not None:
                    self._on_certified(current)
                return LoopOutcome(LoopState.CERTIFIED, iterations, current)

            signature = frozenset((f.category.value, f.reference) for f in failures)
            if signature == last_signature:
                # The previous auto-repair changed nothing — the agent cannot
                # actually clear these Category A failures (e.g. a repair with
                # no handler). Spinning to MAX_ITERATIONS would hide that, so we
                # escalate the stuck failures to the Examiner instead.
                self._audit.log_action(
                    "REPAIR_STALLED", f"{self._key} {current.version_label}",
                    f"{len(failures)} failure(s) unchanged after repair",
                )
                opened = self._halt_for_examiner(failures)
                return LoopOutcome(
                    LoopState.ESCALATED, iterations, current,
                    escalations=opened, unresolved_failures=failures,
                )

            decision = self._router.route(failures)

            if decision.has_escalations:
                opened = self._halt_for_examiner(decision.escalations)
                return LoopOutcome(
                    LoopState.ESCALATED, iterations, current,
                    escalations=opened, unresolved_failures=decision.escalations,
                )

            # All failures are Category A: mint N+1 and auto-repair, then loop.
            last_signature = signature
            repaired = self._auto_repair(current, decision.auto_repairs)
            if repaired is None:
                # The repair itself failed (exception, or produced no file). The
                # agent cannot clear these on its own — escalate rather than
                # crash or spin.
                opened = self._halt_for_examiner(decision.auto_repairs)
                return LoopOutcome(
                    LoopState.ESCALATED, iterations, current,
                    escalations=opened, unresolved_failures=decision.auto_repairs,
                )

        # Iteration cap hit without convergence (signatures kept changing, so
        # the stall detector never fired). Do not abandon the workbook: queue
        # the outstanding failures for the Examiner.
        final = self._versions.get_latest_version(self._key)
        remaining = tuple(self._evaluator.evaluate(final)) if final is not None else ()
        opened = self._halt_for_examiner(remaining) if remaining else ()
        self._audit.log_action(
            "MAX_ITERATIONS", self._key,
            f"stopped after {iterations} iterations; {len(opened)} escalation(s) opened",
        )
        return LoopOutcome(
            LoopState.MAX_ITERATIONS, iterations, final,
            escalations=opened, unresolved_failures=remaining,
        )

    def _auto_repair(
        self, current: ArtifactVersion, repairs: Sequence[Failure]
    ) -> Optional[ArtifactVersion]:
        """Mint N+1 and apply the repairs. Returns the new version, or None if
        the repair failed — in which case the phantom (fileless) version row is
        discarded so it cannot become the wedged "latest" version."""
        reason = "auto-repair: " + ", ".join(sorted({f.category.value for f in repairs}))
        new_version = self._versions.mint_new_version(self._key, reason=reason)
        try:
            # The repairer writes the N+1 file; the old file is never overwritten.
            self._repairer.apply(repairs, current, new_version)
            if not new_version.file_path.exists():
                raise RuntimeError("repairer produced no output file")
        except Exception as exc:  # noqa: BLE001 - any repair failure must be contained
            self._audit.log_action(
                "AUTO_REPAIR_FAILED",
                f"{self._key} {current.version_label} -> {new_version.version_label}",
                str(exc)[:200], metadata={"repairs": [f.reference for f in repairs]},
            )
            if not new_version.file_path.exists():
                try:
                    self._versions.discard_version(new_version)
                except Exception:  # noqa: BLE001 - discard is best-effort cleanup
                    pass
            return None
        self._audit.log_action(
            "AUTO_REPAIR",
            f"{self._key} {current.version_label} -> {new_version.version_label}",
            reason,
            metadata={"repairs": [f.reference for f in repairs]},
        )
        return new_version

    def _halt_for_examiner(self, escalations: Sequence[Failure]) -> tuple[Escalation, ...]:
        opened: list[Escalation] = []
        for f in escalations:
            opened.append(
                self._escalations.open_escalation(
                    category=f.category.value,
                    gate=f.gate.value,
                    reference=f.reference,
                    proof={"detail": f.detail, **f.proof},
                )
            )
        self._audit.log_action(
            "HITL_HALT", self._key, f"{len(opened)} escalation(s) opened",
            metadata={"categories": [f.category.value for f in escalations]},
        )
        return tuple(opened)

    # ---- resume ---------------------------------------------------------- #

    def apply_examiner_resolution(
        self,
        escalation_id: int,
        examiner_id: str,
        resolution: str,
        repairer: Repairer,
        failures: Sequence[Failure],
    ) -> ArtifactVersion:
        """Record the Examiner's decision, mint the corrected version, and let
        a repairer write the verified fact into it. The loop can then be re-run
        to continue from this new version.

        The *fact* comes entirely from the Examiner (via ``resolution`` and the
        ``repairer`` they parameterize) — the agent applies it, it does not
        author it.
        """
        self._escalations.resolve(escalation_id, examiner_id, resolution)
        current = self._versions.get_latest_version(self._key)
        if current is None:
            raise RuntimeError("cannot resume: no current version")
        new_version = self._versions.mint_new_version(
            self._key, reason=f"examiner resolution (esc {escalation_id})"
        )
        try:
            repairer.apply(failures, current, new_version)
            if not new_version.file_path.exists():
                raise RuntimeError("repairer produced no output file")
        except Exception:
            # Roll back the phantom version so the resolved escalation can be
            # re-applied cleanly rather than leaving a wedged fileless latest.
            if not new_version.file_path.exists():
                try:
                    self._versions.discard_version(new_version)
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    pass
            self._audit.log_action(
                "EXAMINER_RESOLUTION_FAILED",
                f"{self._key} {current.version_label}", "repair failed",
                actor=examiner_id, metadata={"escalation_id": escalation_id},
            )
            raise
        self._audit.log_action(
            "EXAMINER_RESOLUTION_APPLIED",
            f"{self._key} {current.version_label} -> {new_version.version_label}",
            resolution, actor=examiner_id, metadata={"escalation_id": escalation_id},
        )
        return new_version

    @property
    def open_escalations(self) -> list[Escalation]:
        return self._escalations.list_open()
