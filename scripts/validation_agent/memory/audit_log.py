"""Append-only audit trail — the single write path for provable actions."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Iterator

from ..models import (
    AuditEntry,
    FixPlan,
    ValidationResult,
    dumps,
    to_jsonable,
)


class AuditLog:
    """Every validator, fixer, and source call records here. Idempotent on hash."""

    def __init__(self, conn: sqlite3.Connection, run_id: str) -> None:
        self._conn = conn
        self._run_id = run_id

    # -- core ------------------------------------------------------------- #
    def record(self, entry: AuditEntry) -> None:
        action_hash = self._hash(entry)
        try:
            self._conn.execute(
                "INSERT INTO audit_log(ts, run_id, actor, action, gate, coord, "
                "before, after, risk, source_refs, result, action_hash) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    entry.ts,
                    entry.run_id,
                    entry.actor,
                    entry.action,
                    entry.gate.value if entry.gate else None,
                    str(entry.coord) if entry.coord else None,
                    dumps(entry.before) if entry.before is not None else None,
                    dumps(entry.after) if entry.after is not None else None,
                    entry.risk.value if entry.risk else None,
                    dumps(entry.source_refs) if entry.source_refs else None,
                    entry.result,
                    action_hash,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            # Duplicate action (same run + identical action_hash) -> no-op.
            self._conn.rollback()

    # -- typed convenience writers --------------------------------------- #
    def record_validation(self, version: int, r: ValidationResult) -> None:
        self._conn.execute(
            "INSERT INTO validation_results(ts, run_id, version, gate, passed, "
            "severity, message, metric, expected, locations) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                _now(),
                self._run_id,
                version,
                r.gate.value,
                int(r.passed),
                r.severity.value,
                r.message,
                r.metric,
                r.expected,
                dumps([str(c) for c in r.locations]),
            ),
        )
        self._conn.commit()

    def record_fix(self, version: int, fix: FixPlan) -> None:
        self._conn.execute(
            "INSERT INTO fixes(ts, run_id, version, strategy_id, risk, coord, "
            "before, after, justification, source_refs) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                _now(),
                self._run_id,
                version,
                fix.strategy_id,
                fix.risk.value,
                str(fix.target),
                dumps(fix.before),
                dumps(fix.after),
                fix.justification,
                dumps(fix.source_refs),
            ),
        )
        self._conn.commit()
        self.record(
            AuditEntry(
                run_id=self._run_id,
                actor="repair",
                action=f"apply_fix:{fix.strategy_id}",
                result="applied",
                coord=fix.target,
                before=fix.before,
                after=fix.after,
                risk=fix.risk,
                source_refs=fix.source_refs,
            )
        )

    # -- readers ---------------------------------------------------------- #
    def trail(self) -> Iterator[AuditEntry]:
        cur = self._conn.execute(
            "SELECT * FROM audit_log WHERE run_id=? ORDER BY id", (self._run_id,)
        )
        for row in cur:
            yield AuditEntry(
                run_id=row["run_id"],
                actor=row["actor"],
                action=row["action"],
                result=row["result"],
                ts=row["ts"],
            )

    def count(self) -> int:
        cur = self._conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log WHERE run_id=?", (self._run_id,)
        )
        return int(cur.fetchone()["n"])

    # -- internals -------------------------------------------------------- #
    @staticmethod
    def _hash(entry: AuditEntry) -> str:
        payload = dumps(
            {
                "actor": entry.actor,
                "action": entry.action,
                "coord": str(entry.coord) if entry.coord else None,
                "before": to_jsonable(entry.before),
                "after": to_jsonable(entry.after),
                "result": entry.result,
            }
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
