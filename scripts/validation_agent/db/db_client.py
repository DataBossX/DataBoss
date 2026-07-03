"""Append-only SQLite access layer.

Enforcement is layered:
  1. A Python SQLite *authorizer* denies UPDATE/DELETE/DROP/ALTER on protected
     tables at the VDBE level for this connection.
  2. Statement-string screening in ``DatabaseManager.execute`` rejects
     multi-statement SQL and mutating verbs (UPDATE/DELETE/DROP/ALTER/REPLACE,
     ``INSERT OR REPLACE``, UPSERT / ``ON CONFLICT``).
  3. Database *triggers* (see schema.sql) RAISE(ABORT) on UPDATE/DELETE and
     therefore protect even a raw ``sqlite3.connect`` that never installs the
     authorizer.

INSERT and SELECT are the only permitted operations. All writes go through the
typed helper methods on ``DatabaseManager``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Sequence

# Tables protected by append-only semantics.
PROTECTED_TABLES = {
    "runs",
    "workbook_versions",
    "audit_events",
    "validation_results",
    "spend_ledger",
    "api_calls",
    "automated_repairs",
    "escalations",
    "source_documents",
    "report_exports",
    "launcher_events",
}

# SQLite authorizer action codes we care about.
_SQLITE_DENY = 1  # sqlite3.SQLITE_DENY (constant value is 1)

_FORBIDDEN_PATTERNS = [
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\breplace\b",
    r"\btruncate\b",
    r"\bupsert\b",
    r"\bon\s+conflict\b",
    r"insert\s+or\s+replace",
    r"insert\s+or\s+ignore",
]
_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN_PATTERNS), re.IGNORECASE)

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class AppendOnlyViolation(RuntimeError):
    """Raised when a caller attempts a non-append-only operation."""


def _authorizer(action: int, arg1: Any, arg2: Any, dbname: Any, source: Any) -> int:
    """SQLite authorizer callback.

    Denies UPDATE/DELETE/DROP/ALTER against protected tables. Internal
    bookkeeping tables (``sqlite_sequence``) and all other actions are allowed
    so that AUTOINCREMENT INSERTs continue to work.
    """
    # Action codes: 9=SQLITE_DELETE, 11=SQLITE_DROP_TABLE, 23=SQLITE_UPDATE,
    # 26=SQLITE_ALTER_TABLE, 24=SQLITE_TRANSACTION, etc.
    SQLITE_DELETE = 9
    SQLITE_DROP_TABLE = 11
    SQLITE_DROP_TRIGGER = 15
    SQLITE_UPDATE = 23
    SQLITE_ALTER_TABLE = 26

    table = arg1 if isinstance(arg1, str) else ""

    if action in (SQLITE_UPDATE, SQLITE_DELETE):
        if table in PROTECTED_TABLES:
            return _SQLITE_DENY
        return sqlite3.SQLITE_OK
    if action in (SQLITE_DROP_TABLE, SQLITE_DROP_TRIGGER, SQLITE_ALTER_TABLE):
        if table in PROTECTED_TABLES:
            return _SQLITE_DENY
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_OK


class DatabaseManager:
    """The only sanctioned gateway for writing to the audit database."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._initialize_schema()
        # Install the authorizer only AFTER schema creation so CREATE
        # statements are permitted during setup.
        self._conn.set_authorizer(_authorizer)

    # ------------------------------------------------------------------ #
    def _initialize_schema(self) -> None:
        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        self._conn.executescript(schema_sql)
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> "DatabaseManager":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _screen(sql: str, expect: str) -> None:
        stripped = sql.strip().rstrip(";").strip()
        # Reject multi-statement SQL (a ';' anywhere in the interior).
        if ";" in stripped:
            raise AppendOnlyViolation("Multi-statement SQL is not permitted.")
        low = stripped.lower()
        if expect == "insert":
            if not low.startswith("insert into"):
                raise AppendOnlyViolation("Only 'INSERT INTO' writes are allowed.")
            if _FORBIDDEN_RE.search(stripped):
                raise AppendOnlyViolation(
                    "Forbidden clause detected (UPDATE/DELETE/DROP/ALTER/"
                    "REPLACE/UPSERT/ON CONFLICT)."
                )
        elif expect == "select":
            if not (low.startswith("select") or low.startswith("with")):
                raise AppendOnlyViolation("Only SELECT queries are allowed here.")
            if _FORBIDDEN_RE.search(stripped):
                raise AppendOnlyViolation("Forbidden clause detected in query.")

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run a single INSERT statement. Returns the new rowid."""
        self._screen(sql, "insert")
        cur = self._conn.execute(sql, tuple(params))
        self._conn.commit()
        return int(cur.lastrowid)

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        """Run a single SELECT and return all rows."""
        self._screen(sql, "select")
        cur = self._conn.execute(sql, tuple(params))
        return cur.fetchall()

    def insert(self, table: str, **fields: Any) -> int:
        """Parameterized INSERT helper into a protected table."""
        if table not in PROTECTED_TABLES:
            raise AppendOnlyViolation(f"Unknown protected table: {table}")
        cols = list(fields.keys())
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(cols)
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
        values = [
            json.dumps(v) if isinstance(v, (dict, list)) else v
            for v in fields.values()
        ]
        return self.execute(sql, values)

    # ------------------- typed convenience writers -------------------- #
    def insert_run(self, run_id: str, workbook_name: str, workbook_hash: str,
                   run_dir: str, mode: str) -> int:
        return self.insert(
            "runs", run_id=run_id, workbook_name=workbook_name,
            workbook_hash=workbook_hash, run_dir=run_dir, mode=mode,
            status="INIT",
        )

    def record_event(self, run_id: str | None, event_type: str,
                     state: str | None = None, description: str = "",
                     data: Any = None) -> int:
        return self.insert(
            "audit_events", run_id=run_id, event_type=event_type, state=state,
            description=description,
            data_json=json.dumps(data) if data is not None else None,
        )

    def record_terminal_status(self, run_id: str, status: str,
                               final_state: str) -> int:
        """Record run termination as an append-only audit event."""
        return self.record_event(
            run_id, "run_terminal", state=final_state,
            description=f"Run terminated: {status}",
            data={"status": status, "final_state": final_state},
        )

    def record_workbook_version(self, run_id: str, version_label: str,
                                file_name: str, file_path: str, sha256: str,
                                size_bytes: int, origin: str, note: str = "") -> int:
        return self.insert(
            "workbook_versions", run_id=run_id, version_label=version_label,
            file_name=file_name, file_path=file_path, sha256=sha256,
            size_bytes=size_bytes, origin=origin, note=note,
        )

    def record_validation(self, run_id: str, iteration: int, result: dict) -> int:
        return self.insert(
            "validation_results", run_id=run_id, iteration=iteration,
            gate_name=result.get("gate_name"), status=result.get("status"),
            severity=result.get("severity"),
            repairable=1 if result.get("repairable") else 0,
            affected_sheet=result.get("affected_sheet"),
            affected_cell_or_range=result.get("affected_cell_or_range"),
            affected_subject=result.get("affected_subject"),
            evidence=json.dumps(result.get("evidence"))
            if result.get("evidence") is not None else None,
            reason=result.get("reason"),
            recommended_action=result.get("recommended_action"),
            confidence=result.get("confidence"),
        )

    def record_spend(self, run_id: str | None, kind: str, description: str,
                     amount_usd: float, cumulative_usd: float,
                     approved: bool) -> int:
        return self.insert(
            "spend_ledger", run_id=run_id, kind=kind, description=description,
            amount_usd=amount_usd, cumulative_usd=cumulative_usd,
            approved=1 if approved else 0,
        )

    def record_api_call(self, run_id: str | None, provider: str, endpoint: str,
                        request_meta: Any, outcome: str, cost_usd: float) -> int:
        return self.insert(
            "api_calls", run_id=run_id, provider=provider, endpoint=endpoint,
            request_meta=json.dumps(request_meta) if request_meta else None,
            outcome=outcome, cost_usd=cost_usd,
        )

    def record_repair(self, run_id: str, iteration: int, **fields: Any) -> int:
        return self.insert("automated_repairs", run_id=run_id,
                           iteration=iteration, **fields)

    def record_escalation(self, run_id: str, category: str, severity: str,
                          subject: str, gate_name: str, reason: str,
                          evidence: Any = None,
                          recommended_action: str = "") -> int:
        return self.insert(
            "escalations", run_id=run_id, category=category, severity=severity,
            subject=subject, gate_name=gate_name, reason=reason,
            evidence=json.dumps(evidence) if evidence is not None else None,
            recommended_action=recommended_action,
        )

    def record_source_document(self, run_id: str, **fields: Any) -> int:
        return self.insert("source_documents", run_id=run_id, **fields)

    def record_report_export(self, run_id: str, export_type: str,
                             file_name: str, file_path: str, sha256: str,
                             note: str = "") -> int:
        return self.insert(
            "report_exports", run_id=run_id, export_type=export_type,
            file_name=file_name, file_path=file_path, sha256=sha256, note=note,
        )

    def record_launcher_event(self, event_type: str, description: str,
                             data: Any = None) -> int:
        return self.insert(
            "launcher_events", event_type=event_type, description=description,
            data_json=json.dumps(data) if data is not None else None,
        )

    # --------------------------- readers ------------------------------ #
    def cumulative_spend(self, run_id: str | None = None) -> float:
        if run_id:
            rows = self.query(
                "SELECT COALESCE(MAX(cumulative_usd), 0.0) AS c "
                "FROM spend_ledger WHERE run_id = ?", (run_id,)
            )
        else:
            rows = self.query(
                "SELECT COALESCE(SUM(amount_usd), 0.0) AS c FROM spend_ledger"
            )
        return float(rows[0]["c"]) if rows else 0.0

    def get_validation_results(self, run_id: str) -> list[dict]:
        rows = self.query(
            "SELECT * FROM validation_results WHERE run_id = ? "
            "ORDER BY id", (run_id,)
        )
        return [dict(r) for r in rows]

    def get_escalations(self, run_id: str) -> list[dict]:
        rows = self.query(
            "SELECT * FROM escalations WHERE run_id = ? ORDER BY id", (run_id,)
        )
        return [dict(r) for r in rows]

    def get_source_documents(self, run_id: str) -> list[dict]:
        rows = self.query(
            "SELECT * FROM source_documents WHERE run_id = ? ORDER BY id",
            (run_id,)
        )
        return [dict(r) for r in rows]

    def get_workbook_versions(self, run_id: str) -> list[dict]:
        rows = self.query(
            "SELECT * FROM workbook_versions WHERE run_id = ? ORDER BY id",
            (run_id,)
        )
        return [dict(r) for r in rows]

    def get_report_exports(self, run_id: str) -> list[dict]:
        rows = self.query(
            "SELECT * FROM report_exports WHERE run_id = ? ORDER BY id",
            (run_id,)
        )
        return [dict(r) for r in rows]

    def get_runs(self, limit: int = 50) -> list[dict]:
        rows = self.query(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    def get_terminal_status(self, run_id: str) -> dict | None:
        rows = self.query(
            "SELECT data_json FROM audit_events WHERE run_id = ? "
            "AND event_type = 'run_terminal' ORDER BY id DESC LIMIT 1",
            (run_id,)
        )
        if rows and rows[0]["data_json"]:
            return json.loads(rows[0]["data_json"])
        return None
