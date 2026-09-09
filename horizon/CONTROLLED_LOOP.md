# Controlled Workbook QA Loop

`horizon.controlled_loop` is the state-driven path for client-facing workbook
work. It does not replace the legacy report builder. It adds the controls needed
to run a bounded **Inspect → Plan → Execute → Verify → Score → Repair → Promote
→ Learn** cycle without allowing an agent to write to an authoritative file.

## Safety contract

- The project manifest is the authority for required checks and candidate,
  template, and workbook-profile hashes.
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

The project manifest must bind every control authority that the work order uses:

```json
{
  "schema_id": "dbx.project_manifest",
  "schema_version": "1.1",
  "authority_hashes": {
    "template": "<verified template hash>",
    "workbook_profile": "<verified profile hash>",
    "source_authority": "<approved source-authority manifest hash>"
  }
}
```

`source_authority` is used by `horizon.source_acquisition` before extraction;
template and workbook-profile hashes bind the later controlled workbook run.

Create a `dbx.work_order` JSON object next to the project controls:

```json
{
  "schema_id": "dbx.work_order",
  "schema_version": "1.1",
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

Do not invent missing authority hashes. Hash the acquired local files, bind
those hashes in the project manifest, and then issue a matching work order.
The work order cannot authorize a substituted template or workbook profile.
Version `1.1` makes this binding mandatory: migrate older controls by adding
the manifest authority hashes and issuing a matching `1.1` work order.

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

### Strict section-abstract tables

Add these check IDs to both the project manifest `required_checks` and work
order `acceptance_tests`:

```json
[
  "abstract_required_fields",
  "abstract_counts",
  "abstract_key_reconciliation",
  "abstract_print_layout"
]
```

Then bind exact table locations, authoritative counts, key reconciliation, and
print settings in the hash-verified workbook profile:

```json
{
  "abstract_tables": [
    {
      "id": "master",
      "sheet": "Master",
      "header_row": 1,
      "start_row": 2,
      "key_field": "instrument_number",
      "key_normalization": "alnum_upper",
      "columns": {
        "instrument_number": "A",
        "document_type": "B",
        "grantor": "C",
        "grantee": "D",
        "recorded_date": "E",
        "legal_description": "F",
        "source_reference": "G",
        "confidence": "H"
      },
      "expected_headers": {
        "instrument_number": ["Instrument Number", "Instrument No."],
        "document_type": "Document Type",
        "grantor": "Grantor",
        "grantee": "Grantee",
        "recorded_date": "Recorded Date",
        "legal_description": "Legal Description",
        "source_reference": "Source Reference",
        "confidence": "Confidence"
      },
      "required_fields": [
        "instrument_number",
        "document_type",
        "grantor",
        "grantee",
        "recorded_date",
        "legal_description",
        "source_reference",
        "confidence"
      ],
      "expected_rows": 20,
      "expected_unique_keys": 20
    },
    {
      "id": "index",
      "sheet": "Index",
      "header_row": 1,
      "start_row": 2,
      "key_field": "instrument_number",
      "key_normalization": "alnum_upper",
      "columns": {
        "instrument_number": "A",
        "document_type": "B",
        "grantor": "C",
        "grantee": "D",
        "recorded_date": "E",
        "legal_description": "F"
      },
      "required_fields": [
        "instrument_number",
        "document_type",
        "grantor",
        "grantee",
        "recorded_date",
        "legal_description"
      ],
      "expected_rows": 20,
      "expected_unique_keys": 20
    }
  ],
  "abstract_key_reconciliations": [
    {
      "left_table": "master",
      "right_table": "index",
      "mode": "exact"
    }
  ],
  "abstract_print_layout": [
    {
      "sheet": "Master",
      "orientation": "landscape",
      "paper_size": 1,
      "fit_to_width": 1,
      "fit_to_height": 0,
      "fit_to_page": true,
      "print_area": "$A$1:$H$21",
      "print_title_rows": "$1:$1",
      "freeze_panes": "A2"
    }
  ]
}
```

Column letters and counts are authority inputs, not inferred defaults. Missing
rules are `not_evaluated` and block technical verification. Populated rows with
blank required fields, duplicate/blank keys, count disagreement, master/index
key-set disagreement, header mismatch, or print-layout mismatch also block.
`paper_size: 1` is OOXML US Letter. A passing structural layout check still
does not replace native Excel save/reopen and Print Preview evidence. Profile
print-area and print-title references must be unqualified because `sheet`
already names their worksheet.

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
