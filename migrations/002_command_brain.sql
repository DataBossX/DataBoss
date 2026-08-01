-- DataBossX Command Brain Alpha
--
-- Additive migration. It creates no foreign keys into the Phase-2 tables from
-- 001_initial_schema.sql so that the Command Brain can be initialised against a
-- standalone database, and so that rolling this migration back (see
-- docs/COMMAND_BRAIN_ROLLBACK.md) is a pure DROP of cb_* objects.
--
-- Two tables are append-only and enforce it with triggers rather than with
-- convention: cb_audit_events and cb_receipts. Both are hash-chained.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Conversation, voice, and intent
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT NULL,
    channel TEXT NOT NULL,                 -- text | voice
    created_at TEXT NOT NULL,
    closed_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS cb_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES cb_conversations(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    role TEXT NOT NULL,                    -- operator | system | agent
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cb_messages_conversation ON cb_messages(conversation_id, ordinal);

CREATE TABLE IF NOT EXISTS cb_voice_sessions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES cb_conversations(id) ON DELETE CASCADE,
    stt_adapter TEXT NOT NULL,
    tts_adapter TEXT NOT NULL,
    simulated INTEGER NOT NULL DEFAULT 1,
    mode TEXT NOT NULL,                    -- push_to_talk | hands_free | text_fallback
    state TEXT NOT NULL,                   -- idle | listening | confirming | stopped
    audio_retention TEXT NOT NULL,         -- none | transcript_only | audio_retained
    started_at TEXT NOT NULL,
    ended_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS cb_transcripts (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES cb_conversations(id) ON DELETE CASCADE,
    voice_session_id TEXT NULL REFERENCES cb_voice_sessions(id) ON DELETE SET NULL,
    raw_text TEXT NOT NULL,
    confirmed INTEGER NOT NULL DEFAULT 0,
    corrected_from TEXT NULL REFERENCES cb_transcripts(id) ON DELETE SET NULL,
    superseded_by TEXT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_intents (
    id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL REFERENCES cb_transcripts(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    risk TEXT NOT NULL,
    confidence REAL NOT NULL,
    requires_clarification INTEGER NOT NULL DEFAULT 0,
    slots_json TEXT NOT NULL DEFAULT '{}',
    quoted_segments_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Planning
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_plans (
    id TEXT PRIMARY KEY,
    intent_id TEXT NULL REFERENCES cb_intents(id) ON DELETE SET NULL,
    project_id TEXT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    autonomy_level INTEGER NOT NULL,
    status TEXT NOT NULL,                  -- DRAFT | APPROVED | REJECTED | EXECUTED | STOPPED
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_plan_steps (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES cb_plans(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    description TEXT NOT NULL,
    tool_id TEXT NULL,
    role_id TEXT NULL,
    required_level INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
);

CREATE INDEX IF NOT EXISTS idx_cb_plan_steps_plan ON cb_plan_steps(plan_id, ordinal);

-- ---------------------------------------------------------------------------
-- Tools
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_tool_definitions (
    tool_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    required_level INTEGER NOT NULL,
    read_only INTEGER NOT NULL,
    input_schema_hash TEXT NOT NULL,
    output_schema_hash TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_tool_invocations (
    id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL,
    plan_id TEXT NULL,
    envelope_id TEXT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NULL,
    status TEXT NOT NULL,                  -- OK | REJECTED | FAILED
    error_code TEXT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cb_tool_invocations_tool ON cb_tool_invocations(tool_id, created_at);

-- ---------------------------------------------------------------------------
-- Model gateway
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_model_providers (
    provider_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    is_local INTEGER NOT NULL,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_model_endpoints (
    model_id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL REFERENCES cb_model_providers(provider_id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    is_local INTEGER NOT NULL,
    simulated INTEGER NOT NULL DEFAULT 0,
    verification_state TEXT NOT NULL,      -- VERIFIED | LIMITED | NOT_VERIFIED | OFFLINE | QUARANTINED
    context_limit INTEGER NOT NULL DEFAULT 0,
    tool_use INTEGER NOT NULL DEFAULT 0,
    structured_output INTEGER NOT NULL DEFAULT 0,
    cost_category TEXT NOT NULL DEFAULT 'UNKNOWN',
    latency_category TEXT NOT NULL DEFAULT 'UNKNOWN',
    data_sensitivity_policy TEXT NOT NULL DEFAULT 'SYNTHETIC',
    permitted_project_classes TEXT NOT NULL DEFAULT '[]',
    last_verified_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS cb_model_capabilities (
    model_id TEXT NOT NULL REFERENCES cb_model_endpoints(model_id) ON DELETE CASCADE,
    capability TEXT NOT NULL,              -- text | vision | audio | embeddings | deterministic
    supported INTEGER NOT NULL,
    PRIMARY KEY (model_id, capability)
);

-- ---------------------------------------------------------------------------
-- Agents
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_agent_roles (
    role_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    max_autonomy INTEGER NOT NULL,
    output_schema_hash TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_agent_instances (
    id TEXT PRIMARY KEY,
    role_id TEXT NOT NULL REFERENCES cb_agent_roles(role_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_agent_assignments (
    id TEXT PRIMARY KEY,
    job_id TEXT NULL,
    envelope_id TEXT NULL,
    role_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    lane_id TEXT NULL,
    status TEXT NOT NULL,                  -- DISPATCHED | SUCCEEDED | REJECTED | FAILED | QUEUED_HUMAN
    output_hash TEXT NULL,
    error_code TEXT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS cb_jobs (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NULL,
    kind TEXT NOT NULL,
    state TEXT NOT NULL,                   -- QUEUED | RUNNING | SUCCEEDED | FAILED | STOPPED
    envelope_id TEXT NULL,
    stop_requested INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cb_jobs_state ON cb_jobs(state, created_at);

-- ---------------------------------------------------------------------------
-- Tournaments
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_tournaments (
    tournament_id TEXT PRIMARY KEY,
    project_id TEXT NULL,
    question TEXT NOT NULL,
    baseline_candidate_id TEXT NULL,
    baseline_hash TEXT NOT NULL,
    status TEXT NOT NULL,                  -- PLANNED | RUNNING | COMPLETE | STOPPED
    accepted_candidate_id TEXT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS cb_tournament_candidates (
    candidate_id TEXT PRIMARY KEY,
    tournament_id TEXT NOT NULL REFERENCES cb_tournaments(tournament_id) ON DELETE CASCADE,
    role_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    iteration INTEGER NOT NULL DEFAULT 0,
    is_baseline INTEGER NOT NULL DEFAULT 0,
    simulated INTEGER NOT NULL DEFAULT 0,
    output_hash TEXT NOT NULL,
    output_json TEXT NOT NULL,
    status TEXT NOT NULL,                  -- SCORED | ACCEPTED | REJECTED | QUARANTINED
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_candidate_scores (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES cb_tournament_candidates(candidate_id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    value REAL NOT NULL,
    weight REAL NOT NULL,
    blocking INTEGER NOT NULL DEFAULT 0,
    detail_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_cb_candidate_scores_candidate ON cb_candidate_scores(candidate_id);

CREATE TABLE IF NOT EXISTS cb_judge_decisions (
    id TEXT PRIMARY KEY,
    tournament_id TEXT NOT NULL REFERENCES cb_tournaments(tournament_id) ON DELETE CASCADE,
    candidate_id TEXT NOT NULL,
    judge_role_id TEXT NOT NULL,
    judge_model_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    independent INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Authority: drafts, envelopes, approvals, leases
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_task_drafts (
    draft_id TEXT PRIMARY KEY,
    plan_id TEXT NULL REFERENCES cb_plans(id) ON DELETE SET NULL,
    project_id TEXT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_task_envelopes (
    envelope_id TEXT PRIMARY KEY,
    draft_id TEXT NULL REFERENCES cb_task_drafts(draft_id) ON DELETE SET NULL,
    project_id TEXT NULL,
    envelope_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    state TEXT NOT NULL,                   -- DRAFT | APPROVED | EXECUTED | EXPIRED | REVOKED
    autonomy_level INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS cb_approvals (
    approval_id TEXT PRIMARY KEY,
    envelope_id TEXT NULL,
    scope_hash TEXT NOT NULL,              -- binds the approval to exact envelope content
    approver_id TEXT NOT NULL,
    method TEXT NOT NULL,                  -- authenticated_ui | authenticated_api
    granted_at TEXT NOT NULL,
    expires_at TEXT NULL,
    consumed_at TEXT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cb_approvals_scope ON cb_approvals(scope_hash);

CREATE TABLE IF NOT EXISTS cb_lane_tokens (
    lane_id TEXT PRIMARY KEY,
    last_token INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cb_leases (
    lease_id TEXT PRIMARY KEY,
    lane_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    fencing_token INTEGER NOT NULL,
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    released_at TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_cb_leases_lane ON cb_leases(lane_id, released_at);

-- ---------------------------------------------------------------------------
-- Operational state the Command Brain reads and reports on
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_artifacts (
    artifact_id TEXT PRIMARY KEY,
    project_id TEXT NULL,
    artifact_class TEXT NOT NULL,          -- index_page | runsheet | workbook | report | test_suite
    label TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    byte_size INTEGER NOT NULL DEFAULT 0,
    locator TEXT NOT NULL,                 -- server-side only; never returned to a client
    synthetic INTEGER NOT NULL DEFAULT 1,
    quarantined INTEGER NOT NULL DEFAULT 0,
    registered_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cb_artifacts_project ON cb_artifacts(project_id, artifact_class);

CREATE TABLE IF NOT EXISTS cb_defects (
    defect_id TEXT PRIMARY KEY,
    project_id TEXT NULL,
    severity TEXT NOT NULL,
    summary TEXT NOT NULL,
    state TEXT NOT NULL,                   -- OPEN | RESOLVED
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_holds (
    hold_id TEXT PRIMARY KEY,
    project_id TEXT NULL,
    scope TEXT NOT NULL,                   -- release | workbook | global
    reason TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    released_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS cb_quarantine (
    id TEXT PRIMARY KEY,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_human_review_queue (
    item_id TEXT PRIMARY KEY,
    project_id TEXT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NULL,
    question TEXT NOT NULL,
    context_json TEXT NOT NULL DEFAULT '{}',
    state TEXT NOT NULL,                   -- OPEN | ANSWERED
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cb_test_suites (
    suite_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Memory
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_memory_items (
    id TEXT PRIMARY KEY,
    project_id TEXT NULL,
    kind TEXT NOT NULL,                    -- VERIFIED_FACT | USER_INSTRUCTION | MODEL_INFERENCE |
                                           -- PROPOSED_PLAN | ACCEPTED_DECISION | SUPERSEDED |
                                           -- REJECTED_CANDIDATE | OPEN_QUESTION
    statement TEXT NOT NULL,
    source TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    superseded_by TEXT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cb_memory_project ON cb_memory_items(project_id, kind);

-- ---------------------------------------------------------------------------
-- Append-only ledger: receipts and audit events
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cb_receipts (
    receipt_id TEXT PRIMARY KEY,
    project_id TEXT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS cb_receipts_no_update BEFORE UPDATE ON cb_receipts
BEGIN
    SELECT RAISE(ABORT, 'cb_receipts is append-only');
END;

CREATE TRIGGER IF NOT EXISTS cb_receipts_no_delete BEFORE DELETE ON cb_receipts
BEGIN
    SELECT RAISE(ABORT, 'cb_receipts is append-only');
END;

CREATE TABLE IF NOT EXISTS cb_audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NULL,
    actor_type TEXT NOT NULL,              -- operator | system | agent | model
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cb_audit_time ON cb_audit_events(created_at, id);
CREATE INDEX IF NOT EXISTS idx_cb_audit_entity ON cb_audit_events(entity_type, entity_id);

CREATE TRIGGER IF NOT EXISTS cb_audit_no_update BEFORE UPDATE ON cb_audit_events
BEGIN
    SELECT RAISE(ABORT, 'cb_audit_events is append-only');
END;

CREATE TRIGGER IF NOT EXISTS cb_audit_no_delete BEFORE DELETE ON cb_audit_events
BEGIN
    SELECT RAISE(ABORT, 'cb_audit_events is append-only');
END;
