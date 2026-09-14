# Human release and package completion

`packages_complete` is not a vibe check. It is true only when:

1. `source_acquisition` passed
2. `reextraction` passed
3. `occurrence_ledger` passed
4. Index fields are complete (`index_reconciliation` with zero blanks and
   conflicts, or a `repair_loop` that ended the same way)
5. `workbook_qa` passed
6. `native_print` passed
7. `drive_readback` passed
8. `human_release` passed

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
