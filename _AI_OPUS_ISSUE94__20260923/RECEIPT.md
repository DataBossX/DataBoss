# Issue #94 adversarial packet — receipt

```
LANE=ISSUE94_ADVERSARIAL_TEST (Opus)
REPO=DataBossX/DataBoss   BRANCH=cursor/kernel-governor-tournament-7f1f
HEAD_AT_START=582d95161cf8220fb37f5224e21e57dcc5c3121c   (dirty: another writer editing backend/, horizon/repair.py, grocery_report_pipeline.py)
HEAD_AT_FINISH=c87d85d385986d8d44b757496ea9ce70ee1b3ef3  (production files identical to 2714a24)
PRE_FIX_BASELINE=582d951 via `git archive` into /tmp/issue94_head (read-only extract)
PATCHED_SCRATCH=/tmp/issue94_fix (git archive of HEAD + FIX_NOTES patch; never /workspace)

WRITES=/workspace/_AI_OPUS_ISSUE94__20260923/{README.md,RECEIPT.md,FIX_NOTES.md,test_issue94_integrity.py,test_backend_security.py}
PRODUCTION_FILES_EDITED=NO
GIT_COMMITS_BY_THIS_LANE=NO   (the parent committed early drafts of this folder in 2714a24)
CLIENT_BYTES_MUTATED=NO
P10_SUCCESSOR_CREATED=NO
EXTERNAL_RELEASE=NO
FIXTURES=SYNTHETIC_ONLY (pytest tmp_path)
NETWORK_OR_LLM_CALLS=NO
```

## Commands

```bash
export PYTHONDONTWRITEBYTECODE=1
# current tree
python3 -m pytest _AI_OPUS_ISSUE94__20260923/ -q -p no:cacheprovider
python3 -m pytest tests -q -p no:cacheprovider
# pre-fix (582d951); its backend imports openai/anthropic/genai/aiosqlite/loguru/dotenv/PIL
# eagerly, so stub packages in /tmp/issue94_stubs were needed only to reach the routes
git archive 582d951 | tar -x -C /tmp/issue94_head
PYTHONPATH=/tmp/issue94_stubs python3 -m pytest _AI_OPUS_ISSUE94__20260923/ -q -p no:cacheprovider
# patched scratch
git apply --check /tmp/issue94_fix.diff        # clean against /workspace @ c87d85d
python3 -m pytest tests _AI_OPUS_ISSUE94__20260923 -q -p no:cacheprovider
python3 -m pyflakes horizon/repair.py horizon/orchestrator.py backend/server.py _AI_OPUS_ISSUE94__20260923/*.py
```

## Results

| Tree | integrity (50) | backend (95) | existing `tests/` |
|---|---|---|---|
| `582d951` pre-fix | 38 failed / 12 passed | 79 failed / 16 passed | n/a |
| `c87d85d` current | 13 failed / 37 passed | 2 failed / 93 passed | 172 passed |
| `c87d85d` + patch | 50 passed | 95 passed | together: **317 passed** |

pyflakes: clean on all touched and packet files (patched scratch).

## Tests still failing on current HEAD `c87d85d`

```
test_backend_security.py::test_auth_is_default_deny_for_routes_added_later[/api/issue94-probe]
test_backend_security.py::test_auth_is_default_deny_for_routes_added_later[/internal/issue94-probe]
test_issue94_integrity.py::test_repair_without_lxml_refuses_instead_of_copying
test_issue94_integrity.py::test_errored_workbook_cannot_converge_even_if_model_validates
test_issue94_integrity.py::test_repair_rejects_any_row_or_cell_loss[drop_row]
test_issue94_integrity.py::test_repair_rejects_any_row_or_cell_loss[drop_cell]
test_issue94_integrity.py::test_recording_date_blank_without_recording_label[r3_unrecorded_substring_trap.txt]
test_issue94_integrity.py::test_missing_recording_date_is_review_required[r2_instrument_but_no_recording_label.txt]
test_issue94_integrity.py::test_missing_recording_date_is_review_required[r3_unrecorded_substring_trap.txt]
test_issue94_integrity.py::test_out_of_range_decimal_is_not_coerced_to_one[decimal interest 1.5]
test_issue94_integrity.py::test_out_of_range_decimal_is_not_coerced_to_one[decimal interest 10.5]
test_issue94_integrity.py::test_out_of_range_decimal_is_not_coerced_to_one[decimal interest 12]
test_issue94_integrity.py::test_incomplete_owner_set_asserts_no_sum[ownership_excerpt]
test_issue94_integrity.py::test_exact_duplicate_schedule_does_not_double_count
test_issue94_integrity.py::test_synthetic_corpus_marks_its_owner_schedule_complete
```

## Environment

Python 3.12.3; fastapi 0.141.1; starlette 1.7.0; httpx 0.28.1; lxml 6.1.3;
openpyxl 3.1.5; pytest 9.1.1; python-multipart installed (`pip --user`).

## SHA-256

```
4190329af89dee2ef7945de65e1e1c9c1f3da737641308d14b0287605a557e7b  test_issue94_integrity.py
cc01ab70f6690e3ab649b395bf1193e90ddee6a1f42411dd923cc85d1a305c6f  test_backend_security.py
42100eda0d7daa3e742a666d2623d318b59c282bd28b860dc494538087b9b7c1  /tmp/issue94_fix.diff (== patch block in FIX_NOTES.md)
```
