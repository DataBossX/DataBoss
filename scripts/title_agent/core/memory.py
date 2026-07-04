"""State, auditing, and version control — the Title Agent's memory.

This module is the single authority for durable state. It owns the SQLite
schema and enforces two of the three pillars of the Golden Law at the
storage layer, where they cannot be bypassed:

* **Append-only audit** — the ``audit_log`` and ``budget_ledger`` tables are
  guarded by SQLite triggers that ``RAISE`` on any ``UPDATE`` or ``DELETE``.
  ``AuditLogger`` never emits anything but ``INSERT``. Even a rogue caller
  holding the raw connection cannot mutate history.

* **No overwrites / strict sequential versioning** — ``VersionController``
  mints ``_v001``, ``_v002`` … monotonically per artifact and refuses to hand
  back a path that already exists on disk. Every automated fix therefore
  spawns a brand-new file; the prior version is preserved verbatim.

The third pillar — never fabricating a legal fact — lives in the validators
and the loop; this layer simply guarantees that whatever they do is recorded
truthfully and irreversibly.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import config

# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

_APPEND_ONLY_TABLES = ("audit_log", "budget_ledger")

SCHEMA: str = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Append-only audit trail. Never UPDATE-d, never DELETE-d.
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT    NOT NULL,
    action     TEXT    NOT NULL,
    reference  TEXT    NOT NULL,
    result     TEXT    NOT NULL,
    actor      TEXT    NOT NULL DEFAULT 'agent',
    metadata   TEXT
);

-- Strict sequential version ledger. One row per minted artifact version.
CREATE TABLE IF NOT EXISTS artifact_versions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_key   TEXT    NOT NULL,
    version_number INTEGER NOT NULL,
    version_label  TEXT    NOT NULL,
    file_path      TEXT    NOT NULL UNIQUE,
    parent_version INTEGER,
    reason         TEXT    NOT NULL,
    created_at     TEXT    NOT NULL,
    UNIQUE (artifact_key, version_number)
);

-- Human-in-the-loop escalation queue. Rows may transition open -> resolved
-- (a status UPDATE is legitimate here); the *audit* of that transition is the
-- immutable record. Escalations themselves are working state, not history.
CREATE TABLE IF NOT EXISTS escalations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    category      TEXT    NOT NULL,
    gate          TEXT    NOT NULL,
    reference     TEXT    NOT NULL,
    proof         TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'open',
    resolution    TEXT,
    examiner_id   TEXT,
    created_at    TEXT    NOT NULL,
    resolved_at   TEXT
);

-- Append-only budget ledger. Cumulative OKCounty spend lives here so the
-- $100 cap survives process restarts. Never UPDATE-d, never DELETE-d.
CREATE TABLE IF NOT EXISTS budget_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    amount      REAL    NOT NULL,
    reference   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_action    ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_versions_key     ON artifact_versions(artifact_key);
CREATE INDEX IF NOT EXISTS idx_escalations_open ON escalations(status);
"""

# Triggers that make the append-only tables tamper-evident at the engine level.
_APPEND_ONLY_TRIGGERS: str = "\n".join(
    f"""
CREATE TRIGGER IF NOT EXISTS {table}_no_update
BEFORE UPDATE ON {table}
BEGIN
    SELECT RAISE(ABORT, '{table} is append-only: UPDATE forbidden');
END;

CREATE TRIGGER IF NOT EXISTS {table}_no_delete
BEFORE DELETE ON {table}
BEGIN
    SELECT RAISE(ABORT, '{table} is append-only: DELETE forbidden');
END;
"""
    for table in _APPEND_ONLY_TABLES
)


def _utc_now() -> str:
    """ISO-8601 UTC timestamp with a trailing Z, second precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _last_row_id(cur: sqlite3.Cursor) -> int:
    """Return the id of the just-inserted row.

    ``sqlite3.Cursor.lastrowid`` is typed ``int | None`` because it is None
    when the last statement was not an INSERT. Every caller here guards this
    behind an INSERT, so a None value is a programming error, not a runtime
    condition — assert loudly rather than paper over it.
    """
    row_id = cur.lastrowid
    if row_id is None:
        raise RuntimeError("expected an inserted row id but lastrowid was None")
    return int(row_id)


# --------------------------------------------------------------------------- #
# SQLiteManager
# --------------------------------------------------------------------------- #


class SQLiteManager:
    """Owns the schema and hands out connections.

    SQLite has no server-side pool, so "connection pooling" here means a
    single serialized connection guarded by a re-entrant lock. That is the
    correct model for an embedded store driven by one loop process: it avoids
    ``database is locked`` races while still allowing the Streamlit frontend
    to open its own read connection independently.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path: Path = Path(db_path) if db_path is not None else config.DB_PATH
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage transactions explicitly
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def initialize(self) -> None:
        """Create tables and the append-only triggers. Idempotent."""
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            self._conn.executescript(SCHEMA)
            self._conn.executescript(_APPEND_ONLY_TRIGGERS)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield the shared connection under the lock.

        Serializing on the lock keeps writers from colliding. Reads are cheap
        enough that funneling them through here as well keeps the model simple
        and correct.
        """
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            yield self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield the connection inside an explicit BEGIN/COMMIT, rolling back
        on any exception."""
        with self.connection() as conn:
            conn.execute("BEGIN")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


# --------------------------------------------------------------------------- #
# AuditLogger
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AuditRecord:
    """An immutable audit entry as read back from the store."""

    id: int
    timestamp: str
    action: str
    reference: str
    result: str
    actor: str
    metadata: Optional[dict[str, Any]]


class AuditLogger:
    """Append-only action log.

    ``log_action`` is the only write path and it emits nothing but ``INSERT``.
    The engine-level triggers make any ``UPDATE``/``DELETE`` an error, so the
    append-only guarantee holds against callers who reach past this class.
    """

    #: Canonical action used when a human overrides an AI decision.
    EXAMINER_OVERRIDE = "EXAMINER_OVERRIDE"

    def __init__(self, manager: SQLiteManager, audit_log_path: Optional[Path] = None) -> None:
        self._db = manager
        self._file_path: Path = (
            Path(audit_log_path) if audit_log_path is not None else config.AUDIT_LOG_PATH
        )
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    def log_action(
        self,
        action: str,
        reference: str,
        result: str,
        *,
        actor: str = "agent",
        metadata: Optional[dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """Record one action. Returns the new row id.

        Parameters mirror the spec's ``log_action(timestamp, action,
        reference, result)`` while adding an ``actor`` (defaults to ``agent``,
        set to an Examiner id for overrides) and structured ``metadata``.
        """
        with self._db.transaction() as conn:
            row_id, ts, meta_json = self._insert(
                conn, action, reference, result, actor=actor,
                metadata=metadata, timestamp=timestamp,
            )
        self._mirror_to_file(ts, action, reference, result, actor, meta_json)
        return row_id

    def _insert(
        self,
        conn: sqlite3.Connection,
        action: str,
        reference: str,
        result: str,
        *,
        actor: str = "agent",
        metadata: Optional[dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> tuple[int, str, Optional[str]]:
        """Emit the audit INSERT on an already-open connection **without**
        opening its own transaction. This lets a caller fold an audit record
        into the same transaction as the state change it describes, so the two
        commit atomically — the file mirror is done by the caller after commit.
        Returns (row_id, timestamp, metadata_json)."""
        ts = timestamp or _utc_now()
        meta_json = (
            json.dumps(metadata, sort_keys=True, default=str)
            if metadata is not None else None
        )
        cur = conn.execute(
            "INSERT INTO audit_log (timestamp, action, reference, result, actor, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, action, reference, result, actor, meta_json),
        )
        return _last_row_id(cur), ts, meta_json

    def log_examiner_override(
        self,
        examiner_id: str,
        reference: str,
        result: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Convenience wrapper: an Examiner override is a first-class audited
        action tagged with the human's id, per the HITL contract."""
        return self.log_action(
            self.EXAMINER_OVERRIDE,
            reference,
            result,
            actor=examiner_id,
            metadata=metadata,
        )

    def _mirror_to_file(
        self,
        ts: str,
        action: str,
        reference: str,
        result: str,
        actor: str,
        meta_json: Optional[str],
    ) -> None:
        """Append a human-readable line to the flat audit log. Best-effort:
        the SQLite row is the source of truth, the file is a convenience
        mirror, so a filesystem hiccup must never lose the DB record."""
        line = json.dumps(
            {
                "ts": ts,
                "action": action,
                "reference": reference,
                "result": result,
                "actor": actor,
                "metadata": json.loads(meta_json) if meta_json else None,
            },
            sort_keys=True,
        )
        try:
            with self._file_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    def read_all(self, *, action: Optional[str] = None) -> list[AuditRecord]:
        """Return the full trail (optionally filtered by action), oldest first."""
        sql = "SELECT * FROM audit_log"
        params: tuple[Any, ...] = ()
        if action is not None:
            sql += " WHERE action = ?"
            params = (action,)
        sql += " ORDER BY id ASC"
        with self._db.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._to_record(r) for r in rows]

    @staticmethod
    def _to_record(row: sqlite3.Row) -> AuditRecord:
        return AuditRecord(
            id=int(row["id"]),
            timestamp=row["timestamp"],
            action=row["action"],
            reference=row["reference"],
            result=row["result"],
            actor=row["actor"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )


# --------------------------------------------------------------------------- #
# VersionController
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ArtifactVersion:
    """A minted, on-disk version of an artifact."""

    id: int
    artifact_key: str
    version_number: int
    version_label: str
    file_path: Path
    parent_version: Optional[int]
    reason: str
    created_at: str


class VersionOverwriteError(RuntimeError):
    """Raised when minting a version would collide with an existing file.

    File overwrites are strictly prohibited; this error is the enforcement.
    """


class VersionController:
    """Guarantees strict, gapless, non-overwriting version progression.

    An *artifact* is identified by a stable ``artifact_key`` (e.g. the
    workbook's logical name) and lives in ``config.WORKBOOK_DIR``. Each mint
    produces ``<key>_vNNN<suffix>`` with a zero-padded, strictly incrementing
    number. The controller never returns a path that already exists on disk,
    so an automated fix can only ever write a fresh file.
    """

    VERSION_PAD = 3  # _v001 .. _v999, widening automatically beyond that.

    def __init__(
        self,
        manager: SQLiteManager,
        workbook_dir: Optional[Path] = None,
    ) -> None:
        self._db = manager
        self._dir: Path = (
            Path(workbook_dir) if workbook_dir is not None else config.WORKBOOK_DIR
        )
        self._dir.mkdir(parents=True, exist_ok=True)

    def get_latest_version(self, artifact_key: str) -> Optional[ArtifactVersion]:
        """Return the highest-numbered version of ``artifact_key``, or None."""
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM artifact_versions WHERE artifact_key = ? "
                "ORDER BY version_number DESC LIMIT 1",
                (artifact_key,),
            ).fetchone()
        return self._to_version(row) if row else None

    def _label(self, number: int) -> str:
        return f"_v{number:0{self.VERSION_PAD}d}"

    def mint_new_version(
        self,
        artifact_key: str,
        reason: str,
        *,
        suffix: str = ".xlsx",
    ) -> ArtifactVersion:
        """Reserve the next version and return its record.

        The returned ``file_path`` is guaranteed **not** to exist yet — the
        caller is responsible for writing the bytes. If a file already sits at
        the computed path (a stray artifact from a crashed run), we raise
        ``VersionOverwriteError`` rather than risk clobbering it.

        The DB row and the on-disk uniqueness together enforce that versions
        are strictly sequential and never reused.
        """
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT version_number FROM artifact_versions WHERE artifact_key = ? "
                "ORDER BY version_number DESC LIMIT 1",
                (artifact_key,),
            ).fetchone()
            parent_number: Optional[int] = int(row["version_number"]) if row else None
            next_number = (parent_number or 0) + 1

            label = self._label(next_number)
            file_path = self._dir / f"{artifact_key}{label}{suffix}"

            if file_path.exists():
                raise VersionOverwriteError(
                    f"Refusing to overwrite existing file: {file_path}"
                )

            created_at = _utc_now()
            cur = conn.execute(
                "INSERT INTO artifact_versions "
                "(artifact_key, version_number, version_label, file_path, "
                " parent_version, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact_key,
                    next_number,
                    label,
                    str(file_path),
                    parent_number,
                    reason,
                    created_at,
                ),
            )
            version_id = _last_row_id(cur)

        return ArtifactVersion(
            id=version_id,
            artifact_key=artifact_key,
            version_number=next_number,
            version_label=label,
            file_path=file_path,
            parent_version=parent_number,
            reason=reason,
            created_at=created_at,
        )

    def discard_version(self, version: ArtifactVersion) -> bool:
        """Remove a just-minted version row whose file was never written.

        Used to roll back a reserved version when the repair that was supposed
        to populate it fails, so a fileless row can never become the "latest"
        version and wedge the loop. Refuses if the file exists on disk — a
        version with real bytes is never silently dropped. Version rows are not
        append-only (only audit_log and budget_ledger are), so this DELETE is
        permitted.
        """
        if version.file_path.exists():
            raise VersionOverwriteError(
                f"refusing to discard a version whose file exists: {version.file_path}"
            )
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM artifact_versions WHERE id = ?", (version.id,))
        return True

    def history(self, artifact_key: str) -> list[ArtifactVersion]:
        """Full version lineage for an artifact, oldest first."""
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM artifact_versions WHERE artifact_key = ? "
                "ORDER BY version_number ASC",
                (artifact_key,),
            ).fetchall()
        return [self._to_version(r) for r in rows]

    @staticmethod
    def _to_version(row: sqlite3.Row) -> ArtifactVersion:
        return ArtifactVersion(
            id=int(row["id"]),
            artifact_key=row["artifact_key"],
            version_number=int(row["version_number"]),
            version_label=row["version_label"],
            file_path=Path(row["file_path"]),
            parent_version=(
                int(row["parent_version"]) if row["parent_version"] is not None else None
            ),
            reason=row["reason"],
            created_at=row["created_at"],
        )


# --------------------------------------------------------------------------- #
# EscalationStore
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Escalation:
    """A Category B failure awaiting an Examiner decision."""

    id: int
    category: str
    gate: str
    reference: str
    proof: dict[str, Any]
    status: str
    resolution: Optional[str]
    examiner_id: Optional[str]
    created_at: str
    resolved_at: Optional[str]

    @property
    def is_open(self) -> bool:
        return self.status == "open"


class EscalationStore:
    """The HITL escalation queue.

    Unlike the audit log, an escalation is *working state*: it legitimately
    transitions ``open -> resolved`` when the Examiner acts. That transition is
    the only mutation allowed, and it is always accompanied by an immutable
    ``EXAMINER_OVERRIDE`` entry in the (append-only) audit log, so the record
    of *who decided what, when* can never be edited away.
    """

    def __init__(self, manager: SQLiteManager, audit: Optional[AuditLogger] = None) -> None:
        self._db = manager
        self._audit = audit or AuditLogger(manager)

    def open_escalation(
        self, category: str, gate: str, reference: str, proof: dict[str, Any]
    ) -> Escalation:
        created = _utc_now()
        proof_json = json.dumps(proof, sort_keys=True, default=str)
        # Escalation state and its ESCALATION_OPENED audit record commit in one
        # transaction so an escalation can never exist without its audit trail.
        with self._db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO escalations (category, gate, reference, proof, status, created_at) "
                "VALUES (?, ?, ?, ?, 'open', ?)",
                (category, gate, reference, proof_json, created),
            )
            esc_id = _last_row_id(cur)
            _, ts, meta_json = self._audit._insert(
                conn, "ESCALATION_OPENED", reference, category,
                metadata={"gate": gate, "escalation_id": esc_id},
            )
        self._audit._mirror_to_file(ts, "ESCALATION_OPENED", reference, category, "agent", meta_json)
        return self.get(esc_id)

    def resolve(self, escalation_id: int, examiner_id: str, resolution: str) -> Escalation:
        """Mark an escalation resolved and record the Examiner override.

        The ownership of the decision is the Examiner's — this method only
        stores the human's stated resolution verbatim; it does not derive or
        infer any fact on their behalf.
        """
        resolved = _utc_now()
        # The resolution and its immutable EXAMINER_OVERRIDE record commit in one
        # transaction: a resolved escalation can never exist without the audit of
        # who decided it — the core Golden Law guarantee for HITL.
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT reference, status FROM escalations WHERE id = ?", (escalation_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"no such escalation: {escalation_id}")
            if row["status"] != "open":
                raise ValueError(f"escalation {escalation_id} is already {row['status']}")
            conn.execute(
                "UPDATE escalations SET status='resolved', resolution=?, examiner_id=?, "
                "resolved_at=? WHERE id=?",
                (resolution, examiner_id, resolved, escalation_id),
            )
            reference = row["reference"]
            _, ts, meta_json = self._audit._insert(
                conn, AuditLogger.EXAMINER_OVERRIDE, reference, resolution,
                actor=examiner_id, metadata={"escalation_id": escalation_id},
            )
        self._audit._mirror_to_file(
            ts, AuditLogger.EXAMINER_OVERRIDE, reference, resolution, examiner_id, meta_json)
        return self.get(escalation_id)

    def get(self, escalation_id: int) -> Escalation:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM escalations WHERE id = ?", (escalation_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"no such escalation: {escalation_id}")
        return self._to_escalation(row)

    def list_open(self) -> list[Escalation]:
        return self._list("WHERE status = 'open'")

    def list_all(self) -> list[Escalation]:
        return self._list("")

    def _list(self, where: str) -> list[Escalation]:
        with self._db.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM escalations {where} ORDER BY id ASC"
            ).fetchall()
        return [self._to_escalation(r) for r in rows]

    @staticmethod
    def _to_escalation(row: sqlite3.Row) -> Escalation:
        return Escalation(
            id=int(row["id"]),
            category=row["category"],
            gate=row["gate"],
            reference=row["reference"],
            proof=json.loads(row["proof"]) if row["proof"] else {},
            status=row["status"],
            resolution=row["resolution"],
            examiner_id=row["examiner_id"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
        )
