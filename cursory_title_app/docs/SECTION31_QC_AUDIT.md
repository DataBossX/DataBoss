# Section 31-12N-24W — Forensic QC Audit
_2026-06-23T03:52:44_  ·  workbook: `b176e398-3112N24W_Roger_Mills_Cursory_Title_Report_6222026.xlsx`

**25 findings** — info:18, med:5, low:2

## MED (5)
- `R-DATE-ORDER` **[HIGH]** Runsheet!E45/F45: Effective date 1919-12-29 is after recorded date 1919-12-17.
- `R-DATE-ORDER` **[HIGH]** Runsheet!E99/F99: Effective date 1938-02-27 is after recorded date 1938-02-13.
- `R-DATE-ORDER` **[HIGH]** Runsheet!E986/F986: Effective date 2019-10-01 is after recorded date 2019-09-03.
- `TI-VERIFY` **[HIGH]** Title: 81 existing VERIFY/NEED flags in Title tab (human-review backlog).
- `TI-NONNUM-ACRES` **[HIGH]** Title: 35 owner rows have non-numeric Net Acres (unresolved).

## LOW (2)
- `O-MISSING-GROSS` **[MEDIUM]** 253 occurrences: 253 occurrences. e.g. OGLs row 2: Lease missing Gross Acres. | OGLs row 3: Lease missing Gross Acres. | OGLs row 4: Lease missing Gross Acres. | OGLs row 5: Lease missing Gross Acres. | OGLs row 6: Lease missing Gross Acres.
- `O-MISSING-EXP` **[MEDIUM]** 241 occurrences: 241 occurrences. e.g. OGLs row 2: Lease missing Expiration date (HBP/released status unknown). | OGLs row 3: Lease missing Expiration date (HBP/released status unknown). | OGLs row 4: Lease missing Expiration date (HBP/released status unknown). | OGLs row 5: Lease missing Expiration date (HBP/released status unknown). | OGLs row 6: Lease missing Expiration date (HBP/released status unknown).

## INFO (18)
- `R-INFO` **[HIGH]** Runsheet: 1051 populated data rows audited.
- `O-INFO` **[HIGH]** OGLs: 307 leases audited.
- `T-BALANCE` **[HIGH]** Tract 1: Conveyance ledger nets to -4.88498e-15 (balanced).
- `T-OWNERS` **[MEDIUM]** Tract 1: 79 current owners; net acres traced=80.0000 of 80.0 tract acres; net interest sum=1.000000.
- `T-BALANCE` **[HIGH]** Tract 2: Conveyance ledger nets to -3.10862e-15 (balanced).
- `T-OWNERS` **[MEDIUM]** Tract 2: 130 current owners; net acres traced=160.0000 of 160.0 tract acres; net interest sum=1.000000.
- `T-BALANCE` **[HIGH]** Tract 3: Conveyance ledger nets to -2.22045e-16 (balanced).
- `T-OWNERS` **[MEDIUM]** Tract 3: 63 current owners; net acres traced=40.0000 of 40.0 tract acres; net interest sum=1.000000.
- `T-BALANCE` **[HIGH]** Tract 4: Conveyance ledger nets to -2.66454e-15 (balanced).
- `T-OWNERS` **[MEDIUM]** Tract 4: 53 current owners; net acres traced=80.0000 of 80.0 tract acres; net interest sum=1.000000.
- `T-BALANCE` **[HIGH]** Tract 5: Conveyance ledger nets to -4.44089e-15 (balanced).
- `T-OWNERS` **[MEDIUM]** Tract 5: 65 current owners; net acres traced=120.0000 of 120.0 tract acres; net interest sum=1.000000.
- `T-BALANCE` **[HIGH]** Tract 6: Conveyance ledger nets to 2.22045e-16 (balanced).
- `T-OWNERS` **[MEDIUM]** Tract 6: 20 current owners; net acres traced=80.0000 of 80.0 tract acres; net interest sum=1.000000.
- `T-BALANCE` **[HIGH]** Tract 7: Conveyance ledger nets to -1.77636e-15 (balanced).
- `T-OWNERS` **[MEDIUM]** Tract 7: 49 current owners; net acres traced=40.0000 of 40.0 tract acres; net interest sum=1.000000.
- `T-BALANCE` **[HIGH]** Tract 8: Conveyance ledger nets to -5.77316e-15 (balanced).
- `T-OWNERS` **[MEDIUM]** Tract 8: 77 current owners; net acres traced=40.0000 of 40.0 tract acres; net interest sum=1.000000.
