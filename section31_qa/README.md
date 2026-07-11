# Section 31 QA Auditor

QA program for the **Section 31-12N-24W, Roger Mills County, Oklahoma** title-report
project. It finds the best report workbook under the Horizon folders, audits it for
title-report defects, and writes every result to a **new, separate output folder** —
the client report and every other original file are never modified.

## How to run (no coding needed)

1. Copy this whole `section31_qa` folder anywhere on the machine that has
   `D:\Desktop\Horizon` (the Desktop is fine).
2. Double-click **`run_section31_qa.bat`**.
3. When it finishes, open the newest `Section31_QA_Output_<date>` folder inside
   `D:\Desktop\Horizon` and read, in this order:
   1. `SECTION31_QA_SUMMARY.txt` — the plain-English summary.
   2. `qa_defects.xlsx` — every issue, with sheet, cell, severity, and what a
      human needs to do about it.
   3. `suggested_corrections.xlsx` — mechanical fixes the tool recommends
      (nothing has been applied unless you asked for it — see below).

To scan a different folder, drag that folder onto the `.bat` file.

## What gets produced

| File | What it is |
| --- | --- |
| `file_index.xlsx` | Every file found, with size, date, SHA1 hash, keyword hits |
| `workbook_candidates.xlsx` | Every Excel workbook, scored; rank 1 is the chosen report |
| `workbook_comparison.xlsx` | Top workbooks compared side by side (sheets, owners, interest sums) |
| `qa_defects.xlsx` | Every QA finding: severity, category, sheet!cell, required human action |
| `suggested_corrections.xlsx` | Cell-level mechanical fix suggestions (never auto-applied) |
| `run_log.txt` | Full technical log of the run |
| `SECTION31_QA_SUMMARY.txt` | Human-readable final summary |
| `*__SAFE_WORKING_COPY.xlsx` | Only with `--make-safe-copy`: a byte-for-byte copy of the best workbook |

## QA checks performed

Bad negatives · non-footing totals (vs. total rows and vs. 8/8ths = 1.0) ·
NRI > WI and interests > 100% · blank required cells · duplicate owners
(normalized names, per tract) · missing notes/assumptions · OGL rows without WI ·
expired leases without HBP notation · HBP claimed "confirmed" without cited
evidence (flagged, never auto-confirmed) · hidden/very-hidden sheets · formula
errors (#REF!, #DIV/0!, …) · numbers stored as text · number-format drift and
merged cells inside data tables · tract labels missing across sheets · wrong
section/township/range references · future or implausible instrument dates ·
malformed book/page references.

## Modes

```
py section31_qa.py                       # normal: read-only audit, writes QA outputs
py section31_qa.py --dry-run             # audits but writes NO files at all
py section31_qa.py --make-safe-copy      # also drops a byte-for-byte working copy
py section31_qa.py --apply-corrections   # applies ONLY trim-whitespace and
                                         # text-number fixes to the SAFE COPY
py section31_qa.py --roots "D:\other"    # scan different folder(s)
```

## Safety guarantees

- Originals are opened read-only; nothing is overwritten, renamed, or deleted.
- The safe working copy is created with a straight file copy (`copy2`), so all
  formatting, images, and plats are byte-for-byte identical.
- `--apply-corrections` edits **the copy only**, applies only whitelisted
  mechanical fixes, and logs every change. Caveat: re-saving the copy through
  openpyxl preserves styles/widths/images but drops charts if the workbook has
  any — diff the copy against the untouched original before adopting it.
- No title facts are invented; HBP is never confirmed by the tool; no WI/NRI
  values are created. Everything judgment-based lands in `qa_defects.xlsx` as a
  human-review item.

## Known limits (human review still required)

- The tool checks internal consistency; it cannot verify facts against the
  county records, production data, or the OCC. Every HIGH defect and every HBP
  item needs an examiner's eyes.
- Legacy `.xls`/`.xlsb` files can't be read by openpyxl; they are listed in the
  index with a warning — save them as `.xlsx` to include them in the audit.
- Cached formula values are what Excel last saved; if a workbook was saved with
  stale calculations, open it in Excel, let it recalculate, save, and rerun.
- Workbook scoring is a heuristic. Rank 1 has been right in testing, but always
  confirm the chosen file in `workbook_candidates.xlsx` is the intended report.
