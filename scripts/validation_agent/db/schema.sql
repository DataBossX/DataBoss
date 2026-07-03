-- DataBossX Validation & Repair Agent -- append-only memory layer.
--
-- Golden Law #2: every action leaves append-only, immutable proof.
-- There are deliberately NO columns that get mutated in place: state changes,
-- corrections, and outcomes are all expressed as *new rows*.  db_client.py
-- rejects UPDATE/DELETE at the connection layer so this invariant cannot be
-- violated even by a buggy caller.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- One row per orchestrator invocation over a source workbook.
CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,           -- validation_run_YYYYMMDD_HHMMSS
    source_path     TEXT NOT NULL,
    source_sha256   TEXT NOT NULL,
    run_folder      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Append-only state-machine trace.  A run's "current" state is the newest row.
CREATE TABLE IF NOT EXISTS run_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    iteration   INTEGER NOT NULL DEFAULT 0,
    state       TEXT NOT NULL,                  -- STATE_INIT, STATE_VALIDATE, ...
    detail      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- Every immutable workbook version (v0 baseline, v1 repaired, ...).
CREATE TABLE IF NOT EXISTS workbook_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    version     INTEGER NOT NULL,               -- 0 = source baseline
    file_path   TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- One row per gate evaluation per iteration.
CREATE TABLE IF NOT EXISTS validation_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    iteration   INTEGER NOT NULL,
    version     INTEGER NOT NULL,
    gate_id     INTEGER NOT NULL,
    gate_name   TEXT NOT NULL,
    status      TEXT NOT NULL,                  -- pass | fail | error | skipped
    detail      TEXT,
    metrics     TEXT,                           -- JSON
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- One row per discrete finding (a gate may raise several).
CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    iteration   INTEGER NOT NULL,
    gate_id     INTEGER NOT NULL,
    gate_name   TEXT NOT NULL,
    category    TEXT NOT NULL,
    severity    TEXT NOT NULL,
    location    TEXT,
    subject     TEXT,
    message     TEXT NOT NULL,
    repairable  INTEGER NOT NULL DEFAULT 0,
    escalate    INTEGER NOT NULL DEFAULT 0,
    payload     TEXT,                           -- JSON (evidence + repair_hint)
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- One row per automated XML repair actually applied.
CREATE TABLE IF NOT EXISTS repairs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    iteration     INTEGER NOT NULL,
    from_version  INTEGER NOT NULL,
    to_version    INTEGER NOT NULL,
    gate_id       INTEGER NOT NULL,
    location      TEXT NOT NULL,
    action_type   TEXT NOT NULL,
    old_value     TEXT,
    new_formula   TEXT,
    rationale     TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- Every OKCountyRecords API call attempt (including blocked ones).
CREATE TABLE IF NOT EXISTS api_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT,
    endpoint      TEXT NOT NULL,
    request_meta  TEXT,                         -- JSON, no secrets
    outcome       TEXT NOT NULL,                -- success | blocked | error
    http_status   INTEGER,
    estimated_cost REAL NOT NULL DEFAULT 0.0,
    actual_cost   REAL NOT NULL DEFAULT 0.0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- Cumulative spend ledger.  SUM(amount) is the authoritative running total the
-- APISpendGuard checks against the $100 cap.
CREATE TABLE IF NOT EXISTS spend_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT,
    amount      REAL NOT NULL,
    description TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- One row per human escalation packet (Section 7).
CREATE TABLE IF NOT EXISTS escalations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    iteration     INTEGER NOT NULL,
    gate_id       INTEGER NOT NULL,
    gate_name     TEXT NOT NULL,
    category      TEXT NOT NULL,
    severity      TEXT NOT NULL,
    payload       TEXT NOT NULL,                -- JSON: full 9-field payload
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- Catch-all structured event log.
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT,
    event_type  TEXT NOT NULL,
    description TEXT,
    data        TEXT,                           -- JSON
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_run       ON run_events(run_id);
CREATE INDEX IF NOT EXISTS idx_results_run_iter ON validation_results(run_id, iteration);
CREATE INDEX IF NOT EXISTS idx_findings_run     ON findings(run_id, iteration);
CREATE INDEX IF NOT EXISTS idx_versions_run     ON workbook_versions(run_id, version);
CREATE INDEX IF NOT EXISTS idx_spend_run        ON spend_ledger(run_id);
CREATE INDEX IF NOT EXISTS idx_escalations_run  ON escalations(run_id);
