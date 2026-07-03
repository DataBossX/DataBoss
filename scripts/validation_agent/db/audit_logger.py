"""AuditLogger -- the single write surface for the append-only memory layer.

Every module logs through here so that provenance, spend, repairs, and
escalations are recorded consistently and immutably.  There is deliberately no
method that updates or deletes: correcting a fact means appending a new fact.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ..models import Escalation, Finding, GateResult, RepairAction
from .db_client import DatabaseManager, db as _default_db


class AuditLogger:
    def __init__(self, database: Optional[DatabaseManager] = None) -> None:
        self.db = database or _default_db

    # -- runs & state machine ----------------------------------------------
    def open_run(self, run_id: str, source_path: str, source_sha256: str,
                 run_folder: str) -> None:
        self.db.insert("runs", {
            "id": run_id,
            "source_path": source_path,
            "source_sha256": source_sha256,
            "run_folder": run_folder,
        })
        self.log_state(run_id, iteration=0, state="STATE_INIT",
                       detail="Run opened; source baseline secured.")

    def log_state(self, run_id: str, iteration: int, state: str,
                  detail: str = "") -> None:
        self.db.insert("run_events", {
            "run_id": run_id,
            "iteration": iteration,
            "state": state,
            "detail": detail,
        })

    def log_version(self, run_id: str, version: int, file_path: str,
                    sha256: str, note: str = "") -> None:
        self.db.insert("workbook_versions", {
            "run_id": run_id,
            "version": version,
            "file_path": file_path,
            "sha256": sha256,
            "note": note,
        })

    # -- validation ---------------------------------------------------------
    def log_gate_result(self, run_id: str, iteration: int, version: int,
                        result: GateResult) -> None:
        self.db.insert("validation_results", {
            "run_id": run_id,
            "iteration": iteration,
            "version": version,
            "gate_id": result.gate_id,
            "gate_name": result.gate_name,
            "status": result.status.value,
            "detail": result.detail,
            "metrics": json.dumps(result.metrics, default=str),
        })
        for finding in result.findings:
            self.log_finding(run_id, iteration, finding)

    def log_finding(self, run_id: str, iteration: int, finding: Finding) -> None:
        self.db.insert("findings", {
            "run_id": run_id,
            "iteration": iteration,
            "gate_id": finding.gate_id,
            "gate_name": finding.gate_name,
            "category": finding.category.value,
            "severity": finding.severity.value,
            "location": str(finding.location) if finding.location else None,
            "subject": finding.subject,
            "message": finding.message,
            "repairable": 1 if finding.repairable else 0,
            "escalate": 1 if finding.escalate else 0,
            "payload": json.dumps(
                {"evidence": finding.evidence, "repair_hint": finding.repair_hint},
                default=str),
        })

    # -- repair -------------------------------------------------------------
    def log_repair(self, run_id: str, iteration: int, from_version: int,
                   to_version: int, action: RepairAction) -> None:
        self.db.insert("repairs", {
            "run_id": run_id,
            "iteration": iteration,
            "from_version": from_version,
            "to_version": to_version,
            "gate_id": action.finding_gate_id,
            "location": str(action.location),
            "action_type": action.action_type,
            "old_value": action.old_value,
            "new_formula": action.new_formula,
            "rationale": action.rationale,
        })

    # -- API + spend --------------------------------------------------------
    def log_api_call(self, run_id: Optional[str], endpoint: str,
                     request_meta: dict[str, Any], outcome: str,
                     http_status: Optional[int], estimated_cost: float,
                     actual_cost: float) -> None:
        self.db.insert("api_calls", {
            "run_id": run_id,
            "endpoint": endpoint,
            "request_meta": json.dumps(request_meta, default=str),
            "outcome": outcome,
            "http_status": http_status,
            "estimated_cost": estimated_cost,
            "actual_cost": actual_cost,
        })

    def log_spend(self, run_id: Optional[str], amount: float,
                  description: str) -> None:
        self.db.insert("spend_ledger", {
            "run_id": run_id,
            "amount": amount,
            "description": description,
        })

    def total_spend(self) -> float:
        val = self.db.scalar("SELECT COALESCE(SUM(amount),0) AS s FROM spend_ledger")
        return float(val or 0.0)

    # -- escalations --------------------------------------------------------
    def log_escalation(self, run_id: str, iteration: int,
                       escalation: Escalation) -> None:
        self.db.insert("escalations", {
            "run_id": run_id,
            "iteration": iteration,
            "gate_id": escalation.gate_id,
            "gate_name": escalation.gate_name,
            "category": escalation.category.value,
            "severity": escalation.severity.value,
            "payload": json.dumps(escalation.to_dict(), default=str),
        })

    # -- generic ------------------------------------------------------------
    def event(self, event_type: str, description: str,
              run_id: Optional[str] = None, data: Any = None) -> None:
        self.db.insert("audit_log", {
            "run_id": run_id,
            "event_type": event_type,
            "description": description,
            "data": json.dumps(data, default=str) if data is not None else None,
        })

