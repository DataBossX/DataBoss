# Section 27 — API & OCR Log

## OKCountyRecords.com API
- **Status: NOT USED.** No API key found in environment variables (`OKCOUNTYRECORDS_API_KEY`, `OKCR_API_KEY`) and no authorized local config present in this container. The prompt's `D:\DataBoss\...` workspace is a Windows path that does not exist in this Linux execution environment, and outbound network access is governed by an environment policy.
- **No searches, no image pulls, no paid downloads were performed.** No credentials were created, printed, logged, or written to any output.

## OCR / extraction pipeline (what ran)
1. `pdfinfo` — provided index = **27 pages**, 606×1002 pt, "Scanner System Image Conversion" (image-only, no embedded text).
2. `pdftoppm -r 175` — rendered all 27 pages to PNG (`records_ocr/pg-*.png`).
3. Pillow — rotated 90° CCW + autocontrast + split each page into left (grantor/grantee/kind) and right (acres/book/page/remarks) halves for legibility.
4. `tesseract 5.3.4` — attempted; **unreliable** on these handwritten/grid ledger pages (output garbled). Fell back to **visual reading** of the rendered halves (the dependable method for this document type).
5. Structured parse → `records_parsed/section27_index_parsed.csv` (81 entries) → `Instrument Index` tab.

## Coverage & confidence
- **Pages 12–16 (typed, modern leasehold layer): fully read & transcribed, HIGH confidence** — these hold the OGLs, assignment chain, and ORRI stack and were cross-checked against the report.
- **Pages 0–11 (handwritten older mineral/surface chain): reviewed at index level, LOW confidence** — not decimalized (cursory scope; mineral NMA left open).
- **Pages 17–26 (mineral/grantee continuation): sampled** — modern family mineral conveyances; no 2017–2026 corporate assignments appear in the index.

## Tools available in environment
Python 3.11, openpyxl, pandas, pypdf, pdfplumber, Pillow, tesseract-ocr, poppler-utils (pdftoppm/pdfinfo). Not used: requests/network to OKCR (no access).
