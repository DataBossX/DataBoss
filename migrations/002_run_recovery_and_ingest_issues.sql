ALTER TABLE ingest_runs ADD COLUMN owner_pid INTEGER;
ALTER TABLE pipeline_runs ADD COLUMN owner_pid INTEGER;

CREATE TABLE ingest_issues (
    id TEXT PRIMARY KEY,
    ingest_run_id TEXT NOT NULL REFERENCES ingest_runs(id),
    rel_path TEXT NOT NULL,
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX ingest_issues_run_idx ON ingest_issues(ingest_run_id);
