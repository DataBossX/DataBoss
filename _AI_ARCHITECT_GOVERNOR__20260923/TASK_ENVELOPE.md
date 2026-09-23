# Task envelope v2: hashable fields, vetoes, and gates

Design only. The implementation belongs in `src/databossx/governor/envelope.py`
and `vetoes.py` (see `IMPLEMENTATION_DELTA.md`). It replaces v0's
`compile_envelope` payload, which hashes only eight fields and defaults to a
write allowlist that includes the governor's own source.

An envelope is the complete, sealed contract for one cycle's mutable work. A
human approval binds its hash, and the builder may do only what it permits.
If anything in it changes, it is a new envelope and needs a new approval.

## 1. Fields

Every field is required. Values are JSON strings, integers, booleans, lists,
and objects. **No floats anywhere.**

| Field | Type | Meaning | Validation |
| --- | --- | --- | --- |
| `schema` | string | `databossx.governor.task_envelope/2` | exact match |
| `cycle_key` | string | `gov-cycle-NNNN` | equals the open `governor_cycles.cycle_key` |
| `scope` | string | mutable scope the writer lease covers, such as `repo:DataBossX/DataBoss` | equals the lease scope |
| `autonomy_level` | string | highest level the envelope may reach: `L0` to `L3` | never `L4` (SQL `CHECK`). L3 also needs an `AUTHORIZE_L3_CANARY` approval, because `public-safe.toml` caps autonomy at L2 |
| `proposal_hash` | hex64 | selected proposal | equals `governor_rank_decisions.selected_proposal_id`'s hash |
| `rank_decision_hash` | hex64 | `governor_rank_decisions.decision_hash` | exists |
| `base.repo` | string | public `owner/name` | allowlisted in governor policy |
| `base.ref_name` | string | branch the base was read from (informational) | non-empty |
| `base.commit` | hex40 | exact base commit | `git rev-parse HEAD` in the worktree equals it before every stage |
| `base.tree` | hex40 | tree of `base.commit` | `git rev-parse <commit>^{tree}` equals it |
| `base.require_clean_tree` | bool | the worktree has no changes except the builder's | always `true` |
| `inputs[]` | `{path, sha256}` | every file the builder relies on, hashed at base | recomputed at BUILD and TEST; any drift is BLOCKED `input_hash_drift` |
| `read_allowlist[]` | glob | readable repository paths | repository-relative; no `..`; no absolute paths |
| `write_allowlist[]` | path | exact repository-relative files the diff may touch | `git diff --name-only` must be a subset; no globs; no V6-protected path |
| `capabilities[]` | string | granted capabilities | each passes the kernel `PolicyEngine.decide(...)`, **after** the unknown-capability deny fix (`IMPLEMENTATION_DELTA.md` 0.3) |
| `denied_capabilities[]` | string | explicit denials (defense in depth) | includes all of the kernel `EXTERNAL_WRITE_CAPABILITIES` plus `workbook.write`, `model.remote`, `egress.any`, `governor.self_edit`, `policy.edit`, `migration.edit` |
| `egress_allowlist[]` | string | network destinations | empty for L2 and L3 in the public-safe profile |
| `env_allowlist[]` | string | environment variable names passed to the sandbox | no name matching `*KEY*`, `*TOKEN*`, `*SECRET*`, `*PASSWORD*`, `*CREDENTIAL*` |
| `budgets` | object of int | `max_files_changed`, `max_diff_added_lines`, `max_diff_removed_lines`, `max_test_invocations`, `max_wall_seconds`, `max_model_calls`, `max_cost_usd_cents` | each at most the governor policy ceiling; exceeding one is ABORTED |
| `tests.command_hash` | hex64 | `content_hash(argv)` of the test command | recomputed per evaluation |
| `tests.env_manifest_hash` | hex64 | `content_hash` of Python, SQLite, platform, test package versions, `requirements.txt` hash | recomputed per evaluation; drift is BLOCKED |
| `tests.target[]` | path | new or changed test files | inside `write_allowlist` |
| `tests.must_fail_at_base[]` | node id | nodes that must fail with the test applied and the fix absent (red proof) | non-empty for `regression_test_and_minimal_fix` |
| `tests.must_pass_at_base[]` | node id | guard nodes that must pass at base (proves the test is not trivially red) | may be empty |
| `tests.invariant[]` | id | governor-native checks | includes `governor.vetoes`, `governor.diff_within_write_allowlist`, `governor.no_schema_change`, `governor.synthetic_fixture_marker` |
| `tests.golden[]` | node id | existing suites | `tests` for repository-scope cycles |
| `tests.adversarial[]` | id | adversarial suites and probes | includes `tests/test_publication_policy.py` and `governor.secret_scan.diff` |
| `tests.rerun_for_reproducibility` | int | identical candidate runs | at least 2 |
| `tests.baseline_must_be_green` | bool | base golden suite is green in the sandbox | always `true` |
| `canary` | object | `level`, synthetic `fixture`, `must_hold[]`, `expected_output_delta` | fixture is a synthetic generator or a file carrying the synthetic marker |
| `rollback` | object | `method`, `rehearsal` | rehearsal is executable: revert the fix only, red again, reapply, tree restored |
| `review` | object | `independent`, `reviewer_must_differ_from[]`, `blocking_dimensions[]` | reviewer differs from builder and proposer |
| `receipts` | object | `terminal_required: true`, `chain: "prev_receipt_hash"` | fixed |
| `terminal_states[]` | string | allowed terminals | exactly the five in `ARCHITECTURE.md` section 7.1 |
| `vetoes_evaluated[]` | string | veto ids that must all be `CLEAR` | exactly V1 to V6 below |
| `provenance` | object | `issues[]` and optional `donor_prs[]` of `{pr, commit}` | public references only |
| `created_at` | string | `YYYY-MM-DDTHH:MM:SSZ` | set once at compile |
| `expires_at` | string | `YYYY-MM-DDTHH:MM:SSZ` | after `created_at`; at most 24 hours later; expiry blocks at the next `tick` |

Deliberately **not** in the envelope:

- **Fence.** It is issued at authorization and recorded in
  `governor_approval_uses.fence`. It answers "who may write now", which is
  separate from "what may be written".
- **Approval ids.** The approval references the envelope hash, not the
  reverse.
- **Model names or prompts.** Cycle 1 uses no model (`max_model_calls = 0`).
  A later envelope that uses a model adds `routes[]`, referencing route
  decisions only once PR #107-style routing is canonical.

`envelope_id` is `envelope_hash[:16]`, replacing v0's `uuid4`, so a
recompiled identical envelope has the same id and the `UNIQUE` constraint
rejects it.

## 2. Canonical hashing rule

```text
envelope_hash = sha256(canonical_json(envelope))

canonical_json(x) = json.dumps(x, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False).encode("utf-8")
  raises on float, NaN, Infinity, bytes, and non-string dict keys
  list order is preserved; the compiler sorts set-like lists before sealing
  (allowlists, capabilities, env names, test id lists, terminal states, veto ids)
```

This is the foundation's manifest serializer (`src/databossx/intake.py:17-18`)
plus `ensure_ascii=False` and a float ban. The same function hashes
proposals, rank decisions, learning records, outcome sets, and receipts.

Sealing and authorization:

1. `envelope.compile(...)` builds the object and sorts set-like lists.
2. `envelope.validate(env)` applies every rule in section 1 and every veto in
   section 3.
3. `envelope.seal(env)` computes the hash and inserts `task_envelopes` with
   state `SEALED`. Content is immutable by trigger.
4. A human runs
   `databossx governor approve --purpose AUTHORIZE_L2 --hash <envelope_hash> --expires <Z time>`.
   This inserts `approvals(project_id='governor', artifact_hash=<envelope_hash>, expires_at=<at most envelope.expires_at>)`.
   The CLI prints scope, base commit, write allowlist, budgets, and veto
   results. It requires the operator to type the first 12 hex characters of
   the hash and to attest that no release hold covers the scope. The
   attestation is stored in `payload_json`.
5. `authorize.consume(...)` inserts `governor_approval_uses` with the current
   fence. The SQL trigger rejects a wrong hash, a non-governor project, a
   missing or past expiry. The primary key rejects reuse. Python also rejects
   an approver id equal to a lease holder or beginning with `governor`.

## 3. Hard vetoes

A veto is a deterministic predicate. A hit stops the proposal (`vetoed`) or
the cycle (BLOCKED). It is recorded as a `VetoResult` holding only the rule
id, path, and line, and it cannot be overridden inside the governor. A human
changes veto rules only through a normal reviewed PR, never through a cycle
(V6).

Vetoes are evaluated at PRIORITIZE (proposal), at seal (envelope), after BUILD
(diff), and before DECIDE (diff, reports, receipt draft). The v0 ids in
`governor/models.py` `HARD_VETOES` map as shown.

| Id | v0 ids | Deterministic check |
| --- | --- | --- |
| `V1_CLIENT_EVIDENCE` | `client_evidence` | Any read, input, fixture, or diff path under `runtime/projects/` other than `governor`, `private_projects/`, `projects/OK-*`, a user home, or an absolute path. Any new fixture text lacking `SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA` (or `SYNTHETIC`/`FICTIONAL` under `examples/`). Any `project.read` capability for a project other than `governor` |
| `V2_WORKBOOK_MUTATION` | `workbook_mutation` | Any diff path ending `.xlsx`, `.xlsm`, `.xls`, `.xltx`, or `.ods`. Any `workbook.write` capability. Any new test opening a workbook path not derived from `tmp_path` (AST check `governor.workbook_paths_tmp_only`). Changes to `horizon/repair.py` or `horizon/workbook*.py` are not vetoed, but score risk of at least 4, so they are never auto-selected |
| `V3_EXTERNAL_RELEASE` | `external_release`, `auto_merge` | Any kernel `EXTERNAL_WRITE_CAPABILITIES` entry (`drive.write`, `drive.delete`, `drive.share`, `dropbox.write`, `github.write`, `original.mutate`, `report.release`) in `capabilities`. Any sandbox command other than the allowlisted `git worktree/apply/diff/commit/revert/rev-parse/status/write-tree` and `python -m pytest`. Any push, tag, merge, deploy, or publish. The governor never opens a PR; that needs a separate human `OPEN_DRAFT_PR` approval bound to `patch_sha256` and the destination branch |
| `V4_SECOND_CONTROL_PLANE_OR_DUPLICATE_IMPLEMENTATION` | `second_control_plane` | Diff adds `CREATE TABLE`, `CREATE VIRTUAL TABLE`, or `ALTER TABLE`; a `sqlite3.connect(` outside `src/databossx/database.py`; a new `*.db` path; socket `bind`/`listen`, `http.server`, `threading.Thread`, an `asyncio` server, cron, or schedule usage; or a module named like `queue`, `ledger`, `approval`, `lease`, `outbox`, or `orchestrator`. At the proposal level: the target or write paths overlap an open PR's changed symbols in the operator-supplied open-PR snapshot. That is duplicate implementation, and the proposal must be resolved by a human choosing one line |
| `V5_SECRET_EXPOSURE` | `secret_exposure` | The `FORBIDDEN` patterns in `governor/policy_gate.py` (credential assignments, provider key prefixes, private-key headers), applied **without** the `_AI_*` allowlist to the diff, new files, junit reports, the review bundle, and the receipt draft. Also: Drive file URLs; a high-entropy detector (at least 32 base64 or hex characters with Shannon entropy of at least 4.0 bits per character, excluding 40- and 64-hex values that appear in the envelope's own hash fields); and any `env_allowlist` name matching the secret-name pattern. A hit records rule id, path, and line only |
| `V6_SELF_MODIFICATION_OR_PERMISSION_EXPANSION` | `permission_expansion`, `history_rewrite` | Diff touches `src/databossx/governor/**`, `src/databossx/policy.py`, `src/databossx/tasks.py`, `src/databossx/database.py`, `config/**`, `migrations/**`, `.github/**`, `SECURITY.md`, `requirements*.txt`, `pyproject.toml`, or `tests/test_governor*.py`. Envelope requests capabilities or budgets above policy ceilings, or a level above what the approval purpose allows. Any history-rewriting git command. Changes to the governor are ordinary human-reviewed PRs, never governor cycles |

V1 to V5 are the five vetoes named in the request. V6 comes from the OS
blueprint's self-builder limits and v0's own `permission_expansion` and
`history_rewrite` ids.

## 4. Blocking gates

A failed gate is not a veto; it ends the cycle with the listed terminal
(BLOCKED, REJECTED, or ABORTED are short for the section 7.1 names).

| Gate | Stage | Check | On failure |
| --- | --- | --- | --- |
| `G_KNOWN_SINGLE_WRITER` | every tick | caller's lease row is the highest fence, unreleased, unexpired | BLOCKED `stale_fence` |
| `G_NOT_HALTED` | every tick | `governor_scope_controls.halted = 0` | ABORTED `halted` |
| `G_KERNEL_PRESENT` | before AUTHORIZE | tracked runner, `tasks.transition`, deny-by-default `PolicyEngine`, `review_gates` all importable or present | BLOCKED `kernel_slice_absent` |
| `G_BASE_UNCHANGED` | every tick after OBSERVE | worktree `HEAD` equals `base.commit`; tree equals `base.tree` | BLOCKED `baseline_drift` |
| `G_INPUT_HASHES` | BUILD, TEST | every `inputs[].sha256` matches | BLOCKED `input_hash_drift` |
| `G_APPROVAL_VALID` | AUTHORIZE, CANARY | approval use inserted (hash, project, expiry, single use) | BLOCKED `missing_or_stale_approval` |
| `G_NO_ACTIVE_HOLD` | AUTHORIZE | hold attestation present in the approval payload | BLOCKED `hold_unattested` |
| `G_BASELINE_GREEN` | TEST | BASELINE has zero failed or errored nodes | BLOCKED `baseline_not_green` |
| `G_RED_PROOF` | BUILD | every `must_fail_at_base` node fails and every `must_pass_at_base` node passes with the test applied and the fix absent; no other node changes outcome | REJECTED `no_red_proof` |
| `G_DIFF_SCOPE` | BUILD | diff paths are within `write_allowlist`; budgets respected | REJECTED `scope_or_budget` |
| `G_CANDIDATE_GREEN` | TEST | CANDIDATE golden, adversarial, and invariant all pass | REJECTED `candidate_failed` |
| `G_REPRODUCIBLE` | TEST | RERUN counts and `outcome_set_hash` equal CANDIDATE | REJECTED `unreproducible_evaluation` |
| `G_ROLLBACK_REHEARSAL` | TEST | reverting only the fix makes exactly `must_fail_at_base` fail again; reapplying restores the candidate tree SHA | REJECTED `rollback_failed` |
| `G_INDEPENDENT_REVIEW` | REVIEW | a `review_decisions` `APPROVE` from a reviewer outside `reviewer_must_differ_from`; `BLOCK` or `REQUEST_CHANGES` stops the cycle | REJECTED `blocking_review` |
| `G_CANARY` | CANARY | every `canary.must_hold` passes; normalized output delta matches `expected_output_delta` | REJECTED `canary_failed` |
| `G_NO_UNSUPPORTED_EVIDENCE_CLAIM` | DECIDE | the diff adds no value-producing path that sets a fact without a label or source rule; receipt text makes no title or legal conclusion | REJECTED `unsupported_conclusion` |
| `G_BUDGET` | every tick | usage at most `budgets` | ABORTED `budget_exceeded` |
| `G_RECEIPT_WRITTEN` | CLOSE | vault bytes hash to `receipt_hash`; the chain trigger accepted the row | the cycle stays open and the scope halts `missing_terminal_receipt` for a human to investigate |

## 5. Example

The sealed envelope for the first cycle, with its computed hash
(`45b4d660...297f`), is in `FIRST_CYCLE.md` section 4.
