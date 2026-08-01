# Command Brain Alpha — Threat Model

Scope: the Command Brain subsystem only. It inherits the repository-wide controls
in `SECURITY.md` and the publication boundary in
`DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md`.

## Assets

| Asset | Why it matters |
| --- | --- |
| Accepted baselines and released artifacts | Overwriting one destroys reviewed work. |
| Release and workbook holds | A hold is the last gate before client harm. |
| Client evidence and workbooks | Confidential; excluded from Alpha entirely. |
| Approvals, leases, fencing tokens | The authority chain itself. |
| The audit ledger and receipts | Reconstructability of every decision. |
| Credentials and local filesystem layout | Direct compromise / reconnaissance. |
| The operator's voice channel | An always-listening authority surface. |

## Trust boundaries

```
   untrusted                     |  trusted local boundary
 ------------------------------- | -------------------------------------
 audio in the room               |  VoiceSession (activation token)
 document text quoted into chat  |  IntentEngine (quoted-content separation)
 model / agent output            |  schemas.validate + scoring + judge
 browser payloads                |  server.py (CSRF, origin, no paths accepted)
 remote model endpoints          |  ModelGateway (policy filters, egress rules)
```

Everything on the left is data. None of it is authority.

## Threats and controls

### T1 — Spoken prompt injection

*Someone speaks a command near the machine, or audio plays through the speakers.*

- Capture requires a press-to-talk activation token; audio with no matching token
  is discarded (`voice.submit_audio`).
- Tokens are single-use — a replayed token is refused.
- The transcript is displayed and confirmed before it becomes an intent.
- Consequential work still needs a separate authenticated approval.
- Voice biometrics are explicitly **not** treated as authorization.

Tests: `test_audio_without_activation_token_is_discarded`,
`test_replayed_activation_token_is_refused`,
`test_voice_session_requires_an_authenticated_session`.

### T2 — Document-borne prompt injection

*A deed, webpage, or report contains "IGNORE PREVIOUS INSTRUCTIONS…".*

- `segment_transcript` separates quoted spans (`"…"`, `<document>…</document>`,
  `>` lines) and marks them `QUOTED_DOCUMENT`.
- Imperatives found there are reported as detected injection and shown as
  warnings; they never become the intent.
- `PolicyEngine` refuses any action whose `authority_source` is
  `QUOTED_DOCUMENT`, unconditionally.

Tests: `test_quoted_document_instructions_cannot_become_authority`,
`test_quoted_authority_source_is_refused_by_policy`.

### T3 — Model output treated as truth

*An agent returns a confident, wrong, or malicious payload.*

- Every agent output is schema-validated before it can influence state; a shape
  mismatch is a recorded refusal, not a partial success.
- Scoring is deterministic and does not read the model's confidence as evidence.
- The producing agent may not be the sole judge (`assert_independent`).
- Blocking gates catch fabrication regardless of aggregate score.
- Majority agreement cannot overwrite a cell any reader called unreadable.

Tests: `test_agent_output_is_schema_validated`,
`test_agent_cannot_be_the_only_judge_of_its_own_result`,
`test_hallucinated_values_are_penalised_and_quarantined`,
`test_a_majority_vote_cannot_override_clear_source_evidence`.

### T4 — Tool abuse (shell, path, credential)

*Something tries to smuggle a command or path through a tool argument.*

- Allowlist only; an unknown `tool_id` is a refusal.
- `scan_tool_input` rejects paths, traversal, shell syntax, and credentials
  anywhere in the payload, before schema validation.
- Tools accept stable IDs; the server resolves locators. `get_artifact_metadata`
  never returns one.
- `run_registered_test_suite` takes a registered suite ID, never a command line.

Tests: `test_arbitrary_shell_command_is_rejected`,
`test_filesystem_paths_are_rejected_everywhere`,
`test_credential_shaped_input_is_rejected`,
`test_test_suite_runner_rejects_anything_unregistered`.

### T5 — Privilege escalation by an agent or tool

*A component tries to widen what it may do.*

- The tool registry is frozen before first use; registration afterwards raises.
- `ToolContext` exposes no registry, policy engine, or grant method.
- Roles declare permitted *and* prohibited tools; overlap is a construction error.
- Approval authorizes one envelope; it never raises the operator's standing mode.

Tests: `test_a_tool_cannot_be_added_after_the_registry_is_frozen`,
`test_a_tool_handler_has_no_route_to_widen_permissions`,
`test_execution_requires_both_the_mode_and_the_approval`.

### T6 — Unauthorized mutation of client work

*Anything writes to a workbook, report, or released artifact.*

- Alpha registers no client artifact and no write-capable tool.
- Writer roles need an approved BOUNDED_WRITER envelope, a live single-writer
  lease, and a current fencing token — checked in that order.
- Two writers can never hold one lane.
- Client files are excluded by default (`client_files_allowed=False`).

Tests: `test_writer_role_requires_an_envelope`,
`test_writer_dispatch_from_an_utterance_alone_is_refused`,
`test_simultaneous_writers_on_one_lane_are_rejected`,
`test_client_files_are_excluded_by_default`.

### T7 — Stale authority

*A paused worker resumes, or an old approval is replayed.*

- Approvals expire, are single-use, and are bound to an exact envelope hash.
- Leases expire; a taken-over lane bumps the fencing token, so the stalled
  worker's token is stale and its write is refused.

Tests: `test_approval_scope_cannot_be_reused`,
`test_expired_approval_is_rejected`,
`test_approval_does_not_cover_a_different_scope`,
`test_stale_fencing_token_is_rejected_after_takeover`.

### T8 — Data exfiltration to a model provider

*Confidential content leaves the machine.*

- `local_only` makes every non-local adapter ineligible for routing and raises
  `EgressDenied` on direct invocation. `local_only` also forces
  `cloud_models_allowed=False`; the stronger statement wins.
- Adapters declare `permitted_project_classes`; a model not cleared for a class
  cannot be routed to it.
- Alpha's corpus is synthetic, so there is nothing confidential to leak.

Tests: `test_local_only_mode_makes_remote_endpoints_unreachable`,
`test_local_only_tournament_uses_only_local_models`.

### T9 — Secret or path disclosure

*A credential or `C:\DataBoss\…` reaches a phone, a log, or a receipt.*

- `redact()` runs on every audit event, every receipt, every command response,
  and the whole command-centre payload.
- Credential-shaped keys are replaced wholesale — never truncated to a "safe"
  suffix.
- Absolute paths become `[LOCAL_PATH:<basename>]`.
- `store.audit` re-scans after redaction and withholds the payload if anything
  secret-shaped survives.

Tests: the whole of `test_command_brain_privacy_audit.py`.

### T10 — Audit tampering

*Someone edits history to hide a decision.*

- `cb_audit_events` and `cb_receipts` refuse UPDATE and DELETE via triggers.
- Entries are hash-chained; `verify_ledger()` detects a rewrite even if the
  triggers are dropped.
- Corrections append (`voice.transcript_superseded`, `memory.superseded`) rather
  than editing.

Tests: `test_the_ledger_refuses_updates_and_deletes`,
`test_ledger_tampering_is_detectable`,
`test_a_correction_appends_rather_than_editing_history`.

### T11 — Runaway autonomy

*The system keeps working without anyone asking it to.*

- Candidate count, improvement iterations, timeout, and cost budget are capped
  and enforced (`BudgetExceeded`).
- The improvement loop stops on: no accepted candidate, improvement below
  threshold, operator stop, or iteration cap.
- `stop_queued_job` is available at OBSERVE and needs no approval.
- There is no background scheduler: nothing runs unless a call runs it.

Tests: `test_candidate_cap_is_enforced`, `test_iteration_cap_is_enforced`,
`test_improvement_loop_stops_when_improvement_is_insignificant`,
`test_stop_request_halts_remaining_candidates`.

### T12 — Network exposure

*The Command Center becomes reachable from outside the machine.*

- `make_server` refuses a non-loopback bind without an explicit override.
- CSRF token required on every mutating request; exact-origin checks; fixed-window
  rate limit; body size cap; no directory serving.
- The page is fully self-contained — a strict CSP has nothing external to fetch.

Tests: `test_server_refuses_a_non_loopback_bind`,
`test_server_binds_loopback_and_mints_a_csrf_token`,
`test_ui_page_is_self_contained`.

## Residual risks

These are real and are **not** closed by this work:

1. **Live audio is not implemented.** The activation-token design is sound, but
   the STT/TTS transports here are labelled simulators. A real microphone path
   needs its own review, particularly around wake-word false positives.
2. **Speaker identity is not established.** The session is authenticated; the
   *speaker* is not. Anyone with physical access to an unlocked, authenticated
   session can speak. Mitigated only by approval being a separate authenticated
   act.
3. **No real model has been verified.** Every non-deterministic capability is
   NOT_VERIFIED. Claims about a live model's vision or grounding quality remain
   unproven until a transport is configured and probed.
4. **The scoring rubric is calibrated against a synthetic benchmark.** Weights and
   thresholds — including the 0.75 human-review share — need re-calibration
   against reviewed real corrections before they govern real work.
5. **Reconciliation normalization is English/US-form specific.** Party and legal
   description normalization will need jurisdiction review.
6. **`hashing_bridge` cannot verify artifacts it cannot reach.** It returns
   NOT_VERIFIED honestly rather than guessing, but that means hash verification
   is unproven for artifacts stored outside this runtime.
7. **Alpha performs no coding-agent execution.** Claude Code and Codex lanes emit
   handoff packages. Wiring real execution is a separate authorization.

## Not in scope for Alpha

Level 4 (release, publish, send, deliver, connector writes), client evidence,
production databases, connector activation, network exposure, and any mutation of
an accepted workbook, report, or release hold.
