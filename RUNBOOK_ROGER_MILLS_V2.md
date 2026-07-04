# RUNBOOK — Roger Mills Final Reports (codexv2)

**Run this on YOUR Windows PC** — the machine where `D:\Desktop\Horizon` actually
lives. The cloud assistant that wrote the tool cannot see your `D:` drive, so it
built the tool for you to run where the files are.

## What it does, in one command
Takes the **best report from each** of `Roger Mills`, `Roger Mills 2`,
`Roger Mills 3`, runs per-folder **loops** + a cross-folder **tournament**, merges
the best data, **fills the OGL numbers from the OGL sheet**, keeps your **tract
sheet** as the authoritative spine (only fixes its formatting), **fixes the title
sheet** metadata, standardizes the **legal descriptions**, collects your **notes**,
matches your **`Template(30).xlsx`** formatting, and writes the finished workbook +
audit files into **`D:\Desktop\Horizon\rogermillsfinalreports`**.

It **never invents title data.** Anything it can't confirm is flagged `[REVIEW]`.

## 0. One-time setup (install once)
```bat
cd /d D:\Desktop\Horizon
py -m pip install --upgrade openpyxl pandas pdfplumber PyMuPDF pytesseract Pillow python-dateutil rapidfuzz
```
Only `openpyxl` is strictly required; the rest just add PDF/OCR + fuzzy matching.

## 1. Preview first (writes nothing)
```bat
py <path-to-repo>\automation\roger_mills_report_builder_v2.py --horizon "D:\Desktop\Horizon" --dry-run
```
Read the console: the tournament scores, which report won each folder, how many
records merged, how many OGL numbers/tracts/notes were found.

## 2. Build the final reports  ← the main command
```bat
py <path-to-repo>\automation\roger_mills_report_builder_v2.py --horizon "D:\Desktop\Horizon"
```
Output lands in `D:\Desktop\Horizon\rogermillsfinalreports\`:
- `31-12N-24W_Roger_Mills_Cursory_Title_Report_codexv2.xlsx` — **the finished report**
- `final_summary_codexv2.txt` — what was done + what still needs human review
- `build_log_codexv2.txt` — full timestamped log
- `_backups\<timestamp>\...` — untouched copies of every original (nothing is deleted)
- `files\` — the audit trail:
  - `tournament_scores_codexv2.csv` — every workbook's score
  - `ogl_number_changes_codexv2.csv` — every OGL number filled/repaired (before→after)
  - `legal_description_changes_codexv2.csv` — every legal-description edit (before→after)
  - `conflicts_review_codexv2.xlsx` — book/page/instrument disagreements to resolve
  - `merge_audit_codexv2.csv` — every merged record and its sources
  - `notes_collected_codexv2.csv` — all notes gathered from the folders
  - `tract_sheet_fixed_codexv2.xlsx` — the standardized tract sheet
  - `source_inventory_codexv2.csv` — every file seen, classified, scored

## 3. Optional: AI polish of legal descriptions (formatting only)
Put your key in `D:\Desktop\Horizon\.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```
then add `--use-llm`:
```bat
py <path-to-repo>\automation\roger_mills_report_builder_v2.py --horizon "D:\Desktop\Horizon" --use-llm
```
The model only **reformats** legal descriptions (Section 31, Township 12 North,
Range 24 West → Sec 31-12N-24W). It is instructed never to add/remove/change any
section, township, range, quarter-call, lot, or acreage, and **every change is
logged** in `legal_description_changes_codexv2.csv` for you to verify. If the key
is missing or the call fails, it silently falls back to deterministic formatting.

## 4. What to review (in order)
1. Open the finished `..._codexv2.xlsx` — check the **Title Sheet** header, the
   **Runsheet** rows, the **OGL** numbers, the **Tract Sheet**, and **Notes**.
2. `conflicts_review_codexv2.xlsx` — resolve any book/page/instrument disagreements.
3. `ogl_number_changes_codexv2.csv` — confirm each filled OGL number is right.
4. Any Runsheet row whose Remarks contains `[REVIEW: not found in index]`.

## 5. Handy flags
| Flag | Purpose |
| --- | --- |
| `--horizon "D:\Desktop\Horizon"` | parent folder holding the `Roger Mills*` folders |
| `--roots "...\Roger Mills" "...\Roger Mills 2"` | scan explicit folders instead of auto-discovery |
| `--template "...\Template(30).xlsx"` | force a specific template (else auto-detected) |
| `--out-dir "...\rogermillsfinalreports"` | change the output folder |
| `--section "31-12N-24W"` | the section label stamped on the report |
| `--dry-run` | plan only; write nothing |
| `--use-llm` | reformat legals via `ANTHROPIC_API_KEY` (formatting only) |

## 6. Prove the machinery works without touching real data
```bat
py <path-to-repo>\automation\make_roger_mills_sample.py .\_sample
py <path-to-repo>\automation\roger_mills_report_builder_v2.py --horizon ".\_sample\Horizon"
```
Generates a clearly-labeled **synthetic** Horizon corpus and runs the whole build
against it, so you can see exactly what the real run will produce.

## 7. Troubleshooting
| Symptom | Fix |
| --- | --- |
| `no Roger Mills* folders found` | fix `--horizon`, or pass `--roots` with the real paths |
| `.xlsx` won't open / missing | `py -m pip install openpyxl` and rerun |
| OGL numbers not filled | make sure the OGL sheet's header row uses recognizable labels (OGL No, Lessor, Lessee, Book, Page); check `ogl_number_changes_codexv2.csv` |
| Many `[REVIEW: not found in index]` | install `pdfplumber PyMuPDF pytesseract Pillow` (+ Tesseract) so the index PDF can be read, then rerun |
| Tract rows look wrong | the tract sheet is treated as authoritative — fix it in the source; the tool only standardizes its text |
