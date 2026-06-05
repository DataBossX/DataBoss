╔══════════════════════════════════════════════════════════════════════════════╗
║  DataBoss Title Engine — QUICK START                                         ║
║  Section 27-11N-25W, Beckham County, Oklahoma                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

──────────────────────────────────────────────────────────────────────────────
FIRST-TIME SETUP  (do once)
──────────────────────────────────────────────────────────────────────────────

1. INSTALL PYTHON
   Download Python 3.10+ from https://www.python.org/
   ✔ Check "Add Python to PATH" during install.

2. INSTALL TESSERACT (OCR for scanned documents)
   Download from https://github.com/UB-Mannheim/tesseract/wiki
   Install to default path (C:\Program Files\Tesseract-OCR\)

3. SET YOUR API KEY
   - Open the "title_engine" folder
   - Copy ".env.example" → rename copy to ".env"
   - Open .env in Notepad
   - Replace "your_key_here" with your OKCountyRecords API key
     Example:  OKCOUNTYRECORDS_API_KEY=abcd1234efgh5678
   - Save and close

4. (Optional) ADD CLAUDE AI KEY for better OCR and field extraction
   - In .env, fill in:  ANTHROPIC_API_KEY=sk-ant-...

──────────────────────────────────────────────────────────────────────────────
RUNNING THE APP  (every time)
──────────────────────────────────────────────────────────────────────────────

Double-click:  RUN_BECKHAM27_TITLE_ENGINE.bat

A browser window opens automatically at http://localhost:8502

──────────────────────────────────────────────────────────────────────────────
HOW TO USE THE APP  (step by step)
──────────────────────────────────────────────────────────────────────────────

STEP 1 — API SETUP
   • Verify your API key shows "SET"
   • Click "Test OKCR Connection" — should say "Connected"
   • Click "Initialize Database"

STEP 2 — DRY-RUN SEARCH
   • Click "Run Dry-Run Search"
   • Wait for all searches to complete (watch the log)
   • This finds instruments in the index — NO charges yet

STEP 3 — COST ESTIMATE
   • Review how many images are available to download
   • Check the estimated cost
   • Click "APPROVE DOWNLOADS" if you want to proceed
     (or increase MAX_COST_USD in .env if auto-approve is blocking you)

STEP 4 — DOWNLOAD DOCUMENTS
   • Click "Start Downloading"
   • PDFs are saved to the output/pdfs/ folder

STEP 5 — OCR / EXTRACTION
   • Click "Run OCR + Extraction"
   • Text is extracted from each PDF
   • Fields (lessor, lessee, royalty, term, acres, etc.) are pulled automatically

STEP 6 — CHAIN DASHBOARD
   • Review lease chain, assignment chain, and mineral ownership
   • Green = no gaps; Red = gaps need curative action

STEP 7 — MISSING DOCUMENTS
   • See any chain gaps and missing instruments
   • Each gap shows what curative action is needed

STEP 8 — EXPORT
   • Click "Generate Excel Workbook" → saves a 13-sheet .xlsx file
   • Click "Generate Narrative Report" → saves a plain-text title report
   • Use the Download buttons to save files to your computer

──────────────────────────────────────────────────────────────────────────────
OUTPUT FILES
──────────────────────────────────────────────────────────────────────────────

output/
  title_engine.db                    ← SQLite database (all data)
  pdfs/                              ← Downloaded instrument images
  reports/
    Beckham_27_11N_25W_TitleChain_YYYY-MM-DD.xlsx   ← 13-sheet Excel workbook
    Beckham_27_11N_25W_Report_YYYY-MM-DD.txt         ← Narrative report

──────────────────────────────────────────────────────────────────────────────
IMPORTANT RULES
──────────────────────────────────────────────────────────────────────────────

✔ Your API key is NEVER saved to any file other than .env
✔ NO images are downloaded without your explicit approval
✔ NO values are fabricated — UNKNOWN is used for unsupported fields
✔ EVERY Excel row includes a SOURCE LINK showing where data came from
✔ This tool produces research output — have it reviewed by a licensed
  Oklahoma attorney before relying on it for any transaction

──────────────────────────────────────────────────────────────────────────────
TROUBLESHOOTING
──────────────────────────────────────────────────────────────────────────────

"streamlit: not found"
   → Run:  pip install streamlit

"tesseract is not installed"
   → Install Tesseract (see Step 2 above)

"No API key configured"
   → Check your .env file — make sure OKCOUNTYRECORDS_API_KEY is set

App won't open in browser
   → Go to http://localhost:8502 manually

Black screen / white screen
   → Refresh the browser page

Database locked
   → Close any other windows running the app, then restart

──────────────────────────────────────────────────────────────────────────────
