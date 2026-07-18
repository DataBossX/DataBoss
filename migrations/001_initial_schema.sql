PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jurisdictions (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    jurisdiction_code TEXT NOT NULL REFERENCES jurisdictions(code),
    policy_version TEXT NOT NULL,
    status TEXT NOT NULL,
    root_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS title_projects (
    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    report_type TEXT NOT NULL,
    release_state TEXT NOT NULL,
    template_asset_version_id INTEGER NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS source_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    root_locator TEXT NOT NULL,
    access_mode TEXT NOT NULL,
    credential_ref TEXT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_connection_id INTEGER NOT NULL REFERENCES source_connections(id) ON DELETE CASCADE,
    provider_cursor TEXT NOT NULL DEFAULT '',
    manifest_hash TEXT NOT NULL DEFAULT '',
    scanned_at TEXT NOT NULL,
    completeness_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    logical_key TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    UNIQUE(project_id, logical_key, asset_class)
);

CREATE TABLE IF NOT EXISTS asset_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    source_snapshot_id INTEGER NULL REFERENCES source_snapshots(id) ON DELETE SET NULL,
    sha256 TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    original_locator TEXT NOT NULL,
    vault_path TEXT NOT NULL,
    provider_version TEXT NOT NULL DEFAULT '',
    duplicate_of_asset_version_id INTEGER NULL REFERENCES asset_versions(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_versions_unique_asset_hash
    ON asset_versions(asset_id, sha256);

CREATE INDEX IF NOT EXISTS idx_asset_versions_sha256 ON asset_versions(sha256);
CREATE INDEX IF NOT EXISTS idx_asset_versions_snapshot ON asset_versions(source_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_assets_project_lookup ON assets(project_id, logical_key);

CREATE TABLE IF NOT EXISTS derived_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    recipe_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifact_lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    derived_artifact_id INTEGER NOT NULL REFERENCES derived_artifacts(id) ON DELETE CASCADE,
    asset_version_id INTEGER NOT NULL REFERENCES asset_versions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workbook_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_version_id INTEGER NOT NULL REFERENCES asset_versions(id) ON DELETE CASCADE,
    template_name TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    approved_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS writable_ranges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workbook_template_id INTEGER NOT NULL REFERENCES workbook_templates(id) ON DELETE CASCADE,
    sheet_name TEXT NOT NULL,
    range_ref TEXT NOT NULL,
    write_contract_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workflow_id INTEGER NOT NULL REFERENCES workflow_definitions(id) ON DELETE RESTRICT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL,
    state TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_state_priority ON tasks(state, priority, id);

CREATE TABLE IF NOT EXISTS task_dependencies (
    parent_task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    child_task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    PRIMARY KEY(parent_task_id, child_task_id)
);

CREATE TABLE IF NOT EXISTS task_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    worker_name TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT NULL,
    status TEXT NOT NULL,
    error_code TEXT NULL,
    log_artifact_id INTEGER NULL REFERENCES derived_artifacts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS task_leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    worker_id TEXT NOT NULL,
    leased_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    heartbeat_at TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_leases_expires ON task_leases(expires_at);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    artifact_hash TEXT NOT NULL,
    approver_id TEXT NOT NULL,
    approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_approvals_artifact_hash ON approvals(project_id, artifact_hash);

CREATE TABLE IF NOT EXISTS outbox_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_project_time ON audit_events(project_id, created_at, id);

CREATE VIRTUAL TABLE IF NOT EXISTS audit_events_fts USING fts5(
    project_id,
    event_type,
    entity_type,
    entity_id,
    payload_json,
    content='audit_events',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS audit_events_ai AFTER INSERT ON audit_events BEGIN
    INSERT INTO audit_events_fts(rowid, project_id, event_type, entity_type, entity_id, payload_json)
    VALUES (new.id, new.project_id, new.event_type, new.entity_type, new.entity_id, new.payload_json);
END;
