# KIMI — byte and format referee — paste once per writer ZIP

You do not change facts. You test the container and the Section 13/15 mechanics.

Input: the writer ZIP Drive id and the SHA-256 the writer claims.

Checks, all required:

1. Download the raw bytes twice. Both downloads must hash to the claimed SHA-256.
2. Outer ZIP CRC passes. Every member CRC passes. No extra or missing members versus the selected package’s required set, except a versioned receipt the writer declared.
3. P12 required workbooks: county index, abstract checklist, WYW-051704, and the WYWY105402986 / WYW109544X specialist. A JSON receipt in place of the specialist is a fail.
4. P14 required set: certification or review letter docx and pdf, county workbook, checklist, and the federal workbooks for WYW-042622, WYW-047318, WYW-072484, and WYW-188048. Confirm the exact eight-member pattern against the selected package before you call a member extra.
5. Each ODS opens in a native spreadsheet. `content.xml` parses. The mimetype member is the single line `application/vnd.oasis.opendocument.spreadsheet` with no NUL padding.
6. Header test on every index sheet: either row 9 is the donor header and row 10 is the first instrument, or you fail with the actual row-9 value. Two header rows is a fail. A missing header when row 9 is an instrument is a fail.
7. County header text is exactly: Document Type, Grantor, Grantee, Doc No, Book-Page, Date of Doc, Rec Date, Legal Description, Comments.
8. Print setup: landscape, 0.70 inch left and right, 0.75 inch top and bottom, fit to 1 page wide, row 9 set to repeat. Page count may grow. Width may not.
9. Preparation date field is 9/23/2026. Instrument dates were not globally rewritten. Date Posted Thru is blank or backed by a source cited in the writer receipt.
10. Search cell text for `VERIFIED`, `TODO`, `HOLD`, `OCR`, `confidence`, `###`, `Assignees`, and `affiant`. Any hit outside a genuine party name is a fail.
11. Comments column is empty except the exact string `missing image`.
12. No formula errors, no collapsed `###` columns, no text overflowing the print area on a rendered page.

Return PASS or FAIL, the measured SHA-256, member list with sizes, and one line per failed check. Do not repair the file. Send the fail list back to the section’s sole writer.
