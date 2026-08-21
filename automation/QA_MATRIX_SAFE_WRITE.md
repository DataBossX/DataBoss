# QA Matrix Safe-Write Patch

## Root cause

The failed production run completed conversion and crashed only when exporting the QA matrix because a Python collection (specifically `[]`) was assigned directly to an Excel cell. Excel writers accept scalar cell values, not Python lists/dictionaries/sets.

## Required integration

Normalize every cell value at the final writer boundary:

```python
from automation.excel_safe_values import excel_safe_value, excel_safe_row

# Per-cell writer
cell.value = excel_safe_value(raw_value)

# Row append/write API
worksheet.append(excel_safe_row(raw_row))
```

For a complete matrix:

```python
from automation.excel_safe_values import excel_safe_rows

safe_rows = excel_safe_rows(raw_rows)
for row in safe_rows:
    worksheet.append(row)
```

Collections are retained as compact deterministic JSON text (`[]`, `{}`, and nested JSON) instead of being silently dropped. Native strings, numbers, booleans, dates, datetimes, times, timedeltas, and `None` remain native. Paths, bytes, non-finite floats, cyclic containers, and custom objects are converted safely.

## Recovery procedure

1. Do **not** rerun OCR/conversion solely because QA export failed.
2. Load the existing text manifest and scored-page outputs from the completed run.
3. Apply `excel_safe_value` at the QA workbook cell-write boundary.
4. Regenerate only the QA matrix.
5. Reopen the workbook in native Excel and verify no repair warning.
6. Confirm row counts match the source manifest/scored-page data.
7. Record the new workbook SHA-256 and preserve the failed run unchanged.

## Verification

Run:

```bash
python -m unittest tests.test_excel_safe_values -v
```

The regression suite covers the original empty-list crash plus nested collections, non-finite floats, paths, bytes, custom objects, cyclic containers, row normalization, and scalar preservation.
