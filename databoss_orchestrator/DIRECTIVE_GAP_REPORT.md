# Directive gap report

Status: **PHASE 0 FOUNDATION**

This pull request provides package installation, validated local file-drop
claims, non-overwriting receipts, and basic health reporting. It does not yet
implement the canonical bidirectional agent bus, a continuously running watcher,
or Drive synchronization. A copied package is only a claim and is not proof of
execution or completion.

## Implemented foundation

- strict Pydantic job and receipt models;
- allowlisted prompt and output paths;
- safe opaque job identifiers;
- approval-required fail-closed behavior without persisted raw tokens;
- staged job-package publication and atomically reserved, non-overwriting receipts;
- duplicate job-ID rejection;
- local adapter health reporting.

## Open directive requirements

- [ ] watcher schema 1.0 compatibility contract and fixtures
- [ ] explicitly validated schema 2.0 envelope
- [ ] `agent_message`, `agent_task`, `agent_review`, `tournament_task`,
      `status_request`, `cancel_request`, and `communication_loop_self_test`
- [ ] complete message envelope, authenticated agent identity, and allowlists
- [ ] CLAIM, HEARTBEAT, PROGRESS, RESULT, ERROR, HASHES, METRICS, and COMPLETE
      artifact collection
- [ ] canonical router and parallel dispatch
- [ ] tournament scoring, champion synthesis, and follow-up routing
- [ ] terminal response collection
- [ ] content-hash idempotency and deduplication beyond job-ID rejection
- [ ] replay protection and message-loop limits
- [ ] bounded retries, exponential backoff, timeout enforcement, and cancellation
- [ ] stale-heartbeat handling, dead-letter quarantine, and restart recovery
- [ ] secret-content detection and receipt/log redaction
- [ ] junction, time-of-check/time-of-use, and platform-specific reparse-point tests
- [ ] immutable hash-chained audit events
- [ ] Google Drive `to_cursor` / `from_cursor` integration
- [ ] Windows startup/service packaging and single-instance locking
- [ ] 60-second watcher health heartbeat
- [ ] command-center dashboard status
- [ ] end-to-end Drive handshake and completion artifacts with verified readback

These items must remain open until demonstrated by tests and terminal receipts.
PR approval or merge must not be inferred from this foundation.
