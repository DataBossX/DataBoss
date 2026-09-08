# Penterra Section 15 (15-45N-76W) — Native Excel Gate Findings
Date: 2026-09-08
Target: /45N-76W Sec 15/Abstract/SECTION15_AI_TOURNAMENT__20260908/CHATGPT/FINAL_VERIFIED_SUCCESSOR__20260908

## Verdicts

- READY FOR OWNER TURN-IN REVIEW: **YES** (content lane only, unchanged from prior receipt)
- READY FOR EXTERNAL RELEASE: **NO**

The prior QA receipt recorded the native page-mechanics gate as "NOT YET PROVED".
That is upgraded here to a **positively demonstrated defect**, on evidence.

## Evidence

Package membership and byte integrity (read back from Drive):
- All 9 objects present in the target folder.
- `Abstract_Checklist_15-45N-76W.xlsx` re-materialized byte-exact:
  4993 bytes, SHA-256 `e8daf1476f3bd83d24d517cbdc6799d024e5269768ad32bf61137ba234427597`
  — matches `SHA256_MANIFEST__20260908.txt` and `DRIVE_READBACK_RECEIPT__20260908.txt`.

Defect, measured on `Abstract_Checklist_15-45N-76W.xlsx`:

| element | count |
|---|---|
| `pageSetup` | **0** |
| `definedName` (Print_Area / Print_Titles) | **0** |
| `pageMargins` | 1 (present: 0.7/0.7/0.75/0.75/0.3/0.3) |
| `sheetPr` / `pageSetUpPr fitToPage` | 0 |

Consequence, measured by print render (LibreOffice Calc 24.2.7):

| | pages | paper |
|---|---|---|
| as-published | 4 | 595.3 x 841.9 pt = **A4** |
| donor recipe applied | 2 | 612.0 x 792.0 pt = **US Letter** |

With no `pageSetup` element, `paperSize` has no stored value and the printing
application falls back to its own locale default. The published Section 15
workbook therefore prints **A4** on an A4-default host, where the accepted
Section 2 convention yields **US Letter**. This is a real paper-size and
pagination defect, not a cosmetic one.

## Donor authority

Page mechanics are NOT invented here. They are taken verbatim from the script
that produced the accepted Section 2 winners from their `__PRE_PAGE_SETUP__20260902`
predecessors:

  Drive: `add_xlsx_page_setup.ps1` (id `1oOBt9YHxfZBm810VmC98AEo3_lq59knl`, 1730 bytes)

Donor law:
- touch only `xl/worksheets/sheet1.xml`; copy every other part verbatim
- inject only if no `pageSetup` (any prefix) already exists
- `FitWidth`  -> `<x:pageSetup orientation="portrait" fitToWidth="1" fitToHeight="0"/>`
- `Checklist` -> `<x:pageSetup scale="34"/>`
- insert immediately before `</x:worksheet>`

Mapping for the exact-six:
- `45N-76W-15_Campbell_Co_Penterra_Abstract_Index.xlsx`  -> FitWidth
- `WYW-021220 Campbell Co. Penterra Abstract Index.xlsx` -> FitWidth
- `WYW-089855 Campbell Co. Penterra Abstract Index.xlsx` -> FitWidth
- `Abstract_Checklist_15-45N-76W.xlsx`                   -> Checklist

## CORRECTION — two conflicting donor authorities

After the initial pass, the Section 11 terminal receipt
(`P11_SECTION11_TERMINAL_RECEIPT__20260908.json`, generated 2026-09-08T15:13Z)
was found. It benchmarks against
`...\45N-76W Sec 2\Abstract\Best of the Best` and enumerates Section 2's
checklist page setup directly:

- print area `$A$1:$L$12`
- orientation **landscape**
- scale **45**

That conflicts with `add_xlsx_page_setup.ps1` (2026-09-02), which emits
`scale="34"` with no orientation and no print area.

The receipt is newer AND exact-target, so under the control law
(SOURCE > newest verified exact-target receipt > deterministic QA > model
opinion) it outranks the .ps1 for what Section 2 actually looks like.

Corroboration: the Section 15 checklist's used range is **A1:L12** — an exact
match for the `$A$1:$L$12` print area the receipt attributes to Section 2.

Caveat: the receipt is a *report about* Section 2, not Section 2 itself. It has
not been confirmed against the actual Best-of-Best workbook. Both profiles are
therefore implemented and labelled; `ChecklistBoB` is the better-supported one.
Render check on `ChecklistBoB`: 2 pages, 792x612 pt landscape.

**Print_Area is still not emitted by the tool.** It requires a
`<definedName name="_xlnm.Print_Area" localSheetId="0">` entry in
`workbook.xml`, which none of these packages currently carry. Same for
Print_Titles. Not guessed at here.

## Open finding for the native pass (do NOT silently "fix")

The donor emits `fitToWidth="1" fitToHeight="0"` but does not emit
`<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>`. In OOXML, `fitToWidth` /
`fitToHeight` are only honoured when `fitToPage` is set. As written, Excel is
expected to ignore the fit and print at 100%.

This affects the accepted Section 2 files too. Section 2 is FROZEN, so nothing
here changes it. Flagged for Ryan's decision only — matching the donor exactly
was chosen over "improving" it.

## Section 11 — read-only lane result (no mutation)

Asked: find a genuine exact-target native/referee/WRITER0 release receipt.

**Answer: none exists.** This is a direct negative from the authoritative
artifact, not an inference from a folder, hash, prompt or source-review PASS.

`P11_SECTION11_TERMINAL_RECEIPT__20260908.json` (Drive `1kQ0wsk7D5U39yLwSHC0WOLeEHbmfXvj2`):
- `"RELEASE_STATUS": "HOLD_NOT_RELEASED"`
- `"writer0_release_token_exists": false`
- `"NO_SUCCESSOR_PROMOTED": true`
- `CONTROL_AUTHORITY`: TaskEnvelope / holder ACK / lease / fence / heartbeat all `ABSENT`
- `COLLISION0`: false
- `SECTION2_PARITY`: FAIL
- `NATIVE_EXCEL_QA`: NOT_RUN; `DRIVE_READBACK`: NOT_RUN
- four blocking client-facing defects E1-E4
- live `WYW-047318` regressed to 79 body rows carrying 13 Section 13 rows

Writer count is 0 (all three workbooks released by the prior Excel PID 8268),
but the actor and authority behind that session are recorded as UNKNOWN.
Accepted baseline preserved: exact-seven ZIP,
SHA-256 `F5570013CC89F944CD8E94D205529F69FFE29D73DFA9C1A4C708BC4CA4BD14A9`.

Section 11 is NOT released. No mutation performed or proposed here.

## What remains

Repair was validated end-to-end on the checklist only. The three index
workbooks were not repaired in this session: the Drive connector returns whole
files as base64, and a byte-exact transfer of the 21 KB county index failed its
SHA-256 check (got `6a8274f4...`, expected `a547effc...`). The corrupt copy was
discarded rather than used. Run the tool locally, where the real files live.

The terminal gate itself — open in Microsoft Excel, save/close/reopen, Print
Preview every page — cannot be executed in this Linux container. It requires the
existing Codex-driven native harness on the Windows host
(Excel 16.0 build 20326), the same one that produced the Section 1 `native_excel_r6b`
receipts.
