"""Orchestrator state machine.

STATE_INIT -> STATE_INGEST -> STATE_VALIDATE -> STATE_TRIAGE ->
STATE_EVALUATE_GATES -> (STATE_REPAIR -> STATE_RECALC -> STATE_ITERATE) ->
STATE_CERTIFY | STATE_ESCALATE

Guarantees:
  * At most ``settings.max_iterations`` (<=5) validate/repair cycles.
  * Verification precedes repair; only SAFE formula/math repairs run.
  * Any legal/source/HBP problem, spend block or LibreOffice failure escalates.
  * A terminal output bundle is generated whether CERTIFY, ESCALATE or
    MAX_ITERATIONS.
  * Every transition is logged to the append-only DB.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import Settings
from db.audit_logger import AuditLogger
from core.run_manager import RunManager
from ingestion.manifest_builder import build_manifest, write_manifest
from ingestion.domain_extractor import extract_domain
from sources.okcounty_client import OKCountyClient
from sources.source_finder import SourceFinder
from validators.val_formula import WorkbookIntegrityGate, FormulaIntegrityGate
from validators.val_sources import SheetClassificationGate, SourceVerificationGate
from validators.val_interest import InterestConservationGate
from validators.val_acreage import AcreageFootingGate
from validators.val_chain import ChainContinuityGate
from validators.val_instrument import InstrumentSourceAuditGate
from validators.val_ogl_wi import OGLRegisterAuditGate, WIDepthConsistencyGate, WellHBPSupportGate
from validators.val_audit import AuditCompletenessGate, FinalCertificationGate
from repair.failure_classifier import classify
from repair.repair_planner import plan_repairs
from repair.xml_editor import apply_formula_edits
from recalc.libreoffice_runner import recalculate
from reports.output_generator import OutputGenerator
from sources.spend_guard import SpendGuard

# AuditCompletenessGate is a finalize-time check (it needs the run's live audit
# counts) so it is NOT in the per-iteration order — it runs once at certify time.
GATE_ORDER = [
    WorkbookIntegrityGate, SheetClassificationGate, InterestConservationGate,
    AcreageFootingGate, ChainContinuityGate, InstrumentSourceAuditGate,
    OGLRegisterAuditGate, WIDepthConsistencyGate, WellHBPSupportGate,
    FormulaIntegrityGate, SourceVerificationGate,
]


class Orchestrator:
    def __init__(self, settings: Settings, db, audit: AuditLogger):
        self.settings = settings
        self.db = db
        self.audit = audit

    def _transition(self, run_id: str, state: str, detail: Optional[Dict[str, Any]] = None):
        self.audit.event(run_id, "state_transition", state=state, payload=detail or {})

    def run(self, workbook_path: Path, prospect: str = "",
            known_formulas: Optional[Dict[str, str]] = None,
            domain_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        workbook_path = Path(workbook_path)
        rm = RunManager(self.settings.outputs_dir, self.audit)
        run_id = rm.run_id
        guard = SpendGuard(self.audit, self.settings.api_cap_usd, run_id)

        self.audit.start_run(
            run_id, str(workbook_path), None, prospect or None,
            "live" if self.settings.live_retrieval_allowed() else "dry_run",
            self.settings.safe_dump())
        self._transition(run_id, "STATE_INIT")

        # ---- INGEST ----
        self._transition(run_id, "STATE_INGEST")
        try:
            v0 = rm.ingest_baseline(workbook_path)
        except Exception as e:
            self.audit.escalate(run_id, {"failure_class": "Broken Workbook Structure / XML Corruption",
                                         "subject": str(workbook_path), "reason": str(e),
                                         "recommended_action": "Provide a valid workbook.", "priority": "HIGH"})
            return self._finalize(rm, run_id, "ESCALATE", [], [], guard, None)

        manifest = build_manifest(v0)
        write_manifest(manifest, rm.path("audit", "manifest.json"))
        self.audit.event(run_id, "manifest_built", payload={"sha": manifest["manifest_sha256"]})

        latest_workbook = v0
        all_results: List[Dict[str, Any]] = []
        domain_context = dict(domain_context or {})

        # Auto-extract domain facts + recording references from the workbook when
        # the caller did not supply them. The extractor never fabricates owner
        # interest; unparseable areas stay None so the gates escalate.
        extracted = extract_domain(v0)
        self.audit.event(run_id, "domain_extracted",
                         payload={"reference_count": extracted["reference_count"]})
        for key in ("tracts", "well", "instruments"):
            domain_context.setdefault(key, extracted.get(key))

        # Build and resolve the missing-source queue (dry-run safe; escalates).
        guard_client = OKCountyClient(self.settings, self.audit, guard, run_id)
        finder = SourceFinder(self.settings, self.audit, guard_client, run_id,
                              search_dirs=[rm.run_dir / "sources"])
        source_docs = finder.build_and_resolve_queue(extracted["references"])
        domain_context.setdefault("source_documents", source_docs)

        for iteration in range(1, self.settings.max_iterations + 1):
            # ---- VALIDATE ----
            self._transition(run_id, "STATE_VALIDATE", {"iteration": iteration})
            context = {
                "run_id": run_id, "prospect": prospect,
                "workbook_path": str(latest_workbook), "manifest": manifest,
                "expected_acres": str(self.settings.expected_acres),
                "source_documents": domain_context.get("source_documents", []),
                "instruments": domain_context.get("instruments"),
                "tracts": domain_context.get("tracts"),
                "ogls": domain_context.get("ogls"),
                "working_interests": domain_context.get("working_interests"),
                "well": domain_context.get("well"),
            }
            results: List[Dict[str, Any]] = []
            for gate_cls in GATE_ORDER:
                try:
                    results.extend(gate_cls().run(context))
                except Exception as e:  # a gate error is logged, not fatal
                    from validators.base_validator import make_result, ERROR, SEV_HIGH
                    results.append(make_result(gate_cls.gate_name, ERROR, severity=SEV_HIGH,
                                               reason=f"gate raised: {e}", confidence=0.0))
            for r in results:
                self.audit.validation_result(run_id, iteration, r)
            all_results = results

            # ---- TRIAGE ----
            self._transition(run_id, "STATE_TRIAGE", {"iteration": iteration})
            repairable = [r for r in results if r["status"] == "FAIL"
                          and classify(r)["route"] == "repair"]
            unsafe = [r for r in results if r["status"] in ("FAIL", "ESCALATE", "ERROR")
                      and classify(r)["route"] == "escalate"]
            for r in unsafe:
                self.audit.escalate(run_id, {
                    "gate_name": r["gate_name"],
                    "failure_class": r.get("failure_class") or "Unsafe Legal Inference",
                    "subject": r.get("affected_subject") or "",
                    "reason": r.get("reason", ""),
                    "needed_document": (r.get("evidence") or {}).get("reference")
                        if isinstance(r.get("evidence"), dict) else None,
                    "recommended_action": r.get("recommended_action", ""),
                    "priority": "HIGH" if r["severity"] in ("HIGH", "FATAL") else "MEDIUM"})

            # ---- EVALUATE GATES ----
            self._transition(run_id, "STATE_EVALUATE_GATES", {"iteration": iteration})
            if not repairable:
                break  # nothing safely fixable; proceed to certify/escalate

            # ---- REPAIR (safe only) ----
            self._transition(run_id, "STATE_REPAIR", {"iteration": iteration})
            plan = plan_repairs(repairable, known_formulas or {})
            if not plan["plans"]:
                # Could not establish intended formulas -> escalate, stop looping.
                for r in plan["escalate"]:
                    self.audit.escalate(run_id, {
                        "gate_name": r["gate_name"], "failure_class": "Formula Defect",
                        "subject": r.get("affected_subject", ""), "reason": r.get("reason", ""),
                        "recommended_action": "Supply intended formula or review manually.",
                        "priority": "MEDIUM"})
                break
            try:
                new_version = rm.next_version_path(latest_workbook.suffix)
                res = apply_formula_edits(latest_workbook, new_version, plan["plans"])
                if not res["verify"]["valid"]:
                    raise RuntimeError(f"repair produced invalid workbook: {res['verify']}")
                digest = rm.register_version(new_version, note=f"iter{iteration} formula repair")
                for e in plan["plans"]:
                    self.audit.repair(run_id, iteration, {
                        "failure_class": e["failure_class"], "target_sheet": e["sheet"],
                        "target_range": e["cell"], "from_version": latest_workbook.name,
                        "to_version": new_version.name, "after_sha256": digest,
                        "action": f"set formula {e['new_formula']}", "evidence": e["evidence"]})
                latest_workbook = new_version
            except Exception as e:
                self.audit.escalate(run_id, {"failure_class": "Broken Workbook Structure / XML Corruption",
                                             "subject": "xml repair", "reason": str(e),
                                             "recommended_action": "Keep prior version; manual repair.",
                                             "priority": "HIGH"})
                break

            # ---- RECALC ----
            self._transition(run_id, "STATE_RECALC", {"iteration": iteration})
            recalc_dest = rm.next_version_path(latest_workbook.suffix)
            rc = recalculate(latest_workbook, recalc_dest, self.settings.libreoffice_path)
            if rc.get("status") == "ok":
                digest = rm.register_version(recalc_dest, note=f"iter{iteration} recalc")
                latest_workbook = recalc_dest
                manifest = build_manifest(latest_workbook)  # refresh view
            else:
                self.audit.event(run_id, "recalc_skipped", payload=rc)
                if rc.get("status") in ("unavailable", "error"):
                    self.audit.escalate(run_id, {"failure_class": "LibreOffice Failure",
                                                 "subject": "recalc", "reason": rc.get("reason", ""),
                                                 "recommended_action": rc.get("recommended_action",
                                                 "Install LibreOffice."), "priority": "MEDIUM"})
            # ---- ITERATE ----
            self._transition(run_id, "STATE_ITERATE", {"iteration": iteration})
        else:
            # loop exhausted without break
            return self._finalize(rm, run_id, "MAX_ITERATIONS", all_results,
                                  domain_context.get("source_documents", []), guard, latest_workbook)

        # ---- CERTIFY / ESCALATE ----
        # Audit completeness runs here with the run's live append-only counts.
        counts = {t: self.db.count(t) for t in
                  ("runs", "workbook_versions", "validation_results", "audit_events")}
        audit_gate = AuditCompletenessGate().run({"audit_counts": counts})[0]
        self.audit.validation_result(run_id, self.settings.max_iterations, audit_gate)
        all_results = all_results + [audit_gate]
        final_gate = FinalCertificationGate().run({"gate_results": all_results})[0]
        self.audit.validation_result(run_id, self.settings.max_iterations, final_gate)
        final_status = "CERTIFY" if final_gate["status"] == "PASS" else "ESCALATE"
        self._transition(run_id, "STATE_CERTIFY" if final_status == "CERTIFY" else "STATE_ESCALATE")
        return self._finalize(rm, run_id, final_status, all_results + [final_gate],
                              domain_context.get("source_documents", []), guard, latest_workbook)

    def _finalize(self, rm: RunManager, run_id: str, final_status: str,
                  results: List[Dict[str, Any]], sources: List[Dict[str, Any]],
                  guard: SpendGuard, latest_workbook: Optional[Path]) -> Dict[str, Any]:
        escalations = [dict(r) for r in self.db.query(
            "SELECT gate_name, failure_class, subject, reason, needed_document, "
            "recommended_action, priority FROM escalations WHERE run_id = ?", (run_id,))]
        # Audit completeness needs live counts.
        counts = {t: self.db.count(t) for t in
                  ("runs", "workbook_versions", "validation_results", "audit_events")}
        context = {
            "run_id": run_id, "final_status": final_status, "gate_results": results,
            "source_documents": sources, "escalations": escalations,
            "audit_counts": counts, "spend_total": str(guard.cumulative()),
            "spend_remaining": str(guard.remaining()),
            "latest_workbook": str(latest_workbook) if latest_workbook else None,
        }
        outputs = OutputGenerator(rm, self.audit, self.db).generate(context)
        self.audit.finalize_run(run_id, final_status)
        context["exports"] = outputs
        return context
