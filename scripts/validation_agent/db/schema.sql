-- DataBossX Validation Agent — append-only audit schema.
-- Protected tables reject UPDATE and DELETE at the database level via triggers,
-- so even a raw sqlite3 connection that bypasses the Python authorizer cannot
-- mutate history. INSERT and SELECT are the only permitted operations.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    workbook_path TEXT,
    workbook_sha256 TEXT,
    prospect TEXT,
    mode TEXT NOT NULL,            -- dry_run | live
    config_snapshot TEXT NOT NULL,-- redacted JSON
    final_status TEXT             -- NULL until terminal; CERTIFY|ESCALATE|MAX_ITERATIONS
);

CREATE TABLE IF NOT EXISTS workbook_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    version_index INTEGER NOT NULL,   -- 0 = v0 baseline
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    event_type TEXT NOT NULL,
    state TEXT,
    payload TEXT,                  -- JSON
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL,          -- PASS|FAIL|ESCALATE|ERROR
    severity TEXT NOT NULL,
    repairable INTEGER NOT NULL,
    affected_sheet TEXT,
    affected_range TEXT,
    affected_subject TEXT,
    evidence TEXT,
    reason TEXT,
    recommended_action TEXT,
    confidence REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS spend_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    description TEXT NOT NULL,
    amount_usd TEXT NOT NULL,      -- Decimal as text
    cumulative_usd TEXT NOT NULL,  -- Decimal as text
    allowed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    service TEXT NOT NULL,
    endpoint TEXT,
    paid INTEGER NOT NULL,
    estimated_cost_usd TEXT,
    outcome TEXT NOT NULL,         -- executed|blocked|dry_run|error
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automated_repairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    failure_class TEXT NOT NULL,
    target_sheet TEXT,
    target_range TEXT,
    from_version TEXT,
    to_version TEXT,
    before_sha256 TEXT,
    after_sha256 TEXT,
    action TEXT NOT NULL,
    evidence TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    gate_name TEXT,
    failure_class TEXT NOT NULL,
    subject TEXT,
    reason TEXT NOT NULL,
    needed_document TEXT,
    recommended_action TEXT,
    priority TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    book_page TEXT,
    instrument_number TEXT,
    parties TEXT,
    legal_description TEXT,
    doc_type TEXT,
    status TEXT NOT NULL,          -- queued|found_local|retrieved|blocked|unavailable
    origin TEXT,                   -- local|run_cache|okcounty|configured_dir
    local_path TEXT,
    sha256 TEXT,
    cost_usd TEXT,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL,           -- markdown|pdf|json|docx|zip|db_copy
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    source_report TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS launcher_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

-- ------------------------------------------------------------------ triggers
-- Block UPDATE and DELETE on every protected table at the DB engine level.
CREATE TRIGGER IF NOT EXISTS block_update_runs BEFORE UPDATE ON runs
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on runs'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_runs BEFORE DELETE ON runs
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on runs'); END;

CREATE TRIGGER IF NOT EXISTS block_update_wv BEFORE UPDATE ON workbook_versions
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on workbook_versions'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_wv BEFORE DELETE ON workbook_versions
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on workbook_versions'); END;

CREATE TRIGGER IF NOT EXISTS block_update_ae BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on audit_events'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_ae BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on audit_events'); END;

CREATE TRIGGER IF NOT EXISTS block_update_vr BEFORE UPDATE ON validation_results
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on validation_results'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_vr BEFORE DELETE ON validation_results
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on validation_results'); END;

CREATE TRIGGER IF NOT EXISTS block_update_sl BEFORE UPDATE ON spend_ledger
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on spend_ledger'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_sl BEFORE DELETE ON spend_ledger
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on spend_ledger'); END;

CREATE TRIGGER IF NOT EXISTS block_update_ac BEFORE UPDATE ON api_calls
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on api_calls'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_ac BEFORE DELETE ON api_calls
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on api_calls'); END;

CREATE TRIGGER IF NOT EXISTS block_update_ar BEFORE UPDATE ON automated_repairs
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on automated_repairs'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_ar BEFORE DELETE ON automated_repairs
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on automated_repairs'); END;

CREATE TRIGGER IF NOT EXISTS block_update_es BEFORE UPDATE ON escalations
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on escalations'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_es BEFORE DELETE ON escalations
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on escalations'); END;

CREATE TRIGGER IF NOT EXISTS block_update_sd BEFORE UPDATE ON source_documents
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on source_documents'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_sd BEFORE DELETE ON source_documents
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on source_documents'); END;

CREATE TRIGGER IF NOT EXISTS block_update_re BEFORE UPDATE ON report_exports
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on report_exports'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_re BEFORE DELETE ON report_exports
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on report_exports'); END;

CREATE TRIGGER IF NOT EXISTS block_update_le BEFORE UPDATE ON launcher_events
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on launcher_events'); END;
CREATE TRIGGER IF NOT EXISTS block_delete_le BEFORE DELETE ON launcher_events
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on launcher_events'); END;
