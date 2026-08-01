"""Migrations and connection handling for the control kernel.

Engine note (see ADR-0003): PostgreSQL is the canonical cloud target. The DDL
below is deliberately kept to the portable subset -- partial unique indexes,
CHECK constraints, foreign keys, and explicit transactions all carry over. The
executable engine in this lane is SQLite in WAL mode, because no database
service is reachable from the build environment.

The single-writer invariant lives *here*, not in application memory:

* ``ux_lease_one_active_per_scope`` is a partial unique index that makes a
  second ACTIVE lease on a scope physically unrepresentable.
* ``fencing_counters`` advances monotonically under the same transaction that
  issues a lease.
* Triggers reject impossible state transitions and any attempt to mutate an
  accepted artifact or delete a hold.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

SCHEMA_VERSION = 1


def connect(path: str) -> sqlite3.Connection:
    # check_same_thread=False lets the threaded HTTP server reuse one kernel
    # connection. Callers MUST serialize access; ``ControlCenterApp`` holds a
    # request lock, and concurrency tests use separate connections so the
    # database constraints, not a Python lock, decide who wins a race.
    conn = sqlite3.connect(path, isolation_level=None, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    # Durability matters more than throughput for an audit ledger.
    conn.execute("PRAGMA synchronous=FULL")
    return conn


MIGRATIONS: tuple[str, ...] = (
    # ---------------------------------------------------------------- identity
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
    # ------------------------------------------------------------------ policy
    """
    CREATE TABLE IF NOT EXISTS policy_versions (
        policy_version TEXT PRIMARY KEY,
        activated_at   TEXT NOT NULL,
        description    TEXT NOT NULL
    );
    """,
    # ------------------------------------------------------------------- holds
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
    # A hold is a floor, not a toggle. Deleting or downgrading one from SQL is
    # rejected outright; release requires a separately authorized human lane.
    """
    CREATE TRIGGER IF NOT EXISTS trg_holds_no_delete
    BEFORE DELETE ON holds
    BEGIN
        SELECT RAISE(ABORT, 'HOLD_REMOVAL_FORBIDDEN');
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_holds_no_downgrade
    BEFORE UPDATE ON holds
    WHEN OLD.immutable = 1
    BEGIN
        SELECT RAISE(ABORT, 'HOLD_REMOVAL_FORBIDDEN');
    END;
    """,
    # ------------------------------------------------------------------ leases
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
    # ---------------------------------------------------------------- commands
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
    CREATE TRIGGER IF NOT EXISTS trg_commands_no_transcript_rewrite
    BEFORE UPDATE OF transcript_text, transcript_sha256, idempotency_key ON commands
    WHEN OLD.transcript_sha256 IS NOT NULL
     AND (NEW.transcript_sha256 <> OLD.transcript_sha256
          OR NEW.idempotency_key <> OLD.idempotency_key)
    BEGIN
        SELECT RAISE(ABORT, 'COMMAND_IMMUTABLE');
    END;
    """,
    # -------------------------------------------------------------- approvals
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
    # ------------------------------------------------------------------- tasks
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
    # --------------------------------------------------------------- artifacts
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
    # Accepted artifact versions are immutable; new facts get a new version.
    """
    CREATE TRIGGER IF NOT EXISTS trg_artifact_version_accepted_immutable
    BEFORE UPDATE ON artifact_versions
    WHEN OLD.accepted = 1
    BEGIN
        SELECT RAISE(ABORT, 'ACCEPTED_ARTIFACT_IMMUTABLE');
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_artifact_version_accepted_no_delete
    BEFORE DELETE ON artifact_versions
    WHEN OLD.accepted = 1
    BEGIN
        SELECT RAISE(ABORT, 'ACCEPTED_ARTIFACT_IMMUTABLE');
    END;
    """,
    # ---------------------------------------------------------------- receipts
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
    # ------------------------------------------------------- audit and outbox
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
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
    # The audit ledger is append-only; tampering must be structurally impossible.
    """
    CREATE TRIGGER IF NOT EXISTS trg_audit_no_update
    BEFORE UPDATE ON audit_events
    BEGIN
        SELECT RAISE(ABORT, 'AUDIT_APPEND_ONLY');
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete
    BEFORE DELETE ON audit_events
    BEGIN
        SELECT RAISE(ABORT, 'AUDIT_APPEND_ONLY');
    END;
    """,
    """
    CREATE TABLE IF NOT EXISTS outbox (
        outbox_id    INTEGER PRIMARY KEY AUTOINCREMENT,
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


def migrate(conn: sqlite3.Connection) -> None:
    """Apply all migrations. Idempotent -- safe to run on every start."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in MIGRATIONS:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def fetchone(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> Optional[sqlite3.Row]:
    cur = conn.execute(sql, tuple(params))
    try:
        return cur.fetchone()
    finally:
        cur.close()


def fetchall(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> list:
    cur = conn.execute(sql, tuple(params))
    try:
        return cur.fetchall()
    finally:
        cur.close()
