# Human release and package completion

`packages_complete` is not a vibe check. It is true only when:

1. `source_acquisition` passed
2. `reextraction` passed (page-render crops, tract export, or isolated
   workbook projection)
3. `occurrence_ledger` passed (same sources)
4. Index fields are complete (`index_reconciliation` with zero blanks and
   conflicts, or a `repair_loop` that ended the same way)
5. `workbook_qa` passed
6. `native_print` passed with a workbook hash
7. `drive_readback` passed with an Isolated/ copy of that section's file
   and a workbook hash
8. `human_release` passed with the same workbook hash

A receipt-dir same-hash copy can satisfy the Drive readback hash gate.
It does not complete a package. `packages_complete` stays false until
finish records `isolated_copy`, Print Preview / Isolated/ / owner-review
hashes match, and the examiner queue has no remaining blanks or conflicts.

## Token

Schema `dbx.human_release_token` / `1.0`. Required keys:

- `sections` — `15`, `13`, and/or `11`, matching the finish run
- `operator`
- `workbook_sha256` — SHA-256 of the isolated workbook that was reviewed
- `external_release` — must be `false`
- `statement` — exactly:

```
I release this isolated copy for owner review only. It is not an external client delivery.
```

`READY_TO_SUBMIT`, `EXTERNAL_RELEASE`, `FINAL_TURNIN`, and `100%` are
rejected.

`pc_operator --execute` writes `sectionN-owner-review-draft.json`
(`dbx.human_release_draft`, `UNAPPROVED_DRAFT`) bound to the current
isolated workbook hash. That draft cannot bind the human-release gate.
Attest it after owner review. Horizon does not invent the examiner name.
A token whose `workbook_sha256` does not match the current isolated file
is dropped so the next command is a reissue, not a stale bind.

```bash
python3 -m horizon.human_release \
  --attest \
  --from-draft /path/to/section15-owner-review-draft.json \
  --workbook /path/to/isolated-letter.xlsx \
  --output /path/to/owner-review-token.json \
  --operator "Pat Examiner"
```

The older write path still works when the examiner supplies the name in
one step.

```bash
python3 -m horizon.human_release \
  --workbook /path/to/isolated-letter.xlsx \
  --output /path/to/owner-review-token.json \
  --operator "Pat Examiner" \
  --section 15 \
  --packet-id SECTION15-OWNER-REVIEW
```

The CLI hashes the isolated workbook, writes the owner-review statement, and
sets `external_release` false. Placeholders such as `EXAMINER_NAME` are
rejected. This is not an external client delivery.

Owner review is not external client delivery. Do not start a second
controller.
