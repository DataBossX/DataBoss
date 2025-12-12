-- Notice List Maker Database Schema
-- SQLite database for caching tract, owner, and address information

-- Tracts table
CREATE TABLE IF NOT EXISTS tracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tract_id TEXT NOT NULL UNIQUE,
    legal_description TEXT NOT NULL,
    township TEXT,
    range TEXT,
    section INTEGER,
    gross_acres REAL,
    net_acres REAL,
    source TEXT,
    source_file TEXT,
    confidence_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tracts_tract_id ON tracts(tract_id);
CREATE INDEX IF NOT EXISTS idx_tracts_legal ON tracts(legal_description);

-- Owners table
CREATE TABLE IF NOT EXISTS owners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_name TEXT NOT NULL,
    tract_id TEXT NOT NULL,
    ownership_type TEXT,  -- MINERAL, LEASEHOLD, WORKING_INTEREST
    interest_decimal REAL,
    interest_fraction TEXT,
    source TEXT,
    confidence_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tract_id) REFERENCES tracts(tract_id)
);

CREATE INDEX IF NOT EXISTS idx_owners_name ON owners(owner_name);
CREATE INDEX IF NOT EXISTS idx_owners_tract ON owners(tract_id);

-- Addresses table
CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_name TEXT NOT NULL,
    street TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    country TEXT DEFAULT 'USA',
    source TEXT,  -- recent_instrument, county_tax_roll, operator_paydeck, manual_override
    source_date DATE,
    confidence_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_addresses_owner ON addresses(owner_name);
CREATE INDEX IF NOT EXISTS idx_addresses_source ON addresses(source);

-- Leases table
CREATE TABLE IF NOT EXISTS leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id TEXT NOT NULL UNIQUE,
    tract_id TEXT NOT NULL,
    lessee_name TEXT NOT NULL,
    lessor_name TEXT NOT NULL,
    effective_date DATE,
    expiration_date DATE,
    is_active BOOLEAN DEFAULT 1,
    primary_term_years INTEGER,
    royalty_fraction TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tract_id) REFERENCES tracts(tract_id)
);

CREATE INDEX IF NOT EXISTS idx_leases_tract ON leases(tract_id);
CREATE INDEX IF NOT EXISTS idx_leases_active ON leases(is_active);

-- Units table (for caching processed units)
CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_name TEXT NOT NULL UNIQUE,
    county TEXT,
    state TEXT,
    operator TEXT,
    total_tracts INTEGER,
    total_offset_tracts INTEGER,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Processing log table
CREATE TABLE IF NOT EXISTS processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_name TEXT,
    action TEXT,  -- 'ingest', 'build_geometry', 'resolve_owners', 'generate_output'
    status TEXT,  -- 'success', 'failure', 'warning'
    message TEXT,
    details TEXT,  -- JSON with additional details
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_log_unit ON processing_log(unit_name);
CREATE INDEX IF NOT EXISTS idx_log_timestamp ON processing_log(timestamp);
