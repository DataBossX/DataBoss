-- Enhanced Notice List Maker Database Schema
-- Supports both SQLite and PostgreSQL/Supabase
-- Includes Evidence tracking, Row Level Security, and Migrations

-- ============================================================================
-- CASES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  -- Use TEXT for SQLite
    unit_name TEXT,
    county TEXT,
    state TEXT,
    plss_meridian TEXT DEFAULT '6PM',
    status TEXT CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,  -- User ID for RLS

    -- Metadata
    source_files JSONB,  -- Use TEXT for SQLite
    unit_tract_count INTEGER DEFAULT 0,
    offset_tract_count INTEGER DEFAULT 0,

    -- Audit fields
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at DESC);


-- ============================================================================
-- TRACTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS tracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    tract_id TEXT NOT NULL,
    legal_description TEXT NOT NULL,

    -- PLSS
    township TEXT,
    range TEXT,
    section INTEGER,

    -- Acreage
    gross_acres DECIMAL(10,2),
    net_acres DECIMAL(10,2),

    -- Classification
    tract_type TEXT CHECK (tract_type IN ('UNIT', 'OFFSET', 'UNKNOWN')),
    offset_method TEXT,  -- polygon, centroid, str_grid
    confidence_score DECIMAL(5,2),
    distance_to_unit_miles DECIMAL(10,2),

    -- Source tracking
    source TEXT,  -- pdf, spreadsheet, manual
    source_file TEXT,

    -- Geometry (PostGIS for Postgres, TEXT for SQLite)
    geometry GEOMETRY(Polygon, 4326),  -- Or TEXT for SQLite

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(case_id, tract_id)
);

CREATE INDEX IF NOT EXISTS idx_tracts_case_id ON tracts(case_id);
CREATE INDEX IF NOT EXISTS idx_tracts_tract_id ON tracts(tract_id);
CREATE INDEX IF NOT EXISTS idx_tracts_type ON tracts(tract_type);
CREATE INDEX IF NOT EXISTS idx_tracts_legal ON tracts(legal_description);


-- ============================================================================
-- PARTIES TABLE (Owners, Lessees, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS parties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    entity_type TEXT,  -- individual, corporation, trust, estate

    -- Dedupe key
    normalized_name TEXT,  -- UPPERCASE, no punctuation

    -- Contact
    primary_phone TEXT,
    primary_email TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(normalized_name)
);

CREATE INDEX IF NOT EXISTS idx_parties_name ON parties(name);
CREATE INDEX IF NOT EXISTS idx_parties_normalized ON parties(normalized_name);


-- ============================================================================
-- INTERESTS TABLE (Ownership links)
-- ============================================================================
CREATE TABLE IF NOT EXISTS interests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    tract_id UUID REFERENCES tracts(id) ON DELETE CASCADE,
    party_id UUID REFERENCES parties(id) ON DELETE CASCADE,

    -- Ownership details
    ownership_type TEXT CHECK (ownership_type IN ('MINERAL', 'LEASEHOLD', 'WORKING_INTEREST', 'ROYALTY', 'UNKNOWN')),
    interest_decimal DECIMAL(10,8),
    interest_fraction TEXT,

    -- Classification
    lease_status TEXT CHECK (lease_status IN ('UMI', 'ROY', 'WI', 'UNKNOWN')),

    -- Source tracking
    source TEXT,
    confidence_score DECIMAL(5,2),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_interests_case ON interests(case_id);
CREATE INDEX IF NOT EXISTS idx_interests_tract ON interests(tract_id);
CREATE INDEX IF NOT EXISTS idx_interests_party ON interests(party_id);
CREATE INDEX IF NOT EXISTS idx_interests_type ON interests(ownership_type);


-- ============================================================================
-- ADDRESSES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID REFERENCES parties(id) ON DELETE CASCADE,

    -- Address components
    street TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    country TEXT DEFAULT 'USA',

    -- Full formatted address
    formatted_address TEXT,

    -- Source tracking
    source TEXT CHECK (source IN ('recent_instrument', 'county_tax_roll', 'operator_paydeck', 'manual_override', 'connector', 'unknown')),
    source_date DATE,
    confidence_score DECIMAL(5,2),

    -- Validation
    is_validated BOOLEAN DEFAULT FALSE,
    validated_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_addresses_party ON addresses(party_id);
CREATE INDEX IF NOT EXISTS idx_addresses_source ON addresses(source);
CREATE INDEX IF NOT EXISTS idx_addresses_confidence ON addresses(confidence_score DESC);


-- ============================================================================
-- LEASES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS leases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lease_id TEXT NOT NULL,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    tract_id UUID REFERENCES tracts(id) ON DELETE CASCADE,

    -- Parties
    lessee_id UUID REFERENCES parties(id),
    lessor_id UUID REFERENCES parties(id),
    lessee_name TEXT NOT NULL,  -- Denormalized for speed
    lessor_name TEXT NOT NULL,

    -- Lease terms
    effective_date DATE,
    expiration_date DATE,
    primary_term_years INTEGER,
    royalty_fraction TEXT,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Source
    source TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(case_id, lease_id)
);

CREATE INDEX IF NOT EXISTS idx_leases_case ON leases(case_id);
CREATE INDEX IF NOT EXISTS idx_leases_tract ON leases(tract_id);
CREATE INDEX IF NOT EXISTS idx_leases_active ON leases(is_active);
CREATE INDEX IF NOT EXISTS idx_leases_lessee ON leases(lessee_id);
CREATE INDEX IF NOT EXISTS idx_leases_lessor ON leases(lessor_id);


-- ============================================================================
-- EVIDENCE TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What does this evidence support?
    interest_id UUID REFERENCES interests(id) ON DELETE CASCADE,
    address_id UUID REFERENCES addresses(id) ON DELETE CASCADE,
    lease_id UUID REFERENCES leases(id) ON DELETE CASCADE,

    -- Evidence details
    evidence_type TEXT CHECK (evidence_type IN ('instrument', 'tax_record', 'paydeck', 'connector_result', 'manual', 'other')),
    source TEXT NOT NULL,  -- Which connector or system provided this

    -- Document reference
    document_type TEXT,  -- deed, lease, assignment, etc.
    recording_number TEXT,
    recording_date DATE,
    book_page TEXT,

    -- Links
    document_url TEXT,
    image_url TEXT,

    -- Content
    extracted_text TEXT,
    metadata JSONB,  -- Use TEXT for SQLite

    -- Quality
    confidence_score DECIMAL(5,2),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_evidence_interest ON evidence(interest_id);
CREATE INDEX IF NOT EXISTS idx_evidence_address ON evidence(address_id);
CREATE INDEX IF NOT EXISTS idx_evidence_lease ON evidence(lease_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence(evidence_type);
CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source);


-- ============================================================================
-- PROCESSING LOG TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS processing_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,

    -- Event
    action TEXT NOT NULL,  -- ingest, build_geometry, resolve_owners, generate_output
    status TEXT CHECK (status IN ('success', 'failure', 'warning')),
    message TEXT,
    details JSONB,  -- Use TEXT for SQLite

    -- Error details
    error_type TEXT,
    error_trace TEXT,

    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_log_case ON processing_log(case_id);
CREATE INDEX IF NOT EXISTS idx_log_timestamp ON processing_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_log_status ON processing_log(status);


-- ============================================================================
-- CONNECTOR SCORECARD TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS connector_scorecard (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_name TEXT NOT NULL,

    -- Stats
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    total_requests INTEGER DEFAULT 0,
    avg_response_time_ms DECIMAL(10,2),

    -- Last activity
    last_success_at TIMESTAMP,
    last_failure_at TIMESTAMP,

    -- Rolling window stats (last 24 hours)
    rolling_success_count INTEGER DEFAULT 0,
    rolling_failure_count INTEGER DEFAULT 0,
    window_start_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(connector_name)
);

CREATE INDEX IF NOT EXISTS idx_scorecard_connector ON connector_scorecard(connector_name);


-- ============================================================================
-- AUDIT QUEUE TABLE (for nightly audits)
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What needs auditing?
    audit_type TEXT CHECK (audit_type IN ('stale_address', 'failed_lookup', 'low_confidence', 'expired_lease')),
    entity_type TEXT,  -- address, interest, lease
    entity_id UUID,

    -- Priority
    priority INTEGER DEFAULT 0,  -- Higher = more urgent

    -- Status
    status TEXT CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,

    -- Results
    resolution TEXT,
    resolved_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_queue_status ON audit_queue(status);
CREATE INDEX IF NOT EXISTS idx_audit_queue_priority ON audit_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_audit_queue_type ON audit_queue(audit_type);


-- ============================================================================
-- ROW LEVEL SECURITY (PostgreSQL/Supabase only)
-- ============================================================================

-- Enable RLS on all tables
-- ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE tracts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE interests ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE parties ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE addresses ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE leases ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;

-- Create policies (example for cases table)
-- CREATE POLICY "Users can view their own cases"
--     ON cases FOR SELECT
--     USING (auth.uid() = created_by);

-- CREATE POLICY "Users can insert their own cases"
--     ON cases FOR INSERT
--     WITH CHECK (auth.uid() = created_by);

-- CREATE POLICY "Users can update their own cases"
--     ON cases FOR UPDATE
--     USING (auth.uid() = created_by);

-- CREATE POLICY "Users can delete their own cases"
--     ON cases FOR DELETE
--     USING (auth.uid() = created_by);


-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Update timestamp trigger function (PostgreSQL)
-- CREATE OR REPLACE FUNCTION update_updated_at_column()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     NEW.updated_at = CURRENT_TIMESTAMP;
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- Apply to all tables
-- CREATE TRIGGER update_cases_updated_at BEFORE UPDATE ON cases
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
-- (Repeat for other tables...)


-- ============================================================================
-- VIEWS
-- ============================================================================

-- Complete notice list view
CREATE VIEW IF NOT EXISTS notice_list_view AS
SELECT
    c.id as case_id,
    c.unit_name,
    t.tract_id,
    t.legal_description,
    t.tract_type,
    t.gross_acres,
    t.net_acres,
    t.distance_to_unit_miles,
    t.offset_method,
    t.confidence_score as tract_confidence,
    p.name as owner_name,
    i.ownership_type,
    i.interest_fraction,
    i.lease_status,
    a.formatted_address,
    a.source as address_source,
    a.source_date as address_date,
    a.confidence_score as address_confidence
FROM cases c
JOIN tracts t ON t.case_id = c.id
JOIN interests i ON i.tract_id = t.id
JOIN parties p ON p.id = i.party_id
LEFT JOIN addresses a ON a.party_id = p.id
WHERE a.id IS NULL OR a.id = (
    SELECT id FROM addresses
    WHERE party_id = p.id
    ORDER BY confidence_score DESC, source_date DESC
    LIMIT 1
);
