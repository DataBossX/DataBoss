# Section 27 — API & OCR Log

## OKCountyRecords.com API — attempted 2026-06-08
- **API key supplied by user; `APPROVE_OKCR_DOWNLOADS=true` set.** Key held only in a session env var — **never printed, logged, written to any file, or committed.**
- **Egress BLOCKED by the environment network policy.** Reachability test:
  - `pypi.org` 200, `github.com` 200, `api.github.com` 200  (allowlisted)
  - `okcountyrecords.com` **403**, `example.com` **403**  (not on allowlist)
  - The 403 is an empty `HTTP/2 ... text/plain` response from the sandbox egress proxy (no origin/Cloudflare headers, empty body) — i.e., the host is not permitted, regardless of credentials.
- **Result: no records could be searched or downloaded from this container.** Per policy, no attempt was made to tunnel/scrape around the block.
- **Delivered instead:** `scripts/okcr_pull.py` — a complete, idempotent pull pipeline that reads the key from `OKCR_API_KEY`, runs a **dry-run cost estimate** (search result/page counts), then downloads the Priority-1 instruments (2266/194, 2307/894, 2308/123, 2340/218, 2451/4, 2480/824, 1719/304, 2401/214), honoring `APPROVE_OKCR_DOWNLOADS`. **Run it on a machine/network where okcountyrecords.com is reachable**, then re-run `build_final.py` to fold the results in. `.env.example` provided (no secrets).

## OCR / extraction pipeline (what ran here)
1. `pdfinfo` — provided index = **27 pages**, image-only (no embedded text).
2. `pdftoppm -r 175` — rendered all 27 pages to PNG.
3. Pillow — rotate 90° CCW + autocontrast + split into left/right halves for legibility.
4. `tesseract 5.3.4` — attempted; unreliable on handwritten/grid ledgers → fell back to **visual reading** of the rendered halves.
5. Structured parse → `records_parsed/section27_index_parsed.csv` (81 entries) → `Instrument Index` tab.

## Coverage & confidence
- **Pages 12–16 (typed leasehold layer): fully read, HIGH confidence** — OGLs, assignment chain, ORRI stack; cross-checked against the report and **matched**.
- **Pages 0–11 (handwritten older chain): index-level review, LOW confidence** — not decimalized (cursory scope).
- **Pages 17–26 (mineral/grantee continuation): sampled** — no 2017–2026 corporate assignments appear in the index.

## Tools available
Python 3.11, openpyxl, pandas, pypdf, pdfplumber, Pillow, requests, tesseract-ocr, poppler-utils. Network to okcountyrecords.com: **blocked**.
