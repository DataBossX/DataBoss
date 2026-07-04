# Acceptance verification — Cursory Title App (Section 31-12N-24W)

Run live against the real workbook `31-...Roger_Mills_Cursory_Title_Report`.
Reproduce: `PYTHONPATH=. python -m cursory_title_app.close_section31 --report <workbook>`

## In-environment checks — 14 / 14 PASSED
| Check | Result | Evidence |
|---|---|---|
| Opens target Section 31 workbook | PASS | 18 sheets loaded |
| Identifies tabs / adds none | PASS | exactly the 18 expected tabs |
| Saves a NEW workbook copy | PASS | `...(6-25-2026).xlsx` written |
| Saved workbook opens without repair | PASS | openpyxl re-load clean |
| Sheet names unchanged | PASS | source == output tab list |
| O–S formulas preserved (not broken) | PASS | all formula cells intact |
| No #REF/#VALUE/#NAME introduced | PASS | zero error tokens |
| Repairs Document Links | PASS | 7 plain-text links → HYPERLINK |
| Flags uncertainty in Review column | PASS | 3 effective>recorded QC flags |
| Produces local QA summary | PASS | 25 audit findings |
| Independent chain reconstruction | PASS | 45 defects; all 8 tracts rooted |
| Entity-resolved ownership gap | PASS | 557.35 ac missing from Title summary |
| Consolidated HTML report generated | PASS | `Section31_Title_Report_(6-25-2026).html` |
| Chain-of-title workbook generated | PASS | `Section31_Chain_of_Title_(6-25-2026).xlsx` |

Plus the unit test suite: **10 passed** (formula-column protection, entity
resolution, legal authorities OK-only, reimport append with live formulas,
round-trip preservation, etc.).

## Blocked by network egress (runs on the user's machine)
These are not failures — the hosts are hard-blocked from the cloud prep
container (verified HTTP 403 CONNECT tunnel failed) and there is no bridge to the
user's local browser. All tooling is built, compiled, and dry-run-verified.
- Open OKCountyRecords document link / pull instruments (okcounty API).
- Vision field extraction (needs the user's ANTHROPIC/OPENAI key).
- OCC/OTC well + production capture (browser portals, user's session).

Close-out path: `docs/RUN_ON_YOUR_MACHINE.md`.
