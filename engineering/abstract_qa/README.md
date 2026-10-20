# Abstract Reconciliation & QA (`aqa`)

Deterministic, resumable, zero-subscription QA for title-abstract packages. Python 3.12, stdlib plus
`openpyxl`, `python-docx`, `pypdf` (and optional `Pillow` for multi-frame images). No network, no cloud.

**Read-only on sources. Writes only into a fresh `runs/<run_id>/` folder. Proposes discrepancies; never
invents or "corrects" title facts. Original images remain the only source of substantive title facts.**

## Run

```
python -m aqa run --config config.local.json [--run-id ID]
python -m aqa run --config config.local.json --resume ID     # reuse completed stages with unchanged inputs
python -m aqa verify runs/ID/final-XXXXXXXXXXXX              # re-hash every artifact against qa_receipt.json
python -m unittest discover -s aqa_tests -t .                    # 41 tests, synthetic fixtures only
```
Exit codes: `0` automated checks clear, `2` blocked (or verify failed), `1` usage/overwrite/config error.
Config: copy `config.example.json` to `config.local.json` (git-ignored). **The shipped schemas, section
regex, narrative patterns and serial regex are placeholders; replace them with the real project values.**

## What each requirement maps to

| # | Requirement | Where |
|---|---|---|
| 1-2 | Recursive inventory of folders and nested ZIPs; SHA-256, ZIP CRC (verified by full read + `testzip`), real PDF pages and image counts | `inventory.py` -> `inventory.json/.csv` |
| 3 | ODS/XLSX/DOCX table + metadata parsing, PDF metadata | `tables.py`, `inventory.pdf_info` |
| 4 | Actual data-row count; excludes pre-header titles, headers, repeated headers, blanks, narrative placeholders, totals; every exclusion counted | `tables.count_rows` |
| 5-6 | Identity-keyed (never positional) reconciliation; conflicts, candidate omissions, legitimate repetitions, in-section duplicates, branch divergence | `reconcile.py` |
| 7 | Canonical federal ledger per serial/date/type; disagreeing fields left blank + listed, status `NEEDS_IMAGE_REVIEW` | `federal.py` -> `federal_ledger.csv/json` |
| 8 | Exact 9-column county and 10-column federal header tests (count, order, case, text) | `checks.test_schema` |
| 9 | Forbidden `BLM File No`/`Comments` headers and values, false Part numbers, page refs outside 1..actual pages | `checks.py` -> `reference_findings.csv` |
| 10 | Style fingerprint vs donor section, deviations marked `owner_override` or `unexplained` | `style.py` |
| 11 | Per-stage and master receipts (hashes, fingerprints, versions); per-section dashboard | `qa_receipt.json`, `qa_dashboard.html`, `section_dashboard.json` |
| 12 | Overwrite refusal, missing/changed/disappeared source detection, cloud-sync detection | `safety.py`, `util.write_new_*` |

## Counting units (never interchangeable)

`census.json` reports each separately: physical pages (all copies vs distinct by SHA), PDF file copies,
distinct PDFs, embedded images / image frames, section-level index placements (county and federal rows),
recorder identities, tract appearances (identity x tract), section applications (identity x section),
federal events and serials. `explanation` recalculates the claimed placement figure from the selected
files and lists which excluded populations (duplicate copies, superseded versions, repeated headers,
narrative rows, totals, unclassified tables) would arithmetically bridge the gap. Subset matches are
leads, not conclusions.

File selection is deterministic: identical bytes -> first sorted path is canonical; same section/kind/stem
with `_vN` suffixes -> highest version, then newest mtime, then path. Every non-selected file is listed
with `duplicate_of` / `superseded_by`. **Review this rule against how the real package folders are named.**

## Safety behaviour

- Output root overlapping a source root or protected canonical-index path, or sitting under a cloud-sync
  folder (OneDrive, Dropbox, Google Drive, iCloud, Box...): run **refused before anything is created**.
- Run directories and every artifact are create-only (`write_new_*`); an existing run id is an error.
  Stage outputs are content-addressed so resume/re-run can never overwrite earlier evidence.
- Online-only cloud placeholders are **not read** (avoids hydration/sync side effects) and block the run.
- Symlinks are not followed; unsafe ZIP member paths and DTD/entity XML are refused; sources are opened `rb` only.
- Source size/mtime is re-checked after reading (`SOURCE_MUTATED_DURING_RUN`).
- Disappeared or changed sources are detected against `expected_sources`, `baseline_manifest`, or the
  previous run's inventory in the same output root.
- Status vocabulary is `BLOCKED` or `AUTOMATED CHECKS CLEAR - IMAGE REVIEW PENDING`. The tool never emits "complete".
- Coordination is by evidence only: hand `final-*/` to the sole production writer. Nothing here writes to canonical indexes.

## Known limits (be explicit with reviewers)

- Page-reference checking can prove a reference is **out of range**, not that it is the **correct** physical page.
- Identity normalisation does not cross-map different reference styles (Book/Page vs reception number); such
  records appear as separate identities / candidate omissions until reviewed against images.
- Candidate omissions classed `may_be_legitimate_tract_not_in_section` are expected for sections that do not cover that tract.
- Merged DOCX cells are de-duplicated; unusual layouts need an eyeball. XLSX formulas are read as cached values.
- Inventory cache keys on path + size + mtime_ns; delete `cache/` to force a full re-hash.
- ODS/XLSX/DOCX files above `max_parse_bytes` are inventoried and hashed but not parsed (a warning is recorded).
