# SECTION 31-12N-24W — TITLE EXAMINATION STATUS & GAP ANALYSIS

**Prospect:** 26-005 • **County:** Roger Mills, Oklahoma • **Scope:** Cursory covering all interest
**Session date:** 2026-07-11 • **Branch:** `claude/section-31-title-exam-gavidf`

---

## 1. Bottom line

**The Section 31-12N-24W base workbook and its source records are not present in any
location this cloud session can reach.** No chain-of-title work, tract-sheet QA, WI
reconciliation, or gap-closing county search can be performed without them, and this
report refuses to invent title facts. Everything that *could* be verified is logged
below; the exact upload list needed to unblock the exam is in §5.

## 2. What was searched (complete log)

### Repository (`DataBossX/DataBoss`)
- Full recursive scan: **zero** spreadsheets, runsheets, PDFs, or title documents
  (consistent with PROJECT_STATUS.md finding — this is a code repo, not a document store).
- `automation/roger_mills_title_report_builder.py` — confirmed to be the *builder tool*
  for this exact job (default `--section 31-12N-24W`, output name
  `31-12N-24W_Roger_Mills_Cursory_Title_Report_(6-27-2026)codexv1.xlsx`). It contains
  **no embedded title data**; it expects to run locally against
  `D:\Desktop\Horizon\Roger Mills`.
- Horizon pipeline (`horizon/`), grocery pipeline, doto_image_commander: machinery only.
- Git: designated remote branch no longer exists on origin; no prior Section 31 commits
  on any branch.

### Google Drive (ryangille02@aol.com) — exhaustive, folder by folder
| Folder | Contents | Section 31 material? |
| --- | --- | --- |
| `horizon/` | Template.xlsx (25-004, 27-15N-24W format), NHE Invoice 7-16-2026, two Beckham 32-11N-25W reports, Diversified workfile, `11N 25W 32.zip` (3 GB images) | **No** |
| `horizon/32-11N-25W Diversified Cursory…/00–09` | Full Beckham job staging (images 0001–4893, Index, Section Notes, Plat, Tax Roll, OCR, chains, QA, delivery) | **No** |
| `penterra/` | Campbell/Johnson Co. Wyoming abstract indexes, project notes | **No** |
| `DataBossX/` | Empty | **No** |
| OCC evidence folder | Beckham/Crook well transfer PDFs, OCC order 156126 (Beckham) | **No** |

Queries run: title/fullText on `Section 31`, `31-12N-24W`, `12N-24W`, `12N 24W`,
`26-005`, `Roger Mills`, `runsheet`, `OGL`, `cursory`, `tract`, all zip archives, all
folders (paginated to end). The **only** Section 31 references anywhere in Drive are in
the NHE invoice (5 days billed 7/1–7/7, "Cursory covering all interest in 31-12N-24W,"
$100 OKCountyRecords views expense).

### Email
- Gmail MCP: **mail service not enabled** for this account (AOL address) — not searchable.

### External record sources (network policy of this environment)
- `okcountyrecords.com` (Roger Mills index) — **blocked** (proxy CONNECT 403).
- `glorecords.blm.gov` (patents) — **blocked**.
- OCC case/order image endpoints — **blocked**.
- WebSearch (snippets only) — works; results in §4.

## 3. What WAS found (usable assets)

1. **Formatting authority:** `Template.xlsx` in Drive `horizon/` — the 25-004
   (27-15N-24W) cursory with the required 13-sheet layout:
   `Overview, Title, OGL, PLAT, Runsheet, Tract 1–5, WI 2, WI 1, Well 1`.
   A verified local copy of this workbook was pulled and inspected this session.
2. **Job scope proof:** NHE Invoice 7-16-2026 (prospect 26-005, OKCountyRecords used).
3. **Merge machinery:** `automation/roger_mills_title_report_builder.py` — inventories,
   backs up, scores every prior report version, merges all versions with conflict audit,
   verifies rows against the index PDF, and writes into the template with formatting
   preserved. Ready to run where the files live.
4. **Disclosure pattern:** the Beckham 32-11N-25W reports demonstrate the required
   discipline (OPEN ITEM entries, no forced totals, no unsupported decimals).

## 4. Public-web reconnaissance (leads only — NOT title facts)

- Red Rocks Oil & Gas Operating LLC is the active recent operator in 12N-24W
  (Bryan 1-19 in Sec 19-12N-24W; Morris 1-6 in Sec 6-12N-24W) —
  mineralanswers.com / shalexp.com snippets.
- A 2025 Pinson Land Services AFE exists for 8-12N-24W (mineralhub.com), confirming
  renewed leasing/drilling in the township.
- No Section-31-specific well, permit, or pooling order surfaced in any snippet.
- These are research leads for operator/WI chains only; none may be entered in the
  workbook without the recorded instruments.

## 5. To unblock the examination (upload list)

Stage the Section 31 job into Drive exactly like the Beckham job was staged:

1. **Every prior report version**, incl.
   `31-12N-24W_Roger_Mills_Cursory_Title_Report_(6-27-2026)codexv1.xlsx` and any
   older/newer versions from `D:\Desktop\Horizon\Roger Mills`.
2. **The runsheet workbook(s)** for 31-12N-24W.
3. **The county index export / index PDF** for 31-12N-24W (OKCountyRecords pulls).
4. **Document images** (a `12N 24W 31.zip` equivalent of the purchased views).
5. **Plat, section notes, tax roll**, and any OGL workbook for prospect 26-005.
6. Any probate files, OCC orders, and correspondence touching Section 31.

Alternatively: run `automation/roger_mills_title_report_builder.py` locally (command in
its docstring) and upload its output + support files for cloud QA.

## 6. QA checklist held ready (applies as soon as data arrives)

- Chain every tract from patent forward; each conveyance subtracts from grantor and
  adds to grantee, with exact and remaining interests shown.
- Every deceased owner: probate / AOH / decree search, else disclosed Oklahoma
  assumption — never an invented fact.
- Every WI owner reconciled to the lease-assignment chain; every operator merger or
  name change supported by an instrument.
- OGL numbers cross-checked owner-by-owner; tract totals reconcile to gross acres;
  Title ↔ Tract ↔ WI ↔ Runsheet ↔ OGL agreement everywhere.
- Workbook format preserved exactly (no added/deleted sheets, no formatting or print
  changes, no AI comments).
