# Receipt: governor architecture packet

```text
TASK            = Design the Continuous Improvement Governor (Issues #68, #69) as a public-safe extension of src/databossx
TERMINAL        = PACKET_COMPLETE_FOR_INDEPENDENT_REVIEW
DISPOSITION     = PRESERVE_AS_TEST_OR_REFERENCE (design only; never runtime)
PACKET_COMPLETE = YES
DATE            = 2026-09-23
```

## Safety flags

```text
CLIENT_BYTES_MUTATED       = NO
CLIENT_EVIDENCE_READ       = NO
WORKBOOK_MUTATED           = NO
EXTERNAL_RELEASE           = NO
MERGED                     = NO
PRODUCTION_FILES_EDITED    = NO
SECRETS_IN_OUTPUT          = NO (see scan below)
NEW_CONTROL_PLANE_PROPOSED = NO (extends governor v0 and the existing tables)
HOLDS_CHANGED              = NO
```

## Writes

- Workspace writes: only the six Markdown files in
  `_AI_ARCHITECT_GOVERNOR__20260923/`. `README.md` was already tracked (parent
  commit `42ed7b2`) and was revised; the other five are new or rewritten.
- No git commit, push, branch switch, or PR by this architect. The parent
  owns git on the shared branch `cursor/kernel-governor-tournament-7f1f`.
- Outside the workspace: detached `/tmp` clones of `5fc0d6c` and of PR
  #114's tree, scratch scripts, and `python-dotenv` installed into a `/tmp`
  package directory for the backend tests. Remote-tracking refs for the PRs
  were fetched read-only. Nothing was pushed.

## Inputs read

| Input | Identity |
| --- | --- |
| `main` | `582d95161cf8220fb37f5224e21e57dcc5c3121c` |
| Branch head (base for all verification) | `5fc0d6c149b5ba5e5c30d4c08aa1c5ccfc074ff6`, tree `0968d5b642c301ce4c46dbddb12e567f01dd9bf9` |
| PR #114 (draft, open) | head `e8b9225a787be148a06e08a21e2b9134d33297d7` |
| PR #116 (open; challenger folder, not runtime) | head `9fffd8223dad7c23d0b8e1c108ebc9f70171abb9` |
| PR #107 `002_engine_tables.sql`, parked PR #67 `cb_*` | read for name collisions only |
| Issues #68, #69, #94 | read for the cycle, vocabulary, and mandatory regressions |
| `docs/DATABOSSX_OS_BLUEPRINT.md` | `842d001edc48496b68689afacc8a2371f11451626b655adf4d8c877dc02c56de` |
| `docs/architecture/databossx-os.build-plan.json` | `08cd82492b3616c0c2ecb787dcf2bb29777ce0f1b796944266e1e0f095f8e857` |
| `migrations/001_initial_schema.sql` | `efd548db59a04ab5841768072dbf311fc58dfa4a5bcf37f7ea4e3b122ed7d0dd` |
| `migrations/002_governor.sql` (v0) | `8a45adbd88f24c62d98854f4f79121b31af0b75df50a1223f4c264dac96390f3` |
| `config/policies/public-safe.toml` | `fa19ee83c2d744c7ed4706d01616ee3fc6785e5323372e88e64ed3fb8284a615` |
| `src/databossx/*.py`, `src/databossx/governor/*.py` at `5fc0d6c` | read in full; v0 `envelope.py` `eb516d41...`, `lease.py` `c614f7f9...`, `cycle.py` `4fec19d7...`, `policy_gate.py` `c052c0a3...` |
| PR #114 kernel files at `e8b9225` | `database.py` `fe018e7a...`, `tasks.py` `a7fc688a...`, `policy.py` `17f23b67...`, `002_kernel_and_connectors.sql` `0f102fd0...` (checked against `git show e8b9225:<path>`) |

## Verifications (all in `/tmp`; reproducible from the scripts named)

| # | Check | Result |
| --- | --- | --- |
| 1 | Revised `002_governor.sql` (sha256 `a49ccd173e6b8cf99296897f9cc06975bae5783af0c588feacd0f528f7818567`, 45 objects) against 001 (30), PR #114 `002` (11), PR #107 `002` (7), PR #67 `cb_*` (49) | 0 name collisions; no `ALTER TABLE`; no DDL for `tasks`, `approvals`, `audit_events`, `outbox_events`, `task_leases` |
| 2 | Same file under the branch's re-run-every-file runner, twice | applies cleanly both times |
| 3 | PR #114 `002` under the branch's runner, twice | **crashes** on the second run: `duplicate column name: input_manifest_hash` |
| 4 | 001 + PR #114 `002` + revised governor file under a tracked runner, twice | applies; each file recorded once |
| 5 | Trigger and constraint behavior (script `test_gov002_revised.py`, sha256 `9da9cd3e...0ec02`) | **67 of 67** pass: replace, edit, delete, float, and range blocked on proposals; lease stealing, `+00:00` expiry, reopen, non-monotonic fence, halted scope blocked; one open cycle per scope; close requires matching receipt; closed cycle frozen; receipt chain enforced; L4 envelope blocked; approval bound, live, governor-only, single-use; append-only evaluations and rank decisions; final learning review; benchmark activation requires reviewer |
| 6 | Revised file dropped into `5fc0d6c` with v0 code unchanged | `tests/test_governor.py`: 2 failed, 3 passed. The failures are v0's `+00:00` lease time and scope-less proposal, which the schema rejects by design |
| 7 | PR #114 `database.py`, `tasks.py`, `policy.py`, `002` copied byte-identical onto `5fc0d6c` with the revised file | full suite 173 passed, 2 failed (the same two v0 tests); double `initialize()` applies `001`, `002_governor`, `002_kernel_and_connectors` once each |
| 8 | PR #114 `PolicyEngine.decide` at `e8b9225` | unknown capability, `workbook.write`, `governor.self_edit` all **allowed** |
| 9 | Proposed deny-unknown fix (31-line diff) | those three denied; sandbox, `connector.scan`, `vault.copy`, `inventory.hash`, read-only Drive scan still allowed; PR #114 suite (head plus the appendix-A candidate) 177 passed before and after |
| 10 | Cycle-1 probes at `5fc0d6c` (script `probe_head.py`) | negated "not a complete" and "NOT the complete" FAIL; "is not complete" PASS (guard); affirmed PASS; "pending" FAIL; prose "is 0.5" FAIL |
| 11 | Cycle-1 suites | BASELINE 175 passed; RED_PROOF 2 failed (exactly `must_fail_at_base`), 177 passed; CANDIDATE 179 passed on two runs; rollback rehearsal 2 failed, 177 passed after revert, then 179 passed and tree `0948f1151dfcba70ef2bf62d3bfe8f0a978b6497` after reapply |
| 12 | Cycle-1 artifacts | test `3c1e2bc698a7115ee73ba90eac63952ee1051fcf441587c05a52d8f6444f1f05`; patch `9a9a41cd28c05dc5134291d5d8b22bbbfc266ff6433193cddc8b88c2d7c410a0` (2 files, +39 / -1); post-fix pipeline `56c78b2b675820ce02529af7c13232e839f9b204a87c62f70f816d5de67ffc79` |
| 13 | Cycle-1 canary (script `canary.py`) | the synthetic corpus's 0.95 `decimal-sum` still flagged at base and candidate; `review_required.csv` and `extracted_facts.csv` identical |
| 14 | Adversarial negation-scope probe (script `probe_scope.py`) | RF-1 confirmed: an unrelated "is not complete" line now suppresses the sum assertion on an affirmed schedule; "incomplete" already did so at base |
| 15 | Hash determinism (script `calc2.py`, sha256 `adb7f103...8f8f`) | three runs, identical output. Envelope `45b4d6606a6efb73b137fbc8ad23fca027684ec166584db1c580fe10689f297f`; P-A `2b455789fe353a5d49d26c3e58a0bd49b7c320c5896fdd11ccf12ee574998631`; rank decision `120f6aaa12b92d5246f2e0e9033968d95bb421231f0e1d4b7d3a409ac6f084d9`; canary binding `e45d098658839d360516b7145b84c0fb5d2a26a9fbaf782f21bc42f3230a74af` |
| 16 | SQL block in `ARCHITECTURE.md` | extracted bytes hash to `a49ccd17...8567` (identical to the tested file) |
| 17 | Public-safety scan of this folder with the branch's `FORBIDDEN` patterns (the `_AI_*` skip removed), plus Drive URL, host path, e-mail, and token-prefix patterns | no hit except one false positive (`governor_cycle@1.0.0` matches the e-mail pattern) |
| 18 | Branch packet judge (`judge_folders`) over this folder | not blocked; `clientish = False`, `second_os = False` |

## Findings for the owner

1. **Two Issue #94 lines exist**: this branch (`3149ead`, `5fc0d6c`) and PR
   #114 (`e8b9225`). One must be chosen before either merges.
2. **Governor v0 defects**: `envelope.py:12` lets a cycle write the
   governor's own source; `lease.py` lets a second worker acquire a live
   scope, reads and inserts outside a transaction, and uses `+00:00` times;
   `cycle.py:89` uses `INSERT OR REPLACE`; `cycle.py:110` decides by file
   existence; the scores are floats; there are no approvals, no audit rows,
   and no receipt chain. `tests/test_governor.py::test_stale_writer_rejected`
   encodes the lease stealing.
3. **Publication gate hole**: `policy_gate.py:40` skips every `_AI_*` path.
4. **PR #114 policy default-allow** (verification 8) contradicts its own
   docstring.
5. **Untracked migration runner**: PR #114's schema cannot be ported onto
   this branch without PR #114's tracked runner (verification 3).
6. **Issue #94 regression-4 residuals at `5fc0d6c`**: the negated-marker
   gap (first cycle), the "pending" marker (P-B), the prose "is" decimal
   (P-C), and document-wide vocabulary scope (RF-1, P-F).

## Packet file hashes (SHA-256, final)

```text
e36ba211352b4697d1d2bd29eb9b5e1846a3660c4b835c9508489b1f32876367  ARCHITECTURE.md
901e4ceffafff25aea26eb959876ddc3b068bce6e1fe7e6b33b1c3b1339ad4c0  FIRST_CYCLE.md
158d1b8d55a1b19d5d3860a9176cd069d4dfe3695777eea3ac2f96a44f0e893a  IMPLEMENTATION_DELTA.md
d95600937c2c46da6dbc734f40dddd64c7e5cdfc465c5a9a6f2caaf1a727a7ab  README.md
3ce8222b8e31307cd0a4a97d8a669046c1bb0263b0db68a6d1d4a36562f46477  TASK_ENVELOPE.md
```

`RECEIPT.md` cannot contain its own hash.

`FOR REVIEW - HOLD NO EXTERNAL RELEASE`
