# First governor cycle: `gov-cycle-0001` (synthetic only)

Design only. This is the exact first cycle the governor runs once
`IMPLEMENTATION_DELTA.md` phases 0 to 3 exist. The base is this branch's
head, `5fc0d6c149b5ba5e5c30d4c08aa1c5ccfc074ff6` (tree
`0968d5b642c301ce4c46dbddb12e567f01dd9bf9`). Every number below was
**pre-verified** in throwaway `/tmp` clones of that commit, with no workspace
or remote mutation. The evidence is in `RECEIPT.md`. Appendix A gives the
same cycle against PR #114's head, for use if the owner picks that Issue #94
line instead.

## 0. Why this cycle

Issue #94 mandatory regression 4 says incomplete owner sets must not assert a
false sum-to-one. Commits `3149ead` and `5fc0d6c` on this branch implement it
with a vocabulary gate in `grocery_report_pipeline.py`:

```text
_OWNER_SET_COMPLETE_RX   = \b(complete\s+owner(?:ship)?\s+set|owner\s+set\s+complete|schedule\s+total)\b
_OWNER_SET_INCOMPLETE_RX = \b(partial|incomplete|missing\s+owners?|owner\s+set\s+unknown)\b
_owner_set_is_complete(text) = not INCOMPLETE.search(text) and bool(COMPLETE.search(text))
```

The gap is that a **negated** marker still matches COMPLETE. "this is not a
complete owner set" contains "complete owner set", and nothing in INCOMPLETE
matches "not a complete". The document is treated as a complete owner set, so
two `0.25` decimals raise a false `decimal-sum` conflict ("Decimals sum to
0.5, expected 1.0"). That is the false-imbalance failure Issue #94 describes,
triggered by a document that says the opposite. No committed test pins it.
`tests/test_issue94_integrity.py` covers "partial" and the affirmed marker,
but no negation.

The governor must not "fix Issue #94" wholesale. This branch and PR #114
(`e8b9225`) each carry an Issue #94 implementation. Porting one onto the other
is proposal P-E below, vetoed by V4 until a human picks one line.

## 1. Preconditions (checked by `tick()`; any failure is BLOCKED)

| Check | Required value |
| --- | --- |
| Base | `HEAD == 5fc0d6c1...` and tree `0968d5b6...` in the worktree. If the branch moved, re-observe; this envelope is then void |
| Kernel slice | `IMPLEMENTATION_DELTA.md` phase 0 merged by a human: tracked runner, `tasks.transition`, deny-by-default `PolicyEngine`, `review_gates` (`G_KERNEL_PRESENT`) |
| Governor code | phases 1 to 3 merged by a human |
| Governor DB | `runtime/projects/governor/project.db` freshly created by `databossx governor init` (any v0-era file deleted first) |
| Writer lease | scope `repo:DataBossX/DataBoss`, not halted, no live holder |
| Open-PR snapshot | operator-supplied JSON listing open PRs 107, 114, 116 with changed paths; hashed into `duplicate_check` |
| Sandbox environment | mirrors CI: `pip install pytest` plus `requirements.txt` (sha256 `fa81e55e...`). Pre-verified with Python 3.12.3, SQLite 3.45.1, pytest 9.1.1, openpyxl 3.1.5, lxml 6.1.3, Pillow 12.3.0, fastapi 0.141.1, python-dotenv present |
| Holds | the operator attests at approval time that no release hold covers public synthetic code in this scope |

Observed pitfall from pre-verification: without `python-dotenv`, the backend
security tests fail on import, and when Pillow appeared mid-session, skipped
tests became passed. That is why `G_BASELINE_GREEN` is mandatory and why
evaluations hash the environment manifest and the full non-passed node set.

## 2. OBSERVE (L0)

Reviewed benchmark cases are `ACTIVE` in `governor_benchmark_cases` (source
`config/governor/benchmarks/issue94.json`). Each probe writes one synthetic
text file carrying `SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA` and runs
`grp.extract_facts` through the existing `_facts_from_text` helper in a
read-only worktree at the base commit.

| `case_key` | Synthetic line after the header | Expectation | Result at `5fc0d6c` |
| --- | --- | --- | --- |
| `issue94.r4.negated_marker.not_a_complete` | `OWNERSHIP schedule -- this is not a complete owner set` | `owner_set_complete is False` | **FAIL** (True) |
| `issue94.r4.negated_marker.not_the_complete_upper` | `OWNERSHIP schedule -- NOT the complete owner set` | False | **FAIL** (True) |
| `issue94.r4.negated_marker.is_not_complete` | `OWNERSHIP schedule -- owner set is not complete` | False | PASS (no COMPLETE phrase is adjacent); kept as a guard |
| `issue94.r4.affirmed_marker` | `OWNERSHIP schedule -- complete owner set` | True | PASS |
| `issue94.r4.pending_marker` | `OWNERSHIP schedule -- complete owner set pending; owner C not located` | False | **FAIL** (True) |
| `issue94.r3.prose_is_decimal` | `The decimal interest is 0.5` | decimals `[0.5]` | **FAIL** (`[]`; `_DECIMAL_RX` accepts `of` or `:` but not `is`) |

Every fixture also carries `Owner A decimal interest 0.25` (0.5 for the
affirmed case) and `Legal: Section 12, T7N, R63W`. Decimal edge forms `.5`,
`0.125`, `0.5.`, and `0.5,` parse correctly at this base, so they produce no
finding.

## 3. PROPOSE and PRIORITIZE (L0)

Five immutable proposals are registered, each with hash
`sha256(canonical_json(proposal))`.

| Key | Hash | value / risk / cost / reversibility / confidence | Veto | Score |
| --- | --- | --- | --- | --- |
| `P-A-issue94-r4-negated-complete-marker` | `2b455789fe353a5d49d26c3e58a0bd49b7c320c5896fdd11ccf12ee574998631` | 5 / 1 / 1 / 5 / 5 | none | `125/1` |
| `P-B-issue94-r4-pending-complete-marker` | `d468b63c57579fb20ae46b82729abb255ae78fa339c14d7a57e54b0149737e95` | 4 / 2 / 1 / 5 / 3 | none | `30/1` |
| `P-C-issue94-r3-prose-decimal` | `76eff15d571e4ee03917c6506a8d0f447f91057ab5dcb1d288fd13f98a4e4107` | 3 / 3 / 2 / 5 / 3 | none | `15/2` |
| `P-D-governor-narrow-own-allowlist` | `940bbc3ab300e05e24a7ff7b70a860349189eec8bf33d3db80807a53babc7c70` | 5 / 2 / 1 / 5 / 5 | **V6** (targets `src/databossx/governor/envelope.py`) | n/a |
| `P-E-port-pr114-issue94-fixes` | `91cbd5f298b1c3f08eaaed4d7751d2612b940305bf0696285c7c4c4a4a074090` | 4 / 4 / 4 / 3 / 4 | **V4** (duplicates open PR #114) | n/a |

Scoring rationale (rules in `ARCHITECTURE.md` section 8):

- **P-A** risk 1: adding an alternation to INCOMPLETE can only turn
  `owner_set_complete` from True to False (proof in section 6). Confidence 5:
  reproduced twice, and a guard case passes at base.
- **P-B** confidence 3: "pending" is ambiguous ("complete owner set pending
  recordation" may still be complete), so the right fix needs human wording.
  Deferred.
- **P-C** risk 3: widening `_DECIMAL_RX` creates new facts in every document.
  Deferred.
- **P-D** is a real governor defect (`envelope.py:12` lets a cycle edit the
  governor). V6 routes it to a human PR; it is item 1.3 of
  `IMPLEMENTATION_DELTA.md`. The governor never fixes itself.
- **P-E** would create a second Issue #94 implementation. A human must choose
  between this branch's line and PR #114's line.

P-A canonical content (hash `2b455789...8631`):

```json
{
  "base_commit": "5fc0d6c149b5ba5e5c30d4c08aa1c5ccfc074ff6",
  "class": "regression_test_and_minimal_fix",
  "duplicate_check": {"open_prs_scanned": [107, 114, 116], "overlapping_open_prs": []},
  "evidence": [
    {"case_key": "issue94.r4.negated_marker.not_a_complete", "kind": "benchmark_probe", "result": "FAIL"},
    {"case_key": "issue94.r4.negated_marker.not_the_complete_upper", "kind": "benchmark_probe", "result": "FAIL"},
    {"case_key": "issue94.r4.negated_marker.is_not_complete", "kind": "benchmark_probe", "result": "PASS"},
    {"case_key": "issue94.r4.affirmed_marker", "kind": "benchmark_probe", "result": "PASS"}
  ],
  "issue_refs": ["DataBossX/DataBoss#94:regression-4"],
  "origin": "governor.observe/1",
  "proposal_key": "P-A-issue94-r4-negated-complete-marker",
  "proposed_write_paths": ["grocery_report_pipeline.py", "tests/test_issue94_negated_owner_set.py"],
  "schema": "databossx.governor.improvement_proposal/1",
  "scope": "repo:DataBossX/DataBoss",
  "scores": {"confidence": 5, "cost": 1, "reversibility": 5, "risk": 1, "value": 5},
  "target": {"path": "grocery_report_pipeline.py", "symbol": "_OWNER_SET_INCOMPLETE_RX"},
  "title": "A negated completeness marker must not assert sum-to-one"
}
```

Rank decision (hash `120f6aaa12b92d5246f2e0e9033968d95bb421231f0e1d4b7d3a409ac6f084d9`):

```json
{
  "candidate_set_hash": "c056d590d2cd0a0ddb7d3d9878ec1ea26a9f7568338bed8290fbacc096691423",
  "formula": "value*confidence*reversibility/(risk*cost); tie: risk asc, proposal_hash asc",
  "ranked": [
    "2b455789fe353a5d49d26c3e58a0bd49b7c320c5896fdd11ccf12ee574998631",
    "d468b63c57579fb20ae46b82729abb255ae78fa339c14d7a57e54b0149737e95",
    "76eff15d571e4ee03917c6506a8d0f447f91057ab5dcb1d288fd13f98a4e4107"
  ],
  "ranker_version": "next-best-move/1",
  "rows": [
    {"proposal_hash": "2b455789fe353a5d49d26c3e58a0bd49b7c320c5896fdd11ccf12ee574998631", "proposal_key": "P-A-issue94-r4-negated-complete-marker", "score": "125/1", "vetoes": []},
    {"proposal_hash": "d468b63c57579fb20ae46b82729abb255ae78fa339c14d7a57e54b0149737e95", "proposal_key": "P-B-issue94-r4-pending-complete-marker", "score": "30/1", "vetoes": []},
    {"proposal_hash": "76eff15d571e4ee03917c6506a8d0f447f91057ab5dcb1d288fd13f98a4e4107", "proposal_key": "P-C-issue94-r3-prose-decimal", "score": "15/2", "vetoes": []},
    {"proposal_hash": "940bbc3ab300e05e24a7ff7b70a860349189eec8bf33d3db80807a53babc7c70", "proposal_key": "P-D-governor-narrow-own-allowlist", "score": null, "vetoes": ["V6_SELF_MODIFICATION_OR_PERMISSION_EXPANSION"]},
    {"proposal_hash": "91cbd5f298b1c3f08eaaed4d7751d2612b940305bf0696285c7c4c4a4a074090", "proposal_key": "P-E-port-pr114-issue94-fixes", "score": null, "vetoes": ["V4_SECOND_CONTROL_PLANE_OR_DUPLICATE_IMPLEMENTATION"]}
  ],
  "schema": "databossx.governor.rank_decision/1",
  "selected_proposal_hash": "2b455789fe353a5d49d26c3e58a0bd49b7c320c5896fdd11ccf12ee574998631"
}
```

Statuses after PRIORITIZE: P-A `selected`; P-B and P-C `deferred`; P-D and
P-E `vetoed`.

## 4. AUTHORIZE (L1 to L2 gate)

Sealed envelope. **`envelope_hash = 45b4d6606a6efb73b137fbc8ad23fca027684ec166584db1c580fe10689f297f`**,
computed as `sha256(canonical_json(envelope))` over exactly this object. The
timestamps are illustrative; a runtime envelope carries its real
`created_at` and `expires_at`, and therefore its own hash.

```json
{
  "autonomy_level": "L2",
  "base": {
    "commit": "5fc0d6c149b5ba5e5c30d4c08aa1c5ccfc074ff6",
    "ref_name": "cursor/kernel-governor-tournament-7f1f",
    "repo": "DataBossX/DataBoss",
    "require_clean_tree": true,
    "tree": "0968d5b642c301ce4c46dbddb12e567f01dd9bf9"
  },
  "budgets": {
    "max_cost_usd_cents": 0,
    "max_diff_added_lines": 80,
    "max_diff_removed_lines": 20,
    "max_files_changed": 2,
    "max_model_calls": 0,
    "max_test_invocations": 12,
    "max_wall_seconds": 900
  },
  "canary": {
    "expected_output_delta": "none; compare review_required.csv and extracted_facts.csv with the trailing timestamp column removed",
    "fixture": "grocery_report_pipeline.make_synthetic_corpus",
    "level": "L3",
    "must_hold": ["tests/test_grocery_pipeline.py::test_decimal_sum_flagged"]
  },
  "capabilities": ["sandbox.fs.write", "sandbox.git.commit", "sandbox.test.run", "sandbox.worktree.create"],
  "created_at": "2026-09-23T20:00:00Z",
  "cycle_key": "gov-cycle-0001",
  "denied_capabilities": ["drive.delete", "drive.share", "drive.write", "dropbox.write", "egress.any", "github.write", "governor.self_edit", "migration.edit", "model.remote", "original.mutate", "policy.edit", "report.release", "workbook.write"],
  "egress_allowlist": [],
  "env_allowlist": ["HOME", "LANG", "PATH", "PYTHONHASHSEED", "PYTHONPATH", "TMPDIR"],
  "expires_at": "2026-09-24T20:00:00Z",
  "inputs": [
    {"path": "grocery_report_pipeline.py", "sha256": "57c79f21069e34bca21eba6b8ccccebb93d8f8b32cfa660e97737e2f340fd2ed"},
    {"path": "pyproject.toml", "sha256": "c5ee3341b56a1f4c0efa12276c33697d516b62fbb9942d8dd47d3dcc73089bcb"},
    {"path": "requirements.txt", "sha256": "fa81e55ee21581c8938352c254e3b6608e9cd0d4419ccce033be11b542097bdd"},
    {"path": "tests/test_issue94_integrity.py", "sha256": "c60d70103095d8e01270039a9d945a0fa6435982594da61a501812a599a8b5c7"}
  ],
  "proposal_hash": "2b455789fe353a5d49d26c3e58a0bd49b7c320c5896fdd11ccf12ee574998631",
  "provenance": {"issues": ["DataBossX/DataBoss#68", "DataBossX/DataBoss#69", "DataBossX/DataBoss#94"]},
  "rank_decision_hash": "120f6aaa12b92d5246f2e0e9033968d95bb421231f0e1d4b7d3a409ac6f084d9",
  "read_allowlist": ["grocery_report_pipeline.py", "pyproject.toml", "requirements.txt", "tests/**"],
  "receipts": {"chain": "prev_receipt_hash", "terminal_required": true},
  "review": {
    "blocking_dimensions": ["correctness", "fail_closed", "no_second_control_plane", "public_safety", "scope"],
    "independent": true,
    "reviewer_must_differ_from": ["builder", "proposer"]
  },
  "rollback": {
    "method": "discard_worktree_or_revert_single_commit",
    "rehearsal": "revert fix only; must_fail_at_base fail again; reapply; candidate tree restored"
  },
  "schema": "databossx.governor.task_envelope/2",
  "scope": "repo:DataBossX/DataBoss",
  "terminal_states": ["CYCLE_ABORTED_BUDGET_OR_STOP", "CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW", "CYCLE_BLOCKED_REQUIRES_AUTHORITY_OR_BASELINE", "CYCLE_NOOP_NO_ELIGIBLE_PROPOSAL", "CYCLE_REJECTED_WITH_ACTIONABLE_DEFECTS"],
  "tests": {
    "adversarial": ["governor.probe.negation_scope", "governor.secret_scan.diff", "tests/test_issue94_integrity.py", "tests/test_publication_policy.py"],
    "baseline_must_be_green": true,
    "command_hash": "3179a53b7da41e999821b18f1818bc17a7fa56cc29b42c22b2724d74024511a2",
    "env_manifest_hash": "498adeb35ebf9ed34f017c64699b09b6cea3dc2b5c0a0a5ef2bdb61789a88aa4",
    "golden": ["tests"],
    "invariant": ["governor.diff_within_write_allowlist", "governor.no_schema_change", "governor.synthetic_fixture_marker", "governor.vetoes"],
    "must_fail_at_base": [
      "tests/test_issue94_negated_owner_set.py::test_negated_complete_marker_does_not_assert_sum[NOT the complete owner set]",
      "tests/test_issue94_negated_owner_set.py::test_negated_complete_marker_does_not_assert_sum[this is not a complete owner set]"
    ],
    "must_pass_at_base": [
      "tests/test_issue94_negated_owner_set.py::test_negated_complete_marker_does_not_assert_sum[owner set is not complete]"
    ],
    "rerun_for_reproducibility": 2,
    "target": ["tests/test_issue94_negated_owner_set.py"]
  },
  "vetoes_evaluated": ["V1_CLIENT_EVIDENCE", "V2_WORKBOOK_MUTATION", "V3_EXTERNAL_RELEASE", "V4_SECOND_CONTROL_PLANE_OR_DUPLICATE_IMPLEMENTATION", "V5_SECRET_EXPOSURE", "V6_SELF_MODIFICATION_OR_PERMISSION_EXPANSION"],
  "write_allowlist": ["grocery_report_pipeline.py", "tests/test_issue94_negated_owner_set.py"]
}
```

The command behind `command_hash` is
`["python","-m","pytest","-q","-p","no:cacheprovider","-o","addopts=","tests"]`.
The manifest behind `env_manifest_hash` lists the versions in section 1 plus
the `requirements.txt` hash.

Human step:

```bash
databossx governor approve --purpose AUTHORIZE_L2 \
  --hash 45b4d6606a6efb73b137fbc8ad23fca027684ec166584db1c580fe10689f297f \
  --expires 2026-09-24T20:00:00Z \
  --attest-no-hold "public synthetic code only; scope repo:DataBossX/DataBoss"
```

`tick()` acquires the writer lease (fence 1 for a fresh scope), inserts
`governor_approval_uses(purpose='AUTHORIZE_L2', bound_hash=<envelope_hash>, fence=1)`,
sets the envelope to `AUTHORIZED`, and advances to BUILDING.

## 5. BUILD IN SANDBOX (L2)

The cycle-1 builder is **deterministic** (`ScriptedPatchBuilder`): it applies
the reviewed test first, then the reviewed fix. No model is called
(`max_model_calls = 0`). Later cycles may put an agent builder behind the
same interface; the governor judges only the resulting diff.

```bash
git worktree add --detach runtime/governor/worktrees/gov-cycle-0001 5fc0d6c149b5ba5e5c30d4c08aa1c5ccfc074ff6
# environment: env_allowlist names only; GIT_TERMINAL_PROMPT=0
```

### 5.1 Test first: `tests/test_issue94_negated_owner_set.py` (new, 38 lines)

```python
from __future__ import annotations

import pytest

import grocery_report_pipeline as grp
from tests.test_issue94_integrity import _facts_from_text


@pytest.mark.parametrize(
    "negation",
    ["this is not a complete owner set", "owner set is not complete", "NOT the complete owner set"],
)
def test_negated_complete_marker_does_not_assert_sum(tmp_path, negation):
    facts = _facts_from_text(
        tmp_path,
        "schedule.txt",
        "SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA\n"
        f"OWNERSHIP schedule -- {negation}\n"
        "Owner A decimal interest 0.25\nOwner B decimal interest 0.25\n"
        "Legal: Section 12, T7N, R63W\n",
    )
    assert facts[0].owner_set_complete is False
    recon = grp.reconcile(facts, tmp_path / "out", grp.BuildLog())
    assert "decimal-sum" not in [row[0] for row in recon["conflicts"]]


def test_affirmed_complete_marker_still_flags_real_imbalance(tmp_path):
    facts = _facts_from_text(
        tmp_path,
        "schedule.txt",
        "SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA\n"
        "OWNERSHIP schedule -- complete owner set\n"
        "Owner A decimal interest 0.5\nOwner B decimal interest 0.25\n"
        "Legal: Section 12, T7N, R63W\n",
    )
    assert facts[0].owner_set_complete is True
    recon = grp.reconcile(facts, tmp_path / "out", grp.BuildLog())
    assert "decimal-sum" in [row[0] for row in recon["conflicts"]]
```

`sha256 = 3c1e2bc698a7115ee73ba90eac63952ee1051fcf441587c05a52d8f6444f1f05`.
Both fixtures carry the synthetic marker (V1). `reconcile` writes generated
outputs only under `tmp_path/out`: new synthetic output, not mutation of an
existing workbook (V2 clear). The second test pins the other direction: a
real imbalance on an affirmed complete set is still flagged.

**RED_PROOF** (test applied, fix absent): `2 failed, 177 passed`. The two
failures are exactly `must_fail_at_base`. The `owner set is not complete`
guard and the affirmed test pass, so `G_RED_PROOF` passes.

### 5.2 Smallest fix: `grocery_report_pipeline.py` (+1 / -1)

```diff
@@ -872,7 +872,7 @@ _OWNER_SET_COMPLETE_RX = re.compile(
     re.I,
 )
 _OWNER_SET_INCOMPLETE_RX = re.compile(
-    r"\b(partial|incomplete|missing\s+owners?|owner\s+set\s+unknown)\b",
+    r"\b(partial|incomplete|missing\s+owners?|owner\s+set\s+unknown|not\s+(?:a\s+|the\s+)?complete)\b",
     re.I,
 )
```

`\b` after `complete` means "not completed" does not match. `re.I` covers
"NOT".

Candidate patch (both files, repository-relative, from `git diff --cached` in
the worktree): `patch_sha256 = 9a9a41cd28c05dc5134291d5d8b22bbbfc266ff6433193cddc8b88c2d7c410a0`,
2 files, +39 / -1. The base tree is `0968d5b642c301ce4c46dbddb12e567f01dd9bf9`
and the candidate tree is `0948f1151dfcba70ef2bf62d3bfe8f0a978b6497`. The
post-fix `grocery_report_pipeline.py` has sha256 `56c78b2b...fc79`.

Post-BUILD veto pass on the diff: V1 to V6 all CLEAR. Both paths are in
`write_allowlist`. There is no DDL, no protected path, no workbook suffix, and
no secret pattern. `G_DIFF_SCOPE`: 2 of 2 files, 39 of 80 added lines, 1 of 20
removed lines.

## 6. TEST (L2)

| Role | Tree | Result (pre-verified) | `outcome_set_hash` |
| --- | --- | --- | --- |
| BASELINE (golden `tests`) | `0968d5b6...` | `175 passed`, 0 failed, 0 skipped. `G_BASELINE_GREEN` passes | `4f53cda1...b945` (empty set) |
| RED_PROOF | base + test only | `2 failed, 177 passed`; failures equal `must_fail_at_base` | `49547f3b...34c7` |
| CANDIDATE (golden + adversarial) | `0948f115...` | `179 passed`, 0 failed | `4f53cda1...b945` |
| RERUN | `0948f115...` | `179 passed`; identical hash. `G_REPRODUCIBLE` passes | `4f53cda1...b945` |
| ROLLBACK_REHEARSAL | revert the fix only, then reapply | after revert: `2 failed, 177 passed`, the same two nodes; after reapply: `179 passed` and `git write-tree == 0948f115...`. `G_ROLLBACK_REHEARSAL` passes | `49547f3b...34c7` at revert |

`outcome_set_hash` is `content_hash(sorted non-passed node ids)`. The empty
set hashes to `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
The red set hashes to `49547f3baaac4966af251d23b99e83455ae6aab199b18abd52d98ba11c9c34c7`.

The adversarial suites inside CANDIDATE, `tests/test_issue94_integrity.py`
and `tests/test_publication_policy.py`, pass unchanged. The diff secret scan
is clear. The invariants (`diff_within_write_allowlist`, `no_schema_change`,
`synthetic_fixture_marker`, `vetoes`) pass.

**Why the fix is safe (reviewer proof obligation).** Let I be "INCOMPLETE
matches" and C be "COMPLETE matches". Then `complete = not I and C`. The fix
only adds an alternation to I, so I_old implies I_new. Therefore
`complete_new` implies `complete_old`: the change can only turn True into
False. In `reconcile`, False yields
`INCOMPLETE_OWNER_SET: sum not asserted` in the calculation row and no
`decimal-sum` conflict. Nothing becomes `OK`.

## 7. ADVERSARIAL REVIEW (independent)

`review.open_gate` creates a kernel `review_gates` row
(`gate_type='governor.independent_review'`) with a bundle holding the
envelope, patch, evaluation table, section 6 proof, and probe table. The
reviewer must be neither the builder nor the proposer. Blocking checklist:

1. **correctness**: the implication holds; the affirmed test still flags a
   real imbalance.
2. **fail_closed**: no path turns a review state into `OK`.
3. **scope**: exactly two files; no API or schema change; no refactor.
4. **public_safety**: synthetic markers present; no private names, paths, or
   identifiers.
5. **no_second_control_plane**: no new module, table, queue, or approval path.

The adversarial probe `governor.probe.negation_scope` produces one finding
the reviewer must record:

- **RF-1 (non-blocking, becomes P-F).** The INCOMPLETE vocabulary is matched
  anywhere in the document, not just in the schedule header. A schedule that
  says "complete owner set" with a real imbalance (0.5 plus 0.25) **and** an
  unrelated line "Note: title curative is not complete" flagged the
  imbalance at base, but reports `sum not asserted` at candidate
  (pre-verified). The same document with "curative incomplete" instead
  already reports `sum not asserted` at base, so the fix extends an existing
  heuristic class rather than creating a new one, and the output never says
  `OK`. Scoping both vocabularies to the schedule header line is a separate
  proposal with its own probe, because it changes behavior for existing
  "partial" and "incomplete" documents too.

Decision recorded in `review_decisions`: `APPROVE` with RF-1 attached, or the
cycle ends `CYCLE_REJECTED_WITH_ACTIONABLE_DEFECTS` with reason
`blocking_review` if the reviewer judges RF-1 blocking.

## 8. CANARY (L3, synthetic only)

This is a human step, because the `public-safe` ceiling is L2:

```bash
databossx governor approve --purpose AUTHORIZE_L3_CANARY \
  --hash e45d098658839d360516b7145b84c0fb5d2a26a9fbaf782f21bc42f3230a74af \
  --expires 2026-09-24T20:00:00Z
```

The bound hash is `content_hash` of this binding, so the canary approval
cannot be reused for another patch, tree, or evaluation outcome:

```json
{
  "candidate_tree": "0948f1151dfcba70ef2bf62d3bfe8f0a978b6497",
  "envelope_hash": "45b4d6606a6efb73b137fbc8ad23fca027684ec166584db1c580fe10689f297f",
  "evaluation_outcome_set_hashes": {
    "BASELINE": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    "CANDIDATE": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    "RED_PROOF": "49547f3baaac4966af251d23b99e83455ae6aab199b18abd52d98ba11c9c34c7",
    "RERUN": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    "ROLLBACK_REHEARSAL": "49547f3baaac4966af251d23b99e83455ae6aab199b18abd52d98ba11c9c34c7"
  },
  "patch_sha256": "9a9a41cd28c05dc5134291d5d8b22bbbfc266ff6433193cddc8b88c2d7c410a0",
  "schema": "databossx.governor.canary_binding/1"
}
```

The canary runs `grp.make_synthetic_corpus` and then
`grp.run_pipeline(corpus, out, "Grocery_Report", apply_quar=False, log=grp.BuildLog())`
at base and at candidate. Pre-verified:

- `tests/test_grocery_pipeline.py::test_decimal_sum_flagged` holds: the
  corpus's real imbalance on Section 12, T7N, R63W is still flagged
  `red, decimal-sum, Decimals sum to 0.95 (expected 1.0)`.
- `review_required.csv` and `extracted_facts.csv` are identical between base
  and candidate after dropping the trailing timestamp column. (In the
  pre-verification run the raw bytes were identical too, because both runs
  fell in the same second.)

`G_CANARY` passes.

## 9. DECIDE

All gates pass, so the terminal is
**`CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW`**. The governor stores the patch as
a `governor.patch` artifact (`9a9a41cd...`) and stops. It never pushes.

A human or supervised agent, outside the governor, can then consume a
separate approval:

```bash
databossx governor approve --purpose OPEN_DRAFT_PR \
  --hash 9a9a41cd28c05dc5134291d5d8b22bbbfc266ff6433193cddc8b88c2d7c410a0 \
  --destination "DataBossX/DataBoss:<new branch based on 5fc0d6c>"
```

The authorized writer applies the exact patch, verifies its sha256, and opens
a **draft** PR. Nothing is merged.

## 10. LEARN

Learning record candidate (`learning_records`, status `candidate`, facts
only):

```json
{
  "schema": "databossx.governor.learning_record/1",
  "cycle_key": "gov-cycle-0001",
  "facts": [
    {"kind": "probe_signal", "case_key": "issue94.r4.negated_marker.not_a_complete", "led_to": "ACCEPTED_FIX"},
    {"kind": "probe_signal", "case_key": "issue94.r4.negated_marker.not_the_complete_upper", "led_to": "ACCEPTED_FIX"},
    {"kind": "coverage_gap", "pattern": "vocabulary gate had no negation case"},
    {"kind": "residual_risk", "id": "RF-1", "pattern": "completeness vocabulary matched document-wide, not in the schedule header", "suggested_case_status": "DRAFT"},
    {"kind": "deferred", "proposal_key": "P-B-issue94-r4-pending-complete-marker"},
    {"kind": "deferred", "proposal_key": "P-C-issue94-r3-prose-decimal"},
    {"kind": "environment", "pattern": "baseline depends on optional packages; the env manifest must be hashed"}
  ],
  "score_vs_outcome": {"proposal_key": "P-A-issue94-r4-negated-complete-marker", "score": "125/1", "outcome": "ACCEPTED_FOR_INDEPENDENT_REVIEW"}
}
```

A human runs `databossx governor learning-review` to accept or reject it. If
accepted, RF-1 seeds a **DRAFT** benchmark case, not an ACTIVE one. P-B and
P-C are re-ranked in `gov-cycle-0002`.

## 11. Terminal receipt

Written exactly once at CLOSE, with the schema in `ARCHITECTURE.md` section
9.1 and `prev_receipt_hash = "GENESIS"` (first receipt). Key values:
`terminal_state = CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW`,
`envelope_hash = 45b4d660...`, `patch_sha256 = 9a9a41cd...`, the section 6
evaluations, RF-1 in `review.findings`, all vetoes `CLEAR`, and every safety
flag `NO`. Then `governor_cycles` is closed (the trigger checks the matching
receipt), the envelope becomes `CONSUMED`, the lease is released, the
worktree is removed, and `governor.cycle.closed` goes to the outbox.

## 12. Alternate terminals for the same cycle

| If | Terminal |
| --- | --- |
| The branch head moved before AUTHORIZE | `CYCLE_BLOCKED_REQUIRES_AUTHORITY_OR_BASELINE` (`baseline_drift`); re-observe |
| Kernel slice not merged | `CYCLE_BLOCKED_REQUIRES_AUTHORITY_OR_BASELINE` (`kernel_slice_absent`); the cycle can still run L0 and L1 and receipt its proposals |
| `python-dotenv` missing in the sandbox | `CYCLE_BLOCKED_REQUIRES_AUTHORITY_OR_BASELINE` (`baseline_not_green`) |
| RED_PROOF shows no failure, or the guard node fails | `CYCLE_REJECTED_WITH_ACTIONABLE_DEFECTS` (`no_red_proof`) |
| The reviewer judges RF-1 blocking | `CYCLE_REJECTED_WITH_ACTIONABLE_DEFECTS` (`blocking_review`); P-F is proposed next |
| Approval not granted before `expires_at` | `CYCLE_BLOCKED_REQUIRES_AUTHORITY_OR_BASELINE` (`missing_or_stale_approval`) |
| The operator runs `databossx governor halt` | `CYCLE_ABORTED_BUDGET_OR_STOP` (`halted`) |
| Every proposal vetoed or no finding | `CYCLE_NOOP_NO_ELIGIBLE_PROPOSAL` |

## Appendix A. The same cycle against PR #114's Issue #94 line

Use this only if the owner picks PR #114's implementation (`e8b9225`) as
canonical. The governor then stacks on PR #114's head and never re-implements
it on `main`. Pre-verified in a `/tmp` clone of `e8b9225`:

- **Gap.** PR #114's `_owner_set_is_complete` returns True for any text with
  at least two labeled decimals and a bare marker (`total`, `8/8`) outside an
  ownership schedule. A synthetic deed with two `0.25` decimals and "Total
  consideration" or "royalty of 1/8 of 8/8" raises a false `decimal-sum`
  conflict. Separately, PR #114's `_DECIMAL_RX` captures `10.5` as `1`.
- **Proposals.** P-A (`988b11463c75660d20dd967eef1b0757e19a68d24a1e287c2b479d21fb70dac6`,
  score `125/1`), P-B decimal truncation (`a46ec3d5d358f4678a7ca9d56d0fba327fd2e27e37f080f4d56dee6d5f58f34f`,
  `50/1`, deferred), and P-C "all seven on main"
  (`c90767eb4ab477eadb06e1d537cacef1eeefc84d655373fa62092ca1e6534448`, V4).
  Rank decision `eb8666bc32abe48cd93abdfa6fe600ec116ffa65ed53e3279ea45885a51009a1`.
- **Envelope** `cfa1752f3406abd8797dd3a9770a87b38951f9fc48c731495321c969914cb9fd`
  (older field names: `base.commit_sha`, `donor_pr: 114`, older terminal
  names; recompute with the section 4 schema before use).
- **Test** `tests/test_issue94_owner_set_completeness.py` (40 lines, sha256
  `6cc89c49...4f76`). **Fix**: require the ownership-schedule context before
  any marker counts (+2 / -5). Patch `fb5897007930ee4e0e97a89b370b8bc87fd227dd41f15f428dde5d3e2973ff94`.
  Trees `6138ea34...` to `d138ea83...`.
- **Numbers.** BASELINE 173 passed; RED_PROOF 2 failed, 175 passed;
  CANDIDATE 177 passed twice; rollback rehearsal red again then restored.
  Canary unchanged (0.95 still flagged).
- **Proof.** Old `complete = D and (M or (S and R))`; new
  `complete = D and S and (M or R)`; new implies old.
