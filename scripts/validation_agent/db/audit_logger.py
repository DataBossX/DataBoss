"""Typed convenience wrappers around the append-only DatabaseManager.

Every method is a single INSERT. Nothing here can mutate prior state.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .db_client import DatabaseManager


def _json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str, sort_keys=True)


class AuditLogger:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    # -- runs ---------------------------------------------------------- #
    def log_run(
        self,
        run_id: str,
        run_folder: str,
        status: str,
        state: Optional[str] = None,
        iteration: int = 0,
        workbook_source_path: Optional[str] = None,
        workbook_source_sha256: Optional[str] = None,
    ) -> int:
        return self.db.insert(
            "runs",
            {
                "run_id": run_id,
                "run_folder": run_folder,
                "workbook_source_path": workbook_source_path,
                "workbook_source_sha256": workbook_source_sha256,
                "status": status,
                "state": state,
                "iteration": iteration,
            },
        )

    # -- audit events -------------------------------------------------- #
    def log_event(
        self,
        event_type: str,
        run_id: Optional[str] = None,
        subject: Optional[str] = None,
        detail: Optional[str] = None,
        payload: Any = None,
    ) -> int:
        return self.db.insert(
            "audit_events",
            {
                "run_id": run_id,
                "event_type": event_type,
                "subject": subject,
                "detail": detail,
                "payload_json": _json(payload),
            },
        )

    # -- workbook versions --------------------------------------------- #
    def log_workbook_version(
        self,
        run_id: str,
        version_index: int,
        version_label: str,
        file_path: str,
        sha256: str,
        origin: str,
        parent_version_index: Optional[int] = None,
    ) -> int:
        return self.db.insert(
            "workbook_versions",
            {
                "run_id": run_id,
                "version_index": version_index,
                "version_label": version_label,
                "file_path": file_path,
                "sha256": sha256,
                "origin": origin,
                "parent_version_index": parent_version_index,
            },
        )

    # -- validation results -------------------------------------------- #
    def log_validation_result(self, run_id: str, iteration: int, result: Any) -> int:
        """`result` is a validators.base_validator.ValidationResult."""
        data = result.as_row() if hasattr(result, "as_row") else dict(result)
        data["run_id"] = run_id
        data["iteration"] = iteration
        return self.db.insert("validation_results", data)

    # -- spend --------------------------------------------------------- #
    def log_spend(
        self,
        decision: str,
        proposed_amount_usd: Decimal,
        amount_usd: Decimal,
        reason: str,
        description: str,
        run_id: Optional[str] = None,
    ) -> int:
        return self.db.insert(
            "spend_ledger",
            {
                "run_id": run_id,
                "decision": decision,
                "reason": reason,
                "proposed_amount_usd": str(proposed_amount_usd),
                "amount_usd": str(amount_usd),
                "description": description,
            },
        )

    # -- api calls ----------------------------------------------------- #
    def log_api_call(
        self,
        provider: str,
        mode: str,
        outcome: str,
        endpoint: Optional[str] = None,
        cost_usd: Decimal = Decimal("0.00"),
        detail: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> int:
        return self.db.insert(
            "api_calls",
            {
                "run_id": run_id,
                "provider": provider,
                "endpoint": endpoint,
                "mode": mode,
                "outcome": outcome,
                "cost_usd": str(cost_usd),
                "detail": detail,
            },
        )

    # -- repairs ------------------------------------------------------- #
    def log_repair(self, run_id: str, iteration: int, **fields: Any) -> int:
        fields["run_id"] = run_id
        fields["iteration"] = iteration
        return self.db.insert("automated_repairs", fields)

    # -- escalations --------------------------------------------------- #
    def log_escalation(self, run_id: str, escalation: Any) -> int:
        data = escalation.as_row() if hasattr(escalation, "as_row") else dict(escalation)
        data["run_id"] = run_id
        return self.db.insert("escalations", data)

    # -- source documents ---------------------------------------------- #
    def log_source_document(
        self,
        status: str,
        reference_key: Optional[str] = None,
        reference_type: Optional[str] = None,
        file_path: Optional[str] = None,
        sha256: Optional[str] = None,
        source: Optional[str] = None,
        detail: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> int:
        return self.db.insert(
            "source_documents",
            {
                "run_id": run_id,
                "reference_key": reference_key,
                "reference_type": reference_type,
                "status": status,
                "file_path": file_path,
                "sha256": sha256,
                "source": source,
                "detail": detail,
            },
        )

    # -- report exports ------------------------------------------------ #
    def log_report_export(
        self,
        export_type: str,
        file_path: str,
        sha256: str,
        detail: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> int:
        return self.db.insert(
            "report_exports",
            {
                "run_id": run_id,
                "export_type": export_type,
                "file_path": file_path,
                "sha256": sha256,
                "detail": detail,
            },
        )

    # -- launcher events ----------------------------------------------- #
    def log_launcher_event(self, event_type: str, detail: Optional[str] = None) -> int:
        return self.db.insert(
            "launcher_events", {"event_type": event_type, "detail": detail}
        )

    # -- read helpers -------------------------------------------------- #
    def cumulative_spend(self, run_id: Optional[str] = None) -> Decimal:
        if run_id:
            val = self.db.scalar(
                "SELECT COALESCE(SUM(CAST(amount_usd AS REAL)), 0) "
                "FROM spend_ledger WHERE run_id = ?",
                (run_id,),
            )
        else:
            val = self.db.scalar(
                "SELECT COALESCE(SUM(CAST(amount_usd AS REAL)), 0) FROM spend_ledger"
            )
        return Decimal(str(val or 0))

    def open_escalations(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if run_id:
            return self.db.query(
                "SELECT * FROM escalations WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            )
        return self.db.query("SELECT * FROM open_escalations")
