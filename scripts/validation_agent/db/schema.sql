-- DataBossX Validation Agent - append-only audit schema
-- Every protected table is INSERT + SELECT only. UPDATE and DELETE are
-- blocked at the database level by BEFORE triggers (defense that survives
-- even a raw sqlite3 connection that bypasses the Python authorizer).

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- 1. runs -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL UNIQUE,
    workbook_name TEXT,
    workbook_hash TEXT,
    run_dir       TEXT,
    mode          TEXT,               -- dry_run | live
    status        TEXT,               -- INIT | RUNNING | CERTIFIED | ESCALATED | MAX_ITERATIONS | ERROR
    final_state   TEXT,
    started_at    TEXT DEFAULT (datetime('now')),
    ended_at      TEXT
);

-- NOTE: runs.status/final_state/ended_at are set once via a fresh INSERT of a
-- run_lifecycle event; the runs row itself is written append-only. To record
-- terminal status we INSERT a new runs row is NOT done; instead terminal info
-- is written to audit_events. runs row is inserted once at start with status
-- INIT and the terminal status is derived from audit_events. (No UPDATE.)

-- 2. workbook_versions ------------------------------------------------------
CREATE TABLE IF NOT EXISTS workbook_versions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT NOT NULL,
    version_label  TEXT NOT NULL,     -- v0, v001, v002...
    file_name      TEXT NOT NULL,
    file_path      TEXT NOT NULL,
    sha256         TEXT NOT NULL,
    size_bytes     INTEGER,
    origin         TEXT,              -- baseline | repair | recalc
    note           TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);

-- 3. audit_events -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT,
    event_type  TEXT NOT NULL,
    state       TEXT,
    description TEXT,
    data_json   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- 4. validation_results -----------------------------------------------------
CREATE TABLE IF NOT EXISTS validation_results (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                TEXT NOT NULL,
    iteration             INTEGER DEFAULT 0,
    gate_name             TEXT NOT NULL,
    status                TEXT NOT NULL,   -- PASS | FAIL | ESCALATE | ERROR
    severity              TEXT,
    repairable            INTEGER DEFAULT 0,
    affected_sheet        TEXT,
    affected_cell_or_range TEXT,
    affected_subject      TEXT,
    evidence              TEXT,
    reason                TEXT,
    recommended_action    TEXT,
    confidence            REAL,
    created_at            TEXT DEFAULT (datetime('now'))
);

-- 5. spend_ledger -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS spend_ledger (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT,
    kind           TEXT,              -- search | document | other
    description    TEXT,
    amount_usd     REAL NOT NULL,
    cumulative_usd REAL NOT NULL,
    approved       INTEGER DEFAULT 0,
    created_at     TEXT DEFAULT (datetime('now'))
);

-- 6. api_calls --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_calls (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT,
    provider     TEXT,
    endpoint     TEXT,
    request_meta TEXT,
    outcome      TEXT,               -- ok | blocked | error
    cost_usd     REAL DEFAULT 0.0,
    created_at   TEXT DEFAULT (datetime('now'))
);

-- 7. automated_repairs ------------------------------------------------------
CREATE TABLE IF NOT EXISTS automated_repairs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL,
    iteration         INTEGER DEFAULT 0,
    repair_type       TEXT,
    target_sheet      TEXT,
    target_cell       TEXT,
    before_value      TEXT,
    after_value       TEXT,
    from_version      TEXT,
    to_version        TEXT,
    evidence          TEXT,
    status            TEXT,           -- applied | rolled_back | skipped
    created_at        TEXT DEFAULT (datetime('now'))
);

-- 8. escalations ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS escalations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    category      TEXT,
    severity      TEXT,
    subject       TEXT,
    gate_name     TEXT,
    reason        TEXT,
    evidence      TEXT,
    recommended_action TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

-- 9. source_documents -------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_documents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL,
    reference_key    TEXT,            -- book/page or instrument number
    doc_type         TEXT,
    county           TEXT,
    party_names      TEXT,
    status           TEXT,            -- found_local | retrieved | queued | blocked | missing
    source_origin    TEXT,            -- local | run_cache | okcounty | none
    file_path        TEXT,
    sha256           TEXT,
    cost_usd         REAL DEFAULT 0.0,
    note             TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

-- 10. report_exports --------------------------------------------------------
CREATE TABLE IF NOT EXISTS report_exports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    export_type  TEXT,               -- markdown | pdf | json | docx | zip | db_copy
    file_name    TEXT,
    file_path    TEXT,
    sha256       TEXT,
    note         TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

-- 11. launcher_events -------------------------------------------------------
CREATE TABLE IF NOT EXISTS launcher_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT,
    description TEXT,
    data_json   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------------------- --
-- Append-only enforcement triggers. Generated for every protected table.
-- These fire even for a raw sqlite3 connection, so they are the durable line
-- of defense (the Python authorizer is only the first line).
-- ------------------------------------------------------------------------- --

CREATE TRIGGER IF NOT EXISTS trg_no_update_runs BEFORE UPDATE ON runs
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on runs'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_runs BEFORE DELETE ON runs
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on runs'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_workbook_versions BEFORE UPDATE ON workbook_versions
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on workbook_versions'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_workbook_versions BEFORE DELETE ON workbook_versions
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on workbook_versions'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_audit_events BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on audit_events'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_audit_events BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on audit_events'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_validation_results BEFORE UPDATE ON validation_results
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on validation_results'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_validation_results BEFORE DELETE ON validation_results
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on validation_results'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_spend_ledger BEFORE UPDATE ON spend_ledger
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on spend_ledger'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_spend_ledger BEFORE DELETE ON spend_ledger
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on spend_ledger'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_api_calls BEFORE UPDATE ON api_calls
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on api_calls'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_api_calls BEFORE DELETE ON api_calls
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on api_calls'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_automated_repairs BEFORE UPDATE ON automated_repairs
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on automated_repairs'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_automated_repairs BEFORE DELETE ON automated_repairs
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on automated_repairs'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_escalations BEFORE UPDATE ON escalations
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on escalations'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_escalations BEFORE DELETE ON escalations
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on escalations'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_source_documents BEFORE UPDATE ON source_documents
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on source_documents'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_source_documents BEFORE DELETE ON source_documents
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on source_documents'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_report_exports BEFORE UPDATE ON report_exports
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on report_exports'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_report_exports BEFORE DELETE ON report_exports
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on report_exports'); END;

CREATE TRIGGER IF NOT EXISTS trg_no_update_launcher_events BEFORE UPDATE ON launcher_events
BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE blocked on launcher_events'); END;
CREATE TRIGGER IF NOT EXISTS trg_no_delete_launcher_events BEFORE DELETE ON launcher_events
BEGIN SELECT RAISE(ABORT, 'append-only: DELETE blocked on launcher_events'); END;
