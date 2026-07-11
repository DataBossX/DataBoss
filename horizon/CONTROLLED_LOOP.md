# Controlled Workbook QA Loop

`horizon.controlled_loop` is the state-driven path for client-facing workbook
work. It does not replace the legacy report builder. It adds the controls needed
to run a bounded **Inspect → Plan → Execute → Verify → Score → Repair → Promote
→ Learn** cycle without allowing an agent to write to an authoritative file.

## Safety contract

- The project manifest is the authority for required checks and candidate hashes.
- A work order must include every manifest check; it cannot weaken the gate.
- Candidate, template, and workbook-profile files are SHA-256 verified.
- Verified inputs are copied into a unique run directory and only snapshots are
  used after inspection.
- One allowlisted defect is repaired per iteration.
- Formula restoration edits one worksheet XML part and clears the stale cached
  result. Every other OOXML package part is verified byte-for-byte before the
  staged file is replaced. The run then blocks until approved recalculation.
- A repair is rolled back when a passing check regresses or the score does not
  improve.
- Technical verification creates only a promotion package. It never writes to a
  canonical destination.
- Human approval must name the exact staged output hash.

## Work order

Create a `dbx.work_order` JSON object next to the project controls:

```json
{
  "schema_id": "dbx.work_order",
  "schema_version": "1.0",
  "work_order_id": "WO-SECTION32-QA-001",
  "project_id": "DBX-OK-BECKHAM-32-11N-25W",
  "objective": "Verify and repair the Section 32 workbook in staging",
  "candidate_path": "beckham32/final_delivery/example.xlsx",
  "candidate_local_path": "D:/DataBossX/beckham32/final_delivery/example.xlsx",
  "expected_sha256": "<same hash declared by the project manifest>",
  "template_path": "D:/DataBossX/templates/section32-template.xlsx",
  "template_expected_sha256": "<verified template hash>",
  "profile_path": "workbook_profile.json",
  "profile_expected_sha256": "<verified profile hash>",
  "staging_root": "runs",
  "acceptance_tests": [
    "<every required_checks value from the project manifest>"
  ],
  "allowed_repairs": ["restore_formula_from_template"],
  "prohibited_paths": ["D:/DataBossX/authoritative"],
  "constraints": {"edit_originals": false},
  "retry_policy": {
    "max_attempts_per_defect": 3,
    "stop_on_regression": true
  },
  "promotion": {"require_human_approval": true}
}
```

Do not invent missing authority hashes. Hash the acquired local files, reconcile
them to the project manifest, and then issue the work order.

## Workbook profile

The deterministic profile identifies the workbook locations to check:

```json
{
  "required_sheet_order": ["Title", "Runsheet", "OGL"],
  "preserve_sheet_order": true,
  "allow_new_sheets": false,
  "current_ownership_ranges": [
    {"sheet": "Title", "range": "M8:M120"}
  ],
  "current_owner_columns": [
    {"sheet": "Title", "column": "E", "start_row": 8, "end_row": 120}
  ],
  "total_assertions": [
    {
      "check_id": "ownership_totals",
      "sheet": "Title",
      "cell": "M122",
      "expected": 40.0,
      "tolerance": 0.01
    }
  ],
  "evidence_root": "D:/DataBossX/authoritative"
}
```

Totals are read from cached formula results. A formula without a cached result is
blocking because `openpyxl` is not a calculation engine. Recalculate using the
approved desktop/LibreOffice workflow before running QA; the loop will not claim
that an uncalculated formula is valid.

## Run

```bash
python -m horizon.controlled_loop \
  --manifest projects/OK-BECKHAM-32-11N-25W/project_manifest.json \
  --work-order projects/OK-BECKHAM-32-11N-25W/work_orders/WO-SECTION32-QA-001.json
```

Each run directory contains:

- immutable candidate, template, and profile snapshots;
- `qa_before.json` and `qa_after.json`;
- one `repair_receipt_NNN.json` per attempted repair;
- `run_receipt.json`;
- a staged workbook;
- `promotion_package.json` only when every technical gate passes.

Checks without a deterministic validator return `not_evaluated` and block
technical verification. In particular, the current Section 32 manifest will
remain blocked until its source manifest, evidence crosswalk, and print-rendering
receipts are available. That is intentional: absence of evidence is not a pass.
