CREATE TABLE title_economic_units (
    id TEXT PRIMARY KEY,
    title_case_id TEXT NOT NULL REFERENCES title_cases(id),
    unit_label TEXT NOT NULL,
    legal_description TEXT NOT NULL,
    lease_recording_reference TEXT NOT NULL,
    recording_reference_key TEXT NOT NULL,
    effective_as_of TEXT,
    depth_scope TEXT NOT NULL,
    product_scope TEXT NOT NULL,
    gross_acres_num INTEGER NOT NULL,
    gross_acres_den INTEGER NOT NULL CHECK (gross_acres_den > 0),
    leased_mineral_num INTEGER NOT NULL,
    leased_mineral_den INTEGER NOT NULL CHECK (leased_mineral_den > 0),
    base_royalty_num INTEGER NOT NULL,
    base_royalty_den INTEGER NOT NULL CHECK (base_royalty_den > 0),
    wi_basis TEXT NOT NULL CHECK (
        wi_basis IN ('WI_EQUALS_LEASEHOLD', 'EXPLICIT_ALLOCATION')
    ),
    review_status TEXT NOT NULL CHECK (
        review_status IN ('REVIEWED', 'NEEDS_REVIEW')
    ),
    unsupported_terms TEXT NOT NULL DEFAULT '',
    evidence_asset_version_id TEXT REFERENCES asset_versions(id),
    evidence_ingest_run_id TEXT REFERENCES ingest_runs(id),
    evidence_char_start INTEGER,
    evidence_char_end INTEGER,
    evidence_source_sha256 TEXT,
    evidence_extraction_sha256 TEXT,
    evidence_span_sha256 TEXT,
    evidence_span_text TEXT,
    UNIQUE(title_case_id, recording_reference_key)
);

CREATE TABLE title_economic_events (
    id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL REFERENCES title_economic_units(id),
    sequence_no INTEGER NOT NULL,
    event_kind TEXT NOT NULL CHECK (
        event_kind IN (
            'OPENING_LEASEHOLD',
            'ASSIGNMENT',
            'WORKING_INTEREST',
            'REVENUE_BURDEN'
        )
    ),
    recording_reference TEXT NOT NULL,
    recording_reference_key TEXT NOT NULL,
    from_party TEXT,
    to_party TEXT NOT NULL,
    interest_num INTEGER NOT NULL,
    interest_den INTEGER NOT NULL CHECK (interest_den > 0),
    interest_basis TEXT NOT NULL CHECK (
        interest_basis IN ('ABSOLUTE_UNIT', 'OF_ASSIGNOR', 'LEASE_8_8')
    ),
    burden_kind TEXT,
    review_status TEXT NOT NULL CHECK (
        review_status IN ('REVIEWED', 'NEEDS_REVIEW')
    ),
    notes TEXT NOT NULL DEFAULT '',
    evidence_asset_version_id TEXT REFERENCES asset_versions(id),
    evidence_ingest_run_id TEXT REFERENCES ingest_runs(id),
    evidence_char_start INTEGER,
    evidence_char_end INTEGER,
    evidence_source_sha256 TEXT,
    evidence_extraction_sha256 TEXT,
    evidence_span_sha256 TEXT,
    evidence_span_text TEXT,
    UNIQUE(unit_id, sequence_no),
    UNIQUE(unit_id, recording_reference_key)
);

CREATE INDEX title_economic_units_case_idx
    ON title_economic_units(title_case_id);
CREATE INDEX title_economic_events_unit_idx
    ON title_economic_events(unit_id, sequence_no);
