ALTER TABLE tasks ADD COLUMN input_manifest_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN idempotency_key TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN capability TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS task_manifests (
    task_id INTEGER PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    input_manifest_hash TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    capability TEXT NOT NULL DEFAULT '',
    outcome_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS connector_cursors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_connection_id INTEGER NOT NULL REFERENCES source_connections(id) ON DELETE CASCADE,
    cursor_kind TEXT NOT NULL,
    cursor_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_connection_id, cursor_kind)
);

CREATE TABLE IF NOT EXISTS evidence_spans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    asset_version_id INTEGER NOT NULL REFERENCES asset_versions(id) ON DELETE CASCADE,
    page TEXT NOT NULL DEFAULT '',
    char_start INTEGER NULL,
    char_end INTEGER NULL,
    snippet TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value_text TEXT NOT NULL DEFAULT '',
    value_state TEXT NOT NULL,
    confidence REAL NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claim_support (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    evidence_span_id INTEGER NOT NULL REFERENCES evidence_spans(id) ON DELETE CASCADE,
    rule_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claim_id_a INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    claim_id_b INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    material INTEGER NOT NULL DEFAULT 1,
    resolution_state TEXT NOT NULL DEFAULT 'OPEN',
    resolved_by TEXT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review_gates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    gate_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_gate_id INTEGER NOT NULL REFERENCES review_gates(id) ON DELETE CASCADE,
    reviewer_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_claims_project ON claims(project_id, predicate);
CREATE INDEX IF NOT EXISTS idx_conflicts_project ON conflicts(project_id, resolution_state);
CREATE INDEX IF NOT EXISTS idx_evidence_spans_asset ON evidence_spans(asset_version_id);
