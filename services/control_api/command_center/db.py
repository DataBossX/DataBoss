"""Migrations and connection handling for the control kernel.

Two engines, one schema. PostgreSQL is the canonical cloud target (ADR-0003);
SQLite in WAL mode is correct for the local runner cache and for offline work.
The table and index DDL is written once in a portable form and shared; only the
trigger bodies differ, because that is the one place the dialects genuinely
diverge.

The single-writer invariant lives *here*, not in application memory, and it
holds identically on both engines:

* ``ux_lease_one_active_per_scope`` is a partial unique index that makes a
  second ACTIVE lease on a scope physically unrepresentable.
* ``fencing_counters`` advances monotonically under the same transaction that
  issues a lease.
* Triggers reject impossible state transitions and any attempt to mutate an
  accepted artifact or delete a hold.

Target selection: a ``postgres://`` / ``postgresql://`` URL selects PostgreSQL,
anything else is treated as a SQLite path.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Iterable, List, Optional, Protocol, Sequence

from . import pg_wire

SCHEMA_VERSION = 1

DIALECT_SQLITE = "sqlite"
DIALECT_POSTGRES = "postgres"

#: Exceptions meaning "a constraint refused this write", on either engine.
IntegrityError = (sqlite3.IntegrityError, pg_wire.PgIntegrityError)

#: Exceptions meaning "the database refused this", including trigger aborts.
DatabaseError = (sqlite3.Error, pg_wire.PgError)


class Row(Protocol):
    """What both engines' result rows guarantee.

    ``sqlite3.Row`` and :class:`pg_wire.Row` both satisfy this structurally, so
    the kernel can index rows by column name and pass them to ``dict()`` without
    caring which engine produced them.
    """

    def keys(self) -> Sequence[str]:
        ...

    def __getitem__(self, key: str) -> Any:
        ...


def is_postgres(target: str) -> bool:
    return target.startswith("postgres://") or target.startswith("postgresql://")


# --------------------------------------------------------------------- facade
_PLACEHOLDER = re.compile(r"'(?:[^']|'')*'|\?")


def _to_numbered(sql: str) -> str:
    """Rewrite ``?`` placeholders to ``$1..$n``, ignoring string literals."""
    counter = [0]

    def replace(match):
        text = match.group(0)
        if text != "?":
            return text            # a quoted literal; leave it alone
        counter[0] += 1
        return f"${counter[0]}"

    return _PLACEHOLDER.sub(replace, sql)


class PostgresConnection:
    """Adapts :mod:`pg_wire` to the sqlite3 surface the kernel uses."""

    dialect = DIALECT_POSTGRES

    def __init__(self, dsn: str):
        self._conn = pg_wire.connect(dsn)

    def execute(self, sql: str, params: Iterable = ()):
        return self._conn.execute(_to_numbered(sql), tuple(params))

    def close(self):
        self._conn.close()


class SqliteConnection:
    """Thin wrapper so both engines expose the same attributes."""

    dialect = DIALECT_SQLITE

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def execute(self, sql: str, params: Iterable = ()):
        return self._conn.execute(sql, tuple(params))

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def connect(target: str):
    """Open a connection to either engine."""
    if is_postgres(target):
        return PostgresConnection(target)

    # check_same_thread=False lets the threaded HTTP server reuse one kernel
    # connection. Callers MUST serialize access; ``ControlCenterApp`` holds a
    # request lock, and concurrency tests use separate connections so the
    # database constraints, not a Python lock, decide who wins a race.
    conn = sqlite3.connect(target, isolation_level=None, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    # Durability matters more than throughput for an audit ledger.
    conn.execute("PRAGMA synchronous=FULL")
    return SqliteConnection(conn)


def begin_sql(dialect: str) -> str:
    """SQLite needs IMMEDIATE to take the write lock up front."""
    return "BEGIN IMMEDIATE" if dialect == DIALECT_SQLITE else "BEGIN"


# ---------------------------------------------------------------------- DDL
#: Shared table and index DDL. ``{serial}`` is the auto-incrementing PK type.
TABLES: tuple = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id       TEXT PRIMARY KEY,
        display_name  TEXT NOT NULL,
        role          TEXT NOT NULL CHECK (role IN ('OWNER','OPERATOR','REVIEWER','VIEWER','RUNNER')),
        created_at    TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id    TEXT PRIMARY KEY,
        user_id       TEXT NOT NULL REFERENCES users(user_id),
        device_id     TEXT NOT NULL,
        csrf_token    TEXT NOT NULL,
        issued_at     TEXT NOT NULL,
        expires_at    TEXT NOT NULL,
        step_up_at    TEXT,
        revoked       INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0,1))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_versions (
        policy_version TEXT PRIMARY KEY,
        activated_at   TEXT NOT NULL,
        description    TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS holds (
        hold_id       TEXT PRIMARY KEY,
        label         TEXT NOT NULL,
        scope_pattern TEXT NOT NULL,
        reason        TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        immutable     INTEGER NOT NULL DEFAULT 1 CHECK (immutable IN (0,1))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS fencing_counters (
        resource_scope TEXT PRIMARY KEY,
        current_value  INTEGER NOT NULL DEFAULT 0 CHECK (current_value >= 0)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS writer_leases (
        lease_id                   TEXT PRIMARY KEY,
        resource_scope             TEXT NOT NULL,
        writer_identity            TEXT NOT NULL,
        state                      TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED','EXPIRED','FORCE_RELEASED')),
        fencing_sequence           INTEGER NOT NULL CHECK (fencing_sequence >= 1),
        issued_at                  TEXT NOT NULL,
        expires_at                 TEXT NOT NULL,
        last_heartbeat_at          TEXT,
        heartbeat_interval_seconds INTEGER NOT NULL CHECK (heartbeat_interval_seconds >= 1),
        stale_threshold_seconds    INTEGER NOT NULL CHECK (stale_threshold_seconds >= 2),
        released_at                TEXT,
        release_reason             TEXT,
        force_released_by          TEXT
    );
    """,
    # THE single-writer invariant. Not a boolean in memory - a unique index.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_lease_one_active_per_scope
        ON writer_leases (resource_scope) WHERE state = 'ACTIVE';
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_lease_scope_sequence
        ON writer_leases (resource_scope, fencing_sequence);
    """,
    """
    CREATE TABLE IF NOT EXISTS commands (
        command_id      TEXT PRIMARY KEY,
        idempotency_key TEXT NOT NULL,
        actor_user_id   TEXT NOT NULL REFERENCES users(user_id),
        session_id      TEXT,
        device_id       TEXT,
        channel         TEXT NOT NULL CHECK (channel IN ('VOICE','TEXT','DRIVE_INBOX','IMPORTED_CONVERSATION')),
        provider        TEXT,
        confidence      REAL,
        transcript_text TEXT NOT NULL,
        transcript_sha256 TEXT NOT NULL,
        audio_retained  INTEGER NOT NULL DEFAULT 0 CHECK (audio_retained IN (0,1)),
        intent_json     TEXT NOT NULL,
        risk_class      TEXT CHECK (risk_class IN ('READ_ONLY','SIMULATION','APPROVAL_REQUIRED','PROHIBITED')),
        status          TEXT NOT NULL,
        policy_version  TEXT,
        content_sha256  TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    );
    """,
    # Duplicate taps and voice retries collapse onto one command, per actor.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_commands_idempotency
        ON commands (actor_user_id, idempotency_key);
    """,
    """
    CREATE TABLE IF NOT EXISTS approvals (
        approval_id           TEXT PRIMARY KEY,
        state                 TEXT NOT NULL,
        actor_user_id         TEXT NOT NULL REFERENCES users(user_id),
        actor_role            TEXT NOT NULL CHECK (actor_role IN ('OWNER','OPERATOR')),
        step_up_method        TEXT NOT NULL CHECK (step_up_method IN ('WEBAUTHN','PASSPHRASE_REPEAT','NONE')),
        operation             TEXT NOT NULL,
        resource_scope        TEXT NOT NULL,
        parameters_sha256     TEXT NOT NULL,
        task_envelope_sha256  TEXT NOT NULL,
        input_hashes_sha256   TEXT,
        policy_version        TEXT NOT NULL,
        nonce                 TEXT NOT NULL UNIQUE,
        issued_at             TEXT NOT NULL,
        expires_at            TEXT NOT NULL,
        consumed_at           TEXT,
        consumed_by_attempt_id TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS task_envelopes (
        task_id           TEXT PRIMARY KEY,
        command_id        TEXT NOT NULL REFERENCES commands(command_id),
        resource_scope    TEXT NOT NULL,
        adapter           TEXT NOT NULL,
        parameters_json   TEXT NOT NULL,
        execution_mode    TEXT NOT NULL CHECK (execution_mode IN ('READ_ONLY','SIMULATED','REAL')),
        risk_class        TEXT NOT NULL,
        approval_token_id TEXT REFERENCES approvals(approval_id),
        issued_at         TEXT NOT NULL,
        expires_at        TEXT NOT NULL,
        nonce             TEXT NOT NULL UNIQUE,
        fencing_sequence  INTEGER NOT NULL CHECK (fencing_sequence >= 1),
        lease_id          TEXT NOT NULL REFERENCES writer_leases(lease_id),
        writer_identity   TEXT NOT NULL,
        policy_version    TEXT NOT NULL,
        input_hashes_json TEXT NOT NULL DEFAULT '{}',
        content_sha256    TEXT NOT NULL,
        CHECK (risk_class <> 'APPROVAL_REQUIRED' OR approval_token_id IS NOT NULL),
        CHECK (risk_class <> 'PROHIBITED')
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id         TEXT PRIMARY KEY,
        task_id        TEXT NOT NULL REFERENCES task_envelopes(task_id),
        command_id     TEXT NOT NULL REFERENCES commands(command_id),
        state          TEXT NOT NULL,
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL,
        title          TEXT NOT NULL,
        detail         TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS execution_attempts (
        attempt_id       TEXT PRIMARY KEY,
        job_id           TEXT NOT NULL REFERENCES jobs(job_id),
        task_id          TEXT NOT NULL REFERENCES task_envelopes(task_id),
        lease_id         TEXT NOT NULL,
        fencing_sequence INTEGER NOT NULL,
        started_at       TEXT NOT NULL,
        finished_at      TEXT,
        outcome          TEXT,
        failure_reason   TEXT
    );
    """,
    # Replay guard: one terminal attempt per task.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_attempt_task_completed
        ON execution_attempts (task_id) WHERE outcome = 'COMPLETED';
    """,
    """
    CREATE TABLE IF NOT EXISTS artifacts (
        artifact_id  TEXT PRIMARY KEY,
        logical_id   TEXT NOT NULL UNIQUE,
        project_id   TEXT,
        state        TEXT NOT NULL,
        synthetic    INTEGER NOT NULL DEFAULT 1 CHECK (synthetic IN (0,1)),
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS artifact_versions (
        version_id           TEXT PRIMARY KEY,
        artifact_id          TEXT NOT NULL REFERENCES artifacts(artifact_id),
        version_number       INTEGER NOT NULL CHECK (version_number >= 1),
        sha256               TEXT NOT NULL,
        byte_size            INTEGER NOT NULL CHECK (byte_size >= 0),
        mime_type            TEXT,
        accepted             INTEGER NOT NULL DEFAULT 0 CHECK (accepted IN (0,1)),
        drive_file_id        TEXT,
        drive_version        TEXT,
        drive_parent_id      TEXT,
        drive_readback_sha256 TEXT,
        drive_readback_at    TEXT,
        created_at           TEXT NOT NULL,
        UNIQUE (artifact_id, version_number)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS verification_receipts (
        receipt_id     TEXT PRIMARY KEY,
        task_id        TEXT NOT NULL,
        command_id     TEXT NOT NULL,
        attempt_id     TEXT,
        payload_json   TEXT NOT NULL,
        content_sha256 TEXT NOT NULL,
        created_at     TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS review_receipts (
        review_id      TEXT PRIMARY KEY,
        watcher_name   TEXT NOT NULL,
        target_kind    TEXT NOT NULL,
        target_id      TEXT NOT NULL,
        state          TEXT NOT NULL,
        verdict        TEXT,
        confidence     REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
        findings_json  TEXT NOT NULL,
        content_sha256 TEXT NOT NULL,
        created_at     TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        audit_id       {serial},
        occurred_at    TEXT NOT NULL,
        actor          TEXT NOT NULL,
        event_type     TEXT NOT NULL,
        resource_scope TEXT,
        subject_id     TEXT,
        outcome        TEXT NOT NULL CHECK (outcome IN ('ALLOW','DENY','INFO')),
        detail_json    TEXT NOT NULL,
        prev_sha256    TEXT,
        content_sha256 TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS outbox (
        outbox_id    {serial},
        created_at   TEXT NOT NULL,
        topic        TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        delivered_at TEXT,
        attempts     INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS nonces_seen (
        nonce      TEXT PRIMARY KEY,
        purpose    TEXT NOT NULL,
        seen_at    TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
)

SERIAL_SQL = {
    DIALECT_SQLITE: "INTEGER PRIMARY KEY AUTOINCREMENT",
    DIALECT_POSTGRES: "BIGSERIAL PRIMARY KEY",
}

# A hold is a floor, not a toggle. An accepted artifact version is final. The
# audit ledger is append-only. Enforced by the database on both engines.
TRIGGERS_SQLITE: tuple = (
    """
    CREATE TRIGGER IF NOT EXISTS trg_holds_no_delete
    BEFORE DELETE ON holds
    BEGIN SELECT RAISE(ABORT, 'HOLD_REMOVAL_FORBIDDEN'); END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_holds_no_downgrade
    BEFORE UPDATE ON holds WHEN OLD.immutable = 1
    BEGIN SELECT RAISE(ABORT, 'HOLD_REMOVAL_FORBIDDEN'); END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_commands_no_transcript_rewrite
    BEFORE UPDATE OF transcript_text, transcript_sha256, idempotency_key ON commands
    WHEN OLD.transcript_sha256 IS NOT NULL
     AND (NEW.transcript_sha256 <> OLD.transcript_sha256
          OR NEW.idempotency_key <> OLD.idempotency_key)
    BEGIN SELECT RAISE(ABORT, 'COMMAND_IMMUTABLE'); END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_artifact_version_accepted_immutable
    BEFORE UPDATE ON artifact_versions WHEN OLD.accepted = 1
    BEGIN SELECT RAISE(ABORT, 'ACCEPTED_ARTIFACT_IMMUTABLE'); END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_artifact_version_accepted_no_delete
    BEFORE DELETE ON artifact_versions WHEN OLD.accepted = 1
    BEGIN SELECT RAISE(ABORT, 'ACCEPTED_ARTIFACT_IMMUTABLE'); END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_audit_no_update
    BEFORE UPDATE ON audit_events
    BEGIN SELECT RAISE(ABORT, 'AUDIT_APPEND_ONLY'); END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete
    BEFORE DELETE ON audit_events
    BEGIN SELECT RAISE(ABORT, 'AUDIT_APPEND_ONLY');END;
    """,
)

#: Same guarantees in plpgsql. RAISE EXCEPTION surfaces as SQLSTATE P0001,
#: which ``pg_wire`` maps to :class:`PgRaisedError`.
TRIGGERS_POSTGRES: tuple = (
    """
    CREATE OR REPLACE FUNCTION dbx_refuse() RETURNS trigger AS $dbx$
    BEGIN RAISE EXCEPTION '%', TG_ARGV[0]; END;
    $dbx$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS trg_holds_no_delete ON holds;",
    """
    CREATE TRIGGER trg_holds_no_delete BEFORE DELETE ON holds
    FOR EACH ROW EXECUTE FUNCTION dbx_refuse('HOLD_REMOVAL_FORBIDDEN');
    """,
    "DROP TRIGGER IF EXISTS trg_holds_no_downgrade ON holds;",
    """
    CREATE TRIGGER trg_holds_no_downgrade BEFORE UPDATE ON holds
    FOR EACH ROW WHEN (OLD.immutable = 1)
    EXECUTE FUNCTION dbx_refuse('HOLD_REMOVAL_FORBIDDEN');
    """,
    "DROP TRIGGER IF EXISTS trg_commands_no_transcript_rewrite ON commands;",
    """
    CREATE TRIGGER trg_commands_no_transcript_rewrite
    BEFORE UPDATE OF transcript_text, transcript_sha256, idempotency_key ON commands
    FOR EACH ROW WHEN (OLD.transcript_sha256 IS NOT NULL
        AND (NEW.transcript_sha256 <> OLD.transcript_sha256
             OR NEW.idempotency_key <> OLD.idempotency_key))
    EXECUTE FUNCTION dbx_refuse('COMMAND_IMMUTABLE');
    """,
    "DROP TRIGGER IF EXISTS trg_artifact_version_accepted_immutable ON artifact_versions;",
    """
    CREATE TRIGGER trg_artifact_version_accepted_immutable
    BEFORE UPDATE ON artifact_versions
    FOR EACH ROW WHEN (OLD.accepted = 1)
    EXECUTE FUNCTION dbx_refuse('ACCEPTED_ARTIFACT_IMMUTABLE');
    """,
    "DROP TRIGGER IF EXISTS trg_artifact_version_accepted_no_delete ON artifact_versions;",
    """
    CREATE TRIGGER trg_artifact_version_accepted_no_delete
    BEFORE DELETE ON artifact_versions
    FOR EACH ROW WHEN (OLD.accepted = 1)
    EXECUTE FUNCTION dbx_refuse('ACCEPTED_ARTIFACT_IMMUTABLE');
    """,
    "DROP TRIGGER IF EXISTS trg_audit_no_update ON audit_events;",
    """
    CREATE TRIGGER trg_audit_no_update BEFORE UPDATE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION dbx_refuse('AUDIT_APPEND_ONLY');
    """,
    "DROP TRIGGER IF EXISTS trg_audit_no_delete ON audit_events;",
    """
    CREATE TRIGGER trg_audit_no_delete BEFORE DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION dbx_refuse('AUDIT_APPEND_ONLY');
    """,
)


def migrations_for(dialect: str) -> list:
    serial = SERIAL_SQL[dialect]
    statements = [table.replace("{serial}", serial) for table in TABLES]
    statements.extend(TRIGGERS_SQLITE if dialect == DIALECT_SQLITE else TRIGGERS_POSTGRES)
    return statements


#: Preserved for callers that only ever used SQLite.
MIGRATIONS: tuple = tuple(migrations_for(DIALECT_SQLITE))


def migrate(conn) -> None:
    """Apply all migrations. Idempotent -- safe to run on every start."""
    dialect = getattr(conn, "dialect", DIALECT_SQLITE)
    conn.execute(begin_sql(dialect))
    try:
        for statement in migrations_for(dialect):
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise


class RowMissing(LookupError):
    """A row the caller had proven must exist was not there.

    Raised instead of letting ``None`` propagate into an index or ``dict()``,
    so a broken invariant surfaces at its source rather than as an obscure
    ``TypeError`` further along.
    """


def require_row(row: Optional[Row], what: str) -> Row:
    if row is None:
        raise RowMissing(f"expected exactly one row for {what}, found none")
    return row


def fetchone(conn, sql: str, params: Iterable = ()) -> Optional[Row]:
    cur = conn.execute(sql, tuple(params))
    try:
        return cur.fetchone()
    finally:
        cur.close()


def fetchall(conn, sql: str, params: Iterable = ()) -> List[Row]:
    cur = conn.execute(sql, tuple(params))
    try:
        return cur.fetchall()
    finally:
        cur.close()
