-- DataBossX Validation Agent — append-only schema.
-- Every protected table has BEFORE UPDATE / BEFORE DELETE triggers that ABORT.
-- Triggers live in the database file, so they fire even for a raw sqlite3
-- connection that bypasses the application authorizer.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    workbook_name TEXT,
    workbook_sha256 TEXT,
    run_folder TEXT,
    mode TEXT,               -- dry-run / live
    status TEXT,             -- INIT / RUNNING / CERTIFIED / ESCALATED / MAX_ITERATIONS / ERROR
    final_state TEXT,
    iterations INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS workbook_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    version_label TEXT NOT NULL,     -- v0 / v001 / v002 ...
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER,
    origin TEXT,                     -- baseline / repair / recalc
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    event_type TEXT NOT NULL,
    component TEXT,
    message TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    iteration INTEGER DEFAULT 0,
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL,            -- PASS / FAIL / ESCALATE / ERROR
    severity TEXT,
    repairable INTEGER DEFAULT 0,
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
    kind TEXT,                       -- estimate / charge / blocked
    amount_usd TEXT NOT NULL,        -- stored as text to preserve Decimal exactness
    cumulative_usd TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    provider TEXT,
    endpoint TEXT,
    request_summary TEXT,
    outcome TEXT,                    -- ok / blocked / error / dry-run
    cost_usd TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automated_repairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    iteration INTEGER DEFAULT 0,
    repair_type TEXT,
    target_sheet TEXT,
    target_range TEXT,
    before_value TEXT,
    after_value TEXT,
    from_version TEXT,
    to_version TEXT,
    justification TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    category TEXT NOT NULL,
    subject TEXT,
    detail TEXT,
    evidence TEXT,
    recommended_action TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    doc_kind TEXT,                   -- book_page / instrument / lease / assignment / well / probate
    reference TEXT,                  -- e.g. 1736/0592 or 2019-001855
    description TEXT,
    status TEXT,                     -- missing / found_local / retrieved / blocked / unverifiable
    file_path TEXT,
    sha256 TEXT,
    source TEXT,                     -- local / cache / okcounty / examiner
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    report_type TEXT,
    file_path TEXT NOT NULL,
    sha256 TEXT,
    version_label TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS launcher_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

-- ---- Append-only enforcement triggers ----
-- One BEFORE UPDATE and BEFORE DELETE guard per protected table.

CREATE TRIGGER IF NOT EXISTS trg_runs_no_update
BEFORE UPDATE ON runs
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on runs');
END;

CREATE TRIGGER IF NOT EXISTS trg_runs_no_delete
BEFORE DELETE ON runs
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on runs');
END;

CREATE TRIGGER IF NOT EXISTS trg_workbook_versions_no_update
BEFORE UPDATE ON workbook_versions
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on workbook_versions');
END;

CREATE TRIGGER IF NOT EXISTS trg_workbook_versions_no_delete
BEFORE DELETE ON workbook_versions
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on workbook_versions');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on audit_events');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on audit_events');
END;

CREATE TRIGGER IF NOT EXISTS trg_validation_results_no_update
BEFORE UPDATE ON validation_results
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on validation_results');
END;

CREATE TRIGGER IF NOT EXISTS trg_validation_results_no_delete
BEFORE DELETE ON validation_results
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on validation_results');
END;

CREATE TRIGGER IF NOT EXISTS trg_spend_ledger_no_update
BEFORE UPDATE ON spend_ledger
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on spend_ledger');
END;

CREATE TRIGGER IF NOT EXISTS trg_spend_ledger_no_delete
BEFORE DELETE ON spend_ledger
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on spend_ledger');
END;

CREATE TRIGGER IF NOT EXISTS trg_api_calls_no_update
BEFORE UPDATE ON api_calls
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on api_calls');
END;

CREATE TRIGGER IF NOT EXISTS trg_api_calls_no_delete
BEFORE DELETE ON api_calls
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on api_calls');
END;

CREATE TRIGGER IF NOT EXISTS trg_automated_repairs_no_update
BEFORE UPDATE ON automated_repairs
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on automated_repairs');
END;

CREATE TRIGGER IF NOT EXISTS trg_automated_repairs_no_delete
BEFORE DELETE ON automated_repairs
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on automated_repairs');
END;

CREATE TRIGGER IF NOT EXISTS trg_escalations_no_update
BEFORE UPDATE ON escalations
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on escalations');
END;

CREATE TRIGGER IF NOT EXISTS trg_escalations_no_delete
BEFORE DELETE ON escalations
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on escalations');
END;

CREATE TRIGGER IF NOT EXISTS trg_source_documents_no_update
BEFORE UPDATE ON source_documents
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on source_documents');
END;

CREATE TRIGGER IF NOT EXISTS trg_source_documents_no_delete
BEFORE DELETE ON source_documents
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on source_documents');
END;

CREATE TRIGGER IF NOT EXISTS trg_report_exports_no_update
BEFORE UPDATE ON report_exports
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on report_exports');
END;

CREATE TRIGGER IF NOT EXISTS trg_report_exports_no_delete
BEFORE DELETE ON report_exports
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on report_exports');
END;

CREATE TRIGGER IF NOT EXISTS trg_launcher_events_no_update
BEFORE UPDATE ON launcher_events
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE blocked on launcher_events');
END;

CREATE TRIGGER IF NOT EXISTS trg_launcher_events_no_delete
BEFORE DELETE ON launcher_events
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE blocked on launcher_events');
END;
