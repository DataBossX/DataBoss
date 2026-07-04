-- DataBossX validation agent — append-only schema.
-- Every table is an immutable event log. No column is ever updated in place.
-- Corrections are new rows that supersede prior rows by timestamp / id.
--
-- Append-only enforcement is layered:
--   1. A SQLite authorizer in db_client.py rejects UPDATE/DELETE/DROP/etc.
--   2. The triggers below are a defense-in-depth backstop that raise on any
--      UPDATE or DELETE attempted through a connection that bypassed the
--      authorizer (e.g. a raw sqlite3 connection).

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- --------------------------------------------------------------------------
-- runs: one row per validation run.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    run_folder TEXT NOT NULL,
    workbook_source_path TEXT,
    workbook_source_sha256 TEXT,
    status TEXT NOT NULL,
    state TEXT,
    iteration INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- workbook_versions: immutable version chain for each run.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workbook_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    version_index INTEGER NOT NULL,
    version_label TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    origin TEXT NOT NULL,               -- source_copy | repair | recalc
    parent_version_index INTEGER,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- audit_events: general append-only audit trail.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    event_type TEXT NOT NULL,
    subject TEXT,
    detail TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- validation_results: one row per gate evaluation.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    iteration INTEGER NOT NULL DEFAULT 0,
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL,               -- PASS | FAIL | ESCALATE | SKIP
    severity TEXT NOT NULL,
    repairable INTEGER NOT NULL DEFAULT 0,
    affected_sheet TEXT,
    affected_cell_or_range TEXT,
    affected_subject TEXT,
    evidence TEXT,
    reason TEXT,
    recommended_action TEXT,
    confidence REAL,
    failure_category TEXT,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- spend_ledger: append-only money log. Balance == SUM(amount_usd).
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS spend_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    decision TEXT NOT NULL,             -- ALLOWED | BLOCKED
    reason TEXT,
    proposed_amount_usd TEXT NOT NULL,
    amount_usd TEXT NOT NULL,           -- actually committed (0 if blocked)
    description TEXT,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- api_calls: record of every external call attempt.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    provider TEXT NOT NULL,
    endpoint TEXT,
    mode TEXT NOT NULL,                 -- dry_run | live
    outcome TEXT NOT NULL,              -- allowed | blocked | auth_failure | error
    cost_usd TEXT NOT NULL DEFAULT '0.00',
    detail TEXT,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- automated_repairs: each attempted/executed repair, immutable.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS automated_repairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    iteration INTEGER NOT NULL DEFAULT 0,
    repair_type TEXT NOT NULL,
    gate_name TEXT,
    target_sheet TEXT,
    target_cell_or_range TEXT,
    from_version_index INTEGER,
    to_version_index INTEGER,
    status TEXT NOT NULL,               -- planned | applied | rolled_back | blocked
    detail TEXT,
    before_sha256 TEXT,
    after_sha256 TEXT,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- escalations: human escalation queue (append-only).
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    failed_gate TEXT NOT NULL,
    workbook_location TEXT,
    subject TEXT,
    sources_checked TEXT,
    sources_missing TEXT,
    checks_attempted TEXT,
    reason_repair_blocked TEXT,
    recommended_examiner_action TEXT,
    urgency TEXT NOT NULL,
    failure_category TEXT,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- source_documents: every source doc checked/found/missing/blocked/failed.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    reference_key TEXT,
    reference_type TEXT,                -- book_page | instrument | party | well | ...
    status TEXT NOT NULL,               -- checked | found | missing | blocked | failed
    file_path TEXT,
    sha256 TEXT,
    source TEXT,                        -- local | run | api | cache
    detail TEXT,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- report_exports: every generated report/export artifact.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS report_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    export_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

-- --------------------------------------------------------------------------
-- launcher_events: desktop launcher / dashboard lifecycle log.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS launcher_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

-- ==========================================================================
-- VIEWS
-- ==========================================================================
CREATE VIEW IF NOT EXISTS spend_summary AS
SELECT
    COALESCE(run_id, '(global)') AS run_id,
    COUNT(*) AS ledger_entries,
    SUM(CASE WHEN decision = 'ALLOWED' THEN 1 ELSE 0 END) AS allowed_count,
    SUM(CASE WHEN decision = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked_count,
    printf('%.2f', COALESCE(SUM(CAST(amount_usd AS REAL)), 0)) AS total_spent_usd
FROM spend_ledger
GROUP BY run_id;

CREATE VIEW IF NOT EXISTS validation_scorecard AS
SELECT
    run_id,
    iteration,
    gate_name,
    status,
    severity,
    repairable,
    confidence,
    created_at
FROM validation_results vr
WHERE vr.id = (
    SELECT MAX(id) FROM validation_results v2
    WHERE v2.run_id = vr.run_id AND v2.gate_name = vr.gate_name
);

CREATE VIEW IF NOT EXISTS latest_run_status AS
SELECT r.run_id, r.status, r.state, r.iteration, r.run_folder, r.created_at
FROM runs r
WHERE r.id = (
    SELECT MAX(id) FROM runs r2 WHERE r2.run_id = r.run_id
);

CREATE VIEW IF NOT EXISTS open_escalations AS
SELECT run_id, failed_gate, subject, urgency, failure_category,
       recommended_examiner_action, created_at
FROM escalations
ORDER BY created_at DESC;

-- ==========================================================================
-- DEFENSE-IN-DEPTH TRIGGERS (backstop for raw-sqlite bypass)
-- ==========================================================================
CREATE TRIGGER IF NOT EXISTS runs_no_update BEFORE UPDATE ON runs
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on runs'); END;
CREATE TRIGGER IF NOT EXISTS runs_no_delete BEFORE DELETE ON runs
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on runs'); END;

CREATE TRIGGER IF NOT EXISTS workbook_versions_no_update BEFORE UPDATE ON workbook_versions
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on workbook_versions'); END;
CREATE TRIGGER IF NOT EXISTS workbook_versions_no_delete BEFORE DELETE ON workbook_versions
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on workbook_versions'); END;

CREATE TRIGGER IF NOT EXISTS audit_events_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on audit_events'); END;
CREATE TRIGGER IF NOT EXISTS audit_events_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on audit_events'); END;

CREATE TRIGGER IF NOT EXISTS validation_results_no_update BEFORE UPDATE ON validation_results
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on validation_results'); END;
CREATE TRIGGER IF NOT EXISTS validation_results_no_delete BEFORE DELETE ON validation_results
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on validation_results'); END;

CREATE TRIGGER IF NOT EXISTS spend_ledger_no_update BEFORE UPDATE ON spend_ledger
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on spend_ledger'); END;
CREATE TRIGGER IF NOT EXISTS spend_ledger_no_delete BEFORE DELETE ON spend_ledger
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on spend_ledger'); END;

CREATE TRIGGER IF NOT EXISTS api_calls_no_update BEFORE UPDATE ON api_calls
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on api_calls'); END;
CREATE TRIGGER IF NOT EXISTS api_calls_no_delete BEFORE DELETE ON api_calls
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on api_calls'); END;

CREATE TRIGGER IF NOT EXISTS automated_repairs_no_update BEFORE UPDATE ON automated_repairs
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on automated_repairs'); END;
CREATE TRIGGER IF NOT EXISTS automated_repairs_no_delete BEFORE DELETE ON automated_repairs
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on automated_repairs'); END;

CREATE TRIGGER IF NOT EXISTS escalations_no_update BEFORE UPDATE ON escalations
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on escalations'); END;
CREATE TRIGGER IF NOT EXISTS escalations_no_delete BEFORE DELETE ON escalations
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on escalations'); END;

CREATE TRIGGER IF NOT EXISTS source_documents_no_update BEFORE UPDATE ON source_documents
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on source_documents'); END;
CREATE TRIGGER IF NOT EXISTS source_documents_no_delete BEFORE DELETE ON source_documents
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on source_documents'); END;

CREATE TRIGGER IF NOT EXISTS report_exports_no_update BEFORE UPDATE ON report_exports
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on report_exports'); END;
CREATE TRIGGER IF NOT EXISTS report_exports_no_delete BEFORE DELETE ON report_exports
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on report_exports'); END;

CREATE TRIGGER IF NOT EXISTS launcher_events_no_update BEFORE UPDATE ON launcher_events
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE forbidden on launcher_events'); END;
CREATE TRIGGER IF NOT EXISTS launcher_events_no_delete BEFORE DELETE ON launcher_events
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE forbidden on launcher_events'); END;
