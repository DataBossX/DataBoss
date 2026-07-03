# TitleFinisher

An application that finishes Oklahoma mineral **cursory title reports** end-to-end while
preserving the examiner's workbook exactly (formatting, formulas, drawings, map, images,
merged cells, tab order, comments — byte-for-byte outside the cells it fills).

It was built from the Roger Mills 31-12N-24W engagement, where the reusable problem was:
*"the workbook is 90% done; the last 10% (exact conveyed fractions, HBP status, well
completion data, and a handful of source-in gaps) needs the recorded instrument images,
OCC well records, and OTC production — which a sandboxed AI session can't reach."*
TitleFinisher automates that last 10% on a machine that **can** reach those sources.

## What it does

1. **Reads the workbook** and builds the open-item worklist automatically — the yellow
   source-in gaps, the `VERIFY — NEED int.` instrument columns, the `Verify base HBP`
   cells, and the `Well 1` TBDs (no manual list needed).
2. **Fetches** the exact documents each open item needs:
   - `okcountyrecords.com` API — instrument images by document number / book-page.
   - OCC Well Records imaging + RBDMS — Form 1002A, spud, perfs, TD/TVD, spacing order.
   - OTC — gross production by PUN/API for HBP.
3. **OCRs and extracts** grantor / grantee / doc type / dates / book-page / legal /
   conveyed-or-reserved interest from each image.
4. **Fills the workbook** in place with format-preserving XML surgery — writes the
   fraction into the tract grid, the NMA into the OGL register, the well data into
   `Well 1`, resolves HBP, and clears each yellow gap it proves (updating the ledger).
5. **Audits** the result against the full lock-set (19 sheets, no new tabs, no comments,
   tracts foot to gross, no formula errors, exclusions clean) and loops until two clean
   passes.
6. **Emits** an audit log + examiner punch list of anything still unresolved.

## Two modes

- **`offline`** (works with no network): reproduces the analysis pass — OCR the local
  index PDF, parse it into an instrument database, run the source-in gap cross-reference,
  and re-audit. This is exactly what produced the current FINAL workbook; run it to verify
  or re-derive.
- **`online`** (on a networked machine with the API key): the full fetch → OCR → extract →
  fill loop above.

## Quick start

```bash
cd automation/title_finisher
cp .env.example .env            # put your okcountyrecords API key in it
python -m pip install -r requirements.txt
# put the workbook + index PDF in ./data/  (or point at them via flags)

# offline: re-run the analysis/audit on local sources (no network needed)
./run.sh offline --workbook "data/…NHE.xlsx" --index "data/12N 24W 31 - Index.pdf"

# online: fetch everything the workbook still needs and fill it in
./run.sh online  --workbook "data/…NHE.xlsx" --county "Roger Mills" --twprge 12N-24W --section 31
```

Windows: use `run.bat` with the same arguments.

## Output

- `data/out/<name> - FINAL.xlsx` — the finished workbook (original never overwritten).
- `data/out/<name> - AUDIT LOG.md` — everything filled, with source (instrument, book/page, where found).
- `data/out/<name> - PUNCH LIST.md` — anything still open, with the exact document to pull.
- `data/proof/` — every retrieved image/record, cited in the audit log.

## Golden rules (enforced in code)

- Never overwrite the original workbook; never convert to Google Sheets.
- Never add/rename/hide/reorder tabs; never add cell comments/notes.
- Never fabricate: a cell is filled only from a retrieved source document, else it stays
  flagged with the precise missing document named.
- Mortgages / releases / liens / UCCs / ROWs / easements / ORRI-only / surface-only
  instruments never touch Runsheet / Tract / Title tabs (rawdata awareness only).
- The only discretionary formatting is the yellow source-in-gap highlight (add/remove
  under the rule) and the Overview/PLAT map block.

See `docs/ARCHITECTURE.md` for module layout and `docs/API_NOTES.md` for the source
endpoints and auth.
