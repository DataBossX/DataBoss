# Combine-Harvest index format

Prepared 10/19/2026. These are display rules for the Johnson County packages in 47N-76W sections 6, 7, 18, 19, 30, and 31, and 47N-77W sections 13 and 24. Overtime Campbell County sections 11, 13, and 15 are layout donors only.

County columns, in order: Document Type, Grantor, Grantee, Doc No, Book-Page, Date of Doc, Rec Date, Legal Description, Comments.

BLM columns, in order: Document Type, Grantor, Grantee, File No, Page, Date of Doc, Rec Date, Comments, Legal Description, Part.

Rows 1-7 are County, Lands, Date, Starting Date, Date Posted Thru, Indexed By, and Project. Row 8 is blank. Row 9 is the header. Entries start on row 10. Use Calibri 11. The preparation date is 10/19/2026, displayed as m/d/yyyy.

Leave Starting Date and Date Posted Thru blank unless a proved search period is in the source register. Do not copy Inception, Available records, or an SRP run date into those cells.

Put each party on its own line in the same cell. End every party except the last with a comma. Do not split a name at `, LLC` or another proved entity comma.

On a BLM file, list every proved section in 47N-76W and 47N-77W, separated by a comma and a new line in the same cell. If the document also covers lands outside those townships, add `, aol` after the last retained leg. If it lists only outside lands, write `outside lands only`. If it lists no lands, leave the cell blank. A missing legal is also blank in the client cell and stays unresolved in the database.

On a section report, show that section's legal and add `, aol` when the document covers any other land, including another project section.

BLM File No and Comments stay in the sheet and stay blank. Page is the first physical PDF page, one integer. Part is one integer in the last column. Do not invent Part 1 for an unnumbered file.

Do not commit selected instrument rows to the public DataBoss repository. Run the builder against a local master JSON and deliver the package on Drive.

```bash
python3 tools/ch185443/build_package.py /path/to/master.json /path/to/output
```
