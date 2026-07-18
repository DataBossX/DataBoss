ALTER TABLE title_instruments ADD COLUMN recording_reference_key TEXT;
ALTER TABLE title_instruments ADD COLUMN evidence_ingest_run_id TEXT REFERENCES ingest_runs(id);
ALTER TABLE title_instruments ADD COLUMN evidence_source_sha256 TEXT;
ALTER TABLE title_instruments ADD COLUMN evidence_extraction_sha256 TEXT;
ALTER TABLE title_instruments ADD COLUMN evidence_span_sha256 TEXT;
ALTER TABLE title_instruments ADD COLUMN evidence_span_text TEXT;

CREATE UNIQUE INDEX title_instruments_recording_key_idx
    ON title_instruments(title_case_id, recording_reference_key)
    WHERE recording_reference_key IS NOT NULL;

CREATE TABLE title_reviewers (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('QUALIFIED_EXAMINER', 'ATTORNEY')),
    pin_salt TEXT NOT NULL,
    pin_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

ALTER TABLE title_review_decisions ADD COLUMN reviewer_id TEXT REFERENCES title_reviewers(id);
