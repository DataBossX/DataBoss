"""Typed, timestamped, append-only logging helpers over :class:`DatabaseManager`.

Every method here is a thin, validated wrapper that stamps ``created_at`` in UTC
ISO-8601 and inserts a single immutable row. Nothing in the system writes audit
history except through this module and the DatabaseManager it wraps.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from db.db_client import DatabaseManager


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _json(value: Any) -> str:
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except Exception:
        return json.dumps({"unserializable": str(value)})


class AuditLogger:
    def __init__(self, db: DatabaseManager):
        self.db = db

    # ------------------------------------------------------------------ runs
    def start_run(self, run_id: str, workbook_path: Optional[str], workbook_sha256: Optional[str],
                  prospect: Optional[str], mode: str, config_snapshot: Dict[str, Any]) -> int:
        return self.db.insert("runs", {
            "run_id": run_id,
            "created_at": utc_now(),
            "workbook_path": workbook_path,
            "workbook_sha256": workbook_sha256,
            "prospect": prospect,
            "mode": mode,
            "config_snapshot": _json(config_snapshot),
            "final_status": None,
        })

    def finalize_run(self, run_id: str, final_status: str) -> int:
        """Append-only 'finalize': record the terminal status as a NEW audit row.

        We never UPDATE the runs row (that is blocked). The authoritative terminal
        status is the latest ``run_finalized`` audit_event for the run.
        """
        return self.event(run_id, "run_finalized", state=final_status,
                          payload={"final_status": final_status})

    def final_status(self, run_id: str) -> Optional[str]:
        rows = self.db.query(
            "SELECT state FROM audit_events WHERE run_id = ? AND event_type = 'run_finalized' "
            "ORDER BY id DESC LIMIT 1", (run_id,))
        return rows[0]["state"] if rows else None

    # ---------------------------------------------------------------- events
    def event(self, run_id: Optional[str], event_type: str, state: Optional[str] = None,
              payload: Optional[Dict[str, Any]] = None) -> int:
        return self.db.insert("audit_events", {
            "run_id": run_id,
            "event_type": event_type,
            "state": state,
            "payload": _json(payload or {}),
            "created_at": utc_now(),
        })

    # ------------------------------------------------------------- versions
    def workbook_version(self, run_id: str, version_index: int, filename: str, path: str,
                         sha256: str, note: Optional[str] = None) -> int:
        return self.db.insert("workbook_versions", {
            "run_id": run_id, "version_index": version_index, "filename": filename,
            "path": path, "sha256": sha256, "note": note, "created_at": utc_now(),
        })

    # ------------------------------------------------------------ validation
    def validation_result(self, run_id: str, iteration: int, result: Dict[str, Any]) -> int:
        return self.db.insert("validation_results", {
            "run_id": run_id,
            "iteration": iteration,
            "gate_name": result["gate_name"],
            "status": result["status"],
            "severity": result["severity"],
            "repairable": 1 if result.get("repairable") else 0,
            "affected_sheet": result.get("affected_sheet"),
            "affected_range": result.get("affected_cell_or_range"),
            "affected_subject": result.get("affected_subject"),
            "evidence": _json(result.get("evidence")),
            "reason": result.get("reason"),
            "recommended_action": result.get("recommended_action"),
            "confidence": float(result.get("confidence", 0.0)),
            "created_at": result.get("created_at") or utc_now(),
        })

    # ----------------------------------------------------------------- spend
    def spend(self, run_id: Optional[str], description: str, amount_usd: str,
              cumulative_usd: str, allowed: bool) -> int:
        return self.db.insert("spend_ledger", {
            "run_id": run_id, "description": description, "amount_usd": amount_usd,
            "cumulative_usd": cumulative_usd, "allowed": 1 if allowed else 0,
            "created_at": utc_now(),
        })

    def api_call(self, run_id: Optional[str], service: str, endpoint: Optional[str], paid: bool,
                 estimated_cost_usd: Optional[str], outcome: str, detail: Optional[str] = None) -> int:
        return self.db.insert("api_calls", {
            "run_id": run_id, "service": service, "endpoint": endpoint,
            "paid": 1 if paid else 0, "estimated_cost_usd": estimated_cost_usd,
            "outcome": outcome, "detail": detail, "created_at": utc_now(),
        })

    # ---------------------------------------------------------------- repair
    def repair(self, run_id: str, iteration: int, record: Dict[str, Any]) -> int:
        record = dict(record)
        record.setdefault("created_at", utc_now())
        record["run_id"] = run_id
        record["iteration"] = iteration
        return self.db.insert("automated_repairs", record)

    # ------------------------------------------------------------ escalation
    def escalate(self, run_id: str, record: Dict[str, Any]) -> int:
        record = dict(record)
        record.setdefault("created_at", utc_now())
        record.setdefault("priority", "HIGH")
        record["run_id"] = run_id
        return self.db.insert("escalations", record)

    # -------------------------------------------------------------- sources
    def source_document(self, record: Dict[str, Any]) -> int:
        record = dict(record)
        record.setdefault("created_at", utc_now())
        return self.db.insert("source_documents", record)

    # -------------------------------------------------------------- exports
    def report_export(self, run_id: str, kind: str, path: str, sha256: str,
                      source_report: Optional[str] = None) -> int:
        return self.db.insert("report_exports", {
            "run_id": run_id, "kind": kind, "path": path, "sha256": sha256,
            "source_report": source_report, "created_at": utc_now(),
        })

    # ------------------------------------------------------------- launcher
    def launcher_event(self, event: str, detail: Optional[str] = None) -> int:
        return self.db.insert("launcher_events", {
            "event": event, "detail": detail, "created_at": utc_now(),
        })
