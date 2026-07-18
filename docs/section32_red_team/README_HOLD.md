# Section 32 Runsheet Red-Team — HOLD (No Release)

**Job:** `SEC32_RUNSHEET_CLAUDE_QA_20260715`
**Status:** `HOLD_NO_RELEASE` — the adversarial audit was **not started**.
**Date:** 2026-07-18

## Why the job is on hold

The job carries a mandatory security gate:

> `security_gate.condition`: *"Do not begin unless SECURITY_REMEDIATION_RECEIPT is PASS."*

That precondition is **not satisfied**:

1. **No `SECURITY_REMEDIATION_RECEIPT` exists.** Searched the Drive by title and by
   full text — no such file, and certainly none marked `PASS`.
2. **Remediation is still pending.** The `SECURITY_REMEDIATION_TASKS` folder sits under a
   parent named `approval_required` and is empty except for one empty subfolder,
   `PENDING_PERMISSION_REMEDIATION`.
3. **An active security HOLD is on record.** `security_incidents/SECURITY_HOLD__2026-07-12`
   exists; the sibling `receipts` folder is empty.
4. **The repo's own `SECURITY.md` documents an open incident** — committed `backend/.env`
   credentials awaiting rotation and client/project metadata exposed in the public repo,
   with containment steps not marked complete.

Beginning the audit would directly violate the job's own gate.

## Inputs could not be verified either

- Neither named candidate workbook exists in Drive under its specified title:
  `GEMINI_SECTION32_MASTER_RUNSHEET.xlsx`, `GROK_SECTION32_CHAINED_RUNSHEET.xlsx`.
- `source_folder` / `output_parent_folder` in the job are unresolved placeholders.
- Related-but-not-identical Section 32 artifacts exist, but none can be assumed to be the
  two candidate runsheets without owner confirmation.

Producing the runsheet, defect register, or conflict matrix from unverified inputs would
mean fabricating rows without genuine source citations — which fails the job's own
acceptance tests. No such outputs were produced.

## To unblock

1. Finish security remediation (rotate exposed credentials; complete client-data
   containment) and file a `SECURITY_REMEDIATION_RECEIPT` = `PASS`.
2. Confirm the resolved source folder and the exact two candidate workbooks.
3. Confirm the output parent folder for `03_CLAUDE_RUNSHEET_RED_TEAM`.

Once those are in place, re-run this job and the full red-team audit can proceed.

See `CLAUDE_COMPLETION_RECEIPT.json` in this folder for the machine-readable record.

## Machinery is ready (built and validated under HOLD)

While the job itself is on hold, the deterministic red-team audit **tool** has been
built and validated on synthetic data, so the audit can run end-to-end the moment the
gate clears and the two real workbooks are confirmed:

- **Tool:** `automation/section32_runsheet_red_team.py`
- **Tests:** `tests/test_section32_red_team.py` (6 tests, all passing)

It ingests two candidate runsheets and emits exactly the four required artifacts —
`CLAUDE_SECTION32_RED_TEAM_RUNSHEET.xlsx`, `CLAUDE_RUNSHEET_DEFECT_REGISTER.xlsx`,
`CLAUDE_CONFLICT_MATRIX.xlsx`, `CLAUDE_COMPLETION_RECEIPT.json` — detecting all twelve
defect classes, correcting only evidence-proven errors (source image > OCR > index >
metadata > prior report), keeping unresolved conflicts visible as `OPEN`, refusing
unsupported decimals, and reporting `UNDETERMINED` rather than a false current owner
whenever the chain is not image-proven and conflict-free.

```
python3 -m automation.section32_runsheet_red_team \
    --gemini <GEMINI_MASTER_RUNSHEET.xlsx> \
    --grok   <GROK_CHAINED_RUNSHEET.xlsx> \
    --out    03_CLAUDE_RUNSHEET_RED_TEAM --section 32 --tract <TRACT>
```

Requires `openpyxl>=3.1` (already used by the `horizon` module). It performs no network
or Drive access and touches no real title documents until pointed at confirmed inputs.
