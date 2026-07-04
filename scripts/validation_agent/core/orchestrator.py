"""
Orchestrator state machine.

States: INIT → INGEST → VALIDATE → TRIAGE → EVALUATE_GATES →
        (REPAIR → RECALC → ITERATE ↺)  → CERTIFY | ESCALATE

Guarantees:
  * Validation/verification always precede repair.
  * Only SAFE_REPAIR (known-intended formula) actions ever mutate a workbook,
    and only on a fresh copied version — the source is never touched.
  * Legal/title/source/HBP problems escalate; they are never auto-repaired.
  * Spend-cap / auth / dependency problems block that path and escalate.
  * Iterations are hard-capped (≤5); the loop cannot run forever.
  * A final export bundle is produced whether the run CERTIFIES or ESCALATES.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import Settings
from db.db_client import DatabaseManager, utcnow
from db.audit_logger import AuditLogger
from core.run_manager import RunManager
from ingestion.workbook_ingestor import ingest
from ingestion.manifest_builder import build_and_write
from ingestion.sheet_classifier import classify_sheets, core_gate
from sources.spend_guard import SpendGuard
from sources.source_cache import SourceCache
from sources.source_finder import SourceFinder
from validators.base_validator import PASS, FAIL, ESCALATE, ERROR
from validators.val_formula import WorkbookIntegrityValidator, FormulaValidator
from validators.val_acreage import AcreageValidator
from validators.val_interest import InterestValidator
from validators.val_chain import ChainValidator
from validators.val_instrument import InstrumentValidator
from validators.val_ogl_wi import OglWiValidator
from validators.val_sources import SourceValidator
from validators.val_audit import (WellHbpValidator, AuditCompletenessValidator,
                                   FinalCertificationValidator)
from repair.failure_classifier import triage_all, Routing
from repair.repair_planner import build_plan
from repair.xml_editor import SafeXlsxEditor, XmlEditError
from recalc.libreoffice_runner import recalc as lo_recalc
from reports.report_finder import ReportFinder
from reports.report_improver import ReportImprover
from reports.output_generator import OutputGenerator

# States
INIT, INGEST, VALIDATE, TRIAGE, EVALUATE_GATES = "INIT", "INGEST", "VALIDATE", "TRIAGE", "EVALUATE_GATES"
REPAIR, RECALC, ITERATE, CERTIFY, ESCALATE_S = "REPAIR", "RECALC", "ITERATE", "CERTIFY", "ESCALATE"
MAX_ITER_STATE = "MAX_ITERATIONS"


@dataclass
class OrchestratorResult:
    run_id: str
    final_state: str
    iterations: int
    run_folder: str
    exports: List[str] = field(default_factory=list)
    gate_summary: Dict[str, int] = field(default_factory=dict)


class Orchestrator:
    def __init__(self, db: DatabaseManager, settings: Settings):
        self.db = db
        self.settings = settings
        self.audit = AuditLogger(db)
        self.rm = RunManager(db, settings.outputs_dir)

    def _log_transition(self, frm: str, to: str, note: str = "") -> None:
        self.audit.event("state_transition", "orchestrator", f"{frm} -> {to}", {"note": note})

    def _run_validators(self, manifest: Dict, classifications, wb_path: str,
                        available_refs, iteration: int) -> List:
        cfg = {
            "expected_acreage": str(self.settings.expected_acreage),
            "available_source_refs": available_refs,
            "audit_event_count": self.db.count("audit_events", "run_id = ?", (self.audit.run_id,)),
            "validation_result_count": self.db.count("validation_results", "run_id = ?", (self.audit.run_id,)) + 1,
        }
        validators = [
            WorkbookIntegrityValidator(manifest, classifications, wb_path, cfg),
            FormulaValidator(manifest, classifications, wb_path, cfg),
            AcreageValidator(manifest, classifications, wb_path, cfg),
            InterestValidator(manifest, classifications, wb_path, cfg),
            ChainValidator(manifest, classifications, wb_path, cfg),
            InstrumentValidator(manifest, classifications, wb_path, cfg),
            OglWiValidator(manifest, classifications, wb_path, cfg),
            SourceValidator(manifest, classifications, wb_path, cfg),
            WellHbpValidator(manifest, classifications, wb_path, cfg),
            AuditCompletenessValidator(manifest, classifications, wb_path, cfg),
        ]
        results = []
        for v in validators:
            try:
                for r in v.run():
                    results.append(r)
                    self.audit.validation(r.to_dict(), iteration)
            except Exception as e:  # a validator crashing must not crash the run
                from validators.base_validator import ValidationResult
                er = ValidationResult(gate_name=v.gate_name, status=ERROR,
                                      reason=f"validator error: {e}")
                results.append(er)
                self.audit.validation(er.to_dict(), iteration)
        return results

    def _apply_safe_repairs(self, plan, wb_path: str, iteration: int) -> Optional[Path]:
        """Apply real formula_sum cell rewrites on a fresh version. Returns new path or None."""
        try:
            editor = SafeXlsxEditor(wb_path)
        except XmlEditError as e:
            self.audit.escalate("Broken Workbook Structure / XML Corruption",
                                "xml_editor", str(e))
            return None
        # Build a subject -> (sheet, total_cell, sum_range) map from the workbook,
        # so we rewrite the exact literal total with the intended SUM over its owner
        # rows. The intended formula is knowable from the block itself, satisfying
        # the "only repair when the exact intended formula is known" rule.
        from validators.wb_access import read_tract_blocks
        block_map = {}
        for b in read_tract_blocks(wb_path):
            if b.get("total_is_formula") is False and b.get("total_cell") and b.get("sum_range"):
                block_map[b["label"]] = (b["sheet"], b["total_cell"], b["sum_range"])
        applied = 0
        for act in plan.actions:
            if act.kind != "formula_sum":
                continue
            info = block_map.get(act.subject)
            if not info:
                continue
            sheet, total_cell, sum_range = info
            part = editor.sheet_part_for(sheet)
            if not part:
                continue
            formula = f"SUM({sum_range})"
            if editor.set_sheet_cell_formula(part, total_cell, formula):
                self.audit.repair(iteration=iteration, repair_type="formula_sum",
                                  target_sheet=sheet, target_range=total_cell,
                                  before_value="hardcoded_total",
                                  after_value=f"={formula}",
                                  from_version=Path(wb_path).name, to_version="pending",
                                  justification=act.description)
                applied += 1
        if applied == 0:
            return None
        new_path = self.rm.next_version_path()
        try:
            info = editor.save_as(new_path)
        except XmlEditError as e:
            self.audit.escalate("Broken Workbook Structure / XML Corruption",
                                "xml_editor.save_as", str(e))
            return None
        committed = self.rm.register_version(new_path, origin="repair")
        self.audit.event("repair_applied", "orchestrator",
                         f"{applied} safe repair(s) -> {committed.name}", info)
        return committed

    def _recalc(self, wb_path: str) -> Optional[Path]:
        dest = self.rm.next_version_path()
        res = lo_recalc(wb_path, dest, self.settings.libreoffice_path)
        if not res.ok:
            self.audit.escalate("LibreOffice Failure", "recalc", res.reason,
                                recommended_action="Install LibreOffice or set LIBREOFFICE_PATH; recalc skipped")
            self.audit.event("recalc_skipped", "orchestrator", res.reason)
            return None
        committed = self.rm.register_version(res.output_path, origin="recalc")
        self.audit.event("recalc_done", "orchestrator", f"recalculated -> {committed.name}",
                         {"libreoffice": res.libreoffice_path})
        return committed

    def run(self, workbook_path: str | Path, extra_report_dirs=None) -> OrchestratorResult:
        mode = "dry-run" if not self.settings.live_enabled() else "live"
        # INIT
        run_id = self.rm.create_run(workbook_path, mode=mode)
        self.audit.bind_run(run_id)
        guard = SpendGuard(self.db, self.settings, run_id)
        self._log_transition(INIT, INGEST, f"run {run_id} mode {mode}")

        # INGEST
        wb_path = str(self.rm.latest_version())
        manifest_obj = ingest(self.rm.path("input") / Path(workbook_path).name)
        manifest = manifest_obj.to_dict()
        build_and_write(manifest_obj, self.rm.path("audit"))
        classifications = classify_sheets(manifest["sheets"])
        gate = core_gate(classifications)
        self.audit.event("ingest", "orchestrator",
                         f"{len(manifest['sheet_names'])} sheets; tracts={gate['tracts_found']}",
                         {"core_gate": gate})
        if gate["fatal"]:
            self.audit.escalate("Unsafe Legal Inference", "core_gate",
                                f"Missing core sheets: {gate['missing_core']}",
                                recommended_action="Confirm workbook has 10 tracts + OGL + WI")

        # Source finder — build the missing-source queue (dry-run safe).
        cache = SourceCache(self.rm.path("sources"))
        finder = SourceFinder(self.db, self.settings, cache, run_id,
                              search_dirs=[str(self.rm.path("sources"))])
        squeue = finder.build_queue(wb_path)
        available_refs = [i.reference for i in squeue.resolved]
        src_summary = finder.summary(squeue)

        # ITERATE loop
        iteration = 0
        final = ESCALATE_S
        last_results: List = []
        while iteration < self.settings.max_iterations:
            self._log_transition(VALIDATE, TRIAGE, f"iteration {iteration}")
            wb_path = str(self.rm.latest_version())
            results = self._run_validators(manifest, classifications, wb_path,
                                            available_refs, iteration)
            last_results = results
            triages = triage_all(results)
            plan = build_plan(triages, results)
            for t in plan.escalations:
                self.audit.escalate(t.failure_type.value, t.gate_name, t.reason,
                                    recommended_action="Human examiner review")
            for t in plan.blocked:
                self.audit.escalate(t.failure_type.value, t.gate_name, t.reason,
                                    recommended_action="Resolve block (spend/auth/dependency)")

            has_fail = any(r.status in (FAIL, ERROR) for r in results)
            has_escalate = any(r.status == ESCALATE for r in results) or plan.escalations or plan.blocked

            self._log_transition(TRIAGE, EVALUATE_GATES, f"safe_repairs={len(plan.actions)}")
            if not has_fail and not has_escalate:
                final = CERTIFY
                break
            if plan.has_safe_repairs:
                self._log_transition(EVALUATE_GATES, REPAIR, f"{len(plan.actions)} actions")
                repaired = self._apply_safe_repairs(plan, wb_path, iteration)
                if repaired is None:
                    # Nothing could actually be safely applied — do not spin.
                    self.audit.event("repair_noop", "orchestrator",
                                     "No safe repair could be applied; escalating")
                    final = ESCALATE_S
                    break
                self._log_transition(REPAIR, RECALC, repaired.name)
                self._recalc(str(repaired))  # best-effort; escalates on dependency failure
                iteration += 1
                self._log_transition(RECALC, ITERATE, f"-> iteration {iteration}")
                continue
            # Only escalations/blocks remain — nothing safe to repair.
            final = ESCALATE_S
            break
        else:
            final = MAX_ITER_STATE

        # Final certification gate.
        fc = FinalCertificationValidator(config={"prior_results": last_results}).run()[0]
        self.audit.validation(fc.to_dict(), iteration)
        if fc.status != PASS and final == CERTIFY:
            final = ESCALATE_S

        self._log_transition(EVALUATE_GATES, final, "finalizing")
        exports = self._finalize(run_id, manifest, last_results, squeue, src_summary,
                                 final, mode, guard, iteration, extra_report_dirs)
        # Record terminal run status (append-only: a new row would double the run;
        # instead we log via audit + a status event — runs table row stays as INIT
        # baseline and final_state lives in audit_events + build summary).
        self.audit.event("run_final", "orchestrator", f"final_state={final}",
                         {"iterations": iteration, "exports": [str(e) for e in exports]})

        gate_summary = {
            "PASS": sum(1 for r in last_results if r.status == PASS),
            "FAIL": sum(1 for r in last_results if r.status == FAIL),
            "ESCALATE": sum(1 for r in last_results if r.status == ESCALATE),
            "ERROR": sum(1 for r in last_results if r.status == ERROR),
        }
        return OrchestratorResult(run_id, final, iteration, str(self.rm.run_folder),
                                  [str(e) for e in exports], gate_summary)

    def _finalize(self, run_id, manifest, results, squeue, src_summary, final,
                  mode, guard, iteration, extra_report_dirs) -> List[Path]:
        outg = OutputGenerator(self.rm.path("exports"))
        # escalations from DB
        esc_rows = self.db.query("SELECT category, subject, detail, recommended_action "
                                 "FROM escalations WHERE run_id = ?", (run_id,))
        escalations = [dict(r) for r in esc_rows]
        spend = {"cumulative": str(guard.cumulative()), "cap": str(guard.cap),
                 "remaining": str(guard.remaining())}

        # Find + improve the best existing report (read-only).
        roots = [str(self.settings.project_root), str(self.settings.outputs_dir),
                 str(self.settings.project_root / "reports")]
        finder = ReportFinder(roots, extra_report_dirs or [])
        best = finder.best()
        improver = ReportImprover(self.rm.path("reports"))
        improved = improver.improve(best_report=best.path if best else None,
                                    manifest=manifest, validation_results=results,
                                    source_summary=src_summary, escalations=escalations,
                                    final_state=final, mode=mode, spend=spend)

        # Markdown audit report.
        md_lines = [f"# Audit Report — {run_id}", "",
                    f"- Final state: **{final}**", f"- Mode: {mode}",
                    f"- Iterations: {iteration}",
                    f"- Spend: ${spend['cumulative']} / ${spend['cap']}", "",
                    "## Gates", ""]
        for r in results:
            md_lines.append(f"- **{r.gate_name}**: {r.status} — {r.reason}")
        md = outg.write_markdown("\n".join(md_lines))

        js = outg.write_json({"run_id": run_id, "final_state": final, "manifest": manifest,
                              "spend": spend, "source_summary": src_summary}, "run_manifest.json")
        missing = [{"reference": i.reference, "kind": i.kind, "sheet": i.sheet,
                    "cell": i.cell, "status": i.status} for i in squeue.missing]
        miss = outg.write_missing_docs(missing)
        matrix = outg.write_escalation_matrix(escalations)
        dbcopy = outg.copy_db(self.settings.db_path)
        pdf = outg.write_pdf_packet(
            f"DataBossX Validation — {final} — {run_id}",
            [("Summary", [f"Mode: {mode}", f"Iterations: {iteration}",
                          f"Spend: ${spend['cumulative']} / ${spend['cap']}",
                          f"Missing sources: {src_summary.get('missing',0)}"]),
             ("Gate Results", [f"{r.gate_name}: {r.status} — {r.reason[:110]}" for r in results]),
             ("Escalations", [f"{e['category']}: {e['subject']} — {str(e['detail'])[:100]}"
                              for e in escalations] or ["None"])])

        # Certified workbook only if certified; else include latest repaired version.
        wb_out = None
        latest = self.rm.latest_version()
        if final == CERTIFY and latest:
            wb_out = outg.exports_dir / f"CERTIFIED_{Path(manifest['file_name']).stem}.xlsx"
            wb_out = _safe_copy(latest, wb_out)
        elif latest and self.db.count("workbook_versions", "run_id = ? AND origin != 'baseline'", (run_id,)) > 0:
            wb_out = outg.exports_dir / f"REPAIRED_{Path(manifest['file_name']).stem}.xlsx"
            wb_out = _safe_copy(latest, wb_out)

        files = [improved, md, js, miss, matrix, dbcopy, pdf, wb_out]
        files = [f for f in files if f]
        bundle = outg.bundle_zip(files)
        for f in files:
            self.audit.report_export(report_type=Path(f).suffix.lstrip("."),
                                     file_path=str(f), version_label=f"iter{iteration}")
        self.audit.report_export(report_type="zip", file_path=str(bundle),
                                 version_label="bundle")
        return files + [bundle]


def _safe_copy(src, dest):
    import shutil
    dest = Path(dest)
    i = 1
    while dest.exists():
        dest = dest.with_name(f"{dest.stem}_{i:02d}{dest.suffix}")
        i += 1
    shutil.copy2(src, dest)
    return dest
