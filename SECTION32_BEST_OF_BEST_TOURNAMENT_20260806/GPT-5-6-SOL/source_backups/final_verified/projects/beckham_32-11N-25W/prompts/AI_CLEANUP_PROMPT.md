# AI Cleanup Prompt — Section 32-11N-25W Diversified Cursory Title Report

## Recommended AI
**Claude Opus 4.6 / Sonnet 4.6 with extended thinking** or **GPT-5.3 Codex** — best for multi-sheet Excel title work requiring legal precision, chain reconciliation, and structured data entry without hallucinating decimals.

## Master Prompt (paste as system + user context)

```
You are a senior Oklahoma oil-and-gas title examiner completing a CURSORY title report for Diversified-affiliated interests in Section 32, Township 11 North, Range 25 West, Beckham County, Oklahoma.

INPUT FILES (attach all):
1. FINAL/32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_MERGED_BEST_2026-07-10.xlsx (working draft)
2. FINAL/Template.xlsx (format/structure reference only — content is from a different section)
3. Cursor_Working_2026-07-10/aid_evidence_register.txt (authoritative evidence register)
4. Cursor_Working_2026-07-10/aid_prior_report.txt (prior narrative)
5. source_canonical/Section Notes/Section Notes.xlsx (index certification: through 07/01/2026, last entry 2490/471)
6. Diversified_Title_Evidence_Register_32-11N-25W_2026-07-09.xlsx if available

NON-NEGOTIABLE RULES:
- NEVER invent WI, NRI, net acres, royalty decimals, or current owner where schedules are absent.
- Use "OPEN ITEM" for unresolved ownership/effect; use confidence % where conclusions are qualified.
- Distinguish: direct image reviewed | index-only | public metadata | regulatory context only.
- Bk 2395/P967 = UCC termination; Bk 2395/P415 = Diversified ABS conveyance.
- Full-section Q-Q ticks ≠ 100% of any estate.
- Cherokee formation limitation in template does NOT apply — this is a Diversified leasehold/WI cursory.

OUTPUT: Updated Excel workbook matching Template sheet names and general layout, populated with Section 32 Beckham County data only.
```

---

## Phase 1 — Structure & Overview (do first; ~15 min)
**Goal:** Lock header metadata and legal scope.

**Tasks:**
1. Open merged workbook + Template Overview side-by-side.
2. Verify: Section 32, T11N, R25W, Beckham County, OK, 640 ac nominal.
3. Populate attachment date fields: Cursory Report 2026-07-10, County Cert 2026-07-01, Last Entry Bk 2490/P471.
4. Keep CONTROLLING CONCLUSION, SCOPE/CUTOFFS, PRIORITY COPY PULL in REMARKS area (B53-B55).
5. Label all 5 tracts on plat overview cells per actual subject tracts (Crook, Pearl, N/2 Hunton, deep leasehold, Diversified branch).
6. Do NOT proceed to decimals in this phase.

**Deliverable:** Overview sheet saved; no other sheets modified.

---

## Phase 2 — Runsheet completion (~30 min)
**Goal:** Complete chronological chain through Diversified.

**Tasks:**
1. Start from patent/receiver receipts (rows 1-4).
2. Enter all pre-1988 direct-image instruments (Bk 502/267, 509/220, 509/176, 502/265, 839/188, 845/47, 872/279, 903/50, 987/159, 995/52, 1014/75) with execution, recording, grantor, grantee, legal, comments.
3. Add every post-1988 index entry from Chain_Post1988 in evidence register (rows 16-45+).
4. Flag each row: DIRECT IMAGE | INDEX ONLY | METADATA.
5. Add recording dates from index where missing (many currently "OPEN — read stamp").
6. Add row for Bk 1014/76, 1014/228 explicitly.
7. End with 2476/121 Agreement and note 2476/1 Canvas→DP Ponies separately.
8. Target: 80+ substantive rows (template has 143; many are different-section filler).

**Deliverable:** Runsheet complete through 2026; no tract matrices yet.

---

## Phase 3 — OGL & Lease schedule (~25 min)
**Goal:** Populate OGL tab from Leases sheet in evidence register.

**Tasks:**
1. For each lease (Bk 63/33, 264/345, 307/31, 340/302, 340/304, 340/323, 342/564, 342/566, 352/719, 352/721, 376/369):
   - Lessor, lessee, date, legal, royalty if known, status (OPEN for term/HBP).
2. Cross-link OGL numbers to Tract sheets and Title sheet.
3. Note depth/wellbore limits from later assignments.
4. Mark HBP as OPEN unless lease-to-well proof exists.

**Deliverable:** OGL sheet populated; linked OGL Nos. in Title sheet column D.

---

## Phase 4 — Tract matrices 1-5 (~45 min, one tract at a time)
**Goal:** Fill instrument columns in Tract 1-5 per template grid format.

**Per tract workflow:**
1. Read existing Tract N sheet in merged file (from Report1 base).
2. For each instrument column: Image #, Book/Page, Date, Grantor, Grantee, Conveyance type, reservations.
3. Mark Evidence Tier row: DIRECT IMAGE REVIEWED vs OPEN ITEM.
4. Do NOT fill decimal ownership rows without source.
5. Present owner row = OPEN ITEM until post-1988 bridge complete.

**Tract definitions:**
- Tract 1: NE/4; Crook #1-32; Morrow-Springer 16,210-20,451 ft
- Tract 2: E/2 SE/4; Pearl #1-32; 11,100-19,480 ft
- Tract 3: N/2 Sec 32 below top Hunton (320 ac nominal)
- Tract 4: Deep leasehold references (872/279 lease list)
- Tract 5: Full-section Diversified branch (index/metadata only for post-1988)

**Deliverable:** All 5 tract sheets with instrument columns through 1014/75 direct; post-1988 as INDEX ONLY columns.

---

## Phase 5 — Title summary & WI sheets (~30 min)
**Goal:** Title sheet = executive ownership summary; WI sheets = participant tables.

**Title sheet:**
- Keep Interest Holder / Category format (appropriate for cursory).
- Per tract: historical participants, burdens, current Diversified status OPEN.
- REPORT TOTAL = "Totals not forced — chain incomplete" unless evidence supports.

**WI 1 / WI 2:**
- Populate historical Crook participants from Bk 509/220 (Mesa 64%, Petrofina 25%, etc.).
- Mark payout/reversion as OPEN.
- Add Diversified row as OPEN ITEM with index refs 2371/470, 2395/415, 2400/551.

---

## Phase 6 — Wells, PLAT, QA (~20 min)
**Goal:** Regulatory context and quality pass.

**Well 1:**
- All 11 Section 32 APIs from evidence register.
- Status, operator, formation, spud; mark Diversified title inference = NONE.

**PLAT:**
- Ensure tract labels match Overview; add north arrow/section sketch references if images available.

**QA checklist:**
- [ ] Every Direct_Diversified instrument from evidence register appears in Runsheet + Tract 5
- [ ] No false decimals
- [ ] 2395/967 not treated as conveyance
- [ ] Assumptions sheet current
- [ ] Examiner field filled
- [ ] All OPEN ITEMs have specific curative action

---

## Phase 7 — Final opinion language (~15 min)
Add to Overview REMARKS or new Title Opinion cell:
- Qualified acquisition conclusion (C1)
- Principal chain (C2)
- Critical open requirements 1-12 from evidence register
- Explicit assumptions A1-A10

---

## What the AI must NOT do
- Fabricate recording dates, grantee fractions, or net acres
- Treat memoranda (2371/533) as conveyances
- Conflate FourPoint and Tapstone branches without schedule review
- Use template Roger Mills / 27-15N-24W data
- Force REPORT TOTAL numbers

## Success criteria
A reviewer can trace every Diversified-indexed instrument from patent → 2476/121, see what was directly reviewed vs index-only, and get a prioritized copy-pull list without encountering unsupported ownership decimals.
