# Section 27 — QA Report

**Output workbook:** `11N_25W_27_Beckham_Co_Diversified_Cursory_Report_FULLY_UPDATED.xlsx` (19 tabs)

| Check | Result | Evidence |
|---|---|---|
| Workbook loads (openpyxl) | PASS | Loads, 19 sheets |
| Formula-error literals (REF/VALUE/DIV0/NAME/NA) | PASS | 0 found in scan |
| Section gross = 640 ac | PASS | Overview + tract table |
| Tracts sum to 640 | PASS | 160+160+160+159+1 |
| WI reconciles to 1.000000000 | PASS | 0.700520833 + 0.299479167 = 1.0 |
| Apparent Diversified ties to 448.333333 NMA | PASS | 0.700520833×640 |
| Residual ties to 191.666667 NMA | PASS | 0.299479167×640 |
| WI predecessor steps net to 0 | PASS | cols H/I/J/K/L each = 0 |
| OGL layer verified vs county index | PASS | French Energy/Arrowhead/Todco/Sanguine book-pages all matched |
| 2017–2026 corporate assignments verified | N/A | Not in index; no OKCR API; flagged Gap #2 |
| NRI booked | OMITTED (by design) | UNRESOLVED/ESTIMATE-ONLY |
| Per-lessor/per-tract NMA | OPEN | "Unknown" — not derivable |
| Every carried interest has source/assumption | PASS | WI + Assumptions + Source/Instrument Index |
| No API key/secret in any output | PASS | none present |
| High-impact gaps listed | PASS | 12 items (4H/5M/3L) |

**Blunt confidence: MEDIUM** for a cursory leasehold reconstruction. Strong on the verified OGL/depth layer; weak on WI quantum, corporate succession, and NRI. **Not** acquisition/division-order grade.
