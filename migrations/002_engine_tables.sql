CREATE TABLE IF NOT EXISTS model_route_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    capability TEXT NOT NULL,
    policy_profile TEXT NOT NULL,
    selected_worker TEXT NULL,
    selected_provider TEXT NULL,
    rejection_json TEXT NOT NULL,
    considered_json TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    decision_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_route_decisions_project
    ON model_route_decisions(project_id, created_at, id);

CREATE TABLE IF NOT EXISTS derived_cache (
    cache_key TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    recipe_version TEXT NOT NULL,
    input_manifest_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_derived_cache_project
    ON derived_cache(project_id, recipe_version);

CREATE TABLE IF NOT EXISTS engine_receipts (
    receipt_sha256 TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    body_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_engine_receipts_project
    ON engine_receipts(project_id, created_at);

CREATE TABLE IF NOT EXISTS candidate_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subject_key TEXT NOT NULL,
    result_json TEXT NOT NULL,
    conflict_count INTEGER NOT NULL,
    receipt_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
