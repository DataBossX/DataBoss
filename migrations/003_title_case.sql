CREATE TABLE title_cases (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    legal_description TEXT NOT NULL,
    gross_acres_num INTEGER NOT NULL,
    gross_acres_den INTEGER NOT NULL CHECK (gross_acres_den > 0),
    status TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TEXT NOT NULL
);

CREATE TABLE title_opening_ownership (
    id TEXT PRIMARY KEY,
    title_case_id TEXT NOT NULL REFERENCES title_cases(id),
    owner_name TEXT NOT NULL,
    interest_num INTEGER NOT NULL,
    interest_den INTEGER NOT NULL CHECK (interest_den > 0),
    UNIQUE(title_case_id, owner_name)
);

CREATE TABLE title_instruments (
    id TEXT PRIMARY KEY,
    title_case_id TEXT NOT NULL REFERENCES title_cases(id),
    sequence_no INTEGER NOT NULL,
    instrument_type TEXT NOT NULL,
    recording_reference TEXT NOT NULL,
    effective_date TEXT,
    grantor_name TEXT NOT NULL,
    grantee_name TEXT NOT NULL,
    conveyed_num INTEGER NOT NULL,
    conveyed_den INTEGER NOT NULL CHECK (conveyed_den > 0),
    interest_basis TEXT NOT NULL CHECK (
        interest_basis IN ('ABSOLUTE_ESTATE', 'OF_GRANTOR')
    ),
    evidence_asset_version_id TEXT REFERENCES asset_versions(id),
    evidence_char_start INTEGER,
    evidence_char_end INTEGER,
    review_status TEXT NOT NULL CHECK (
        review_status IN ('REVIEWED', 'NEEDS_REVIEW')
    ),
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE(title_case_id, sequence_no)
);

CREATE TABLE title_package_details (
    pipeline_run_id TEXT PRIMARY KEY REFERENCES pipeline_runs(id),
    title_case_id TEXT NOT NULL REFERENCES title_cases(id),
    package_manifest_sha256 TEXT NOT NULL,
    blocking_defect_count INTEGER NOT NULL,
    review_status TEXT NOT NULL,
    approved_manifest_sha256 TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT
);

CREATE TABLE title_defects (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    sequence_no INTEGER,
    recording_reference TEXT,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE title_review_decisions (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
    package_manifest_sha256 TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('APPROVE', 'REJECT')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX title_cases_project_idx ON title_cases(project_id);
CREATE INDEX title_instruments_case_idx ON title_instruments(title_case_id, sequence_no);
CREATE INDEX title_defects_run_idx ON title_defects(pipeline_run_id);
