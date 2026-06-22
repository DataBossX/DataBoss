# Doc-Type Normalization

County indexes use terse abbreviations. The app normalizes the **Doc Type**
(column C) to a consistent value, while **preserving the original wording in
Notes (column J)**. Never discard what the county actually wrote — the original
abbreviation goes into Notes so the source is traceable.

## Mapping

| County abbreviation | Normalized Doc Type (col C) |
|---------------------|-----------------------------|
| `O/L` | Oil and Gas Lease |
| `ASGT` | Assignment |
| `PT-ASGT` | Partial Assignment |
| `MD` | Mineral Deed |
| `QCD` / `QC` | Quitclaim (Quitclaim Mineral Deed where context supports) |
| `RATIF` | Ratification |
| `REL` | Release |
| `MTG` | Mortgage |
| `DEED` / `WD` | Warranty Deed |
| `FD` | Final Decree |
| `AFF` | Affidavit |
| `ROW` | Right of Way |
| `COR` | Correction |
| `MEMO` | Memorandum |
| `ORDER` / `JUDG` / `DECREE` | Court/probate item |

## Rules

- **Preserve the original in Notes.** When normalizing, append the original
  county wording to column J, e.g. `Notes: "Index abbrev: PT-ASGT"`. Do not
  overwrite existing Notes content — append.
- **QCD/QC context rule.** Map to "Quitclaim". Use "Quitclaim Mineral Deed" only
  where the surrounding context clearly supports a mineral conveyance; otherwise
  keep the plain "Quitclaim" and let a human refine. If context is ambiguous,
  flag `VERIFY: OCR uncertain` or note the ambiguity rather than asserting
  "Mineral Deed."
- **DEED/WD.** Both map to "Warranty Deed". If the index shows a deed type that
  is not clearly a warranty deed, keep the original wording in Notes and flag for
  review rather than forcing "Warranty Deed."
- **ORDER/JUDG/DECREE.** These collapse to "Court/probate item" as the normalized
  type; the specific instrument label (order, judgment, decree, final decree)
  belongs in Notes so the distinction is not lost. Note that `FD` (Final Decree)
  has its own normalized value ("Final Decree") and should not be merged into the
  generic court/probate bucket.
- **Unknown abbreviations.** If an abbreviation is not in the table, do NOT guess
  a normalized type. Leave column C with the original wording (or blank) and flag
  `VERIFY: OCR uncertain` / add a note for human classification.
- **Handwriting caveat.** Because the index is handwritten cursive, the
  abbreviation itself may be misread. Any normalization derived from an uncertain
  read carries `VERIFY: OCR uncertain` (see `REFUSE_TO_GUESS.md`).
