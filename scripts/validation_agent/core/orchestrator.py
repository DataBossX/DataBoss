"""Validation orchestrator — the state machine that drives a run.

States:
  INIT -> INGEST -> VALIDATE -> TRIAGE -> EVALUATE_GATES
       -> (REPAIR -> RECALC -> ITERATE)* -> (CERTIFY | ESCALATE | MAX_ITERATIONS)

Guarantees:
  * Max iterations is bounded (<= settings.max_iterations, hard cap 5).
  * Validation/verification always precede repair.
  * Only safe formula/format repairs are applied; unsafe legal/source facts
    are escalated.
  * A terminal output bundle is generated whether certified or escalated.
  * Every transition is logged to the append-only audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import Settings, get_settings
from core.run_manager import RunManager, sha256_file
from db.db_client import DatabaseManager
from db.audit_logger import AuditLogger
from ingestion.workbook_ingestor import WorkbookIngestor
from ingestion.sheet_classifier import classify_workbook
from ingestion.manifest_builder import build_manifest, write_manifest
from ingestion.data_extractor import extract_context
from validators.base_validator import PASS, FAIL, ESCALATE, ERROR
from validators.val_audit import (
    WorkbookIntegrityValidator, SheetClassificationValidator,
    AuditCompletenessValidator, FinalCertificationValidator,
)
from validators.val_interest import InterestConservationValidator
from validators.val_acreage import AcreageFootingValidator
from validators.val_chain import ChainContinuityValidator
from validators.val_instrument import InstrumentSourceAuditValidator
from validators.val_ogl_wi import (
    OGLRegisterAuditValidator, WIDepthConsistencyValidator,
    WellHBPSupportValidator,
)
from validators.val_formula import FormulaIntegrityValidator
from validators.val_sources import SourceVerificationValidator
from repair.repair_planner import build_plan
from repair.xml_editor import XMLWorkbookEditor
from recalc.libreoffice_runner import recalculate
from sources.spend_guard import SpendGuard
from reports.output_generator import OutputGenerator

# Terminal statuses.
CERTIFIED = "CERTIFIED"
ESCALATED = "ESCALATED"
MAX_ITERATIONS = "MAX_ITERATIONS"
FAILED = "ERROR"


@dataclass
class OrchestratorResult:
    run_id: str
    run_dir: Path
    status: str
    final_state: str
    iterations: int
    results: list[dict] = field(default_factory=list)
    escalations: list[dict] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Orchestrator:
    def __init__(self, settings: Optional[Settings] = None,
                 timestamp: Optional[str] = None):
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.timestamp = timestamp
        self.db = DatabaseManager(self.settings.db_path)
        self.audit = AuditLogger(self.settings.audit_log_path, db=self.db)
        self.rm: Optional[RunManager] = None
        self.run_id = ""
        self.spend_guard: Optional[SpendGuard] = None
        self._repairs_applied = 0

    # ------------------------------------------------------------------ #
    def _log(self, state: str, event: str, desc: str, data: Any = None) -> None:
        self.audit.log(event, desc, run_id=self.run_id, state=state, data=data)

    def _build_validators(self):
        return [
            WorkbookIntegrityValidator(self.settings),
            SheetClassificationValidator(self.settings),
            InterestConservationValidator(self.settings),
            AcreageFootingValidator(self.settings),
            ChainContinuityValidator(self.settings),
            InstrumentSourceAuditValidator(self.settings),
            OGLRegisterAuditValidator(self.settings),
            WIDepthConsistencyValidator(self.settings),
            WellHBPSupportValidator(self.settings),
            FormulaIntegrityValidator(self.settings),
            SourceVerificationValidator(self.settings),
        ]

    def _default_context(self, manifest: dict, classification: dict) -> dict:
        """Assemble a validation context from the manifest.

        Real workbook-specific extraction (tract acreages, interest rows, chain
        links, etc.) is supplied by the caller via ``extra_context``. When
        absent, the affected validators ESCALATE rather than guess — which is
        the safe default.
        """
        return {
            "manifest": manifest,
            "classification": classification,
            "expected_acreage": str(self.settings.expected_acreage),
        }

    # ------------------------------------------------------------------ #
    def run(self, source_workbook: str | Path,
            extra_context: Optional[dict] = None,
            examiner_approved_spend: bool = False) -> OrchestratorResult:
        state = "STATE_INIT"
        # --- INIT ---
        self.rm = RunManager(self.settings.outputs_dir, timestamp=self.timestamp)
        self.run_id = self.rm.run_id
        self.spend_guard = SpendGuard(
            db=self.db, run_id=self.run_id, cap_usd=self.settings.api_cap_usd,
            per_doc_limit=self.settings.per_doc_limit_usd,
            auto_approve=self.settings.auto_approve_paid,
        )
        mode = "dry_run" if self.settings.dry_run else "live"
        self._log(state, "state_enter", "Run initialized.",
                  {"workbook": str(source_workbook), "mode": mode})

        try:
            baseline, base_hash = self.rm.ingest_baseline(source_workbook)
        except (FileNotFoundError, FileExistsError) as e:
            self._log(state, "error", f"Baseline ingest failed: {e}")
            self.db.record_terminal_status(self.run_id, FAILED, state)
            return OrchestratorResult(self.run_id, self.rm.run_dir, FAILED,
                                      state, 0)

        self.db.insert_run(self.run_id, Path(source_workbook).name, base_hash,
                           str(self.rm.run_dir), mode)
        self.db.record_workbook_version(
            self.run_id, "v0", baseline.name, str(baseline),
            sha256_file(baseline), baseline.stat().st_size, "baseline",
            "immutable source copy")

        # --- INGEST ---
        state = "STATE_INGEST"
        ingestor = WorkbookIngestor(baseline)
        wb_manifest = ingestor.ingest()
        classification = classify_workbook(wb_manifest)
        manifest = build_manifest(wb_manifest, classification)
        mpath, mhash = write_manifest(self.rm.run_dir, manifest)
        self._log(state, "state_enter", "Workbook ingested.",
                  {"manifest": str(mpath), "manifest_hash": mhash,
                   "sheets": len(wb_manifest.sheets)})

        base_context = self._default_context(manifest, classification)
        # Auto-extract structured data from the classified sheets so the data
        # gates evaluate REAL workbook values. Extraction is conservative:
        # anything it cannot confidently map is omitted (-> gate escalates).
        extracted = extract_context(baseline, classification)
        base_context.update(extracted)
        self._log(state, "data_extracted",
                  "Structured data extracted from workbook.",
                  {"keys": sorted(extracted.keys())})
        # An explicit caller-supplied context always wins (used by tests and by
        # an examiner overriding auto-extraction).
        if extra_context:
            base_context.update(extra_context)

        # --- Iterative validate/repair loop ---
        iteration = 0
        all_results: list[dict] = []
        current_version = baseline
        max_iter = min(self.settings.max_iterations, 5)

        while iteration < max_iter:
            iteration += 1
            # --- VALIDATE ---
            state = "STATE_VALIDATE"
            self._log(state, "state_enter", f"Validation iteration {iteration}.")
            iter_results = self._validate(iteration, base_context)
            all_results = iter_results  # latest iteration is authoritative

            # --- TRIAGE / EVALUATE_GATES ---
            state = "STATE_EVALUATE_GATES"
            blocking = [r for r in iter_results
                        if r["status"] in {FAIL, ESCALATE, ERROR}]
            repairable = [r for r in iter_results if r.get("repairable")]
            self._log(state, "state_enter", "Gates evaluated.",
                      {"blocking": len(blocking), "repairable": len(repairable)})

            if not blocking:
                break  # all gates pass -> proceed to certify

            # --- TRIAGE ---
            state = "STATE_TRIAGE"
            plan = build_plan(iter_results)
            self._log(state, "state_enter", "Triage complete.",
                      {"safe_repairs": len(plan.actions),
                       "escalations": len(plan.escalations)})

            if not plan.has_repairs:
                # Nothing safe to repair; stop looping and escalate.
                break

            # --- REPAIR ---
            state = "STATE_REPAIR"
            new_version = self._apply_repairs(iteration, current_version, plan)
            if new_version is None:
                self._log(state, "repair_abort",
                          "Repair failed/rolled back; escalating.")
                break
            current_version = new_version

            # --- RECALC ---
            state = "STATE_RECALC"
            current_version = self._recalc(iteration, current_version)

            # --- ITERATE ---
            state = "STATE_ITERATE"
            self._log(state, "state_enter",
                      f"Iteration {iteration} complete; re-validating.")
            base_context = self._refresh_context(base_context, current_version)

        # --- Terminal decision ---
        final_cert = FinalCertificationValidator(self.settings).run(
            {"all_results": all_results})[0].to_dict()
        self.db.record_validation(self.run_id, iteration, final_cert)
        all_results.append(final_cert)

        blocking = [r for r in all_results
                    if r["status"] in {FAIL, ESCALATE, ERROR}
                    and r["gate_name"] != "Final Certification Gate"]

        if iteration >= max_iter and blocking:
            status, state = MAX_ITERATIONS, "STATE_ESCALATE"
        elif not blocking:
            status, state = CERTIFIED, "STATE_CERTIFY"
        else:
            status, state = ESCALATED, "STATE_ESCALATE"

        escalations = self._persist_escalations(all_results)
        self._log(state, "state_enter", f"Terminal state: {status}.",
                  {"iterations": iteration})

        exports = self._generate_outputs(status, manifest, all_results,
                                         escalations, current_version)
        self.db.record_terminal_status(self.run_id, status, state)

        return OrchestratorResult(
            run_id=self.run_id, run_dir=self.rm.run_dir, status=status,
            final_state=state, iterations=iteration, results=all_results,
            escalations=escalations, exports=[str(p) for p in exports],
        )

    # ------------------------------------------------------------------ #
    def _validate(self, iteration: int, context: dict) -> list[dict]:
        results: list[dict] = []
        for validator in self._build_validators():
            try:
                for res in validator.run(context):
                    d = res.to_dict()
                    results.append(d)
                    self.db.record_validation(self.run_id, iteration, d)
            except Exception as e:  # a validator crash is ERROR, not silent
                err = {
                    "gate_name": validator.gate_name, "status": ERROR,
                    "severity": "high", "repairable": False,
                    "reason": f"Validator crashed: {e}",
                    "recommended_action": "Investigate validator error.",
                    "affected_subject": None, "affected_sheet": None,
                    "affected_cell_or_range": None, "evidence": None,
                    "confidence": 1.0, "created_at": _now(),
                }
                results.append(err)
                self.db.record_validation(self.run_id, iteration, err)
        return results

    def _apply_repairs(self, iteration: int, version_path: Path, plan):
        dest = self.rm.next_version_path(suffix=version_path.suffix)
        try:
            with XMLWorkbookEditor(version_path) as editor:
                for action in plan.actions:
                    if action.kind == "set_formula":
                        editor.set_cell_formula(action.sheet, action.cell,
                                                action.formula)
                report = editor.save_as(dest)
        except Exception as e:
            self._log("STATE_REPAIR", "repair_error", f"XML repair failed: {e}")
            return None
        if not report.get("verified"):
            # Corruption -> rollback by discarding the new version.
            self._log("STATE_REPAIR", "repair_rollback",
                      "Repaired workbook failed verification; rolling back.",
                      report.get("verify_detail"))
            try:
                Path(dest).unlink(missing_ok=True)
            except Exception:
                pass
            return None
        self.rm.register_version(dest)
        self._repairs_applied += len(plan.actions)
        self.db.record_workbook_version(
            self.run_id, dest.stem.split("_")[-1], dest.name, str(dest),
            report["dest_hash"], dest.stat().st_size, "repair",
            f"{len(plan.actions)} safe repair(s)")
        for action in plan.actions:
            self.db.record_repair(
                self.run_id, iteration, repair_type=action.kind,
                target_sheet=action.sheet, target_cell=action.cell,
                before_value=action.before_value, after_value=action.formula,
                from_version=version_path.name, to_version=dest.name,
                evidence=str(action.evidence), status="applied")
        self._log("STATE_REPAIR", "repair_applied",
                  f"{len(plan.actions)} repair(s) applied.",
                  {"version": dest.name, "hash": report["dest_hash"]})
        return dest

    def _recalc(self, iteration: int, version_path: Path) -> Path:
        dest = self.rm.next_version_path(suffix=".xlsx")
        result = recalculate(version_path, dest,
                             configured_path=self.settings.libreoffice_path)
        if result.ok and result.output_path:
            self.rm.register_version(result.output_path)
            self.db.record_workbook_version(
                self.run_id, result.output_path.stem.split("_")[-1],
                result.output_path.name, str(result.output_path),
                sha256_file(result.output_path),
                result.output_path.stat().st_size, "recalc",
                "LibreOffice recalculation")
            self._log("STATE_RECALC", "recalc_ok", "Recalculation succeeded.",
                      result.to_dict())
            return result.output_path
        # Not fatal — recalc is best-effort; log honestly and keep prior version.
        self._log("STATE_RECALC", "recalc_skip",
                  "Recalculation unavailable/failed; keeping prior version.",
                  result.to_dict())
        if not result.available:
            self.db.record_escalation(
                self.run_id, "LibreOffice Failure", "low",
                "recalculation", "WI/Depth Consistency Gate",
                result.error,
                recommended_action="Install LibreOffice or set LIBREOFFICE_PATH.")
        return version_path

    def _refresh_context(self, context: dict, version_path: Path) -> dict:
        """After a repair, re-ingest the new version's manifest into context."""
        try:
            ing = WorkbookIngestor(version_path)
            wb_manifest = ing.ingest()
            classification = classify_workbook(wb_manifest)
            context = dict(context)
            context["manifest"] = build_manifest(wb_manifest, classification)
            context["classification"] = classification
            # A successful formula repair clears the hardcoded value; drop the
            # stale defect signal so the next iteration re-derives cleanly.
            context.pop("value_map", None)
        except Exception:
            pass
        return context

    def _persist_escalations(self, results: list[dict]) -> list[dict]:
        escalations: list[dict] = []
        for r in results:
            if r["status"] in {ESCALATE, FAIL, ERROR} and \
                    r["gate_name"] != "Final Certification Gate":
                esc = {
                    "category": r["gate_name"],
                    "severity": r.get("severity"),
                    "subject": r.get("affected_subject"),
                    "gate_name": r["gate_name"],
                    "reason": r.get("reason"),
                    "recommended_action": r.get("recommended_action"),
                    "evidence": r.get("evidence"),
                }
                escalations.append(esc)
                self.db.record_escalation(
                    self.run_id, esc["category"], esc["severity"] or "medium",
                    esc["subject"] or "", esc["gate_name"], esc["reason"] or "",
                    evidence=esc["evidence"],
                    recommended_action=esc["recommended_action"] or "")
        return escalations

    def _generate_outputs(self, status: str, manifest: dict,
                          results: list[dict], escalations: list[dict],
                          current_version: Path) -> list[Path]:
        gen = OutputGenerator(self.rm, db=self.db, run_id=self.run_id)
        spend = {
            "cumulative": float(self.spend_guard.cumulative),
            "cap": float(self.spend_guard.cap),
            "remaining": float(self.spend_guard.remaining()),
        }
        source_docs = self.db.get_source_documents(self.run_id)

        from reports.report_improver import build_improved_markdown
        md = build_improved_markdown(
            run_id=self.run_id,
            mode="dry_run" if self.settings.dry_run else "live",
            source_report=None, manifest=manifest,
            validation_results=results, source_documents=source_docs,
            escalations=escalations, spend=spend,
            credentials_ok=self.settings.okcounty_configured(), timestamp=_now())

        exports: list[Path] = []
        exports.append(gen.write_markdown(md))
        exports.append(gen.write_json_manifest(manifest))
        exports.append(gen.write_source_packet(source_docs))
        exports.append(gen.write_missing_documents(source_docs))
        exports.append(gen.write_escalation_matrix(escalations))

        pdf = gen.write_pdf_packet(
            f"DataBossX {status} Packet — {self.run_id}",
            [("Status", status),
             ("Escalations", f"{len(escalations)} item(s)"),
             ("Spend", f"${spend['cumulative']:.2f} / ${spend['cap']:.2f}")])
        if pdf:
            exports.append(pdf)

        dbcopy = gen.copy_database()
        if dbcopy:
            exports.append(dbcopy)

        # Export a certified copy only when certified; otherwise export a
        # repaired copy ONLY if repairs were actually applied this run.
        if status == CERTIFIED:
            wb_copy = gen.copy_workbook(current_version, certified=True)
            if wb_copy:
                exports.append(wb_copy)
        elif self._repairs_applied > 0:
            wb_copy = gen.copy_workbook(current_version, certified=False)
            if wb_copy:
                exports.append(wb_copy)

        exports.append(gen.build_zip())
        self._log("STATE_CERTIFY" if status == CERTIFIED else "STATE_ESCALATE",
                  "outputs_generated", f"{len(exports)} export(s) written.")
        return exports

    def close(self) -> None:
        self.db.close()
