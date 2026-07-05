# PROJECT RULES EXTRACT — Section 31-12N-24W, Roger Mills County, OK

_Extracted by DataBossX Title Report Engine v3._

## Source scan for saved rules
A recursive scan of the Horizon root was performed for saved chats, prompts,
notes, markdown, and text instructions. Rule-reference material found in this
checkout: `RUNBOOK.md`, `QA_CHECKLIST.md`, `REPORT_PIPELINE_PLAN.md`,
`PROJECT_STATUS.md`, `horizon/README.md`, `prompts/*.md`. **No project-specific
saved chat transcript containing ownership data was found** — consistent with
those files, which state the real source title documents live on the operator's
local machine (`D:\Desktop\Horizon`) and are not present in the cloud checkout.

Per the mission spec: *"If no saved chats are found, use the rules in this prompt
as controlling."* The controlling rules are therefore reproduced below and are
enforced in code (see the module noted after each rule).

## Controlling rules (authority order)
1. Actual runsheet / instrument data
2. OGL / lease schedule data
3. Template workbook structure and formatting
4. Tract 1 formatting, columns, notes, formulas, ownership flow
5. Existing tract sheets only if supported by the runsheet
6. Prior reports only as references, never controlling ownership
7. Chat transcripts / notes only for rules, not ownership
8. Assumptions only when evidence is incomplete — labeled and highlighted yellow

## Enforced rules
1. **Runsheet is the controlling source.** — `parser.py`, `chain.py`
2. Use the actual runsheet rows and instruments. — `parser.py`
3. Do not invent owners, leases, OGL numbers, assignments, book/page, acreage,
   reservations, or assumptions. — enforced throughout; `qa.py` placeholder check
4. Existing tract sheets are not trusted unless supported by the runsheet. — `writer.py`
5. Template formatting must be preserved exactly. — `writer._open_template_copy` copies
   the template byte-for-byte then edits the copy in place.
6. Overview/map tab must remain first. — `qa.py` "Overview/map tab is first"
7. Tract 1 is the master style, layout, notes, formulas, OGL carry-down. — `tract1_profile.py`, `writer.py`
8. All tract tabs must look like Tract 1 unless the template requires otherwise. — `writer._write_tract_rows`
9. Title Sheet contains final calculated owners only. — `verifier.py`
10. Remove intermediate owners from the Title Sheet unless they retain interest. — `chain._finalize_owners` (drops zero-interest owners)
11. OGL column contains OGL numbers only. — `parser._sanitize_ogl_column`, `qa._ogl_column_pollution`
12. Never put assignment/deed book/page or recording references in the OGL column. — same
13. Use ASSN as conveyance type for assignments. — `models.normalize_instrument_type`
14. Carry OGL numbers beside leased owners exactly like Tract 1. — `chain._finalize_owners` (ogl_by_owner)
15. Every tract must balance to its control acreage. — `chain._finalize_owners`
16. No negative acres. — `qa._negative_acres`
17. No negative WI. — `qa` "No negative WI"
18. Grantor cannot convey more than owned. — `chain._apply_fee_conveyance` over-conveyance guard
19. Conveyance math must use Decimal, not float. — `utils.py` (Fraction/Decimal only)
20. Leases do not transfer mineral ownership. — `chain._apply_leasehold`
21. Assignments transfer leasehold interest only. — `chain._apply_leasehold`
22. Reservations must be preserved. — `chain._apply_fee_conveyance` (reserved stays with grantor)
23. NPRI / ORRI / royalty burdens noted and carried. — `chain._apply_informational` (RD), owner royalty field
24. Probate/heirship/trust/estate/affidavit/missing releases/unmatched OGLs/
    ambiguous tracts/acreage gaps must be flagged. — `chain._apply_informational`, `ogl_matcher`
25. Yellow highlight only true unresolved assumptions or review items. — `utils.yellow_cell` used only for assumptions/unbalanced
26. No strange highlights. — single yellow constant; no other fills used as flags
27. Add notes explaining material chain decisions. — `chain.py` note composition
28. Reasonable landman assumptions only when necessary. — `chain.determine_control_acres`, opening vesting
29. Every assumption labeled "ASSUMPTION:". — `assumptions.collect_assumptions`
30. Every assumption logged in the Audit Log. — `audit.build_audit`
31. Every assumption cell highlighted yellow. — `writer` Assumptions sheet + inline
32. Do not make unsupported final ownership claims. — `verifier` marks Needs Verification
33. If ownership can't be proven, preserve best-supported chain result and mark
    Needs Verification. — `verifier.final_owner_table`
34. Final workbook includes an Audit Log sheet. — `writer._add_audit_sheet`
35. Final workbook includes review flags / curative notes. — `writer._add_flags_sheet`
36. Final workbook must open in Excel. — `qa` "Workbook opens with openpyxl"
37. Do not create #REF! formulas. — `qa._scan_for_ref`
38. Do not break named ranges, merged cells, page setup, hidden sheets, formulas,
    borders, widths, colors, print settings. — template-copy mode edits data cells only
39. Final output must be a real XLSX file. — `writer.write_report`
