"""The validation state machine.

STATE_INIT → INGEST → VALIDATE → TRIAGE → EVALUATE_GATES → {REPAIR → RECALC →
ITERATE → VALIDATE} → CERTIFY | ESCALATE.

Invariants enforced here:
* Verification/validation always happen before any repair.
* Only safe formula/math/format failures may be repaired; any unsafe
  legal/source/title/economic failure halts the repair path and escalates.
* Iterations are hard-capped (<= 5) so the loop can never run forever.
* Every state transition is logged to the append-only audit trail.
* A final output is always generated (certify, escalate, max-iterations, fatal).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import Settings
from core.enums import GateStatus, State, Urgency
from core.run_manager import RunManager
from db.audit_logger import AuditLogger
from db.db_client import DatabaseManager
from ingestion.manifest_builder import build_manifest, write_manifest
from ingestion.sheet_classifier import classify_workbook
from ingestion.workbook_ingestor import ingest_workbook
from recalc.libreoffice_runner import LibreOfficeRunner
from repair.failure_classifier import triage_results
from repair.repair_planner import plan_repairs
from repair.xml_editor import XmlWorkbookEditor
from reports.output_generator import OutputGenerator
from sources.source_cache import SourceCache
from sources.source_finder import SourceFinder, build_reference_queue
from sources.spend_guard import SpendGuard
from validators.base_validator import Escalation, ValidationResult
from validators.val_acreage import AcreageFootingGate
from validators.val_audit import AuditCompletenessGate
from validators.val_certification import FinalCertificationGate
from validators.val_chain import ChainContinuityGate
from validators.val_classification import SheetClassificationGate
from validators.val_formula import FormulaIntegrityGate
from validators.val_instrument import InstrumentSourceAuditGate
from validators.val_interest import InterestConservationGate
from validators.val_ogl_wi import (
    OGLRegisterAuditGate,
    WellHBPSupportGate,
    WIDepthConsistencyGate,
)
from validators.val_sources import SourceVerificationGate
from validators.val_workbook import WorkbookIntegrityGate

# Ordered gate pipeline (certification runs last, separately).
GATES = [
    WorkbookIntegrityGate,
    SheetClassificationGate,
    InterestConservationGate,
    AcreageFootingGate,
    ChainContinuityGate,
    InstrumentSourceAuditGate,
    OGLRegisterAuditGate,
    WIDepthConsistencyGate,
    WellHBPSupportGate,
    FormulaIntegrityGate,
    SourceVerificationGate,
    AuditCompletenessGate,
]


@dataclass
class OrchestratorResult:
    run_id: str
    run_folder: str
    final_state: State
    certified: bool
    iterations: int
    results: List[ValidationResult] = field(default_factory=list)
    escalations: List[Escalation] = field(default_factory=list)
    export_files: List[Dict[str, str]] = field(default_factory=list)
    export_zip: Optional[str] = None
    detail: str = ""


def _escalation_from_result(
    result: ValidationResult, source_index: Dict[str, Any], workbook_loc: str
) -> Escalation:
    return Escalation(
        failed_gate=result.gate_name,
        workbook_location=workbook_loc,
        subject=result.affected_subject or result.affected_cell_or_range,
        sources_checked=[str(k) for k in source_index.get("found_keys", [])],
        sources_missing=[
            str(m.get("reference_key")) for m in source_index.get("missing", [])
        ],
        checks_attempted=[result.gate_name],
        reason_repair_blocked=result.reason,
        recommended_examiner_action=result.recommended_action,
        urgency=Urgency.CRITICAL if result.severity.value == "FATAL" else Urgency.HIGH,
        failure_category=result.failure_category,
    )


class Orchestrator:
    def __init__(self, settings: Settings, db: DatabaseManager, audit: AuditLogger) -> None:
        self.settings = settings
        self.db = db
        self.audit = audit
        self.state = State.INIT

    def _transition(self, run_id: str, new_state: State, detail: str = "") -> None:
        self.state = new_state
        self.audit.log_event(
            event_type="STATE_TRANSITION",
            run_id=run_id,
            subject=new_state.value,
            detail=detail,
        )

    def _run_gates(self, context: Dict[str, Any]) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        for gate_cls in GATES:
            gate = gate_cls()
            try:
                results.extend(gate.validate(context))
            except Exception as exc:  # a gate crash must not be swallowed silently
                results.append(
                    ValidationResult(
                        gate_name=gate.gate_name,
                        status=GateStatus.ESCALATE,
                        reason=f"gate raised an exception: {exc}",
                        recommended_action="Investigate validator error before certifying.",
                        confidence=0.0,
                    )
                )
        return results

    def run(self, workbook_path: Path, timestamp: Optional[str] = None) -> OrchestratorResult:
        workbook_path = Path(workbook_path)
        run = RunManager.create(self.settings.outputs_dir, timestamp)
        run_id = run.run_id

        self.audit.log_run(
            run_id=run_id, run_folder=str(run.run_folder), status="STARTED",
            state=State.INIT.value, iteration=0,
            workbook_source_path=str(workbook_path),
        )
        self._transition(run_id, State.INGEST, "ingesting workbook")

        # -- INGEST -------------------------------------------------------
        v0 = run.ingest_source_workbook(workbook_path)
        self.audit.log_workbook_version(
            run_id=run_id, version_index=v0.index, version_label=v0.label,
            file_path=str(v0.path), sha256=v0.sha256, origin=v0.origin,
        )
        structure = ingest_workbook(v0.path)
        classification = classify_workbook(structure)
        manifest = build_manifest(structure, classification, run_id)
        manifest_meta = write_manifest(manifest, run.audit_dir)
        self.audit.log_event("MANIFEST_BUILT", run_id, subject=manifest_meta["path"],
                             detail=manifest_meta["sha256"])

        # -- SOURCES ------------------------------------------------------
        spend_guard = SpendGuard(self.settings, self.audit, run_id)
        cache = SourceCache(run.sources_dir / "source_cache.json")
        finder = SourceFinder(
            self.settings, self.audit, cache, okcounty=None, run_id=run_id,
            run_sources_dir=run.sources_dir,
        )
        references = build_reference_queue(structure, classification)
        source_index = finder.find(references).to_dict()

        base_context: Dict[str, Any] = {
            "structure": structure,
            "classification": classification,
            "manifest": manifest,
            "settings": self.settings,
            "workbook_path": v0.path,
            "source_index": source_index,
            "db": self.db,
            "run_id": run_id,
        }

        recalc_runner = LibreOfficeRunner(self.settings.libreoffice_path)
        iterations = 0
        final_results: List[ValidationResult] = []
        certified = False
        final_state = State.ESCALATE

        while True:
            self._transition(run_id, State.VALIDATE, f"iteration {iterations}")
            latest = run.latest_version()
            context = dict(base_context)
            context["workbook_path"] = latest.path if latest else v0.path
            # re-ingest structure of the latest version so validators see repairs
            if latest and latest.index > 0:
                context["structure"] = ingest_workbook(latest.path)
                context["classification"] = classify_workbook(context["structure"])
            results = self._run_gates(context)
            for r in results:
                self.audit.log_validation_result(run_id, iterations, r)
            final_results = results

            self._transition(run_id, State.TRIAGE, "classifying failures")
            triages = triage_results(results)
            repair_triages = [t for t in triages if t.route == "repair"]
            escalate_triages = [t for t in triages if t.route == "escalate"]

            self._transition(run_id, State.EVALUATE_GATES, "evaluating gate outcomes")

            # No open findings at all -> certify.
            if not triages:
                final_state = State.CERTIFY
                break

            # Any unsafe failure halts the repair path and escalates.
            if escalate_triages:
                final_state = State.ESCALATE
                break

            # Only safe repairs remain.
            if iterations >= self.settings.max_iterations - 1:
                # out of repair budget; escalate whatever remains
                final_state = State.ESCALATE
                break

            # -- REPAIR ---------------------------------------------------
            self._transition(run_id, State.REPAIR, "planning safe repairs")
            plan = plan_repairs(repair_triages, context["structure"])
            if not plan.has_work:
                final_state = State.ESCALATE
                break
            new_version_path = run.new_version_path("repair")
            editor = XmlWorkbookEditor(context["workbook_path"])
            outcome = editor.apply_formula_repairs(plan.ops, new_version_path)
            if not outcome.ok or outcome.output_path is None:
                self.audit.log_repair(
                    run_id, iterations, repair_type="formula",
                    status="rolled_back", detail=outcome.detail,
                    before_sha256=outcome.before_sha256,
                )
                final_state = State.ESCALATE
                break
            repaired = run.register_version(outcome.output_path, "repair")
            self.audit.log_workbook_version(
                run_id=run_id, version_index=repaired.index, version_label=repaired.label,
                file_path=str(repaired.path), sha256=repaired.sha256,
                origin="repair", parent_version_index=repaired.parent_index,
            )
            self.audit.log_repair(
                run_id, iterations, repair_type="formula", status="applied",
                from_version_index=repaired.parent_index, to_version_index=repaired.index,
                detail="; ".join(outcome.applied),
                before_sha256=outcome.before_sha256, after_sha256=outcome.after_sha256,
            )

            # -- RECALC ---------------------------------------------------
            self._transition(run_id, State.RECALC, "recalculating with LibreOffice")
            recalc_dest = run.new_version_path("recalc")
            rr = recalc_runner.recalculate(repaired.path, recalc_dest)
            if rr.ok and rr.output_path is not None:
                recalced = run.register_version(rr.output_path, "recalc")
                self.audit.log_workbook_version(
                    run_id=run_id, version_index=recalced.index,
                    version_label=recalced.label, file_path=str(recalced.path),
                    sha256=recalced.sha256, origin="recalc",
                    parent_version_index=recalced.parent_index,
                )
            else:
                # recalc unavailable/failed: not fatal (fullCalcOnLoad is set),
                # but record it honestly.
                self.audit.log_event(
                    "RECALC_UNAVAILABLE", run_id, subject="libreoffice",
                    detail=rr.detail,
                )

            self._transition(run_id, State.ITERATE, f"iteration {iterations} complete")
            iterations += 1

        # -- CERTIFY / ESCALATE ------------------------------------------
        cert_gate = FinalCertificationGate()
        cert_context = dict(base_context)
        cert_context["prior_results"] = final_results
        cert_results = cert_gate.validate(cert_context)
        for r in cert_results:
            self.audit.log_validation_result(run_id, iterations, r)
        certified = final_state == State.CERTIFY and all(r.passed for r in cert_results)
        final_state = State.CERTIFY if certified else State.ESCALATE
        all_results = final_results + cert_results

        # Build escalations for every open FAIL/ESCALATE.
        escalations: List[Escalation] = []
        latest = run.latest_version()
        wb_loc = str(latest.path) if latest else str(v0.path)
        for r in all_results:
            if r.status in (GateStatus.FAIL, GateStatus.ESCALATE):
                esc = _escalation_from_result(r, source_index, wb_loc)
                escalations.append(esc)
                self.audit.log_escalation(run_id, esc)

        self._transition(run_id, final_state, "finalizing outputs")

        repaired_flag = latest is not None and latest.index > 0
        generator = OutputGenerator(self.audit, run_id, run.exports_dir)
        bundle = generator.generate(
            {
                "results": all_results,
                "escalations": escalations,
                "source_index": source_index,
                "manifest_path": manifest_meta["path"],
                "db_path": str(self.settings.db_path),
                "certified": certified,
                "final_state": final_state.value,
                "latest_version_path": str(latest.path) if latest else None,
                "repaired": repaired_flag,
            }
        )

        self.audit.log_run(
            run_id=run_id, run_folder=str(run.run_folder),
            status="CERTIFIED" if certified else "ESCALATED",
            state=final_state.value, iteration=iterations,
        )

        return OrchestratorResult(
            run_id=run_id,
            run_folder=str(run.run_folder),
            final_state=final_state,
            certified=certified,
            iterations=iterations,
            results=all_results,
            escalations=escalations,
            export_files=bundle.files,
            export_zip=bundle.zip_path,
            detail="ok",
        )
