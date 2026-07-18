CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_root TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('local', 'synthetic')),
    status TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TEXT NOT NULL
);

CREATE TABLE ingest_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    manifest_sha256 TEXT,
    asset_count INTEGER NOT NULL DEFAULT 0,
    unique_blob_count INTEGER NOT NULL DEFAULT 0,
    issue_count INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE blobs (
    sha256 TEXT PRIMARY KEY CHECK (length(sha256) = 64),
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    vault_relpath TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE asset_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    ingest_run_id TEXT NOT NULL REFERENCES ingest_runs(id),
    rel_path TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    source_mtime_ns INTEGER NOT NULL,
    blob_sha256 TEXT NOT NULL REFERENCES blobs(sha256),
    custody_at TEXT NOT NULL,
    UNIQUE (ingest_run_id, rel_path)
);

CREATE TABLE text_extractions (
    id TEXT PRIMARY KEY,
    asset_version_id TEXT NOT NULL UNIQUE REFERENCES asset_versions(id),
    status TEXT NOT NULL,
    extractor TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    text_sha256 TEXT,
    text_content TEXT NOT NULL DEFAULT '',
    char_count INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE asset_text_fts USING fts5(
    text_content,
    rel_path,
    project_id UNINDEXED,
    asset_version_id UNINDEXED,
    tokenize = 'unicode61'
);

CREATE TRIGGER text_extractions_fts_insert AFTER INSERT ON text_extractions
BEGIN
    INSERT INTO asset_text_fts(text_content, rel_path, project_id, asset_version_id)
    SELECT NEW.text_content, a.rel_path, a.project_id, NEW.asset_version_id
      FROM asset_versions a WHERE a.id = NEW.asset_version_id;
END;

CREATE TABLE pipeline_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    ingest_run_id TEXT NOT NULL REFERENCES ingest_runs(id),
    pipeline TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    input_manifest_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    run_dir TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    exit_code INTEGER,
    error TEXT
);

CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
    rel_path TEXT NOT NULL,
    blob_sha256 TEXT NOT NULL REFERENCES blobs(sha256),
    size_bytes INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (pipeline_run_id, rel_path)
);

CREATE TABLE provenance_edges (
    id TEXT PRIMARY KEY,
    parent_type TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    child_type TEXT NOT NULL,
    child_id TEXT NOT NULL,
    recipe TEXT NOT NULL,
    recipe_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL,
    project_id TEXT,
    run_id TEXT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    details_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE
);

CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;

CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;

CREATE INDEX asset_versions_project_idx ON asset_versions(project_id);
CREATE INDEX pipeline_runs_project_idx ON pipeline_runs(project_id);
CREATE INDEX audit_events_project_idx ON audit_events(project_id, sequence);
