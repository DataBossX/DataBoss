# DataBoss Title Factory Master Playbook

## Immediate scope

Section 32, Township 11 North, Range 25 West, Beckham County, Oklahoma. The
private production corpus remains on the operator workstation and is not in
this repository.

## Mandatory sequence

`INSPECT → BACKUP → INVENTORY → PREPROCESS → OCR/VISION → EXTRACT → RECONCILE → CHAIN → POPULATE → VALIDATE → REPORT`

The source image controls every field. Model agreement is supporting evidence,
not truth. Material conflicts stay unresolved until human review.

## File safety

- Never edit, move, rename, or delete a source.
- Store derived images and results in timestamped run folders.
- Back up every workbook selected for a copy/edit operation under
  `_DATABOSS_BACKUPS/stamp_*` with hashes.
- Archive all extraction candidates and conflicts; never select-and-delete.

## Workbook safety

- Do not add audit sheets to a client workbook.
- Put provenance, reconciliation, review, and preservation information in the
  separate control workbook.
- Inventory high-risk OOXML features before work and compare them afterward.
- Do not call a workbook template-safe unless the preservation audit passes.
- Do not populate cells without an approved workbook fingerprint and
  writable-range mapping.

## Readiness rule

A preservation-audited template copy is not a completed title report. Submission
requires the mounted Section 32 corpus, approved mapping, complete provenance,
title/tract/OGL/WI validation, and human examiner sign-off.
