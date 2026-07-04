# Runbook — finish Roger Mills reports on your Windows machine

This runs the whole loop-and-tournament workflow locally, where your `.env`, browser, and
okcountyrecords API key work (a cloud sandbox can't reach `D:\` or those hosts).

## One-time setup
```bat
:: 1. install Python 3.11+ and Tesseract OCR (https://github.com/UB-Mannheim/tesseract/wiki)
:: 2. copy the app folder anywhere, e.g. D:\Desktop\Horizon\title_finisher
cd /d D:\Desktop\Horizon\title_finisher
copy .env.example .env
notepad .env
::   set OKCR_API_KEY=<your key>   (or point it at D:\Desktop\Horizon\.env values)
::   set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
run.bat worklist --workbook "D:\Desktop\Horizon\Roger Mills\<a report>.xlsx"
```
If your key already lives in `D:\Desktop\Horizon\.env`, either copy those lines into this
app's `.env` or run with it on the environment:
```bat
for /f "usebackq tokens=*" %i in ("D:\Desktop\Horizon\.env") do set %i
```

## Step 1 — Tournament: pick the best base across all three folders
```bat
run.bat tournament ^
  --folders "D:\Desktop\Horizon\Roger Mills" "D:\Desktop\Horizon\Roger Mills 2" "D:\Desktop\Horizon\Roger Mills 3" ^
  --section-gross 637.42
```
Prints every candidate with its score breakdown and the WINNER (the strongest 19-sheet base).

## Step 2 — Batch: select best base, finish it, loop the audit, write the final report
```bat
run.bat batch ^
  --folders "D:\Desktop\Horizon\Roger Mills" "D:\Desktop\Horizon\Roger Mills 2" "D:\Desktop\Horizon\Roger Mills 3" ^
  --outdir "D:\Desktop\Horizon\rogermillsfinalreports" ^
  --section-gross 637.42
```
This tournament-selects the winner, removes rule-excluded rows, resolves documented
source-in gaps, reconciles Title OGL numbers against the OGL sheet, loops the QC audit until
clean, and writes the finished workbook + `AUDIT LOG` + `PUNCH LIST` into
`rogermillsfinalreports`. It never overwrites the examiner's per-owner net-acre allocation —
the tract sheets stay the source of truth and Title net acres derive from them.

## Step 3 — Online: fill the remaining evidence-gated cells from the county/OCC/OTC
```bat
run.bat online ^
  --workbook "D:\Desktop\Horizon\rogermillsfinalreports\<winner> - FINAL.xlsx" ^
  --county "Roger Mills" --twprge 12N-24W --section 31
```
With the API key set and the network open, this pulls instrument images, OCC Form 1002A /
1073, and OTC production, OCRs them, and fills the fractions / HBP / well data — writing only
what a retrieved document supports and leaving the rest flagged.

## What "best" means (tournament rubric, deterministic)
19-sheet structure (gate) · all tracts foot to gross · section ties to gross · no bare TBD ·
no formula errors · share of net acres owner-identified · fewest unresolved gap highlights ·
no excluded rows on the title tabs · Title OGL refs numeric and in the register. Each
candidate's breakdown is printed and written to the audit log so the choice is auditable.

## Golden rules the tool enforces
Never overwrites the original; never adds tabs or comments; preserves formatting/formulas/
map/media byte-for-byte outside touched cells; never fabricates (a cell is filled only from a
retrieved source, else it stays flagged with the document named); mortgages/liens/UCCs/ROWs/
easements/ORRI/surface-only never land on Runsheet/Tract/Title (rawdata only). Match the
`Template.xlsx` layout — the 19-sheet NHE template is the format target.
```
```
