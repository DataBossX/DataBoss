# Best AI workflow and staged prompt for the Diversified report

## Recommended setup

For actual workbook editing, use **ChatGPT Work on desktop or Codex desktop with access to the complete local folder**, at the strongest available reasoning setting. OpenAI's current guidance describes Work as the surface for creating reports and spreadsheets and says desktop Work can use local files; Codex can also work across local files, tools, and repeatable spreadsheet-producing workflows. For an independent second opinion, use **Claude Opus 4.8** as a read-only red-team reviewer; Anthropic describes Opus 4.8 as its generally most capable agentic model with a 1M-token context window.

The primary agent must have native file access and the ability to run Microsoft Excel. A chat model that only receives screenshots or an uploaded XLSX is not sufficient for the final mutation/verification pass.

Official model/surface references:

- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://openai.com/academy/what-is-codex/
- https://www.anthropic.com/claude/opus

## Files to provide

At minimum provide:

1. `Template.xlsx`
2. `32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_BEST_AVAILABLE_2026-07-10.xlsx`
3. `READ_ME_Diversified_Report_Audit_and_Completion_2026-07-10.md`
4. All three `AUDIT_*.md` files
5. Both QA JSON files
6. The complete source folders: record images, section index, Section Notes, source inventory/OCR outputs, prior reports/registers, plats/tax roll, and OCC well/completion files

Do not upload confidential files to a service unless the engagement permits it. Work on copies and preserve every original.

## Operating instructions

Run the prompt below **one phase at a time**. Do not ask the model to perform all phases in one response. After each phase, require the listed checkpoint artifact, review it, then paste only the next phase instruction. A phase may be repeated until its checkpoint passes.

## Master prompt

> You are the lead land/title-data QA agent for a source-limited Oklahoma oil-and-gas cursory report covering Section 32-11N-25W, Beckham County, Oklahoma, with Diversified-affiliated interests. You are editing a working report, not issuing a legal opinion.
>
> Your governing rules are:
>
> 1. Preserve every original file. Work only on a new versioned copy of the workbook.
> 2. Treat `Template.xlsx` as the structural/style reference, not as factual title evidence. Remove all stale prior-project values, links, names, formulas, images, and assumptions.
> 3. Never infer a current vested entity, estate, fraction, WI, NRI, ORRI, royalty, net acres, depth, wellbore, lien release, or HBP status from an index tick, party name, operator listing, or missing schedule.
> 4. Distinguish four evidence classes in every relevant row: DIRECT IMAGE, PUBLIC METADATA/INDEX, OCR LEAD, and EXPRESS ASSUMPTION.
> 5. One recorded instrument per Runsheet row. Do not combine separate assignments, mortgages, releases, terminations, agreements, affidavits, or mergers.
> 6. A blank numeric field means NOT DETERMINABLE, not zero. Formulas must be blank-safe and must not manufacture totals.
> 7. Every assumption must state its basis, purpose, affected tract/cells, and risk. The only preauthorized assumptions are nominal aliquot acreage for geographic organization and the screening rules stated in the supplied READ_ME.
> 8. Do not label metadata as a reviewed conveyance. Do not apply a release/termination without matching the operative collateral schedule. Do not use regulatory well data as title or HBP proof.
> 9. Stop and flag any conflict between the direct image, metadata, index, OCR, prior report, and workbook. Do not silently choose one.
> 10. Do not consume paid record-copy/print tokens or contact third parties without explicit authorization.
> 11. Keep a change log with old value, new value, source, evidence tier, confidence, and reason.
> 12. At the end of each phase, produce only the required checkpoint artifacts and a short PASS/FAIL list. Do not begin the next phase until instructed.

## Phase 0 - Freeze scope and establish controls

Append to the master prompt:

> Perform Phase 0 only. Inventory every provided file; record filename, size, SHA-256, type, date range, and apparent role. Identify duplicates and likely stale outputs without moving or deleting anything. Establish the subject legal description, certified-through date, local image cutoff, report date, and evidence hierarchy. Create `PHASE_0_INVENTORY.md` and `PHASE_0_INVENTORY.csv`. Stop.

Checkpoint:

- Every file accounted for.
- Originals identified and hash-locked.
- Subject and date boundaries explicit.
- No workbook edited.

## Phase 1 - Reproduce the workbook/template audit

Append:

> Perform Phase 1 only. Compare the candidate workbook to `Template.xlsx` at OOXML package, workbook, sheet, cell, formula, merge, style, dimensions, visibility, print area, page setup, defined-name, external-link, image/drawing, hyperlink, date-type, and error-token levels. Separate intentional source-supported differences from defects. Reconcile your results to `AUDIT_1_Exhaustive_Workbook_and_Template_Differences_2026-07-10.md`. Create `PHASE_1_TEMPLATE_DIFF.md` and a machine-readable JSON diff summary. Stop.

Checkpoint:

- Sheet order and names checked.
- Every formula/merge/name/link defect enumerated.
- Print/layout differences enumerated.
- No unsupported repair made.

## Phase 2 - Build the canonical source and instrument ledger

Append:

> Perform Phase 2 only. Build a one-row-per-instrument canonical ledger from all supplied sources and reconcile it to `AUDIT_3_Instruments_Sources_and_Copy_Pull_2026-07-10.md`. Fields must include sequence, instrument ID, book/page start-end, execution/effective date, recorded date, type, grantor, grantee, legal/estate clue, evidence tier, direct-image range, public URL, source file, confidence, conflict note, title-treatment note, required copy pages, and reviewed/not-reviewed status. Include financing, releases, terminations, mergers, agreements, affidavits, wellbore instruments, countywide/no-legal screens, and the DP Legacy Central and Canvas branches. Create `PHASE_2_CANONICAL_LEDGER.xlsx` and `.csv`. Stop.

Checkpoint:

- One instrument per row.
- All corrected page ranges/dates/types carried.
- All omitted modern and countywide records included.
- No title effect inferred from metadata alone.

## Phase 3 - Direct-image abstraction and conflict resolution

Append:

> Perform Phase 3 only. Review the specifically cited direct images page by page. For each instrument abstract granting language, estate, fraction, depth, wellbore, reservations, exceptions, payout/reversion, effective date, legal description, signatures, acknowledgments, recording stamp, and exhibits. Record exact image/page support. Reconcile the known corrections for 845/47, 872/279, 987/159, and 1014/75 and every conflict listed in the audits. Never rely on OCR where the image is legible. Create `PHASE_3_DIRECT_IMAGE_ABSTRACTS.md` plus an exceptions table. Stop.

Checkpoint:

- Exact page/image citations.
- Image/OCR/index conflicts resolved or expressly open.
- No unstated interpretation.

## Phase 4 - Copy-pull and continuation plan

Append:

> Perform Phase 4 only. From the canonical ledger, create a prioritized page-level copy-pull manifest for every missing operative page, exhibit, schedule, amendment, release, mortgage/UCC, agreement, merger plan, and countywide screen. Include the six Bk 1016 bridge items, Bk 1536/P368, Bk 2393/P1-698, the complete 2020-2026 packages, all eleven underlying OGLs, patents, central UCC, no-legal-description, and continuation searches. Estimate only page counts supported by metadata; otherwise say unknown. Do not purchase anything. Create `PHASE_4_COPY_PULL.md` and `.csv`. Stop.

Checkpoint:

- Each open report conclusion maps to a required source.
- County/corporate/UCC/regulatory continuation separated.
- No paid action taken.

## Phase 5 - Ownership logic and assumptions gate

Append:

> Perform Phase 5 only. Attempt chain and ownership calculations only where every required link and operative schedule is present. For each tract/branch, show source title, conveyance path, estate, depth/wellbore, gross acres, fractions, burdens, payout/reversion, current holder, WI, NRI, ORRI, net acres, and lien status. If any predicate is missing, return NOT DETERMINABLE and name the exact missing source. Prepare an assumptions register. Do not use nominal aliquot acreage as owned acreage. Create `PHASE_5_CHAIN_AND_MATH.md` and a machine-auditable calculation table. Stop.

Checkpoint:

- Every number traceable to record evidence.
- Fractions cross-foot.
- Overlapping depth/wellbore estates are not added.
- Blank/not-determinable is preserved where required.

## Phase 6 - Controlled workbook rebuild

Append:

> Perform Phase 6 only. Create a new versioned workbook from a clean copy of `Template.xlsx`. Populate it from the canonical ledger and approved Phase 5 outputs. Preserve required sheet names/order and template visual language. Use static evidence matrices where a transactional ownership model would imply unsupported present decimals. Add source hyperlinks, evidence tiers, confidence, assumptions, open requirements, and one-instrument-per-row Runsheet treatment. Remove broken names/external links/stale content. Set legible legal-size print areas and repeat headers. Create the workbook and `PHASE_6_CHANGE_LOG.csv`. Stop.

Checkpoint:

- No stale-project terms.
- No broken names, links, or formulas.
- All required instruments present.
- Blank-safe totals only.

## Phase 7 - Native and visual QA

Append:

> Perform Phase 7 only. Validate the workbook as an OOXML ZIP and in native Microsoft Excel: normal open, targeted calculation, save, close, reopen. Check formula errors, defined names, external links, dates, hyperlinks, merge integrity, hidden rows/columns, print areas, page scaling, headers, filters, frozen panes, images, and every required token. Render or publish Overview, Title, Runsheet, OGL, Tract 5, WI 1, WI 2, PLAT, and Well 1. Detect clipping/overflow and correct it. Create `PHASE_7_QA.json`, `PHASE_7_VISUAL_QA.md`, and the final versioned workbook. Stop.

Checkpoint:

- Excel calculation state complete.
- Zero formula-error cells.
- Zero stale terms, broken names, or external links.
- Zero unexplained visual overflow.
- Hash and file size recorded.

## Phase 8 - Independent red-team review

Give the final workbook, audits, ledger, and QA artifacts to Claude Opus 4.8 or another independent strongest available frontier model in read-only mode and append:

> Perform a read-only red-team review. Find contradictions, unsupported inferences, omitted instruments, false certainty, calculation risks, mislabeled evidence tiers, title-versus-regulatory conflation, unmatched lien releases, assumption leakage, print/layout defects, and places where a reader could mistake nominal acreage for ownership. Do not edit the workbook. Produce ranked findings with exact sheet/cell or ledger-row references and a release recommendation: BLOCK, QUALIFIED INTERNAL USE, or READY FOR ATTORNEY REVIEW. Stop.

Only return to Phase 6 for findings supported by evidence. Never accept a red-team suggestion that fills a missing title fact by inference.

## Release rule

The report may be marked **READY FOR ATTORNEY REVIEW** when workbook/QA gates pass. It may not be labeled complete present title, certified ownership, or final division-order title until the operative copy pull, full chain, lien matching, OGL/HBP analysis, continuation searches, and qualified legal review are complete.

