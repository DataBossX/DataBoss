# Isolated Letter layout and native Excel Print Preview

Section 15's known print defect is A4 / missing `pageSetup` / missing
Print_Titles. Horizon can write the Penterra Letter contract onto a **copy**.
Only Microsoft Excel on Windows can prove Print Preview.

## Isolated layout repair

```bash
python3 -m horizon.print_layout_repair \
  --workbook /path/to/source-index.xlsx \
  --output /path/to/isolated-letter.xlsx \
  --receipt /path/to/print-layout-repair-receipt.json
```

The copy gets landscape, `paper_size` 1 (US Letter), and print titles on
rows 1–8. The source file is not modified. This is not native Print Preview.

## Native receipt

Schema `dbx.native_print_receipt` / `1.0`. Required keys:

- `workbook_sha256` — SHA-256 of the workbook that was previewed
- `application` — must be `Microsoft Excel`
- `host` — must be `Windows`
- `paper_size` — `1` or `Letter`
- `orientation` — `landscape`
- `page_count` and `expected_page_count` — integers, must match
- `print_titles` and `print_area_set` — must be `true`
- `operator` — who ran Print Preview

Do not put a live page count in this repository. The writer holds
`expected_page_count` for that section (historically Section 15 repaired to
two Letter pages; this module does not hard-code that).

`pc_operator --execute` writes `sectionN-native-print-draft.json`
(`dbx.native_print_draft`, `UNAPPROVED_DRAFT`) bound to the current isolated
workbook hash. That draft cannot bind the native-print gate. After Print
Preview, attest it. Horizon does not invent `PAGE_COUNT`. A receipt whose
`workbook_sha256` does not match the current isolated file (Letter, or
`sectionN-delta.xlsx` after a source-proved fill) is dropped so the next
command is a reprint, not a stale bind.

```bash
python3 -m horizon.native_print \
  --attest \
  --from-draft /path/to/section15-native-print-draft.json \
  --workbook /path/to/isolated-letter.xlsx \
  --output /path/to/native-excel-print-receipt.json \
  --operator "Pat Examiner" \
  --page-count PAGE_COUNT
```

The older `--write` path still works when the examiner supplies both the
name and the page count in one step.

```bash
python3 -m horizon.native_print \
  --packet /path/to/native-excel-print-receipt.json \
  --workbook /path/to/isolated-letter.xlsx \
  --output /path/to/native-print-gate-receipt.json
```

`technical_pass` is not package release. Drive readback remains required.
