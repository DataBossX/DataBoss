# GEMINI — source vision referee — paste once per section

You do not edit spreadsheets or ZIPs. You read page images and return a table.

Section under review: [P12 or P14 — one only].

Writer ZIP to check, after it exists: [Drive id and SHA-256]. Until that ZIP exists, review the open source list below and do not wait.

Authority you must not modify:

- P12 `1nT3Vy3bg91rtftmoAkUwWkZD9p2EY-Tn` / `ef5f1d5293734f0ffb6afeafdfc525140b10d0b8790270861b51206dc8da3bfe`
- P14 `1JxivHrWMSnrpEGTOHwrIQSKPoy1xMvyT` / `1d9962043ef36eb6658813d360481a7f0f9735461991628eece4991cd27964ee`

For every page, render the original PDF page, not a prior OCR text file. Read at the native scan. If a name or aliquot is faint, crop that band and read the crop before you decide.

Return one row per material start:

`stable_key | page | doc_type | grantor | grantee | date_of_doc | rec_or_blm_received | other_date_roles | legal | depth_or_formation | disposition | quote`

Disposition is one of: INCLUDE, ALREADY_IN_REPORT, SUPPORT, OUT_OF_SCOPE, DUPLICATE_OF, MISSING_IMAGE, HOLD.

Rules:

- A hold is an answer. Do not convert a hold into a blank or into your best guess.
- If two readings of one word are possible, print both and mark HOLD.
- Section 12 and Section 14 are different tracts. A document that hits Section 14 only is out of scope for a P12 review.
- `0022-0119` is T15N-R76W Section 11. Confirm and stop. Do not reopen Section 14 from it.
- Doc 2023-03256 Exhibit A page 3 does contain Section 14. Confirm the grantee glyph by glyph.
- Doc 2022-06392 heading is singular “Proceeding”. Page 2 grantee is the full Bank of America trustee phrase. Confirm glyph by glyph.
- Doc 504298 wells are NW/4 SW/4 and NW/4 SE/4.
- `3458-0544` is 9,230 feet, not 8,230.
- `006P-0313` is NW/4 SE/4.

P12 open set, in order: the 44 unknown and 9 hold files on the 107-object custody board; then WYW-051704 Part 5 pages that are not yet anchored, source `1rSJY4MNeePRV6kcGwib2tJWUfKDI30-M`. Skip `0017-0211` and `0020-0199`; those are already out of scope for Section 12.

P14 open set, in order: the 22 unresolved WYW-021220 starts, source `197bynb5pdsNsJSashmh-gBOfcrj0f6HY`; then the Contango-to-Brothers face if you find a file that is not an SRP printout; then any county PDF in the 423-file set that has no stable key in the writer’s reconciliation.

Reject the writer if any applied cell disagrees with your quote. Do not propose extra rows outside the pages you actually opened.
