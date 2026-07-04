# Roger Mills Cursory Title Report Builder (codexv2)

A single-file, **run-it-locally** tool that turns a messy folder of Roger Mills
title files into one clean, chained Excel title report — plus a set of review
artifacts. It runs on **your** machine, where `D:\Desktop\Horizon\Roger Mills`
actually lives, because a cloud assistant cannot see your `D:` drive and must
never invent title data.

The script is `roger_mills_title_report_builder.py` (in this folder).

## What it does, in order

0. **Unzips** every `.zip` under `--root` (recursively, including zips inside
   zips; path-traversal-safe; skips archives already extracted).
1. **Inventories** every file and classifies it (template / report / runsheet /
   OGL / index PDF / data / …).
1b. **Tidies**: finds exact-byte **duplicates** and **trash** (empty files,
   `~$` Office locks, `Thumbs.db`, `.tmp`) and **moves** them to a reversible
   `_quarantine` folder (never deletes). Every action is logged to
   `tidy_manifest_codexv2.csv`. Use `--no-tidy` to only report, not move.
2. **Backs up** every original (timestamped) before reading anything.
3. **Analyzes** every workbook and scores them.
4. **Picks the best base** report workbook in a weighted tournament.
5. **Merges** rows from all report sources — **workbooks and CSV/TSV** — with
   fuzzy header matching, normalization, and intelligent de-duplication.
5b. **Runsheet notes + OGL numbers**: attaches runsheet notes (from a runsheet
   **workbook, CSV, or scanned PDF**) and OGL numbers (from an OGL schedule) to
   the matching rows by instrument no. / book+page.
5c. **Chains the interest**: parses fractions (`1/2`), fraction products
   (`1/2 of 1/8`), decimals, percents, and **NMA** (net mineral acres, needs
   `--gross-acres`) into exact rationals, and walks every conveyance
   chronologically.
6. **Verifies** rows against the index PDF (text → pdfplumber → PyMuPDF → OCR).
7. **Builds** the final workbook by copying your `Template(30).xlsx` formatting
   and writing the merged rows, then **appends** three sheets:
   `Interest Chain`, `Ownership Ledger`, and `OGL Summary`. It **loops till
   perfect**: rebuild + validate up to `--max-passes`.
8/9. Writes support files and a `final_validation_summary_codexv2.txt` that ends
   with a **PERFECTION CHECKLIST** — the exact human-review items that remain.

**It never invents data.** Anything it cannot confirm or parse is *flagged*
(over-conveyance, unparsed interest, missing party, unverified row), not guessed.

## Install (once)

```bat
py -m pip install --upgrade openpyxl pandas pdfplumber PyMuPDF pytesseract Pillow python-dateutil rapidfuzz
```

Only `openpyxl` is strictly required; the rest degrade gracefully (PDF/OCR and
fuzzy matching just do less without them).

## Run

Simplest — output auto-lands in `D:\Desktop\Horizon\rogermillsfinalreports`:

```bat
py automation\roger_mills_title_report_builder.py ^
    --root "D:\Desktop\Horizon\Roger Mills" ^
    --section "31-12N-24W" ^
    --gross-acres 640
```

Explicit destination + tuning:

```bat
py automation\roger_mills_title_report_builder.py ^
    --root "D:\Desktop\Horizon\Roger Mills" ^
    --final-dir "D:\Desktop\Horizon\rogermillsfinalreports" ^
    --section "31-12N-24W" ^
    --gross-acres 640 ^
    --max-passes 3
```

Run with `--dry-run` first to see the plan (and what would be quarantined)
without writing anything or moving files.

## Naming hints so every engine fires

| Put this in the filename | …and the file is treated as |
|--------------------------|------------------------------|
| `template`               | the formatting authority     |
| `runsheet` (xlsx/csv/pdf)| runsheet notes source        |
| `ogl` / `lease schedule` | OGL number source            |
| anything else tabular    | a candidate report to merge  |

Pass `--gross-acres <acres>` so **NMA** interests convert to a fraction of the
whole; without it they are left unparsed and flagged.

## Flags

| Flag | Effect |
|------|--------|
| `--root` | folder to scan (required) |
| `--section` | tract label, e.g. `31-12N-24W` |
| `--gross-acres` | gross mineral acres → enables NMA chaining |
| `--final-dir` | output folder (default `<root>\rogermillsfinalreports`) |
| `--output` / `--support-dir` | override individual paths |
| `--template` | force a specific template workbook |
| `--max-passes` | loop-till-perfect rebuild attempts (default 3) |
| `--no-unzip` | skip archive extraction |
| `--no-tidy` | detect duplicates/trash but do **not** move them |
| `--dry-run` | analyze/plan only; write nothing, move nothing |

## Outputs

In `rogermillsfinalreports\`:
- `31-12N-24W_Roger_Mills_Cursory_Title_Report_codexv2.xlsx` — the report, with
  `Interest Chain`, `Ownership Ledger`, and `OGL Summary` sheets.

In `rogermillsfinalreports\files\`:
- `final_validation_summary_codexv2.txt` — stats + **PERFECTION CHECKLIST**
- `tidy_manifest_codexv2.csv` — every duplicate/trash decision
- `source_inventory_codexv2.csv`, `merge_audit_codexv2.csv`,
  `conflicts_review_codexv2.xlsx`, `build_log_codexv2.txt`
- `backup_<timestamp>\` — untouched copies of every original
- `_quarantine\` — moved duplicates/trash (restore from here to undo a tidy)

## The "loop till perfect" workflow

1. Run the tool. 2. Open `final_validation_summary_codexv2.txt` and work down the
PERFECTION CHECKLIST (fix an unparseable interest, resolve a name mismatch that
made a party go negative, confirm a flagged row against the index, etc.).
3. Fix the underlying source files. 4. Re-run. Repeat until the checklist reports
"No automated issues remain." — then do a final examiner spot-check and sign off.
