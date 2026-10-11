# PENTERRA Abstract Packages — Sections 6, 7, 13, 24 (Johnson County, Wyoming)

Finishing and reconciliation pass over the four PENTERRA abstract packages, formatted to
match the two finished **Overtime** abstract packages (Campbell County Sections 11 and 15).

## What the finished Overtime packages look like

Each finished Overtime section package is a flat six/seven-file set:

| Role | Example (Overtime Section 11) |
|---|---|
| County/section index | `45N-76W-11_Campbell_Co_Penterra_Abstract_Index.ods` |
| Federal lease index (one per serial) | `WYW-005955 Campbell Co. Penterra Abstract Index.ods` |
| Checklist | `Abstract_Checklist_11-45N-76W.xlsx` |
| Certification letter | `11-45N-76W_Certification_Letter.docx` + `.pdf` |

Index workbooks carry a 7-field header (`Index County`, `Lands`, `Date`, `Starting Date`,
`Date Posted Thru`, `Indexed By`, `Project`) above a 9-column table
(`Document Type, Grantor, Grantee, Doc No, Book-Page, Date of Doc, Rec Date, Legal
Description, Comments`). Federal companions use a 7-column variant keyed on `Page`.

The checklist is three stacked blocks — *Abstract checklist*, *Abstract Excel Sheet*,
*Certification Letter* — and **the entry count lives in the checklist**
(Overtime S11: `County index: 475 entries; source cutoff 4/22/2026`).

## Counting rule (validated, not assumed)

```
county abstract entries = county index rows - BLM survey/plat rows
                          (Dependent Resurvey Plat, Corner Record)
```

Validation against the finished packages:

* Overtime S11 — 476 index rows − 1 BLM plat row = **475**, matching its checklist. Its
  `Date Posted Thru` (4/22/2026) also reproduces the checklist's stated source cutoff.
* Overtime federal WYW-005955 — **48** page-anchored rows, matching its checklist.

Only the **first** index table counts. The Section 13 and 24 working drafts append a
second *Historical proposals* table; those are baseline proposals, not admitted entries,
and are reported separately.

## Counts

| Section | Twp-Rng | Index rows | BLM plat rows | County entries | Proposals (excluded) | Federal leases | Federal entries | Total |
|---|---|---|---|---|---|---|---|---|
| 6  | 47N-76W | 49 | 4 | **45** | 0 | 0 | 0 | 45 |
| 7  | 47N-76W | 3 | 0 | **3** | 0 | 1 | 1 | 4 |
| 13 | 47N-77W | 28 | 1 | **27** | 24 | 5 | 12 | 39 |
| 24 | 47N-77W | 95 | 5 | **90** | 6 | 5 | 28 | 118 |
| **Total** | | **175** | **10** | **165** | **30** | **11** | **41** | **206** |

19 workbooks in total, which reconciles to the "All 19 workbooks" figure stated in the
source package `READ_ME.md`.

## What is NOT finished, and why

These packages **cannot be certified complete**, and no deliverable here claims otherwise.
Finishing them in the substantive sense means abstracting county records that have not yet
been reviewed — original title work on primary records, not formatting. Fabricating index
entries, dates or search cutoffs to fill the gap would corrupt a legal record, so the
qualifications state the position plainly instead.

Blocking items:

* **Section 7** — 53 of 9,081 physical county pages carry recorded review; 9,028 do not.
  Only 3 index entries are source-supported.
* **Sections 6 and 7** — no starting date and no posted-through date established.
* **Sections 13 and 24** — no authoritative posted-through date established.
* **Section 6** — no separate official federal lease index accepted.
* **Section 24** — federal companion W-39577 is on HOLD: its schedule describes
  T42N-R77W Sections 1 and 12; applicability to target Section 24 is not proved.
* All four certification letters remain **unsigned**; present rights and examiner
  acceptance remain open in every section.

The full punch-list is the `Open Items` sheet of the reconciliation workbook.

## Deliverables

`deliverables/`

* `Abstract_Checklist_{6,7,13,24}-47N-7{6,7}W.xlsx` — Overtime three-block checklist,
  filled with the counts above plus a Qualifications block.
* `{6,7,13,24}-47N-7{6,7}W_Certification_Letter.docx` — Overtime letter layout
  (Section 11 heading pattern), unsigned, with truthful contents and qualifications.
* `PENTERRA_Abstract_Packages_Reconciliation.xlsx` — `Counts Summary`, `File Inventory`,
  `Open Items`, `Format Parity`.

## Scripts

`scripts/`

* `counter.py` — derives header fields and entry counts from an index workbook.
* `build_packages.py` — emits the checklists and certification letters.
* `build_reconciliation.py` — emits the reconciliation workbook.
* `slim_docx.py` — drops the legacy `stylesWithEffects` part and template thumbnail,
  cleaning the matching relationship and content-type entries (letters 37 KB -> 21 KB).
* `counts.json`, `sections.json`, `file_ids.json`, `inventory.json` — derived inputs.

Counts in the deliverables come from `counts.json`, which `counter.py` derives from the
actual workbooks. Where a source value is absent it is carried through as
`Unknown`/`N/A` rather than filled in.

## Defects found

* A stray Word lock file `~$stract_Letter_7-47N-76W_UNSIGNED_QUALIFIED.docx` (162 bytes)
  sits in the Section 7 `Abstract` folder; excluded from the final package.
* Reference defect in the finished Overtime Section 15 package: its letter heading reads
  *"Section 2 Abstract Certification Letter"*. Section 11's heading is correct and was
  used as the template here.
