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
   chronologically. Understands **proportional** conveyances — "1/2 of
   grantor's interest" transfers half of whatever the grantor then holds, not
   half of the whole tract (flagged `PROPORTIONAL`; `PROPORTIONAL_NO_BASIS` if
   the grantor's prior interest isn't established).
5d. **Extracts deed instruments** (best-effort, review-only): scans PDF/DOCX
   instruments (files named `*deed*`, `*lease*`, `*assignment*`, etc.) and pulls
   grantor/grantee/date/book-page/instrument type into a **`Deeds (auto-extract
   VERIFY)`** sheet. These are **never** merged into the authoritative chain —
   they are a starting point you verify against the original.
6. **Verifies** rows against the index PDF (text → pdfplumber → PyMuPDF → OCR).
7. **Builds** the final workbook by copying your `Template(30).xlsx` formatting
   and writing the merged rows, then **appends** analysis sheets:
   `Title Summary` (current net ownership per party — fraction, decimal, and NMA
   — plus active leases), `Interest Chain` (flagged rows highlighted red),
   `Ownership Ledger` (negative positions amber), `OGL Summary`, `Review Flags`
   (a single consolidated examiner punch-list), and `Deeds (auto-extract
   VERIFY)`. It **loops till perfect**: rebuild + validate up to `--max-passes`.
8/9. Writes support files, a `final_validation_summary_codexv2.txt` that ends
   with a **PERFECTION CHECKLIST**, and a self-contained **HTML** interest-chain
   report you can open in any browser or share (no external assets, works
   offline).

**It never invents data.** Anything it cannot confirm or parse is *flagged*
(over-conveyance, unparsed interest, missing party, unverified row), not guessed.

## Install (once)

```bat
py -m pip install --upgrade openpyxl pandas pdfplumber PyMuPDF pytesseract Pillow python-dateutil rapidfuzz python-docx
```

Only `openpyxl` is strictly required; the rest degrade gracefully (PDF/OCR,
DOCX deed extraction, and fuzzy matching just do less without them).

## Run

### Easiest: double-click the launcher (Windows)

Double-click **`run_roger_mills.bat`** (in this folder). It installs the Python
packages, runs a quick **self-test**, then asks you for the folder, the section,
and (optionally) the gross acres — and offers a preview-only mode. No command
line needed. The finished reports land in `<your folder>\rogermillsfinalreports`.

### Verify your install first (optional)

```bat
py automation\roger_mills_title_report_builder.py --self-test
```

Builds a tiny synthetic report in a temp folder and prints PASS/FAIL — touches
none of your files. Do this once before the first real run.

### Command line

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
| `--root` | folder to scan (required, unless `--self-test`) |
| `--self-test` | build a synthetic report to verify the install, then exit |
| `--section` | tract label, e.g. `31-12N-24W` |
| `--gross-acres` | gross mineral acres → enables NMA chaining |
| `--final-dir` | output folder (default `<root>\rogermillsfinalreports`) |
| `--output` / `--support-dir` | override individual paths |
| `--template` | force a specific template workbook |
| `--max-passes` | loop-till-perfect rebuild attempts (default 3) |
| `--no-unzip` | skip archive extraction |
| `--no-tidy` | detect duplicates/trash but do **not** move them |
| `--no-deeds` | skip best-effort deed/DOCX instrument extraction |
| `--no-html` | skip the HTML interest-chain report |
| `--dry-run` | analyze/plan only; write nothing, move nothing |

## Outputs

In `rogermillsfinalreports\`:
- `31-12N-24W_Roger_Mills_Cursory_Title_Report_codexv2.xlsx` — the report, with
  `Title Summary`, `Interest Chain`, `Ownership Ledger`, `OGL Summary`,
  `Review Flags`, and (when instruments are found) `Deeds (auto-extract VERIFY)`
  sheets.
- `31-12N-24W_interest_chain_report_codexv2.html` — self-contained browser view
  (leads with current ownership).

In `rogermillsfinalreports\files\`:
- `final_validation_summary_codexv2.txt` — stats + **PERFECTION CHECKLIST**
- `tidy_manifest_codexv2.csv` — every duplicate/trash decision
- `source_inventory_codexv2.csv`, `merge_audit_codexv2.csv`,
  `conflicts_review_codexv2.xlsx`, `build_log_codexv2.txt`
- `backup_<timestamp>\` — untouched copies of every original
- `_quarantine\` — moved duplicates/trash (restore from here to undo a tidy)

## Tests

A regression suite covers interest parsing, the chain math (including
proportional conveyances and over-conveyance flags), duplicate/trash detection,
safe+idempotent zip extraction, the CSV loader, and a full end-to-end build:

```bash
python -m unittest tests.test_roger_mills_builder
```

It needs only `openpyxl`; PDF-dependent checks skip themselves if PyMuPDF isn't
installed.

## The "loop till perfect" workflow

1. Run the tool. 2. Open `final_validation_summary_codexv2.txt` and work down the
PERFECTION CHECKLIST (fix an unparseable interest, resolve a name mismatch that
made a party go negative, confirm a flagged row against the index, etc.).
3. Fix the underlying source files. 4. Re-run. Repeat until the checklist reports
"No automated issues remain." — then do a final examiner spot-check and sign off.
