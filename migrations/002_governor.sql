-- Continuous Improvement Governor tables.
-- Intentionally does not create claims/evidence/connector tables so this
-- migration can coexist with other 002 drafts (PR #114) during review.

CREATE TABLE IF NOT EXISTS improvement_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    value_score REAL NOT NULL,
    risk_score REAL NOT NULL,
    cost_score REAL NOT NULL,
    reversibility TEXT NOT NULL,
    confidence REAL NOT NULL,
    autonomy_level TEXT NOT NULL,
    vetoes_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_envelopes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    envelope_id TEXT NOT NULL UNIQUE,
    proposal_id TEXT NOT NULL,
    base_commit TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    envelope_hash TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS writer_leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    fence INTEGER NOT NULL,
    leased_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    UNIQUE(scope, fence)
);

CREATE TABLE IF NOT EXISTS cycle_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id TEXT NOT NULL UNIQUE,
    envelope_hash TEXT NOT NULL,
    outcome TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS learning_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL UNIQUE,
    source_receipt_id TEXT NOT NULL,
    reviewed INTEGER NOT NULL DEFAULT 0,
    claim TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tournament_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id TEXT NOT NULL UNIQUE,
    folder_glob TEXT NOT NULL,
    scorecard_json TEXT NOT NULL,
    winner_folder TEXT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON improvement_proposals(status, id);
CREATE INDEX IF NOT EXISTS idx_envelopes_state ON task_envelopes(state, id);
