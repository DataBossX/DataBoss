"""
Database schema initialization
"""

import aiosqlite
from pathlib import Path


DATABASE_SCHEMA = """
-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_hash TEXT UNIQUE NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    uploaded_at TIMESTAMP NOT NULL,
    document_type TEXT NOT NULL,
    document_type_confidence REAL NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    metadata JSON
);

-- OCR results table
CREATE TABLE IF NOT EXISTS ocr_results (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    engine TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    overall_confidence REAL NOT NULL,
    processing_time REAL NOT NULL,
    created_at TIMESTAMP NOT NULL,
    metadata JSON,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- OCR fusion results table
CREATE TABLE IF NOT EXISTS ocr_fusion_results (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    fused_text TEXT NOT NULL,
    overall_confidence REAL NOT NULL,
    fusion_method TEXT NOT NULL,
    llm_model_used TEXT,
    created_at TIMESTAMP NOT NULL,
    metadata JSON,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- Entity extractions table
CREATE TABLE IF NOT EXISTS entity_extractions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    overall_confidence REAL NOT NULL,
    created_at TIMESTAMP NOT NULL,
    metadata JSON,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- Grantors table
CREATE TABLE IF NOT EXISTS grantors (
    id TEXT PRIMARY KEY,
    extraction_id TEXT NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    source_text TEXT,
    marital_status TEXT,
    metadata JSON,
    FOREIGN KEY (extraction_id) REFERENCES entity_extractions(id)
);

-- Grantees table
CREATE TABLE IF NOT EXISTS grantees (
    id TEXT PRIMARY KEY,
    extraction_id TEXT NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    source_text TEXT,
    percentage_interest TEXT,
    metadata JSON,
    FOREIGN KEY (extraction_id) REFERENCES entity_extractions(id)
);

-- Legal descriptions table
CREATE TABLE IF NOT EXISTS legal_descriptions (
    id TEXT PRIMARY KEY,
    extraction_id TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    section TEXT,
    township TEXT,
    range TEXT,
    meridian TEXT,
    county TEXT,
    state TEXT,
    acres TEXT,
    confidence REAL NOT NULL,
    metadata JSON,
    FOREIGN KEY (extraction_id) REFERENCES entity_extractions(id)
);

-- Chain graphs table
CREATE TABLE IF NOT EXISTS chain_graphs (
    id TEXT PRIMARY KEY,
    property_description TEXT NOT NULL,
    interest_type TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    metadata JSON
);

-- Chain nodes table
CREATE TABLE IF NOT EXISTS chain_nodes (
    id TEXT PRIMARY KEY,
    chain_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    is_current_owner BOOLEAN DEFAULT 0,
    is_original_grantor BOOLEAN DEFAULT 0,
    metadata JSON,
    FOREIGN KEY (chain_id) REFERENCES chain_graphs(id)
);

-- Chain links table
CREATE TABLE IF NOT EXISTS chain_links (
    id TEXT PRIMARY KEY,
    chain_id TEXT NOT NULL,
    from_node_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    transaction_date TIMESTAMP,
    transaction_type TEXT NOT NULL,
    interest_transferred TEXT NOT NULL,
    metadata JSON,
    FOREIGN KEY (chain_id) REFERENCES chain_graphs(id),
    FOREIGN KEY (from_node_id) REFERENCES chain_nodes(id),
    FOREIGN KEY (to_node_id) REFERENCES chain_nodes(id)
);

-- Chain gaps table
CREATE TABLE IF NOT EXISTS chain_gaps (
    id TEXT PRIMARY KEY,
    chain_id TEXT NOT NULL,
    gap_type TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence REAL NOT NULL,
    metadata JSON,
    FOREIGN KEY (chain_id) REFERENCES chain_graphs(id)
);

-- Extraction rules table
CREATE TABLE IF NOT EXISTS extraction_rules (
    id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    pattern TEXT NOT NULL,
    target_field TEXT NOT NULL,
    confidence_threshold REAL NOT NULL,
    version INTEGER NOT NULL,
    parent_rule_id TEXT,
    created_at TIMESTAMP NOT NULL,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    avg_confidence REAL DEFAULT 0.0,
    is_active BOOLEAN DEFAULT 1,
    metadata JSON
);

-- Rule mutations table
CREATE TABLE IF NOT EXISTS rule_mutations (
    id TEXT PRIMARY KEY,
    original_rule_id TEXT NOT NULL,
    mutated_rule_id TEXT NOT NULL,
    mutation_type TEXT NOT NULL,
    mutation_description TEXT NOT NULL,
    reason TEXT NOT NULL,
    applied BOOLEAN DEFAULT 0,
    applied_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    test_results JSON,
    FOREIGN KEY (original_rule_id) REFERENCES extraction_rules(id),
    FOREIGN KEY (mutated_rule_id) REFERENCES extraction_rules(id)
);

-- Evolution history table
CREATE TABLE IF NOT EXISTS evolution_history (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    metrics JSON,
    created_at TIMESTAMP NOT NULL,
    metadata JSON,
    FOREIGN KEY (rule_id) REFERENCES extraction_rules(id)
);

-- Predictive insights table
CREATE TABLE IF NOT EXISTS predictive_insights (
    id TEXT PRIMARY KEY,
    chain_id TEXT,
    property_description TEXT,
    overall_risk_score REAL NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    metadata JSON,
    FOREIGN KEY (chain_id) REFERENCES chain_graphs(id)
);

-- System logs table
CREATE TABLE IF NOT EXISTS system_logs (
    id TEXT PRIMARY KEY,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    component TEXT NOT NULL,
    details JSON,
    created_at TIMESTAMP NOT NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_ocr_results_doc ON ocr_results(document_id);
CREATE INDEX IF NOT EXISTS idx_extractions_doc ON entity_extractions(document_id);
CREATE INDEX IF NOT EXISTS idx_grantors_extraction ON grantors(extraction_id);
CREATE INDEX IF NOT EXISTS idx_grantees_extraction ON grantees(extraction_id);
CREATE INDEX IF NOT EXISTS idx_chain_nodes_chain ON chain_nodes(chain_id);
CREATE INDEX IF NOT EXISTS idx_chain_links_chain ON chain_links(chain_id);
CREATE INDEX IF NOT EXISTS idx_rules_active ON extraction_rules(is_active);
"""


async def init_database(db_path: str = "./databossx_land_intel.db"):
    """
    Initialize database with schema

    Args:
        db_path: Path to SQLite database file
    """
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        # Enable foreign keys
        await db.execute("PRAGMA foreign_keys = ON")

        # Execute schema
        await db.executescript(DATABASE_SCHEMA)

        await db.commit()

    return db_path
