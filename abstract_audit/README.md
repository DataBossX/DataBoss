# Abstract 4576 — Audit Toolkit

Verification tooling for the Campbell County, WY (T45N-R76W) Penterra
mineral title abstracts. Answers the questions that decide whether a
section is turn-in ready, without opening Excel.

## The Section 15 standard

Section 15 (`p15_exact6_reference_20260914`) is the reference deliverable.
A section is complete when its folder holds **exactly** these files:

| Artifact | Filename |
| --- | --- |
| Section index | `45N-76W-NN_Campbell_Co_Penterra_Abstract_Index.xlsx` |
| Lease index (one per federal lease) | `WYW-NNNNNN Campbell Co. Penterra Abstract Index.xlsx` |
| Checklist | `Abstract_Checklist_NN-45N-76W.xlsx` |
| Certification letter | `NN-45N-76W_Certification_Letter.docx` |
| Certification letter | `NN-45N-76W_Certification_Letter.pdf` |

Section 15 touches 2 leases, so its set is 4 + 2 = **6 files**.

Every index carries a 7-row header block (Index County, Lands, Date,
Starting Date, Date Posted Thru, Indexed By, Project) above a 9-column
document table: Document Type, Grantor, Grantee, Doc No, Book-Page,
Date of Doc, Rec Date, Legal Description, Comments.

`Book-Page` is legitimately blank on modern e-recorded documents
(Doc No `2026-03115` style), so it is **not** counted as a defect.
Required-never-blank columns: Document Type, Grantor, Grantee, Doc No,
Rec Date.

## Usage

Audit one or more index workbooks:

    python index_audit.py "45N-76W-15_...Index.xlsx" --json report.json

Cross-check a BLM folder, an image folder, or a section deliverable:

    python parity.py --blm-dir ./BLM --image-dir ./images \
                     --section-dir ./Section14 --section 14 \
                     --leases WYW-047318 WYW-042622

Sweep an entire working tree and get one percent-complete figure:

    python run_audit.py --root "D:/Abstract4576" --json status.json

## Tests

    python -m pytest tests/ -q
