# RED TEAM TEST PLAN — DataBossX Command Center

Suites: `tests/command_center/test_red_team.py` (67), `test_api_security.py` (30),
`test_control_kernel.py` (30), `test_slice_and_moves.py` (27). **154 total, all
executed, all passing.**

Run:

```bash
PYTHONPATH=services/control_api python -m unittest discover -s tests/command_center -t . -p "test_*.py"
```

Standard applied to every case: the failure must be **visible, safe,
understandable, and auditable**. Silent partial success counts as a failure.

## Directive-required scenarios → coverage

| # | Required scenario | Test | Result |
| --- | --- | --- | --- |
| 1 | Unauthenticated access | `test_protected_routes_reject_anonymous_requests` | 401 on all 6 routes |
| 2 | Viewer attempts approval | `test_viewer_cannot_approve` | `NotAuthorized` |
| 3 | Expired session | `test_expired_session_is_refused` | 401 |
| 4 | Expired approval | `test_expired_approval_is_refused` | `ApprovalExpired` |
| 5 | Approval replay | `test_approval_replay_is_refused` | `ApprovalAlreadyConsumed` |
| 6 | Approval used for a different resource | `test_approval_for_a_different_resource_is_refused` | `ApprovalScopeMismatch` |
| 7 | Changed parameters after approval | `test_changed_parameters_after_approval_are_refused` | `ApprovalScopeMismatch` |
| 8 | Duplicate command | `test_duplicate_command_returns_the_original` | same `command_id` |
| 9 | Duplicate mobile tap | `test_duplicate_mobile_tap_creates_only_one_command` | 6 taps → 1 command |
| 10 | Replayed job | `test_completed_job_cannot_be_replayed` | `IntegrityError` |
| 11 | Arbitrary command attempt | `test_arbitrary_shell_command_is_not_representable` | not representable |
| 12 | Arbitrary path attempt | `test_absolute_paths_are_rejected_as_scopes` | `PathNotAllowed` ×4 |
| 13 | Path traversal | `test_path_traversal_is_rejected` | `PathNotAllowed` ×3 |
| 14 | Stale lease | `test_stale_lease_prevents_execution` | `LeaseExpired` |
| 15 | Old fencing sequence | `test_old_fencing_sequence_prevents_execution` | `StaleFencingToken` |
| 16 | Lost heartbeat | `test_lost_heartbeat_expires_the_lease_and_frees_the_scope` | expired, new sequence |
| 17 | Hash mismatch | `test_command_file_hash_mismatch_is_refused` | `ReadbackMismatch` |
| 18 | Artifact changed after approval | `test_artifact_changed_after_approval_is_refused` | `ArtifactChanged` |
| 19 | Audit write failure | `test_state_change_and_audit_share_a_transaction` | state rolled back |
| 20 | Outbox failure | `test_interrupted_transaction_leaves_no_partial_state` | no partial rows |
| 21 | Database interruption | same | chain still valid |
| 22 | Drive notification missed | `test_missed_notification_is_caught_by_reconciliation` | reported untracked |
| 23 | Drive upload incomplete | `test_incomplete_upload_is_detected_by_readback` | pointer not advanced |
| 24 | Drive readback mismatch | `test_readback_mismatch_refuses_and_does_not_advance_the_pointer` | `ReadbackMismatch` |
| 25 | Runner disconnect mid-job | `test_runner_disconnect_mid_job_leaves_a_failed_receipt_not_silence` | fail-closed receipt + rollback |
| 26 | Client hold removal attempt | `test_hold_removal_is_refused_for_every_role` | refused for all 4 roles |
| 27 | Simulated presented as real | `test_watcher_flags_a_simulated_result_presented_as_real` | `REQUEST_CHANGES` |
| 28 | Prompt injection in a document | `PromptInjectionTests` (3) | classified `PROHIBITED` |
| 29 | Contradictory title claims | `test_contradictory_claims_do_not_silently_resolve` | both versions retained |
| 30 | Unknown ownership balance | `test_unknown_ownership_balance_is_reported_not_forced` | remainder reported |
| 31 | Secret-status probing | `test_no_secret_status_endpoint_exists` | 404 on all 5 |
| 32 | Absolute path leakage | `test_absolute_paths_are_redacted_from_phone_responses` | redacted |
| 33 | Wildcard CORS regression | `test_cors_is_never_wildcard_with_credentials` | no header for foreign origin |
| 34 | Raw evidence exfiltration | `test_raw_evidence_never_leaves_as_an_artifact` | watcher blocks |

All 34 required scenarios covered.

## Additional coverage beyond the required list

- **Concurrency:** 12 threads on 12 connections race one scope — exactly one
  winner, eleven `LEASE_HELD`.
- **Constraint bypass:** direct SQL insert of a second ACTIVE lease → rejected.
- **Audit tamper detection:** triggers dropped, a row edited — the hash chain
  still reports the tamper.
- **Immutability:** accepted artifact versions cannot be updated or deleted;
  command transcripts cannot be rewritten.
- **Watcher isolation:** `ReadOnlyView` refuses non-SELECT SQL and has no write
  surface at all.
- **Honest reporting:** watchers report `NOT_RUN` rather than `PASS` for checks
  they could not execute.
- **Kill switch:** engaged switch refuses all work before verification.
- **Step-up:** consequential approval without step-up → `StepUpRequired`.
- **Binding:** any non-loopback bind → `NotAuthorized`.
- **Visual:** 7 viewports, 0 findings (`scripts/command_center_visual_qa.py`).

## Not covered here, and why

| Gap | Reason |
| --- | --- |
| Real WebAuthn assertion replay | No authenticator available; step-up is a stub |
| Postgres-specific concurrency (SELECT FOR UPDATE, deadlocks) | No Postgres reachable — ADR-0003, blocks canary |
| Real Google Drive API faults (429, partial upload, revoked token) | No Drive write authority — ADR-0004 |
| TLS/HSTS behaviour | No TLS terminator in this environment |
| Load and soak testing | Out of scope for a first vertical slice |

These are listed as open gaps, not as passing tests.
