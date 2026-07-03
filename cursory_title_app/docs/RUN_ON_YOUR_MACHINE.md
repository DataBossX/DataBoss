# Close the Section 31 open items — run this on YOUR machine

The OKCountyRecords / OCC / OTC hosts are **egress-blocked from the cloud prep
environment** (proxy 403), so document retrieval must run where the network and
your API key work — your Windows box. Everything below is built and tested; it
just needs to run somewhere with real internet.

## 0. One-time setup
```bat
cd cursory_title_app
copy .env.example .env
```
Put these in `.env` (never commit it):
- `OKCOUNTY_API_KEY=` your key (https://okcountyrecords.com/account/dashboard/api-console)
- `ANTHROPIC_API_KEY=` (or `OPENAI_API_KEY=`) for the vision extraction
```bat
pip install -r requirements.txt
python -m playwright install chromium
```

## 1. Pull the exact open-item documents (paid — you confirm)
```bat
:: dry run first — lists all 52 targets + cost estimate, downloads nothing
python -m cursory_title_app.okcounty.fetch

:: then actually pull (≈ $26 at $0.50/image). Start smaller if you like:
python -m cursory_title_app.okcounty.fetch --confirm --group source_in_roots
python -m cursory_title_app.okcounty.fetch --confirm --group mineral_balance_candidates
python -m cursory_title_app.okcounty.fetch --confirm --group conveyed_fraction_instruments
```
PDFs land in `_data/okcounty_pdfs/`. The target list (`section31_targets.json`)
is the exact instrument numbers behind the 67 source-in gaps, the open mineral
balances (incl. Kirk estate + Psi Lke→Cummins/Eagle Owl), and the 25 flagged
conveyed-fraction instruments.

## 2. Extract fields (vision) → review CSV
```bat
python -m cursory_title_app.okcounty.process
```
Produces `_data/output/okcounty_reimport.csv` — one row per document, every read
flagged with a confidence score. **Open it, verify each row against the PDF, set
`approve=yes`** on the ones you trust (and change `action` to `update` +
`runsheet_row` if it edits an existing row).

## 3. Write approved rows into the workbook (format-preserving)
```bat
python -c "from cursory_title_app.reports import reimport; from pathlib import Path; print(reimport.apply_csv(Path('31-...(7-3-26)-NHE.xlsx'), Path('_data/output/okcounty_reimport.csv')))"
```
Writes only approved rows to a new `*.REIMPORT.xlsx`; `add` rows are appended with
the O–S formulas copied down; tabs/formatting/formulas verified after write.

## 4. Rebuild the consolidated report
```bat
python -c "from cursory_title_app.reports import builder; from pathlib import Path; builder.build_all(Path('31-...REIMPORT.xlsx'), prefer='com')"
```
Regenerates the dated workbook, ownership reconciliation, chain-of-title, curative
manifest, and the consolidated HTML report — now with the newly-closed items.

## What this CANNOT pull (different sources)
- **Base-lease HBP** → OTC gross production by PUN (tax.ok.gov / OTC portal).
- **Well completion / operator** → OCC Form 1002A & 1073 (imaging.occ.ok.gov).
These are not in the county records API; pull them from OTC/OCC in your browser.

> Cursory research/drafting aid. Not a title opinion. Verify every extracted field
> against the recorded image before relying on it.
