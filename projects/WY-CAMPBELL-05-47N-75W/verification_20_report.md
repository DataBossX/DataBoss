# Verification: Section 20 CURSOR_REBUILT abstract index vs original

_Date: 2026-07-18 · Method: instrument-level diff of Drive file
`replaced_New 47N-75W-20_Campbell_Co_Penterra_Abstract_Index.ods`
(1x79gjHfUZ2gKt9jByZxzISiFTEaRGCc2) against
`NEW_47N-75W-20_..._CURSOR_REBUILT.ods` (1vhd54oAr7IVhaKXOqde4yGuzj08z1z79)_

## Verdict: DO NOT APPROVE AS-IS — same instrument set, but 3 defects and
## several substantive edits need examiner confirmation.

### Instrument coverage — PASS
- Every one of the original's 135 instrument entries is present in the
  rebuild. Zero entries lost, zero genuinely new instruments.

### Defect 1 — unconverted Excel date serials (data corruption)
Three raw spreadsheet serial numbers sit in date columns instead of dates:
- Doc 564274 (WD Wagensen → Flying T): Date of Doc = `31097` (original: blank)
- Doc 564275 (WD Rogers → Flying T): Date of Doc = `31171` (original: blank)
- Doc 962219 (Sheridan I-M → I-B): dates = `40816` / `40830`
  (original: 8/30/2007 / 5/15/2007; serials decode to 9/30/2011 / 10/14/2011,
  matching the other Sheridan entries — likely an intended correction left
  in raw serial form)

### Defect 2 — three template header fields dropped
The rebuild's header omits `Date Posted Thru:`, `Indexed By:`, and
`Project:` (original: 6/1/2026 / Ryan Gille / Abstract 4775 Ryder). The
certified through-date disappearing from the face of the index is a
certification-scope problem, not a cosmetic one.

### Substantive edits requiring examiner sign-off (11 changed rows)
- Doc 674876 (Mineral Deed Napier → West): Rec Date changed
  8/6/1993 → 12/19/2002.
- Several rows (e.g. 1393393, 865866) gained the comment "Doc No was
  Book-Page reference; actual instrument number not proven — left blank for
  HOLD/review" — a reasonable flag, but it alters the record and needs
  confirmation against county data.
- Header Date changed 7/13/2026 → 07/14/2026 (expected for a rebuild).

## Required before APPROVED
1. Convert the three serial values to real dates (or restore blanks) and
   confirm the 962219 date correction against the county record.
2. Restore the three header fields, including `Date Posted Thru: 6/1/2026`
   (or the actual re-run through-date).
3. Examiner confirms the 674876 recording-date change and the HOLD/review
   doc-number annotations.
4. Section 17: no pre-rebuild original was found in Drive — locate it (or
   confirm the rebuild is the first index) before approving Section 17.
