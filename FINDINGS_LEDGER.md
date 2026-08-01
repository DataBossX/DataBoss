# DataBossX — Findings Disposition Ledger

_Blocking regression-source record for PR #60. Companion to `CODE_REVIEW.md`._
_Cycle baseline: `main` @ 582d951 • Reviewer: Claude Code (independent, read-only)._

**Release state: FOR REVIEW — HOLD — NO EXTERNAL RELEASE.** No merge, deployment,
client execution, or hold removal is authorized from this record.

## Disposition rule
Every still-valid finding must reach exactly one terminal disposition before the
hold on it can be lifted by an authorized human:
- **FIX+TEST** — repaired with a focused regression test that fails before / passes after.
- **DISPROVEN** — shown not to be a defect, with evidence.
- **ACCEPT (bounded)** — accepted as a bounded risk, with the bound stated.
- **DEFER (stop-condition)** — deferred, with an explicit condition that re-opens it.

Documentation of a finding is **not** closure. Closure = one of the four above,
landed on the canonical integration path (#66 + #61) with source-finding provenance
(`CODE_REVIEW.md#F<n>`).

## Priority order (per directive)
1. Integrity findings that can emit an **unflagged wrong title fact** → F1, F2, F4, F8.
2. Authentication / CORS / publication-boundary → F3, F5, F9, F11, F13, F16.
3. Robustness / determinism / hygiene → the rest.

---

## Ledger

| ID | Sev | Source | Current disposition | Target | Regression test to author | Lands on |
|----|-----|--------|---------------------|--------|---------------------------|----------|
| **F1** | CRITICAL | `horizon/repair.py:65-71` | **FIX+TEST done** (#60 c/p → #61) | FIX+TEST ✓ | `test_review_fixes_f1_f2_f4.py::test_f1_errored_cell_stays_flagged_not_downgraded` — repaired `t="e"` cell keeps the error marker, not downgraded to a plain value. | #61 (repair/QA path) |
| **F2** | HIGH | `grocery_report_pipeline.py:903` | **FIX+TEST done** (#60 c/p → #61) | FIX+TEST ✓ | `::test_f2_no_recording_date_fabrication` — deed with only `Effective Date:` leaves `recording_date` blank AND fires `missing-recording-data`. | #61 |
| **F4** | MED/HIGH | `grocery_report_pipeline.py:823` | **FIX+TEST done** (#60 c/p → #61) | FIX+TEST ✓ | `::test_f4_two_digit_decimals_reconcile_without_false_conflict` — `0.5+0.5` no false conflict; `0.5+0.3` still caught. | #61 |
| **F8** | MED | `horizon/workbook_qa.py:139-141` | OPEN | FIX+TEST | `=IFERROR(VLOOKUP(...),"#N/A")` is classified valid (not `broken_formula`); a truly errored cell (`data_type=='e'`) still is. | #61 |
| **F3** | HIGH | `backend/server.py` (endpoints) | OPEN — verify vs #66 head | FIX+TEST or DISPROVEN | Unauthenticated `GET /api/documents/{id}` returns 401/403. Confirm whether #66's API-security layer already covers the legacy backend. | #66 |
| **F5** | MED/HIGH | `backend/server.py:40-46` | **FIXED on #66** (CORS allowlist; wildcard disables credentials) | verify + close | Cross-origin credentialed request from a non-allowlisted origin is rejected. | #66 (done) |
| **F6** | MED | `horizon/repair.py:55` | OPEN | FIX+TEST | Worksheet with an error-formula + a malformed region: row/cell count is preserved (no silent drop) or repair refuses and escalates. | #61 |
| **F7** | MED | `horizon/report_io.py:69` | OPEN | FIX+TEST | Source workbook with an extra sheet but no `xl/media` → extra sheet survives in the emitted `_vNNN`. | #61 |
| **F9** | MED | `Dockerfile:9-10` | OPEN | FIX+TEST | Build log / `docker history` does not contain `.env` values (remove `RUN cat`). CI grep asserts absence. | #66 |
| **F10** | MED | `grocery_report_pipeline.py:723-725` | OPEN | FIX+TEST | Two byte-identical dupes with the same basename in different folders → both quarantined to distinct paths (no overwrite). | #61 |
| **F11** | MED | `doto_image_commander/core/database.py:196-198` | OPEN | FIX or ACCEPT (bounded) | `insert_many` with a table not in the whitelist raises; columns validated. If no untrusted caller exists, ACCEPT with that bound stated. | #66 |
| **F12** | LOW/MED | `backend/server.py:270-277` | OPEN | FIX+TEST | Oversized upload rejected before full read; disallowed content-type rejected. | #66 |
| **F13** | LOW | `.env.example:5` | OPEN | FIX | Template ships `MOCK_AUTH=false`. | #66 |
| **F14** | LOW | `horizon/foundation.py` (scan/fidelity/dedupe) | OPEN | FIX+TEST | Same corpus, two hosts / walk orders → identical keeper + receipt (sort by `rel`; `rel` as final tiebreak). | #61 |
| **F15** | LOW | `grocery_report_pipeline.py:828` | OPEN | FIX+TEST or ACCEPT | Doc containing bare "OK" does not yield a `state` at ≥0.6 unflagged. | #61 |
| **F16** | LOW | `backend/server.py:195,245,312` | OPEN | FIX | 500 responses return a generic message; detail only in server logs. | #66 |
| **F17** | LOW | `requirements.txt` (dup pins) | OPEN | FIX | One pin per package (pydantic/fastapi/uvicorn/requests/python-dotenv). | main / either |
| **F18** | LOW | `grocery_report_pipeline.py:255,817,970` | OPEN | ACCEPT or FIX | Dead code removed; no behavior change. | #61 |

---

## Cross-PR notes
- **F5 is already resolved on #66** — do not re-fix; verify against #66 head and close with provenance.
- **F3/F9/F11–F13/F16** land naturally on **#66** (it owns `backend/`, `Dockerfile`, `doto_image_commander/`).
- **F1/F2/F4/F6–F8/F10/F14/F15/F18** land on **#61** (repair/QA/pipeline path). None of these files are under active edit by #66 or #61 as of their current heads, so they can be authored without a one-writer collision — but the final commit must be placed by the branch's owning writer.
- **One-writer rule:** this reviewer does not push to #66/#61 directly (both are actively written). Bounded repairs + tests are authored as provenance-tagged, cherry-pickable commits and handed to the integrator, unless the owner directs otherwise.

## Stop conditions for the hold
The hold on any finding lifts only when: (a) its row shows FIX+TEST / DISPROVEN /
ACCEPT / DEFER, (b) the change is on the canonical path with `CODE_REVIEW.md#F<n>`
provenance, and (c) an authorized human approves. No automated actor lifts a hold.
