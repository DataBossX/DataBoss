# Grocery Report -- Executive Summary

**Generated:** 2026-07-04 01:29:06  •  **Pipeline:** grocery_report_pipeline v1.0.0
**Source root:** `/home/user/DataBoss/_synthetic_corpus`

> This summary is produced by a deterministic pipeline. Every fact traces to a
> source document. Rows marked **REVIEW REQUIRED** are NOT verified and must be
> confirmed by a title professional before use. No legal/title facts were
> invented.

## At a glance
| Metric | Value |
| --- | --- |
| Source documents inventoried | 9 |
| Documents with extractable text | 9 |
| Documents with structured facts | 8 |
| Structured fact records (rows) | 10 |
| Tracts / legal descriptions identified | 2 |
| Reconciliation conflicts / gaps | 2 |
| Validation issues (red / yellow) | 2 / 9 |

## Delivery risk (Monday, July 6 2026)
**YELLOW/RED** -- 2 hard conflict(s) and 9 review item(s); 9/9 documents yielded text. Resolve red items and OCR the untextable documents before delivery.

## Top items requiring review
| severity | rule | subject | detail |
| --- | --- | --- | --- |
| red | impossible-date | 07_bad_date.txt | recording_date=2099-12-31 is out of valid range |
| red | decimal-sum | SEC 12-T7N-R63W | Decimals sum to 0.95 (expected 1.0) |
| yellow | high-value-low-confidence | 02_oil_gas_lease.txt | royalty='3/16' confidence 0.55 |
| yellow | high-value-low-confidence | 03_assignment.txt | net_revenue_interest='78.5%' confidence 0.55 |
| yellow | missing-recording-data | 04_ownership_note.txt | No book/page/instrument and no recording date extracted |
| yellow | missing-recording-data | 06_prior_report_DRAFT.txt | No book/page/instrument and no recording date extracted |
| yellow | missing-recording-data | 08_ownership_schedule.csv | No book/page/instrument and no recording date extracted |
| yellow | missing-recording-data | 08_ownership_schedule.csv | No book/page/instrument and no recording date extracted |
| yellow | missing-recording-data | 08_ownership_schedule.csv | No book/page/instrument and no recording date extracted |
| yellow | chain-gap | SEC 12-T7N-R63W | Grantee 'Acme Minerals LLC' (2019-03-20) != next grantor 'Foo' (2099-12-31) |
| yellow | stale-prior-draft | 06_prior_report_DRAFT.txt | Prior report/draft present -- confirm every carried-forward fact against current source documents before trusting it. |