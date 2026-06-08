# NEEDS APPROVAL TO DOWNLOAD RECORDS — Section 27-11N-25W, Beckham Co., OK

**Status (updated 2026-06-08): Key + `APPROVE_OKCR_DOWNLOADS=true` RECEIVED, but downloads are BLOCKED by the environment network allowlist** (okcountyrecords.com returns HTTP 403 from the sandbox egress proxy; pypi/github reachable). No paid records were retrieved. Run `scripts/okcr_pull.py` where the host is reachable to execute the pulls below.

## Why this file exists
The research that would *close* the high-priority title gaps requires pulling imaged instruments from **OKCountyRecords.com (paid)**. In this execution environment:
- No API key is present (`OKCOUNTYRECORDS_API_KEY` / `OKCR_API_KEY` unset).
- No authorized local config / `D:\DataBoss\...` workspace exists (Linux container; the path is Windows-only).
- No `APPROVE_OKCR_DOWNLOADS=true` flag was provided.
- Outbound network access is governed by the environment's policy.

Per instructions, I **stopped before paid downloads** and produced this approval manifest.

## Records proposed for download (ranked)
See `SECTION_27_RECORD_DOWNLOAD_MANIFEST.xlsx` for the full table. Summary:

### Priority 1 — required to verify the carried Diversified chain & depth
| Instrument | Book/Page | Type | Why needed |
|---|---|---|---|
| 2017-004597 | 2266/194 | Assignment | Track A first recorded step into Sec 27 |
| 2019-002937 | 2307/894 | Partial Assignment | EnerVest leasehold (Mandrell 2-27 / Betty Sites 1-27) |
| 2019-002988 | 2308/123 | Partial Assignment | Track A continuation |
| 2020-004390 | 2340/218 | Name Change | FourPoint → Unbridled continuity |
| 2025-001808 | 2451/4 | Merger | Succession to Diversified (need Sec-27 asset schedule) |
| 2026-001031 | 2480/824 | Affidavit/Support | Support of successor path |
| 2001-008828 | 1719/304 | Partial Release | Proves depth limit below ~17,960' strat equiv |

### Priority 2 — Track B reconciliation & wellbore scope
2023-000993 / 2401/214 (Teocalli wellbore Exhibit A); 2020-004435 / 2340/403; 2020-004462 / 2340/490; and the DP Legacy/DP Sooner series (2389/581; 2393/1; 2395/415; 2400/551).

### Priority 3 — per-tract NMA & NRI
ORRI assignments (1626/104; 1636/188-190; 1641/318-339; 1663/497) and mineral deeds / probate / affidavits for per-lessor net mineral acres.

## Cost estimate
Approx. **~70–90 imaged pages** across Priority 1–2 at OKCR per-image pricing. **Exact page counts and fees must be pulled from the OKCR search API result headers before any download** (dry-run first). No blanket downloading of search results.

## To proceed
Provide an OKCR API key via environment variable **and** set `APPROVE_OKCR_DOWNLOADS=true`. I will then dry-run a cost estimate, download lowest-cost OCR-usable images for Priority 1 first, OCR/parse them, update the chain, and refresh this manifest with actual costs and "Downloaded? = YES".
