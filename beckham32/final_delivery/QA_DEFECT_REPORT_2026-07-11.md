# QA Defect Report — FINAL_VERIFIED_2026-07-11 (v2) independent examiner QA

**Run date:** 2026-07-11 (second independent QA pass, this session)
**Subject:** `32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_FINAL_VERIFIED_2026-07-11.xlsx`
**Subject SHA-256 (verified against delivery note):** `1d8b4a67c540ba41a6340530d9b17bae4e4c4c840de0e552daa2268ef3265b02` (660,580 bytes)
**Engine:** independent structural + content scans (this repo, `databossx/workbook_qa.py` family checks, run against the binary extracted from git)

## Checks that PASSED as claimed

| Check | Result |
|---|---|
| Sheet names/order (13, template order) | PASS |
| PLAT hidden state preserved | PASS |
| External links | 0 — PASS |
| Formula errors / formulas | 0 / 0 (values-only by design) — PASS |
| Negative numeric constants | 0 — PASS |
| Stale-project residue (448.333333, 377.53845154, 2237/381, 2572/490, 2610/574, 27-15N-24W, Roger Mills, White Sail, Greenhead) | 0 hits — PASS. The 4 "Presidio" text hits are the intentional Presidio WAB separate-chain disclosure (Runsheet row 98), not residue. |
| Media parts (plat/parcel images) | 3 present — PASS |
| Runsheet population | 102 data rows + header — matches note |

## DEFECT 1 (mechanical): broken defined names present despite claimed purge

The delivery notes state "21 broken #REF! defined names purged" / "Broken defined
names: 21 purged." The delivered v2 binary contains **22 defined names**: 21
resolving to `#REF!` (`_Fill, _Key1, _Sort, Check1_1..Check7_1, check5,
oijjjojoijpojpoi, Plat_LastSaved, SORT, Test, Test1..Test4, Tract, XXXXXX`)
plus stale `_Order1=255`. This is the exact defect set AUDIT_1 flagged in the
NHE base. The purge did not reach this build.

**Disposition:** purged in staged v2.1 (workbook.xml `<definedNames>` block
removed surgically; no other part touched).

## DEFECT 2 (material regression): two OPEN instruments omitted vs v1

FINAL_READINESS_STATEMENT (v1) records that examiner-identified **1536/368**
and **2393/1** were added as OPEN, metadata-unverified pull items (Runsheet
rows 49–50). Neither token appears anywhere in the delivered v2 binary (text
or numeric scan of all 13 sheets). `2393/1-698` (I-2022-004277) is the 698-page
ConocoPhillips/Louisiana Land/Burlington → DP Legacy Central assignment that
AUDIT_3 classifies as plainly material. v2's register-completeness proof
cross-referenced the 19-sheet working register — these two records appear in
no register (per the readiness statement itself), which is exactly why the
proof could not catch their absence.

**Disposition:** restored in staged v2.1 as Runsheet rows 104–105, populated
into the existing styled empty rows, clearly labeled
"RESTORED OPEN ITEM 2026-07-11" with AUDIT_3-sourced metadata and OPEN
evidence tiers. No conclusions added — both remain pull items.

## Staged corrected candidate (NOT promoted)

`32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_FINAL_VERIFIED_v2.1_STAGED_2026-07-11.xlsx`
**SHA-256:** `75b10fa70e835d46d3b392a954a3d57ea66d9393dbc4b835178bb62dd4398e60` (660,701 bytes)

Method: byte-level zip surgery only — `xl/workbook.xml` definedNames block
removed; Runsheet rows 104–105 populated in `xl/worksheets/sheet5.xml`
preserving existing cell styles. Every other package part is byte-identical to
v2 (media 3/3, PLAT hidden, print settings untouched). A first staging attempt
via openpyxl re-save was **rejected** because it silently dropped all 3
embedded images (regression-check discipline).

Full re-verification of v2.1: sheet order PASS, defined names 0, external
links 0, formula errors 0, negatives 0, stale residue 0, required tokens
(incl. 2393/1-698 and 1536/368) present, media 3/3.

Promotion of v2.1 over v2 is left to the controlled promotion process; open it
interactively in Excel and re-inspect print previews before client issuance.
