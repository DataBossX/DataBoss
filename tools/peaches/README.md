# Peaches local accounting tools

Preparation date: 10/19/2026.

This generic tool bundle extends the existing local Peaches audit pipeline. It accounts for every physical PDF page and records literal index-cell states in an owned SQLite database. It does not call an AI provider, run a background worker, or certify that an abstract is complete.

## What changed

The original image-only queue emitted only page 1 for PDFs with five or more pages. The updated queue includes every physical page of every measured PDF. Each record uses the SHA-256 of the original PDF bytes plus its 1-based physical page number. Identical copies share page records while retaining every relative path; different files with the same basename remain separate.

Boundary signals remain candidates. Native text and OCR do not establish visual review. A named review receipt can be imported only for its exact source hash and physical page, with a recognized visual method, reviewer, time, and evidence reference. The module validates the receipt's structure, not the truth of its contents. The original PDF is never modified.

The new importer records source bodies, source instances, page status, workbook snapshots, index cells, and run membership. Counts are scoped to the current import and historical snapshots remain available. The database intentionally leaves the source-document count undetermined until a separate, accepted boundary ledger establishes it.

## Installation and offline verification

Use a Python environment with the dependencies in requirements.txt. No API keys are needed.

```bash
cd tools/peaches
python -m unittest discover -s tests -p test_accounting.py -v
python tests/run_tests.py
```

The regression suite includes five synthetic image-only PDFs with 195, 79, 211, 195, and 88 pages: 768 pages produce 768 page records, initially unreviewed. It also checks basename collisions, identical-content aliases, missing page measurements, OCR separation, blank/unknown accounting, conflicting review receipts, source changes, stale database hashes, lock refusal, and retained review state on repeat imports.

## Build an inventory and complete page census

Use immutable source copies and a separate output directory. Paths below are illustrative.

```bash
python -m peaches.inventory /private/sources /private/qa/run-001
python -m peaches.boundaries /private/sources /private/qa/run-001/boundaries.csv
python -m peaches.vision_queue --inventory /private/qa/run-001/inventory.csv --boundaries /private/qa/run-001/boundaries.csv --out /private/qa/run-001/pages.csv
```

The page-queue command creates its output exclusively and refuses an existing target. The companion pages.csv.issues.json records unmeasured PDFs and ignored ambiguous boundary hints. Its exit status is nonzero if a PDF could not be measured. Missing measurements never create a guessed page 1.

The optional `--reviews prior_reviews.csv` accepts these columns:

| Column | Meaning |
| --- | --- |
| source_sha256 | Full lowercase SHA-256 of the original PDF |
| page | Positive 1-based physical page number |
| status | VISUALLY_REVIEWED for a visual receipt |
| review_method | HUMAN_VISION, MODEL_VISION, or INHERITED_VISION |
| reviewer | Identity of the reviewer or reviewing worker |
| reviewed_at | Receipt timestamp with timezone recommended |
| evidence_ref | Traceable review artifact or receipt reference |
| disposition | Internal page role, such as continuation or document start |

Blank or OCR-only receipts leave the page unreviewed. Contradictory accepted receipts require adjudication.

## Import source and cell accounting

```bash
python -m peaches.accounting --database /private/qa/accounting.sqlite --inventory /private/qa/run-001/inventory.csv --boundaries /private/qa/run-001/boundaries.csv --source-root /private/sources --workbook /private/sources/index.xlsx
```

Supply `--workbook` repeatedly for each index workbook. The importer recognizes the existing county nine-column and federal ten-column row-9 schemas, reads the selected index sheet, and starts at row 10. It rejects an unrecognized schema rather than classifying columns by a guess.

For an existing database, provide `--expected-db-sha` with the SHA-256 observed immediately before importing. A competing .writer.lock, an unexpected database digest, an active SQLite sidecar, a source-hash mismatch, an unsupported database schema, or a conflicting prior visual receipt causes refusal. The tool writes a staged database and replaces the owned target only after integrity and input-digest checks pass. A lock is never automatically stolen. Every cooperating writer must follow this lease protocol; this cannot prevent arbitrary external software from disregarding it.

The JSON result distinguishes:

| Classification | Meaning |
| --- | --- |
| EXPECTED_BLANK | Blank Comments, plus blank federal File No |
| UNRESOLVED_BLANK | Another empty index cell, without a source-specific absence disposition |
| UNKNOWN_EXACT | Literal UNKNOWN, disregarding case |
| UNKNOWN_QUALIFIED | A nonempty cell containing UNKNOWN with additional text |
| POPULATED_UNVERIFIED | A populated cell whose source accuracy this importer has not certified |

Expected blank columns are excluded from the unresolved total. A legal left blank because the source truly lists no lands remains conservatively unresolved in this generic importer until a separate source-absence ledger is adjudicated. The tool does not infer that a blank date or legal is intentionally absent.

## Database tables

| Table | Grain |
| --- | --- |
| sources | Immutable content SHA-256 |
| source_instances | Content SHA-256 and relative path |
| pages | Content SHA-256 and physical page |
| workbooks | Workbook SHA-256 and selected index-sheet metadata |
| cells | Workbook SHA-256, sheet, row, and column |
| runs | Import identifier, timestamp, input hashes, issues |
| run_sources | Sources in a particular import |
| run_workbooks | Workbook instances in a particular import |

Source aliases are counted as file instances but do not multiply physical-page work. Historical workbook snapshots do not inflate the current run's cell totals.

## Scope and limits

This is a generic, offline draft tool bundle. It has not imported or modified a live landman application, deployed a Site, or processed any private source files as part of its regression tests.

The original boundary detector, workbook parser, formatting QA, donor comparison, package builder, and orchestration commands remain available. Their pre-existing limitations remain: parser-level donor comparison is not native-application print verification; the inherited QA date check is not a full calendar validator; page/part formatting and county sort checks need human or separate deterministic QA where noted. The all-page queue and importer do not depend on the original boundary detector deciding document starts correctly.

A complete delivery still requires accepted source-document boundaries, all-page evidence, resolved field exceptions, native workbook/PDF checks, and final package receipts.
