"""Append-only audit logging helpers built on DatabaseManager."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .db_client import DatabaseManager, utcnow


class AuditLogger:
    def __init__(self, db: DatabaseManager, run_id: Optional[str] = None):
        self.db = db
        self.run_id = run_id

    def bind_run(self, run_id: str) -> "AuditLogger":
        self.run_id = run_id
        return self

    def event(self, event_type: str, component: str, message: str,
              payload: Optional[Dict[str, Any]] = None) -> int:
        return self.db.insert("audit_events", {
            "run_id": self.run_id,
            "event_type": event_type,
            "component": component,
            "message": message,
            "payload_json": json.dumps(payload, default=str) if payload else None,
            "created_at": utcnow(),
        })

    def validation(self, result: Dict[str, Any], iteration: int = 0) -> int:
        row = {
            "run_id": self.run_id,
            "iteration": iteration,
            "gate_name": result.get("gate_name"),
            "status": result.get("status"),
            "severity": result.get("severity"),
            "repairable": 1 if result.get("repairable") else 0,
            "affected_sheet": result.get("affected_sheet"),
            "affected_range": result.get("affected_cell_or_range") or result.get("affected_range"),
            "affected_subject": result.get("affected_subject"),
            "evidence": json.dumps(result.get("evidence"), default=str) if result.get("evidence") is not None else None,
            "reason": result.get("reason"),
            "recommended_action": result.get("recommended_action"),
            "confidence": result.get("confidence"),
            "created_at": utcnow(),
        }
        return self.db.insert("validation_results", row)

    def escalate(self, category: str, subject: str, detail: str,
                 evidence: Optional[str] = None, recommended_action: Optional[str] = None) -> int:
        return self.db.insert("escalations", {
            "run_id": self.run_id,
            "category": category,
            "subject": subject,
            "detail": detail,
            "evidence": evidence,
            "recommended_action": recommended_action,
            "created_at": utcnow(),
        })

    def repair(self, **kw: Any) -> int:
        kw.setdefault("run_id", self.run_id)
        kw.setdefault("created_at", utcnow())
        return self.db.insert("automated_repairs", kw)

    def source_document(self, **kw: Any) -> int:
        kw.setdefault("run_id", self.run_id)
        kw.setdefault("created_at", utcnow())
        return self.db.insert("source_documents", kw)

    def report_export(self, **kw: Any) -> int:
        kw.setdefault("run_id", self.run_id)
        kw.setdefault("created_at", utcnow())
        return self.db.insert("report_exports", kw)

    def launcher(self, event: str, detail: str = "") -> int:
        return self.db.insert("launcher_events", {
            "event": event, "detail": detail, "created_at": utcnow(),
        })
