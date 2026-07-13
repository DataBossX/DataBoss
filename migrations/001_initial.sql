-- 001_initial.sql
-- Initial DataBossX trusted-kernel schema.
-- Covers core evidence/memory entities, work/task-graph entities, and the
-- title-product extensions, plus an FTS5 index over evidence span text.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    number      INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Core evidence & memory
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS projects (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    jurisdiction        TEXT NOT NULL,
    policy_set          TEXT NOT NULL,
    confidentiality     TEXT NOT NULL,
    lifecycle_state     TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_connections (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    provider            TEXT NOT NULL,
    root_path           TEXT NOT NULL,
    capabilities        TEXT NOT NULL DEFAULT '[]',
    credential_ref      TEXT
);

CREATE TABLE IF NOT EXISTS source_snapshots (
    id                  TEXT PRIMARY KEY,
    connection_id       TEXT NOT NULL REFERENCES source_connections(id),
    cursor              TEXT,
    scan_time           TEXT NOT NULL,
    completeness        TEXT NOT NULL,
    manifest_hash       TEXT NOT NULL,
    status              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    snapshot_id         TEXT NOT NULL REFERENCES source_snapshots(id),
    logical_path        TEXT NOT NULL,
    mime_type           TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_versions (
    id                  TEXT PRIMARY KEY,
    asset_id            TEXT NOT NULL REFERENCES assets(id),
    locator             TEXT NOT NULL,
    provider_version    TEXT,
    byte_hash           TEXT NOT NULL,
    size_bytes          INTEGER NOT NULL,
    custody_time        TEXT NOT NULL,
    vault_path          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS derived_artifacts (
    id                          TEXT PRIMARY KEY,
    parent_asset_version_ids    TEXT NOT NULL DEFAULT '[]',
    recipe_version              TEXT NOT NULL,
    artifact_type               TEXT NOT NULL,
    vault_path                  TEXT NOT NULL,
    byte_hash                   TEXT NOT NULL,
    created_at                  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_spans (
    id                  TEXT PRIMARY KEY,
    asset_version_id    TEXT NOT NULL REFERENCES asset_versions(id),
    page_or_sheet       TEXT,
    row_or_region       TEXT,
    text_excerpt        TEXT NOT NULL,
    char_start          INTEGER,
    char_end            INTEGER,
    bbox_json           TEXT,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    subject             TEXT NOT NULL,
    predicate           TEXT NOT NULL,
    value               TEXT NOT NULL,
    value_state         TEXT NOT NULL CHECK (value_state IN
                            ('proved', 'qualified', 'assumed', 'missing',
                             'unknown', 'inferred', 'externally_researched')),
    confidence          REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source_span_ids     TEXT NOT NULL DEFAULT '[]',
    created_at          TEXT NOT NULL,
    revised_at          TEXT,
    revision_of         TEXT REFERENCES claims(id)
);

CREATE TABLE IF NOT EXISTS claim_supports (
    id                      TEXT PRIMARY KEY,
    claim_id                TEXT NOT NULL REFERENCES claims(id),
    span_id                 TEXT NOT NULL REFERENCES evidence_spans(id),
    support_rule_version    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conflicts (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    claim_ids           TEXT NOT NULL DEFAULT '[]',
    materiality         TEXT NOT NULL CHECK (materiality IN ('high', 'medium', 'low')),
    resolution_note     TEXT,
    resolved_by         TEXT,
    resolved_at         TEXT
);

-- ---------------------------------------------------------------------------
-- Work entities
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    version             TEXT NOT NULL,
    description         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id                  TEXT PRIMARY KEY,
    workflow_id         TEXT NOT NULL REFERENCES workflow_definitions(id),
    project_id          TEXT NOT NULL REFERENCES projects(id),
    status              TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    metadata_json       TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(id),
    name                TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN
                            ('PLANNED', 'BLOCKED', 'READY', 'LEASED', 'RUNNING',
                             'WAITING_HUMAN', 'SUCCEEDED', 'FAILED_RETRYABLE',
                             'FAILED_TERMINAL')),
    worker_type         TEXT NOT NULL,
    input_json          TEXT NOT NULL,
    output_json         TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    lease_expires_at    TEXT,
    attempt_count       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    upstream_task_id    TEXT NOT NULL REFERENCES tasks(id),
    downstream_task_id  TEXT NOT NULL REFERENCES tasks(id),
    PRIMARY KEY (upstream_task_id, downstream_task_id)
);

CREATE TABLE IF NOT EXISTS task_attempts (
    id                  TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL REFERENCES tasks(id),
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    outcome             TEXT,
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS task_leases (
    id                  TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL REFERENCES tasks(id),
    worker_id           TEXT NOT NULL,
    granted_at          TEXT NOT NULL,
    expires_at          TEXT NOT NULL,
    heartbeat_at        TEXT
);

CREATE TABLE IF NOT EXISTS worker_capabilities (
    id                  TEXT PRIMARY KEY,
    worker_type         TEXT NOT NULL,
    capability          TEXT NOT NULL,
    version             TEXT NOT NULL,
    description         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_gates (
    id                      TEXT PRIMARY KEY,
    task_id                 TEXT NOT NULL REFERENCES tasks(id),
    gate_type               TEXT NOT NULL,
    required_role           TEXT NOT NULL,
    prompt_for_reviewer     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_decisions (
    id                  TEXT PRIMARY KEY,
    gate_id             TEXT NOT NULL REFERENCES review_gates(id),
    reviewer            TEXT NOT NULL,
    decision            TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'deferred')),
    note                TEXT,
    decided_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id                  TEXT PRIMARY KEY,
    gate_id             TEXT NOT NULL REFERENCES review_gates(id),
    decision_id         TEXT NOT NULL REFERENCES review_decisions(id),
    artifact_hash       TEXT NOT NULL,
    artifact_type       TEXT NOT NULL,
    approved_by         TEXT NOT NULL,
    approved_at         TEXT NOT NULL,
    expires_at          TEXT
);

CREATE TABLE IF NOT EXISTS artifact_versions (
    id                  TEXT PRIMARY KEY,
    artifact_type       TEXT NOT NULL,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    vault_path          TEXT NOT NULL,
    byte_hash           TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    approved            INTEGER NOT NULL DEFAULT 0,
    approval_id         TEXT REFERENCES approvals(id)
);

CREATE TABLE IF NOT EXISTS model_route_decisions (
    id                  TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL REFERENCES tasks(id),
    provider            TEXT NOT NULL,
    model_name          TEXT NOT NULL,
    reason              TEXT NOT NULL,
    input_hash          TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_definitions (
    id                      TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    version                 TEXT NOT NULL,
    description             TEXT NOT NULL,
    schema_json             TEXT NOT NULL,
    max_privilege_level     TEXT NOT NULL CHECK (max_privilege_level IN
                                ('read_only', 'local_write', 'external_write'))
);

CREATE TABLE IF NOT EXISTS tool_runs (
    id                  TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL REFERENCES tasks(id),
    tool_id             TEXT NOT NULL REFERENCES tool_definitions(id),
    input_hash          TEXT NOT NULL,
    output_hash         TEXT,
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    status              TEXT NOT NULL
);

-- Append-only audit event log. UPDATE/DELETE are blocked by triggers so the
-- immutability guarantee holds even if a caller bypasses the Python layer.
CREATE TABLE IF NOT EXISTS audit_events (
    id                  TEXT PRIMARY KEY,
    event_type          TEXT NOT NULL,
    actor               TEXT,
    project_id          TEXT,
    task_id             TEXT,
    artifact_hash       TEXT,
    payload_json        TEXT,
    occurred_at         TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only: UPDATE is forbidden');
END;

CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only: DELETE is forbidden');
END;

-- ---------------------------------------------------------------------------
-- Title extensions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS title_projects (
    id                  TEXT PRIMARY KEY REFERENCES projects(id),
    section             TEXT NOT NULL,
    township            TEXT NOT NULL,
    range               TEXT NOT NULL,
    county              TEXT NOT NULL,
    state               TEXT NOT NULL,
    search_from_date    TEXT,
    search_to_date      TEXT
);

CREATE TABLE IF NOT EXISTS jurisdictions (
    id                      TEXT PRIMARY KEY,
    state                   TEXT NOT NULL,
    county                  TEXT NOT NULL,
    search_standards_url    TEXT
);

CREATE TABLE IF NOT EXISTS tracts (
    id                          TEXT PRIMARY KEY,
    project_id                  TEXT NOT NULL REFERENCES projects(id),
    label                       TEXT NOT NULL,
    legal_description           TEXT NOT NULL,
    gross_acres_numerator       INTEGER,
    gross_acres_denominator     INTEGER
);

CREATE TABLE IF NOT EXISTS instruments (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    asset_version_id    TEXT NOT NULL REFERENCES asset_versions(id),
    instrument_type     TEXT NOT NULL,
    effective_date      TEXT,
    execution_date      TEXT,
    recording_date      TEXT,
    book                TEXT,
    page                TEXT,
    instrument_no       TEXT,
    county              TEXT,
    state               TEXT
);

CREATE TABLE IF NOT EXISTS instrument_parties (
    id                  TEXT PRIMARY KEY,
    instrument_id       TEXT NOT NULL REFERENCES instruments(id),
    role                TEXT NOT NULL CHECK (role IN
                            ('grantor', 'grantee', 'lessor', 'lessee',
                             'assignor', 'assignee', 'decedent', 'other')),
    name                TEXT NOT NULL,
    normalized_name     TEXT
);

CREATE TABLE IF NOT EXISTS recording_references (
    id                  TEXT PRIMARY KEY,
    instrument_id       TEXT NOT NULL REFERENCES instruments(id),
    book                TEXT NOT NULL,
    page                TEXT NOT NULL,
    county              TEXT NOT NULL,
    state               TEXT NOT NULL,
    recording_date      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chain_links (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    from_party          TEXT,
    to_party            TEXT,
    instrument_id       TEXT NOT NULL REFERENCES instruments(id),
    link_type           TEXT NOT NULL,
    tract_id            TEXT REFERENCES tracts(id),
    effective_date      TEXT
);

CREATE TABLE IF NOT EXISTS interest_ledger_entries (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    tract_id            TEXT NOT NULL REFERENCES tracts(id),
    instrument_id       TEXT NOT NULL REFERENCES instruments(id),
    interest_type       TEXT NOT NULL CHECK (interest_type IN
                            ('WI', 'NRI', 'ORRI', 'royalty', 'NMA', 'other')),
    numerator           INTEGER NOT NULL,
    denominator         INTEGER NOT NULL CHECK (denominator != 0),
    as_of_date          TEXT,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS title_exceptions (
    id                      TEXT PRIMARY KEY,
    project_id              TEXT NOT NULL REFERENCES projects(id),
    exception_type          TEXT NOT NULL,
    description             TEXT NOT NULL,
    instruments_affected    TEXT NOT NULL DEFAULT '[]',
    severity                TEXT NOT NULL CHECK (severity IN ('fatal', 'material', 'minor')),
    status                  TEXT NOT NULL CHECK (status IN
                                ('open', 'curative_pending', 'waived', 'resolved'))
);

CREATE TABLE IF NOT EXISTS curative_items (
    id                  TEXT PRIMARY KEY,
    exception_id        TEXT NOT NULL REFERENCES title_exceptions(id),
    action_required     TEXT NOT NULL,
    assigned_to         TEXT,
    due_date            TEXT,
    status              TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'complete'))
);

CREATE TABLE IF NOT EXISTS workbook_candidates (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id),
    asset_version_id    TEXT NOT NULL REFERENCES asset_versions(id),
    candidate_label     TEXT NOT NULL,
    structural_score    REAL,
    evidence_score      REAL,
    selected            INTEGER NOT NULL DEFAULT 0,
    selected_by         TEXT,
    selected_at         TEXT,
    superseded_by       TEXT
);

-- ---------------------------------------------------------------------------
-- Full text search over evidence span excerpts
-- ---------------------------------------------------------------------------

CREATE VIRTUAL TABLE IF NOT EXISTS evidence_spans_fts USING fts5(
    text_excerpt,
    content='evidence_spans',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS evidence_spans_ai AFTER INSERT ON evidence_spans BEGIN
    INSERT INTO evidence_spans_fts(rowid, text_excerpt) VALUES (new.rowid, new.text_excerpt);
END;

CREATE TRIGGER IF NOT EXISTS evidence_spans_ad AFTER DELETE ON evidence_spans BEGIN
    INSERT INTO evidence_spans_fts(evidence_spans_fts, rowid, text_excerpt)
        VALUES ('delete', old.rowid, old.text_excerpt);
END;

CREATE TRIGGER IF NOT EXISTS evidence_spans_au AFTER UPDATE ON evidence_spans BEGIN
    INSERT INTO evidence_spans_fts(evidence_spans_fts, rowid, text_excerpt)
        VALUES ('delete', old.rowid, old.text_excerpt);
    INSERT INTO evidence_spans_fts(rowid, text_excerpt) VALUES (new.rowid, new.text_excerpt);
END;

-- Helpful indices for common lookups.
CREATE INDEX IF NOT EXISTS idx_tasks_run_status ON tasks(run_id, status);
CREATE INDEX IF NOT EXISTS idx_task_deps_downstream ON task_dependencies(downstream_task_id);
CREATE INDEX IF NOT EXISTS idx_task_deps_upstream ON task_dependencies(upstream_task_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_project ON audit_events(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_occurred_at ON audit_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_claims_project ON claims(project_id);
CREATE INDEX IF NOT EXISTS idx_evidence_spans_asset_version ON evidence_spans(asset_version_id);
