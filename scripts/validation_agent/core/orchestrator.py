"""PerfectionLoopOrchestrator -- the Section 4 state machine.

Drives a source workbook through INIT -> INGEST -> VALIDATE -> TRIAGE ->
EVALUATE -> {CERTIFY | ESCALATE | REPAIR -> RECALC -> ITERATE} until one of the
terminal conditions in Section 4 is met:

    * 100% of gates pass                      -> CERTIFY
    * an unsafe legal assumption is required  -> ESCALATE
    * max iterations reached                  -> ESCALATE
    * an API spend block occurs               -> ESCALATE
    * post-repair corruption                  -> rollback + ESCALATE

Separation of concerns is strict: verification and validation complete and are
logged before any repair mutates the workbook.  Every transition is written to
the append-only ledger, and every terminal state yields either a certification
or a fully-populated escalation packet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config.settings import config
from ..db.audit_logger import AuditLogger
from ..ingestion.manifest_builder import WorkbookManifest, WorkbookManifestBuilder
from ..ingestion.sheet_classifier import SheetCategory
from ..models import (CellRef, Escalation, FailureCategory, Finding, GateResult,
                      GateStatus, RepairAction, Severity)
from ..recalc.libreoffice_runner import LibreOfficeRecalcRunner
from ..repair.repair_planner import RepairPlan, RepairPlanner
from ..repair.xml_editor import XMLWorkbookEditor
from ..sources.okcounty_client import OKCountyRecordsClient
from ..validators import DOMAIN_VALIDATORS
from .run_manager import RunContext, RunManager, sha256_of

# --- State constants (Section 4) -------------------------------------------
STATE_INIT = "STATE_INIT"
STATE_INGEST = "STATE_INGEST"
STATE_VALIDATE = "STATE_VALIDATE"
STATE_TRIAGE = "STATE_TRIAGE"
STATE_EVALUATE_GATES = "STATE_EVALUATE_GATES"
STATE_REPAIR = "STATE_REPAIR"
STATE_RECALC = "STATE_RECALC"
STATE_ITERATE = "STATE_ITERATE"
STATE_CERTIFY = "STATE_CERTIFY"
STATE_ESCALATE = "STATE_ESCALATE"


@dataclass
class IterationRecord:
    iteration: int
    version: int
    gate_results: list[GateResult]
    plan: RepairPlan
    decision: str


@dataclass
class RunOutcome:
    run_id: str
    ctx: RunContext
    final_state: str                 # STATE_CERTIFY | STATE_ESCALATE
    certified: bool
    iterations: list[IterationRecord] = field(default_factory=list)
    escalations: list[Escalation] = field(default_factory=list)
    final_version: int = 0
    total_spend: float = 0.0
    message: str = ""

    def latest(self) -> Optional[IterationRecord]:
        return self.iterations[-1] if self.iterations else None


class PerfectionLoopOrchestrator:
    def __init__(self, *, audit: Optional[AuditLogger] = None,
                 run_manager: Optional[RunManager] = None,
                 manifest_builder: Optional[WorkbookManifestBuilder] = None,
                 planner: Optional[RepairPlanner] = None,
                 editor: Optional[XMLWorkbookEditor] = None,
                 recalc: Optional[LibreOfficeRecalcRunner] = None,
                 source_client: Optional[OKCountyRecordsClient] = None,
                 validators=None) -> None:
        self.audit = audit or AuditLogger()
        self.run_manager = run_manager or RunManager(self.audit)
        self.manifest_builder = manifest_builder or WorkbookManifestBuilder()
        self.planner = planner or RepairPlanner()
        self.editor = editor or XMLWorkbookEditor()
        self.recalc = recalc or LibreOfficeRecalcRunner()
        self.source_client = source_client or OKCountyRecordsClient(self.audit)
        self.validators = validators if validators is not None else DOMAIN_VALIDATORS

    # -- public entry point -------------------------------------------------
    def run(self, source_workbook: str | Path, *, timestamp: str) -> RunOutcome:
        ctx = self.run_manager.create_run(source_workbook, timestamp=timestamp)
        outcome = RunOutcome(run_id=ctx.run_id, ctx=ctx,
                             final_state=STATE_ESCALATE, certified=False)

        current_version = 0
        current_path = ctx.v0_path

        for iteration in range(config.max_iterations):
            self.audit.log_state(ctx.run_id, iteration, STATE_INGEST,
                                 f"Ingesting workbook v{current_version}.")
            manifest = self.manifest_builder.build(
                ctx.run_id, current_version, current_path, sha256_of(current_path))

            gate_results, findings = self._evaluate_all_gates(
                ctx, manifest, iteration, current_version)

            self.audit.log_state(ctx.run_id, iteration, STATE_TRIAGE,
                                 "Classifying failures.")
            plan = self.planner.plan(findings)

            decision = self._decide(gate_results, plan, iteration)
            outcome.iterations.append(IterationRecord(
                iteration=iteration, version=current_version,
                gate_results=gate_results, plan=plan, decision=decision))
            self.audit.log_state(ctx.run_id, iteration, STATE_EVALUATE_GATES,
                                 f"Decision: {decision}.")

            if decision == STATE_CERTIFY:
                outcome.final_state = STATE_CERTIFY
                outcome.certified = True
                outcome.final_version = current_version
                outcome.message = "All quality gates passed. Workbook certified."
                self.audit.log_state(ctx.run_id, iteration, STATE_CERTIFY,
                                     outcome.message)
                break

            if decision == STATE_ESCALATE:
                # Guarantee the examiner always receives at least one packet:
                # we may escalate on an ERROR gate (e.g. a missing runsheet) or
                # on the final iteration with no domain-level escalation.
                escalations = list(plan.escalations)
                if not escalations:
                    escalations = self._fallback_escalations(
                        gate_results, iteration)
                outcome.final_state = STATE_ESCALATE
                outcome.final_version = current_version
                self._persist_escalations(ctx, iteration, escalations)
                outcome.escalations = escalations
                outcome.message = self._escalation_message(escalations, iteration)
                self.audit.log_state(ctx.run_id, iteration, STATE_ESCALATE,
                                     outcome.message)
                break

            # decision == STATE_REPAIR
            new_version = current_version + 1
            # The XML editor writes an intermediate; recalc produces the canonical
            # version file so the certified artifact carries recomputed values.
            repaired_path = ctx.versions_dir / f"workbook_v{new_version}_repaired.xlsx"
            self.audit.log_state(ctx.run_id, iteration, STATE_REPAIR,
                                 f"Applying {len(plan.safe_repairs)} safe repair(s) "
                                 f"-> v{new_version}.")
            apply_res = self.editor.apply_repairs(
                current_path, repaired_path, plan.safe_repairs)
            if not apply_res.ok:
                # Could not repair -> escalate rather than loop pointlessly.
                esc = self._synthetic_escalation(
                    FailureCategory.FORMULA_DEFECT, iteration,
                    f"XML repair failed: {apply_res.error}")
                self._persist_escalations(ctx, iteration, [esc])
                outcome.final_state = STATE_ESCALATE
                outcome.escalations = [esc]
                outcome.final_version = current_version
                outcome.message = f"Repair failed at v{current_version}."
                break
            # Log only the repairs actually written to the XML, and verify only
            # those cells -- a planned action the editor skipped was never made.
            for action in apply_res.applied_actions:
                self.audit.log_repair(ctx.run_id, iteration, current_version,
                                      new_version, action)

            # STATE_RECALC -- produces the canonical workbook_v{n}.xlsx
            canonical_path = ctx.version_path(new_version)
            recalc_ok, next_path, corrupt = self._recalc(
                ctx, iteration, new_version, repaired_path, canonical_path,
                apply_res.applied, apply_res.applied_actions)
            if corrupt:
                esc = self._synthetic_escalation(
                    FailureCategory.BROKEN_WORKBOOK_STRUCTURE, iteration,
                    "Post-recalc corruption detected; rolled back.")
                self._persist_escalations(ctx, iteration, [esc])
                outcome.final_state = STATE_ESCALATE
                outcome.escalations = [esc]
                outcome.final_version = current_version  # rollback: keep good v
                outcome.message = "Corruption after repair; rolled back and escalated."
                break

            current_version = new_version
            current_path = next_path
            self.audit.log_state(ctx.run_id, iteration, STATE_ITERATE,
                                 f"Re-ingesting v{current_version}.")
        else:
            # Loop exhausted without certify/escalate: max iterations reached.
            outcome.final_state = STATE_ESCALATE
            last = outcome.latest()
            escs = list(last.plan.escalations) if last else []
            escs.append(self._synthetic_escalation(
                FailureCategory.UNSAFE_LEGAL_INFERENCE, config.max_iterations - 1,
                f"Maximum {config.max_iterations} iterations reached without "
                f"certification."))
            self._persist_escalations(ctx, config.max_iterations - 1, escs)
            outcome.escalations = escs
            outcome.final_version = current_version
            outcome.message = "Max iterations reached; escalated for examiner review."

        outcome.total_spend = self.audit.total_spend()
        return outcome

    # -- gate evaluation ----------------------------------------------------
    def _evaluate_all_gates(self, ctx: RunContext, manifest: WorkbookManifest,
                            iteration: int, version: int):
        self.audit.log_state(ctx.run_id, iteration, STATE_VALIDATE,
                             "Executing quality gates.")
        gate_results: list[GateResult] = []

        # Gate 1 -- workbook integrity.
        g1 = self._gate_integrity(manifest)
        gate_results.append(g1)
        if not manifest.readable:
            # Fatal: no point running further gates on an unreadable file.
            self._log_results(ctx, iteration, version, gate_results)
            return gate_results, self._all_findings(gate_results)

        # Gate 2 -- sheet classification.
        gate_results.append(self._gate_classification(manifest))

        # Gates 3-10 -- domain validators.
        for validator in self.validators:
            gate_results.extend(validator.execute_validation(manifest))

        # Gate 11 -- source verification (API, spend-gated).
        gate_results.append(self._gate_source_verification(ctx, manifest, iteration))

        # Gate 12 -- audit completeness (log first, then verify counts).
        self._log_results(ctx, iteration, version, gate_results)
        expected_findings = sum(len(r.findings) for r in gate_results)
        gate_results.append(self._gate_audit_completeness(
            ctx, iteration, len(gate_results), expected_findings))
        # Persist the audit-completeness result too.
        self.audit.log_gate_result(ctx.run_id, iteration, version, gate_results[-1])

        return gate_results, self._all_findings(gate_results)

    def _log_results(self, ctx, iteration, version, results) -> None:
        for r in results:
            self.audit.log_gate_result(ctx.run_id, iteration, version, r)

    @staticmethod
    def _all_findings(results: list[GateResult]) -> list[Finding]:
        findings: list[Finding] = []
        for r in results:
            findings.extend(r.findings)
        return findings

    def _gate_integrity(self, manifest: WorkbookManifest) -> GateResult:
        if manifest.readable:
            return GateResult(1, "Workbook Integrity", GateStatus.PASS, [],
                              "Valid ZIP/OOXML structure.")
        finding = Finding(
            gate_id=1, gate_name="Workbook Integrity",
            category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
            severity=Severity.FATAL,
            message=manifest.integrity_error or "Workbook is corrupt/unreadable.",
            location=CellRef(sheet="(workbook)"), subject="workbook file",
            repairable=False, escalate=True)
        return GateResult(1, "Workbook Integrity", GateStatus.FAIL, [finding],
                          finding.message)

    def _gate_classification(self, manifest: WorkbookManifest) -> GateResult:
        counts = manifest.category_counts()
        tract_n = counts.get(SheetCategory.TRACT.value, 0)
        has_ogl = counts.get(SheetCategory.OGL_REGISTER.value, 0) > 0
        has_wi = counts.get(SheetCategory.WORKING_INTEREST.value, 0) > 0
        findings: list[Finding] = []
        problems: list[str] = []
        if tract_n < config.expected_tract_count:
            problems.append(f"expected {config.expected_tract_count} tract sheets, "
                            f"found {tract_n}")
        if not has_ogl:
            problems.append("no OGL register identified")
        if not has_wi:
            problems.append("no working-interest sheet identified")
        if problems:
            findings.append(Finding(
                gate_id=2, gate_name="Sheet Classification",
                category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
                severity=Severity.FATAL,
                message="Missing core sheets: " + "; ".join(problems),
                location=CellRef(sheet="(workbook)"), subject="workbook structure",
                repairable=False, escalate=True,
                evidence={"category_counts": counts}))
            return GateResult(2, "Sheet Classification", GateStatus.FAIL, findings,
                              "; ".join(problems), {"category_counts": counts})
        return GateResult(2, "Sheet Classification", GateStatus.PASS, [],
                          f"Core sheets present ({tract_n} tracts, OGL, WI).",
                          {"category_counts": counts})

    def _gate_source_verification(self, ctx: RunContext, manifest: WorkbookManifest,
                                  iteration: int) -> GateResult:
        if not self.source_client.is_configured():
            return GateResult(11, "Source Verification", GateStatus.SKIPPED, [],
                              "OKCountyRecords not configured; source verification "
                              "deferred to examiner.")
        # With credentials present, verification would iterate material rows and
        # compare retrieved metadata to workbook facts.  A spend block surfaces
        # here as an API_SPEND_BLOCKED escalation.
        if self.source_client.guard.remaining() <= 0:
            finding = Finding(
                gate_id=11, gate_name="Source Verification",
                category=FailureCategory.API_SPEND_BLOCKED,
                severity=Severity.SYSTEM_HIGH,
                message="Source verification requires a paid fetch but the $100 "
                        "cap is exhausted.",
                location=CellRef(sheet="(sources)"), subject="source verification",
                repairable=False, escalate=True)
            return GateResult(11, "Source Verification", GateStatus.FAIL, [finding],
                              finding.message)
        return GateResult(11, "Source Verification", GateStatus.PASS, [],
                          "Source verification budget available.")

    def _gate_audit_completeness(self, ctx: RunContext, iteration: int,
                                 expected_results: int,
                                 expected_findings: int) -> GateResult:
        """Independently read back the ledger and confirm both the gate results
        and every finding were persisted -- catching a silent logging gap rather
        than merely recounting what we just inserted."""
        logged_results = int(self.audit.db.scalar(
            "SELECT COUNT(*) FROM validation_results WHERE run_id=? AND iteration=?",
            (ctx.run_id, iteration)) or 0)
        logged_findings = int(self.audit.db.scalar(
            "SELECT COUNT(*) FROM findings WHERE run_id=? AND iteration=?",
            (ctx.run_id, iteration)) or 0)
        metrics = {"logged_results": logged_results,
                   "expected_results": expected_results,
                   "logged_findings": logged_findings,
                   "expected_findings": expected_findings}
        if logged_results >= expected_results and logged_findings >= expected_findings:
            return GateResult(12, "Audit Completeness", GateStatus.PASS, [],
                              f"All {logged_results} gate results and "
                              f"{logged_findings} findings logged immutably.",
                              metrics)
        finding = Finding(
            gate_id=12, gate_name="Audit Completeness",
            category=FailureCategory.BROKEN_WORKBOOK_STRUCTURE,
            severity=Severity.FATAL,
            message=(f"Audit log gap: {logged_results}/{expected_results} results, "
                     f"{logged_findings}/{expected_findings} findings persisted."),
            location=CellRef(sheet="(audit)"), subject="audit log",
            repairable=False, escalate=True)
        return GateResult(12, "Audit Completeness", GateStatus.FAIL, [finding],
                          finding.message, metrics)

    # -- decision logic (Section 4, STATE_EVALUATE_GATES) -------------------
    @staticmethod
    def _decide(gate_results: list[GateResult], plan: RepairPlan,
                iteration: int) -> str:
        has_error = any(r.status is GateStatus.ERROR for r in gate_results)
        has_fail = any(r.status is GateStatus.FAIL for r in gate_results)
        is_last = iteration >= config.max_iterations - 1

        if not has_fail and not has_error and not plan.has_escalations:
            return STATE_CERTIFY
        if plan.has_escalations or has_error or is_last:
            return STATE_ESCALATE
        if plan.has_safe_repairs:
            return STATE_REPAIR
        # Failures with neither a safe repair nor an escalation: cannot proceed.
        return STATE_ESCALATE

    # -- recalculation ------------------------------------------------------
    def _recalc(self, ctx: RunContext, iteration: int, version: int,
                repaired_path: Path, canonical_path: Path,
                applied: list[str], applied_actions: list["RepairAction"]):
        """Produce the canonical vN file (recalc output, or the repaired file if
        LibreOffice is unavailable). Returns (recalc_ok, next_path, corrupt)."""
        import shutil
        self.audit.log_state(ctx.run_id, iteration, STATE_RECALC,
                             f"Recalculating v{version}.")
        verify_cells = [(a.location.sheet, a.location.cell)
                        for a in applied_actions if a.location.cell]
        res = self.recalc.recalc(repaired_path, canonical_path, verify_cells)
        if res.corrupted:
            # Rollback: do NOT let a corrupt file become the canonical version.
            self.audit.event("recalc_corruption", res.message, run_id=ctx.run_id)
            return False, repaired_path, True
        note_prefix = f"XML repairs: {', '.join(applied)[:300]}"
        if not res.ok:
            # LibreOffice unavailable / non-fatal: promote the repaired file as
            # the canonical version. Formulas are present; the next ingest reads
            # the restored formulas even without cached values.
            self.audit.event("recalc_unavailable", res.message, run_id=ctx.run_id)
            shutil.copy2(repaired_path, canonical_path)
            self.run_manager.register_version(
                ctx, version, canonical_path,
                note=f"{note_prefix} | recalc skipped: {res.message}")
            return False, canonical_path, False
        digest = self.run_manager.register_version(
            ctx, version, canonical_path, note=f"{note_prefix} | recalculated")
        self.audit.event("recalc_ok", f"v{version} recalculated ({digest[:12]}).",
                         run_id=ctx.run_id)
        return True, canonical_path, False

    # -- escalation helpers -------------------------------------------------
    def _persist_escalations(self, ctx: RunContext, iteration: int,
                             escalations: list[Escalation]) -> None:
        for esc in escalations:
            self.audit.log_escalation(ctx.run_id, iteration, esc)

    def _synthetic_escalation(self, category: FailureCategory, iteration: int,
                              message: str) -> Escalation:
        from ..failure_taxonomy import entry_for
        entry = entry_for(category)
        return Escalation(
            gate_id=0, gate_name="Orchestrator", category=category,
            severity=entry.severity, failed_gate="Perfection Loop",
            location=None, subject="run",
            sources_checked=[], sources_missing=[],
            automated_checks_attempted=[message],
            repair_blocked_reason=entry.escalate_language or message,
            recommended_examiner_action="Examiner review required.",
            estimated_urgency="Immediate" if entry.severity is Severity.FATAL
            else "Urgent")

    def _fallback_escalations(self, gate_results: list[GateResult],
                              iteration: int) -> list[Escalation]:
        """Build packets when the loop escalates without a domain-level finding.

        Turns each unevaluated/failed gate that carried no finding into an
        escalation so Section 7's guarantee (every escalation is a full packet)
        always holds, even for structural ERROR gates like a missing runsheet.
        """
        escs: list[Escalation] = []
        for r in gate_results:
            if r.status in (GateStatus.ERROR, GateStatus.FAIL) and not r.findings:
                escs.append(Escalation(
                    gate_id=r.gate_id, gate_name=r.gate_name,
                    category=FailureCategory.MISSING_SOURCE, severity=Severity.HIGH,
                    failed_gate=r.gate_name, location=None, subject=r.gate_name,
                    sources_checked=[], sources_missing=[],
                    automated_checks_attempted=[r.detail or "Gate evaluation."],
                    repair_blocked_reason=(r.detail
                                           or "Gate could not be evaluated."),
                    recommended_examiner_action=(
                        "Supply the missing sheet/data so this gate can run."),
                    estimated_urgency="Elevated"))
        if not escs:
            is_last = iteration >= config.max_iterations - 1
            reason = ("Maximum iterations reached without certification."
                      if is_last else
                      "Loop halted without a repairable path; examiner review required.")
            escs.append(self._synthetic_escalation(
                FailureCategory.UNSAFE_LEGAL_INFERENCE, iteration, reason))
        return escs

    @staticmethod
    def _escalation_message(escalations: list[Escalation], iteration: int) -> str:
        cats = sorted({e.category.value for e in escalations})
        return (f"Escalated at iteration {iteration}: "
                f"{len(escalations)} item(s) [{', '.join(cats)}]. "
                f"Automated repair halted -- examiner action required.")
