# Combine-Harvest index format

Prepared 10/19/2026. These commands format the Johnson County packages for 47N-76W sections 6, 7, 18, 19, 30, and 31, and 47N-77W sections 13 and 24. Finished Overtime sections 11, 13, and 15 control column geometry. They are not part of this abstract.

County columns, in order: Document Type, Grantor, Grantee, Doc No, Book-Page, Date of Doc, Rec Date, Legal Description, Comments.

BLM columns, in order: Document Type, Grantor, Grantee, File No, Page, Date of Doc, Rec Date, Comments, Legal Description, Part.

Rows 1-7 are County, Lands, Date, Starting Date, Date Posted Thru, Indexed By, and Project. Row 8 is blank. Row 9 is the header. Entries start on row 10. The font is Calibri 11. The preparation date is 10/19/2026, displayed as m/d/yyyy.

Starting Date stays blank unless a proved start date is in the source register. Date Posted Thru stays the visible value Unknown unless an official cutoff is verified. Do not copy Inception, Available records, or an SRP run date into those cells, and do not treat the preparation date as the recording cutoff.

All-digit county document numbers are stored as integers. The original spelling, including leading zeros, stays in the database. An Unknown document number stays Unknown.

On a BLM sheet, File No and Comments stay in place and stay blank. Page is one physical starting page. Part is one source part number in the last column. Do not invent Part 1 for an unnumbered file.

County Comments are blank or exactly `missing image`.

Do not commit instrument rows to the public DataBoss repository. Run the builder against a local master JSON and deliver the package on Drive. The builder does not issue an adoption receipt and does not replace R41.

```bash
python3 tools/ch185443/build_package.py /path/to/master.json /path/to/output
python3 tools/ch185443/qa_cycles.py /path/to/output
python3 tools/ch185443/qa_cycles.py /path/to/output --print
python3 -m unittest tools/ch185443/tests/test_format.py
```
