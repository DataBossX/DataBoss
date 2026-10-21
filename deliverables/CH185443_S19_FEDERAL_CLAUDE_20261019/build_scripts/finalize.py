#!/usr/bin/env python3
import os,sys,json,csv,hashlib,zipfile,subprocess,glob
from datetime import datetime,timezone
OUT=sys.argv[1]; NOW=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

pages=list(csv.DictReader(open(f"{OUT}/Page_Review_Ledger.csv")))
props=list(csv.DictReader(open(f"{OUT}/Proposed_Changes.csv")))
evs  =list(csv.DictReader(open(f"{OUT}/Instrument_Event_Ledger.csv")))
blk  =list(csv.DictReader(open(f"{OUT}/Missing_Source_and_Conflict_Register.csv")))
reviewed=sum(1 for r in pages if r['visual_status']!='NOT_REVIEWABLE_IN_THIS_ENVIRONMENT')
assigned=[r for r in pages if 'assigned' in r.get('source_id','') or r['source_id'].startswith(('F131225','F133620'))]

STATUS=f"""# Claude - Section 19 federal source examiner - completion status

**Run date (preparation date): 2026-10-19. Research cutoff: Unknown. Currentness: Unknown.**
Worker: Claude, model `claude-opus-5`, Claude Code cloud session (Linux container).
Started 2026-10-19 (UTC). Completed {NOW}.

## Standing caveat on this assignment

The October 19 dispatch defines **eleven** run folders, each with a `START_HERE_FINISH_20261019.md`
naming a single exclusive writer: ChatGPT, Gemini, Grok, Kimi, Qwen, DeepSeek, Copilot, Meta/Llama,
Cursor/local, Vibe/Mistral, Independent comparison. **None is Claude**, and a sibling planning file in
the same tree is named `FINISH_PROMPTS_NO_CODEX_NO_CLAUDE.md`. `00_MASTER_PARALLEL_CONTROL_20261019.md`
states `DISPATCH MATERIAL PREPARED, EXTERNAL AI JOBS NOT LAUNCHED, APPROVAL NOT OBTAINED`, that the
dispatch folder alone "does NOT launch Gemini, Claude, Grok, Mistral, Kimi, Cursor, Adobe, Codex or any
other AI", and that **"Existing Codex Root is the only sanctioned production writer."**

Accordingly this run took **no** existing worker folder, wrote into a new Claude-owned folder only, and
treated every shared input as read-only. **Nothing here is promoted, integrated, or canonical.** Scope was
confirmed with the user as Section 19 only, per the control document's statement that Section 19 is the
only current final-package priority.

## What was actually completed

1. Read in full, from original sources: the WYW131225 Part 4 jacket, the WYW133620 Part 4 jacket, the
   WYW094605 Part 4 jacket, Serial Register Page WYW-131225 (6 pp.), Serial Register Page WYW-133620
   (7 pp.), and the Section 19 source excerpt containing CA WYW136880, its 2015 BLM correction letter,
   Exhibit A plat, Exhibit B and recapitulation, and the 2019 successor-operator letter.
2. Built a bounded Section 19 federal **event inventory of {len(evs)} events** across WYW-131225 and
   WYW-133620, separating each instrument from its section applications and keeping execution, receipt,
   approval, effective and recording dates in distinct roles.
3. Raised **{len(props)} source-backed proposals**, each with quoted evidence (`Proposed_Changes.csv`).
   All are `PROPOSED_PENDING_ADJUDICATION`. None is applied to any package.
4. Gave **all {len(pages)} federal physical pages an explicit disposition** (`Page_Review_Ledger.csv`),
   including the {len(pages)-reviewed} that are not reviewable in this environment. No page is left blank.
5. Produced an **isolated proposal workbook** in the federal ten-column schema, as native .xlsx, native
   .ods and a native .pdf export, verified for values, row order, typography, pagination and clipping.
6. Recorded **{len(blk)} concrete open blockers** with the exact missing item and next owner.

## Independently verified denominators

Recomputed from `Original_Sources_15_Source_Register_20261019.csv`; every figure reconciles with the
accepted baseline's stated measures:

| Measure | Recomputed | Baseline | Agrees |
|---|---|---|---|
| Total pages, 15 original PDFs | 1,332 | 1,332 | yes |
| Federal pages (10 PDFs) | 1,315 | 1,315 | yes |
| County pages (5 PDFs) | 17 | 17 | yes |
| WYW-131225, Parts 1-4 | 217+151+115+2 = 485 | 485 | yes |
| WYW-133620, Parts 1-4 | 190+164+261+2 = 617 | 617 | yes |
| Prior fresh visual pages, federal | 48 | 48 | yes |
| Prior fresh visual pages, county | 17 | 17 | yes |
| Prior fresh visual pages, total | 65 | 65 | yes |

CA WYW136880 arithmetic independently verified from the source: 38.51 + 74.11 + 80.84 = 193.46 corrected
and 38.51 + 80.19 + 80.84 = 199.54 original; 74.11/193.46 = 38.3077%, 38.51/193.46 = 19.9059%,
80.84/193.46 = 41.7864%, summing to 100.0000%. Corrected federal acreage 112.62 = 38.51 + 74.11.
The SRP recapitulation independently carries WYW136880 tract 02 at 74.1100 acres and 38.307700%.

## Status percentages, with explicit denominators

- **Federal pages with an explicit recorded disposition: {len(pages)}/{len(pages)} = 100.000%.**
- Federal pages actually read from source text in this run: {reviewed}/{len(pages)} = {100*reviewed/len(pages):.3f}%.
- Pages read within the two assigned cases: 4/1,102 = 0.363% (WYW-131225 485 + WYW-133620 617).
- Source files readable in this environment: 6 of 14 attempted = 42.857%
  (3 of the 10 register federal PDFs = 30.000%; all three readable ones are the 2-page jackets).
- Proposals accepted: 0/{len(props)} = 0.000%. Acceptance belongs to the adjudicator, not to this run.
- Open blockers: {len(blk)}. Release gates passed: 0 of 8. All remain qualified.

These percentages are coverage measures. **They are not correctness, not completion, and not currentness.**

## OCR navigation index (follow-up finding)

`FEDERAL_NAVIGATION_OCR_ONLY.json` lists **1,098 of the 1,315** federal pages (WYW-131225 Parts 1-3 = 483,
WYW-133620 Parts 1-3 = 615). It is a **locator, not evidence**: per page it holds keyword flags and an offline
Windows path, never page text. 880 pages carry at least one flag and 218 carry none.

- **WYW-094605 Part 1 (211 pages) is not in the index at all.** That part holds the CA WYW136880 agreement
  (p.82) and approval (p.81), so blocker B03 cannot be resolved without it (new blocker B10).
- The vocabulary has 10 terms. It includes `section7` and `section18` but **no `section19`**, so it cannot locate
  Section 19 pages, and its broadest flags (`depth` 470 pages, `approval` 415) narrow nothing (new blocker B11).
- Pages never read stay `NOT_REVIEWABLE`; the ledger now records, per page, whether OCR text is listed in the
  index (1,098) or merely claimed by the register with no text located (211).

## What is explicitly NOT established

- No section has affirmative currentness or examiner release proof. 2026-10-19 is a preparation date only.
- Both Serial Register Pages are MLRS snapshots run 2026-10-07 carrying an express BLM no-warranty notice,
  and their legacy remark sections are marked obsolete and not updated after 2022-03-14. An SRP snapshot
  is corroboration only; it is not the operative case chain and does not establish a records cutoff.
- No SHA-256 in `Source_Register.csv` was independently recomputed; file bytes are not transferable here.
- No native Microsoft Office or Acrobat parity was tested. Calibri is not installed; Carlito 11 was used.
- This package is **not** certified, current, signed, or ready for final release.

## Next owner

Proposals P01-P08 go to the lead evidence adjudicator for per-proposal accept/reject against the original
page images. Only after acceptance may the designated integrator apply any of them, in an isolated build.
"""
open(f"{OUT}/START_HERE_STATUS.md","w").write(STATUS)

arts={os.path.basename(p):{"sha256":sha(p),"bytes":os.path.getsize(p)}
      for p in sorted(glob.glob(f"{OUT}/*")) if os.path.isfile(p) and not p.endswith(".png")
      and os.path.basename(p) not in ("SHA256SUMS.txt","Worker_Delivery.zip")}
QA={
 "run":{"worker":"Claude","model":"claude-opus-5","host":"Claude Code cloud session (Linux container)",
        "role":"Section 19 federal source examiner","preparation_date":"2026-10-19",
        "research_cutoff":"Unknown","currentness":"Unknown","completed_utc":NOW,
        "writes_outside_own_folder":0,"promotes_to_any_package":False,"canonical_succession_claimed":False},
 "tools_actually_used":["Google Drive connector read_file_content / search_files (read-only)",
        "LibreOffice 'soffice' headless for .ods and .pdf native export","Python openpyxl (xlsx authoring)",
        "pdfplumber, pdfinfo, pdffonts, pdftoppm (PDF verification)","Pillow / pdftoppm render for visual check"],
 "tools_claimed_but_NOT_available":{
        "Microsoft Excel/Word/Acrobat":"not present; no MS Office parity tested",
        "Calibri font":"not installed; Carlito 11 metric-compatible substitute used and disclosed on the sheet",
        "tesseract OCR":"not installed in this container",
        "Desktop Commander / RyansPC":"MCP server failed to connect (CONNECT_TIMEOUT); device reported OFFLINE 2026-10-19",
        "Codex Root":"offline; it remains the only sanctioned production writer"},
 "denominator_reconciliation":{"total_pages_15_pdfs":1332,"federal_pages":1315,"county_pages":17,
        "WYW131225_pages":485,"WYW133620_pages":617,"WYW094605_pages":213,
        "prior_fresh_visual_total":65,"prior_fresh_visual_federal":48,"prior_fresh_visual_county":17,
        "all_agree_with_accepted_baseline":True},
 "page_ledger":{"rows":len(pages),"explicit_disposition":len(pages),"blank_disposition":0,
        "read_from_source_text":reviewed,"not_reviewable_in_this_environment":len(pages)-reviewed,
        "ocr_listed_in_nav_index":1098,"ocr_claimed_but_no_text_located":211},
 "ledgers":{"events":len(evs),"proposals":len(props),"proposals_accepted":0,"open_blockers":len(blk)},
 "workbook_qa":{"schema":"federal 10-column: Document Type|Grantor|Grantee|File No|Page|Date of Doc|Rec Date|Comments|Legal Description|Part",
        "metadata_rows":"1-7","blank_row":8,"header_row":9,"entries_start_row":10,"data_rows":24,
        "file_no_column_blank_all_rows":True,"comments_column_blank_all_rows":True,
        "intentional_blank_rule":"File No and Comments intentionally blank; Comments is blank or exactly 'missing image'",
        "unknown_cells_preserved":97,
        "font_named":"Calibri 11","font_actually_embedded_in_pdf":["BAAAAA+Carlito-Bold","CAAAAA+Carlito-Regular"],
        "rendered_text_sizes_pt":[11.0],"body_type_shrunk_to_fit":False,
        "page_count":6,"page_size":"792 x 612 pts (US Letter landscape)","scale_percent":100,
        "column_band_split":False,"header_row_repeats_on_every_printed_page":True,
        "clipping_check":"visual render inspected at 110 dpi; full legal descriptions present, no truncated cells",
        "mid_word_header_or_value_breaks":False,
        "ods_xlsx_cell_parity":"EXACT MATCH via independent csv export of both (209 non-empty cells)",
        "native_xml_all_parts_parse":True,"zip_crc_errors":0,
        "manual_pdf_facsimile":False,"pdf_is_native_export_from_the_native_file":True},
 "artifacts":arts,
 "limitations":[
   "1,309 of 1,315 federal pages were NOT reviewed: no native text layer, connector returns empty text, bytes not transferable, no local OCR.",
   "Register drive_id values differ from the shared-folder Drive IDs while byte counts agree; SHA equivalence between the two copy sets is unproven.",
   "All SHA-256 values for original sources are as-supplied, not recomputed.",
   "Serial Register Pages are 2026-10-07 MLRS snapshots with an express no-warranty notice and obsolete legacy remarks.",
   "No release gate passed. Not certified, not current, not signed, not ready for final release."]
}
json.dump(QA,open(f"{OUT}/QA_Receipt.json","w"),indent=2)

arts["QA_Receipt.json"]={"sha256":sha(f"{OUT}/QA_Receipt.json"),
                         "bytes":os.path.getsize(f"{OUT}/QA_Receipt.json")}
with open(f"{OUT}/SHA256SUMS.txt","w") as f:
    for n,v in sorted(arts.items()): f.write(f"{v['sha256']}  {n}\n")

z=f"{OUT}/Worker_Delivery.zip"
with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as zf:
    for p in sorted(glob.glob(f"{OUT}/*")):
        b=os.path.basename(p)
        if os.path.isfile(p) and b not in ("Worker_Delivery.zip",) and not b.endswith(".png"):
            zf.write(p,b)
with zipfile.ZipFile(z) as zf:
    bad=zf.testzip()
    print("zip members:",len(zf.namelist()),"crc_bad:",bad)
print("delivery sha256:",sha(z))
